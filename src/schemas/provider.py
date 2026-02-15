import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProviderCreate(BaseModel):
    name: str
    notes: str | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None


class ProviderResponse(BaseModel):
    id: uuid.UUID
    name: str
    notes: str | None = None
    created_at: datetime
    proxy_count: int | None = None

    model_config = ConfigDict(from_attributes=True)
