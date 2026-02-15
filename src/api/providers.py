import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.provider import Provider
from src.models.proxy import Proxy
from src.schemas.common import PaginatedResponse, PaginationMeta
from src.schemas.provider import ProviderCreate, ProviderResponse, ProviderUpdate

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=PaginatedResponse[ProviderResponse])
async def list_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    total_stmt = select(func.count(Provider.id))
    total = (await db.execute(total_stmt)).scalar() or 0

    stmt = (
        select(
            Provider,
            func.count(Proxy.id).label("proxy_count"),
        )
        .outerjoin(Proxy, Proxy.provider_id == Provider.id)
        .group_by(Provider.id)
        .order_by(Provider.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    data = []
    for provider, proxy_count in rows:
        resp = ProviderResponse.model_validate(provider)
        resp.proxy_count = proxy_count
        data.append(resp)

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    provider = Provider(name=body.name, notes=body.notes)
    db.add(provider)
    await db.flush()
    resp = ProviderResponse.model_validate(provider)
    resp.proxy_count = 0
    return resp


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    stmt = (
        select(
            Provider,
            func.count(Proxy.id).label("proxy_count"),
        )
        .outerjoin(Proxy, Proxy.provider_id == Provider.id)
        .where(Provider.id == provider_id)
        .group_by(Provider.id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider, proxy_count = row
    resp = ProviderResponse.model_validate(provider)
    resp.proxy_count = proxy_count
    return resp


@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    provider = await db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)
    await db.flush()
    return ProviderResponse.model_validate(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    provider = await db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
