import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PoolCreate(BaseModel):
    name: str
    rotation_strategy: Literal["round_robin", "random"] = "round_robin"


class PoolUpdate(BaseModel):
    name: str | None = None
    rotation_strategy: Literal["round_robin", "random"] | None = None


class PoolResponse(BaseModel):
    id: uuid.UUID
    name: str
    rotation_strategy: str
    proxy_count: int | None = None
    healthy_count: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PoolAddProxies(BaseModel):
    proxy_ids: list[uuid.UUID]


class PoolRemoveProxies(BaseModel):
    proxy_ids: list[uuid.UUID]
