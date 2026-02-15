from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertCreate(BaseModel):
    name: str
    condition_type: str
    condition_config: dict
    action_type: str
    action_config: dict
    is_enabled: bool = True


class AlertUpdate(BaseModel):
    name: str | None = None
    condition_type: str | None = None
    condition_config: dict | None = None
    action_type: str | None = None
    action_config: dict | None = None
    is_enabled: bool | None = None


class AlertResponse(BaseModel):
    id: UUID
    name: str
    condition_type: str
    condition_config: dict
    action_type: str
    action_config: dict
    is_enabled: bool
    last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
