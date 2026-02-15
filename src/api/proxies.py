import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.associations import PoolProxy
from src.models.proxy import Proxy
from src.redis import get_redis
from src.rotation.engine import RotationEngine
from src.schemas.common import PaginatedResponse, PaginationMeta
from src.schemas.proxy import ProxyBulkImport, ProxyCreate, ProxyResponse, ProxyUpdate
from src.services.import_parser import parse_proxy_list

router = APIRouter(prefix="/ips", tags=["proxies"])


_SORT_COLUMNS = {
    "host": Proxy.host,
    "port": Proxy.port,
    "protocol": Proxy.protocol,
    "provider": Proxy.provider_id,
    "status": Proxy.last_health_status,
    "latency": Proxy.avg_latency_ms,
}


@router.get("", response_model=PaginatedResponse[ProxyResponse])
async def list_proxies(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    pool_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    protocol: str | None = Query(None),
    provider_id: uuid.UUID | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str = Query("asc"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    base = select(Proxy)
    count_base = select(func.count(Proxy.id))

    if pool_id:
        base = base.join(PoolProxy, PoolProxy.proxy_id == Proxy.id).where(PoolProxy.pool_id == pool_id)
        count_base = count_base.join(PoolProxy, PoolProxy.proxy_id == Proxy.id).where(PoolProxy.pool_id == pool_id)
    if status_filter:
        base = base.where(Proxy.last_health_status == status_filter)
        count_base = count_base.where(Proxy.last_health_status == status_filter)
    if protocol:
        base = base.where(Proxy.protocol == protocol)
        count_base = count_base.where(Proxy.protocol == protocol)
    if provider_id:
        base = base.where(Proxy.provider_id == provider_id)
        count_base = count_base.where(Proxy.provider_id == provider_id)

    total = (await db.execute(count_base)).scalar() or 0

    col = _SORT_COLUMNS.get(sort_by) if sort_by else None
    if col is not None:
        order = col.desc().nullslast() if sort_dir == "desc" else col.asc().nullsfirst()
        stmt = base.order_by(order).offset((page - 1) * per_page).limit(per_page)
    else:
        stmt = base.order_by(Proxy.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    proxies = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        data=[ProxyResponse.model_validate(p) for p in proxies],
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )


@router.post("", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy(
    body: ProxyCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    proxy = Proxy(
        host=body.host,
        port=body.port,
        protocol=body.protocol,
        provider_id=body.provider_id,
        username=body.username,
        password_encrypted=body.password,
    )
    db.add(proxy)
    await db.flush()
    return ProxyResponse.model_validate(proxy)


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_import_proxies(
    body: ProxyBulkImport,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    created = 0
    skipped = 0

    proxy_entries = []

    # Parse raw text if provided
    if body.proxies:
        parsed = parse_proxy_list(body.proxies)
        for p in parsed:
            proxy_entries.append({
                "host": p.host,
                "port": p.port,
                "protocol": p.protocol,
                "username": p.username,
                "password": p.password,
            })

    # Use structured list if provided
    if body.proxy_list:
        for p in body.proxy_list:
            proxy_entries.append({
                "host": p.host,
                "port": p.port,
                "protocol": p.protocol,
                "username": p.username,
                "password": p.password,
            })

    for entry in proxy_entries:
        # Check for duplicate
        existing = await db.execute(
            select(Proxy.id).where(
                Proxy.host == entry["host"],
                Proxy.port == entry["port"],
                Proxy.protocol == entry["protocol"],
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        proxy = Proxy(
            host=entry["host"],
            port=entry["port"],
            protocol=entry["protocol"],
            provider_id=body.provider_id,
            username=entry["username"],
            password_encrypted=entry["password"],
        )
        db.add(proxy)
        created += 1

    await db.flush()

    return {"created": created, "skipped": skipped}


@router.get("/{proxy_id}", response_model=ProxyResponse)
async def get_proxy(
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    proxy = await db.get(Proxy, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return ProxyResponse.model_validate(proxy)


@router.patch("/{proxy_id}", response_model=ProxyResponse)
async def update_proxy(
    proxy_id: uuid.UUID,
    body: ProxyUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    proxy = await db.get(Proxy, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(proxy, key, value)
    await db.flush()
    return ProxyResponse.model_validate(proxy)


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    proxy = await db.get(Proxy, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    await db.delete(proxy)


@router.post("/{proxy_id}/check")
async def check_proxy(
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    proxy = await db.get(Proxy, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")

    from src.health.checker import check_single_proxy

    health_status, latency = await check_single_proxy(proxy)

    # Update in DB
    proxy.last_health_status = health_status
    if health_status == "healthy":
        proxy.avg_latency_ms = latency
    await db.flush()

    # Update in Redis
    redis = await get_redis()
    engine = RotationEngine(redis)
    await engine.update_proxy_health(str(proxy.id), health_status)
    await engine.cache_proxy_info(str(proxy.id), {
        "host": proxy.host,
        "port": proxy.port,
        "protocol": proxy.protocol,
        "username": proxy.username or "",
        "password": proxy.password_encrypted or "",
    })

    return {
        "id": str(proxy.id),
        "status": health_status,
        "latency_ms": latency,
    }
