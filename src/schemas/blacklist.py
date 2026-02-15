from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BlacklistCreate(BaseModel):
    proxy_id: UUID
    target_domain: str | None = None
    reason: str | None = None
    cooldown_seconds: int | None = None


class BlacklistResponse(BaseModel):
    id: UUID
    project_id: UUID
    proxy_id: UUID
    target_domain: str | None = None
    reason: str | None = None
    auto_generated: bool
    blacklisted_at: datetime
    expires_at: datetime | None = None

    # Joined fields
    proxy_host: str | None = None
    proxy_port: int | None = None

    model_config = ConfigDict(from_attributes=True)


class BlacklistBulkRemove(BaseModel):
    proxy_ids: list[UUID]
