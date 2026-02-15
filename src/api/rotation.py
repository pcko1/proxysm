from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_project_by_api_key
from src.database import get_db
from src.models.associations import ProjectPool
from src.models.pool import Pool
from src.models.project import Project
from src.redis import get_redis
from src.rotation.engine import PoolExhaustedError, RotationEngine

router = APIRouter(tags=["rotation"])


@router.get("/rotate/{project_slug}")
async def rotate_proxy(
    project_slug: str,
    db: AsyncSession = Depends(get_db),
    auth_project: Project = Depends(get_project_by_api_key),
):
    # Look up project by slug
    stmt = select(Project).where(Project.slug == project_slug)
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify the authenticated project matches the slug
    if project.id != auth_project.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key does not match project")

    # Get all pools assigned to project, ordered by priority desc
    pool_stmt = (
        select(Pool, ProjectPool.priority)
        .join(ProjectPool, ProjectPool.pool_id == Pool.id)
        .where(ProjectPool.project_id == project.id)
        .order_by(ProjectPool.priority.desc())
    )
    rows = (await db.execute(pool_stmt)).all()

    if not rows:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No pools assigned to project")

    redis = await get_redis()
    engine = RotationEngine(redis)

    for pool, priority in rows:
        try:
            proxy = await engine.get_next_proxy(str(pool.id), pool.rotation_strategy)
            return {
                "host": proxy["host"],
                "port": proxy["port"],
                "protocol": proxy["protocol"],
                "username": proxy.get("username"),
                "password": proxy.get("password"),
            }
        except PoolExhaustedError:
            continue

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="All pools exhausted, no healthy proxies available",
    )
