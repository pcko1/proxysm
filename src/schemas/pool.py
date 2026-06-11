import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# NOTE: "least_connections" is implemented in the rotation engine but is NOT
# exposed here: the proxy servers never seed or maintain the
# pool:{id}:connections ZSET (engine.track_connection is never called), so the
# strategy would raise PoolExhaustedError on every request.
RotationStrategy = Literal["round_robin", "random", "weighted_random"]


class PoolCreate(BaseModel):
    name: str
    rotation_strategy: RotationStrategy = "round_robin"


class PoolUpdate(BaseModel):
    name: str | None = None
    rotation_strategy: RotationStrategy | None = None


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
