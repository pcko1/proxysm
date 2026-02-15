import hashlib
import re
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import admin_auth
from src.database import get_db
from src.models.associations import ProjectPool
from src.models.pool import Pool
from src.models.project import Project
from src.schemas.common import PaginatedResponse, PaginationMeta
from src.schemas.pool import PoolResponse
from src.schemas.project import (
    ProjectAssignPools,
    ProjectCreate,
    ProjectCreateResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _make_slug(name: str) -> str:
    slug = name.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return slug


def _build_project_response(project: Project, pools: list[Pool]) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        slug=project.slug,
        pools=[PoolResponse.model_validate(p) for p in pools],
        created_at=project.created_at,
    )


async def _get_project_pools(db: AsyncSession, project_id: uuid.UUID) -> list[Pool]:
    stmt = (
        select(Pool)
        .join(ProjectPool, ProjectPool.pool_id == Pool.id)
        .where(ProjectPool.project_id == project_id)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get("", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    total = (await db.execute(select(func.count(Project.id)))).scalar() or 0

    stmt = (
        select(Project)
        .order_by(Project.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    projects = (await db.execute(stmt)).scalars().all()

    data = []
    for project in projects:
        pools = await _get_project_pools(db, project.id)
        data.append(_build_project_response(project, pools))

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(total=total, page=page, per_page=per_page),
    )


@router.post("", response_model=ProjectCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    api_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    slug = _make_slug(body.name)

    project = Project(name=body.name, slug=slug, api_key_hash=key_hash)
    db.add(project)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{body.name}' already exists",
        )

    return ProjectCreateResponse(
        id=project.id,
        name=project.name,
        slug=project.slug,
        pools=[],
        created_at=project.created_at,
        api_key=api_key,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    pools = await _get_project_pools(db, project_id)
    return _build_project_response(project, pools)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        project.name = update_data["name"]
        project.slug = _make_slug(update_data["name"])
    await db.flush()
    pools = await _get_project_pools(db, project_id)
    return _build_project_response(project, pools)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)


@router.post("/{project_id}/pools", status_code=status.HTTP_201_CREATED)
async def assign_pools(
    project_id: uuid.UUID,
    body: ProjectAssignPools,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    added = 0
    for pool_id in body.pool_ids:
        pool = await db.get(Pool, pool_id)
        if pool is None:
            continue
        existing = await db.execute(
            select(ProjectPool.id).where(
                ProjectPool.project_id == project_id,
                ProjectPool.pool_id == pool_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        db.add(ProjectPool(project_id=project_id, pool_id=pool_id))
        added += 1

    await db.flush()
    return {"added": added}


@router.delete("/{project_id}/pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_pool(
    project_id: uuid.UUID,
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    result = await db.execute(
        select(ProjectPool).where(
            ProjectPool.project_id == project_id,
            ProjectPool.pool_id == pool_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Pool not assigned to project")
    await db.delete(link)


@router.post("/{project_id}/rotate-key", response_model=ProjectCreateResponse)
async def rotate_api_key(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    api_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    project.api_key_hash = key_hash
    await db.flush()

    pools = await _get_project_pools(db, project_id)
    return ProjectCreateResponse(
        id=project.id,
        name=project.name,
        slug=project.slug,
        pools=[PoolResponse.model_validate(p) for p in pools],
        created_at=project.created_at,
        api_key=api_key,
    )
