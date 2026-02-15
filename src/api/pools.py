import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.associations import PoolProxy
from src.models.pool import Pool
from src.models.proxy import Proxy
from src.redis import get_redis
from src.rotation.engine import RotationEngine
from src.schemas.common import PaginatedResponse, PaginationMeta
from src.schemas.pool import PoolAddProxies, PoolCreate, PoolRemoveProxies, PoolResponse, PoolUpdate

router = APIRouter(prefix="/pools", tags=["pools"])


async def _get_pool_counts(db: AsyncSession, pool_id: uuid.UUID) -> tuple[int, int]:
    """Return (proxy_count, healthy_count) for a pool."""
    proxy_count = (await db.execute(
        select(func.count(PoolProxy.id)).where(PoolProxy.pool_id == pool_id)
    )).scalar() or 0
    healthy_count = (await db.execute(
        select(func.count(PoolProxy.id))
        .join(Proxy, Proxy.id == PoolProxy.proxy_id)
        .where(PoolProxy.pool_id == pool_id, Proxy.last_health_status == "healthy")
    )).scalar() or 0
    return proxy_count, healthy_count


async def _sync_pool_redis(db: AsyncSession, pool_id: uuid.UUID) -> None:
    """Sync pool proxy list and proxy info to Redis."""
    stmt = (
        select(Proxy)
        .join(PoolProxy, PoolProxy.proxy_id == Proxy.id)
        .where(PoolProxy.pool_id == pool_id, Proxy.is_active == True)  # noqa: E712
    )
    proxies = (await db.execute(stmt)).scalars().all()
    redis = await get_redis()
    engine = RotationEngine(redis)
    proxy_ids = [str(p.id) for p in proxies]
    await engine.sync_pool(str(pool_id), proxy_ids)
    # Cache proxy info so rotation works immediately (before first health check)
    for proxy in proxies:
        await engine.cache_proxy_info(str(proxy.id), {
            "host": proxy.host,
            "port": proxy.port,
            "protocol": proxy.protocol,
            "username": proxy.username or "",
            "password": proxy.password_encrypted or "",
        })


@router.get("", response_model=PaginatedResponse[PoolResponse])
async def list_pools(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    total = (await db.execute(select(func.count(Pool.id)))).scalar() or 0

    # Subquery for proxy_count
    proxy_count_sq = (
        select(PoolProxy.pool_id, func.count(PoolProxy.id).label("proxy_count"))
        .group_by(PoolProxy.pool_id)
        .subquery()
    )
    # Subquery for healthy_count
    healthy_count_sq = (
        select(PoolProxy.pool_id, func.count(PoolProxy.id).label("healthy_count"))
        .join(Proxy, Proxy.id == PoolProxy.proxy_id)
        .where(Proxy.last_health_status == "healthy")
        .group_by(PoolProxy.pool_id)
        .subquery()
    )

    stmt = (
        select(
            Pool,
            func.coalesce(proxy_count_sq.c.proxy_count, 0).label("proxy_count"),
            func.coalesce(healthy_count_sq.c.healthy_count, 0).label("healthy_count"),
        )
        .outerjoin(proxy_count_sq, proxy_count_sq.c.pool_id == Pool.id)
        .outerjoin(healthy_count_sq, healthy_count_sq.c.pool_id == Pool.id)
        .order_by(Pool.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()

    data = []
    for pool, proxy_count, healthy_count in rows:
        resp = PoolResponse.model_validate(pool)
        resp.proxy_count = proxy_count
        resp.healthy_count = healthy_count
        data.append(resp)

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )


@router.post("", response_model=PoolResponse, status_code=status.HTTP_201_CREATED)
async def create_pool(
    body: PoolCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    pool = Pool(name=body.name, rotation_strategy=body.rotation_strategy)
    db.add(pool)
    await db.flush()
    resp = PoolResponse.model_validate(pool)
    resp.proxy_count = 0
    resp.healthy_count = 0
    return resp


@router.get("/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    proxy_count, healthy_count = await _get_pool_counts(db, pool_id)
    resp = PoolResponse.model_validate(pool)
    resp.proxy_count = proxy_count
    resp.healthy_count = healthy_count
    return resp


@router.patch("/{pool_id}", response_model=PoolResponse)
async def update_pool(
    pool_id: uuid.UUID,
    body: PoolUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pool, key, value)
    await db.flush()
    proxy_count, healthy_count = await _get_pool_counts(db, pool_id)
    resp = PoolResponse.model_validate(pool)
    resp.proxy_count = proxy_count
    resp.healthy_count = healthy_count
    return resp


@router.delete("/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    await db.delete(pool)


@router.post("/{pool_id}/ips", status_code=status.HTTP_201_CREATED)
async def add_proxies_to_pool(
    pool_id: uuid.UUID,
    body: PoolAddProxies,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    added = 0
    for proxy_id in body.proxy_ids:
        # Check proxy exists
        proxy = await db.get(Proxy, proxy_id)
        if proxy is None:
            continue
        # Check not already in pool
        existing = await db.execute(
            select(PoolProxy.id).where(
                PoolProxy.pool_id == pool_id,
                PoolProxy.proxy_id == proxy_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        db.add(PoolProxy(pool_id=pool_id, proxy_id=proxy_id))
        added += 1

    await db.flush()
    await _sync_pool_redis(db, pool_id)
    return {"added": added}


@router.delete("/{pool_id}/ips")
async def remove_proxies_from_pool(
    pool_id: uuid.UUID,
    body: PoolRemoveProxies,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    removed = 0
    for proxy_id in body.proxy_ids:
        result = await db.execute(
            select(PoolProxy).where(
                PoolProxy.pool_id == pool_id,
                PoolProxy.proxy_id == proxy_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is not None:
            await db.delete(link)
            removed += 1

    await db.flush()
    await _sync_pool_redis(db, pool_id)
    return {"removed": removed}
