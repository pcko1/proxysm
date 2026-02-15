import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.alert import AlertRule
from src.schemas.alert import AlertCreate, AlertResponse, AlertUpdate

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """List all alert rules."""
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AlertCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Create a new alert rule."""
    alert = AlertRule(
        name=body.name,
        condition_type=body.condition_type,
        condition_config=body.condition_config,
        action_type=body.action_type,
        action_config=body.action_config,
        is_enabled=body.is_enabled,
    )
    db.add(alert)
    await db.flush()
    return AlertResponse.model_validate(alert)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Get a single alert rule."""
    alert = await db.get(AlertRule, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertResponse.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: uuid.UUID,
    body: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Update an alert rule."""
    alert = await db.get(AlertRule, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(alert, key, value)
    await db.flush()
    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Delete an alert rule."""
    alert = await db.get(AlertRule, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    await db.delete(alert)
