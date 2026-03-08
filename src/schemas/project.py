import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.schemas.pool import PoolResponse


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    api_key: str | None = None
    pools: list[PoolResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectCreateResponse(ProjectResponse):
    api_key: str


class ProjectAssignPools(BaseModel):
    pool_ids: list[uuid.UUID]
