import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProxyCreate(BaseModel):
    host: str
    port: int = Field(ge=0, le=65535)
    protocol: Literal["http", "https", "socks5"]
    provider: str | None = None
    username: str | None = None
    password: str | None = None


class ProxyUpdate(BaseModel):
    is_active: bool | None = None


class ProxyResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    host: str
    port: int
    protocol: str
    provider: str | None = None
    is_active: bool
    last_health_status: str | None = None
    last_health_check: datetime | None = None
    avg_latency_ms: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProxyBulkImport(BaseModel):
    provider: str | None = None
    protocol: Literal["http", "https", "socks5"] = "http"
    proxies: str | None = None
    proxy_list: list[ProxyCreate] | None = None
    url: str | None = None
    filename: str | None = None
