import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    name: str = Field(max_length=255)
    type: Literal["url", "file", "manual"]
    url: str | None = None
    provider: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    provider: str | None = None
    is_active: bool | None = None


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    url: str | None = None
    provider: str | None = None
    is_active: bool
    last_polled_at: datetime | None = None
    last_status_code: int | None = None
    consecutive_failures: int
    proxy_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
