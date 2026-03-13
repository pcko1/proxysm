import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.proxy import Proxy
from src.models.source import ProxySource
from src.schemas.common import PaginatedResponse, PaginationMeta
from src.schemas.source import SourceCreate, SourceResponse, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


async def _source_to_response(db: AsyncSession, source: ProxySource) -> SourceResponse:
    """Convert a ProxySource model to a SourceResponse with proxy_count."""
    proxy_count = (await db.execute(
        select(func.count(Proxy.id)).where(Proxy.source_id == source.id)
    )).scalar() or 0
    resp = SourceResponse.model_validate(source)
    resp.proxy_count = proxy_count
    return resp


@router.get("", response_model=PaginatedResponse[SourceResponse])
async def list_sources(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    total = (await db.execute(select(func.count(ProxySource.id)))).scalar() or 0

    proxy_count_sq = (
        select(Proxy.source_id, func.count(Proxy.id).label("proxy_count"))
        .group_by(Proxy.source_id)
        .subquery()
    )

    stmt = (
        select(
            ProxySource,
            func.coalesce(proxy_count_sq.c.proxy_count, 0).label("proxy_count"),
        )
        .outerjoin(proxy_count_sq, proxy_count_sq.c.source_id == ProxySource.id)
        .order_by(ProxySource.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()

    data = []
    for source, proxy_count in rows:
        resp = SourceResponse.model_validate(source)
        resp.proxy_count = proxy_count
        data.append(resp)

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    source = ProxySource(
        name=body.name,
        type=body.type,
        url=body.url,
        provider=body.provider,
    )
    db.add(source)
    await db.flush()
    resp = SourceResponse.model_validate(source)
    resp.proxy_count = 0
    return resp


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    source = await db.get(ProxySource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return await _source_to_response(db, source)


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: uuid.UUID,
    body: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    source = await db.get(ProxySource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)
    await db.flush()
    return await _source_to_response(db, source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    source = await db.get(ProxySource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)


@router.post("/{source_id}/poll")
async def poll_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    source = await db.get(ProxySource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.type != "url":
        raise HTTPException(status_code=400, detail="Only URL sources can be polled")
    if not source.url:
        raise HTTPException(status_code=400, detail="Source has no URL configured")

    # Commit current transaction before running poller (uses its own sessions)
    await db.commit()

    from src.services.source_poller import poll_single_source_by_id

    result = await poll_single_source_by_id(source_id)
    return result
