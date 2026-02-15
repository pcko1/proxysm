import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.blacklist import ProjectProxyBlacklist
from src.models.project import Project
from src.models.proxy import Proxy
from src.redis import get_redis
from src.schemas.blacklist import BlacklistBulkRemove, BlacklistCreate, BlacklistResponse

router = APIRouter(tags=["blacklist"])


@router.get("/projects/{project_id}/blacklist", response_model=list[BlacklistResponse])
async def get_project_blacklist(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Get all blacklisted proxies for a project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        select(ProjectProxyBlacklist, Proxy.host, Proxy.port)
        .outerjoin(Proxy, ProjectProxyBlacklist.proxy_id == Proxy.id)
        .where(ProjectProxyBlacklist.project_id == project_id)
        .order_by(ProjectProxyBlacklist.blacklisted_at.desc())
    )
    rows = await db.execute(stmt)
    results = []
    for row in rows:
        bl = row[0]
        results.append(BlacklistResponse(
            id=bl.id,
            project_id=bl.project_id,
            proxy_id=bl.proxy_id,
            target_domain=bl.target_domain,
            reason=bl.reason,
            auto_generated=bl.auto_generated,
            blacklisted_at=bl.blacklisted_at,
            expires_at=bl.expires_at,
            proxy_host=row[1],
            proxy_port=row[2],
        ))
    return results


@router.post(
    "/projects/{project_id}/blacklist",
    response_model=BlacklistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def blacklist_proxy(
    project_id: uuid.UUID,
    body: BlacklistCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Manually blacklist a proxy for a project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    proxy = await db.get(Proxy, body.proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")

    # Check if already blacklisted
    existing = await db.execute(
        select(ProjectProxyBlacklist.id).where(
            ProjectProxyBlacklist.project_id == project_id,
            ProjectProxyBlacklist.proxy_id == body.proxy_id,
            ProjectProxyBlacklist.target_domain == body.target_domain,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Proxy already blacklisted for this project")

    expires_at = None
    if body.cooldown_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.cooldown_seconds)

    entry = ProjectProxyBlacklist(
        project_id=project_id,
        proxy_id=body.proxy_id,
        target_domain=body.target_domain,
        reason=body.reason,
        auto_generated=False,
        expires_at=expires_at,
    )
    db.add(entry)
    await db.flush()

    # Add to Redis blacklist set
    redis = await get_redis()
    await redis.sadd(f"blacklist:{project_id}", str(body.proxy_id))

    return BlacklistResponse(
        id=entry.id,
        project_id=entry.project_id,
        proxy_id=entry.proxy_id,
        target_domain=entry.target_domain,
        reason=entry.reason,
        auto_generated=entry.auto_generated,
        blacklisted_at=entry.blacklisted_at,
        expires_at=entry.expires_at,
        proxy_host=proxy.host,
        proxy_port=proxy.port,
    )


@router.delete(
    "/projects/{project_id}/blacklist/{proxy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_from_blacklist(
    project_id: uuid.UUID,
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Remove a proxy from a project's blacklist."""
    result = await db.execute(
        delete(ProjectProxyBlacklist).where(
            ProjectProxyBlacklist.project_id == project_id,
            ProjectProxyBlacklist.proxy_id == proxy_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Blacklist entry not found")

    # Remove from Redis
    redis = await get_redis()
    await redis.srem(f"blacklist:{project_id}", str(proxy_id))


@router.post(
    "/projects/{project_id}/blacklist/bulk-remove",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def bulk_remove_from_blacklist(
    project_id: uuid.UUID,
    body: BlacklistBulkRemove,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Remove multiple proxies from a project's blacklist."""
    await db.execute(
        delete(ProjectProxyBlacklist).where(
            ProjectProxyBlacklist.project_id == project_id,
            ProjectProxyBlacklist.proxy_id.in_(body.proxy_ids),
        )
    )

    # Remove from Redis
    redis = await get_redis()
    pipe = redis.pipeline()
    for pid in body.proxy_ids:
        pipe.srem(f"blacklist:{project_id}", str(pid))
    await pipe.execute()
