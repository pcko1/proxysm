import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.metrics import MetricsRollup
from src.models.pool import Pool
from src.models.project import Project
from src.models.proxy import Proxy
from src.schemas.stats import EntityStats, OverviewStats, TimeseriesPoint, TimeseriesResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewStats)
async def get_overview_stats(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Global dashboard statistics."""
    # Count proxies by status
    status_counts = await db.execute(
        select(
            Proxy.last_health_status,
            func.count(Proxy.id),
        ).group_by(Proxy.last_health_status)
    )
    status_map: dict[str, int] = {}
    total_proxies = 0
    for row in status_counts:
        status_map[row[0]] = row[1]
        total_proxies += row[1]

    # Count pools, projects
    total_pools = (await db.execute(select(func.count(Pool.id)))).scalar() or 0
    total_projects = (await db.execute(select(func.count(Project.id)))).scalar() or 0

    # Get last 24h metrics totals across all entities at proxy level
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    metrics_row = await db.execute(
        select(
            func.coalesce(func.sum(MetricsRollup.total_requests), 0),
            func.coalesce(func.sum(MetricsRollup.successful_requests), 0),
            func.coalesce(func.sum(MetricsRollup.failed_requests), 0),
            func.coalesce(func.sum(MetricsRollup.bytes_sent), 0),
            func.coalesce(func.sum(MetricsRollup.bytes_received), 0),
            func.avg(MetricsRollup.avg_response_time_ms),
        ).where(
            MetricsRollup.entity_type == "proxy",
            MetricsRollup.period_granularity == "5min",
            MetricsRollup.period_start >= cutoff,
        )
    )
    m = metrics_row.one()

    return OverviewStats(
        total_proxies=total_proxies,
        healthy_proxies=status_map.get("healthy", 0),
        degraded_proxies=status_map.get("degraded", 0),
        dead_proxies=status_map.get("dead", 0),
        unknown_proxies=status_map.get("unknown", 0),
        total_pools=total_pools,
        total_projects=total_projects,
        total_requests_24h=int(m[0]),
        successful_requests_24h=int(m[1]),
        failed_requests_24h=int(m[2]),
        bytes_sent_24h=int(m[3]),
        bytes_received_24h=int(m[4]),
        avg_response_time_ms=round(m[5], 2) if m[5] is not None else None,
    )


async def _entity_stats(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
) -> EntityStats:
    """Compute aggregate stats for a given entity from metrics_rollup."""
    result = await db.execute(
        select(
            func.coalesce(func.sum(MetricsRollup.total_requests), 0),
            func.coalesce(func.sum(MetricsRollup.successful_requests), 0),
            func.coalesce(func.sum(MetricsRollup.failed_requests), 0),
            func.coalesce(func.sum(MetricsRollup.bytes_sent), 0),
            func.coalesce(func.sum(MetricsRollup.bytes_received), 0),
            func.avg(MetricsRollup.avg_response_time_ms),
            func.max(MetricsRollup.p95_response_time_ms),
        ).where(
            MetricsRollup.entity_type == entity_type,
            MetricsRollup.entity_id == entity_id,
            MetricsRollup.period_granularity == "5min",
        )
    )
    row = result.one()
    total = int(row[0])
    failed = int(row[2])
    error_rate = (failed / total * 100) if total > 0 else 0.0

    return EntityStats(
        total_requests=total,
        successful_requests=int(row[1]),
        failed_requests=failed,
        error_rate=round(error_rate, 2),
        avg_response_time_ms=round(row[5], 2) if row[5] is not None else None,
        p95_response_time_ms=round(row[6], 2) if row[6] is not None else None,
        bytes_sent=int(row[3]),
        bytes_received=int(row[4]),
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
async def get_timeseries(
    entity_type: str | None = Query(None),
    entity_id: uuid.UUID | None = Query(None),
    granularity: str = Query("1hour"),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Time-series data for charts."""
    if granularity not in ("5min", "1hour", "1day"):
        raise HTTPException(status_code=400, detail="Invalid granularity. Use 5min, 1hour, or 1day.")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    stmt = select(
        MetricsRollup.period_start,
        func.sum(MetricsRollup.total_requests).label("total_requests"),
        func.sum(MetricsRollup.successful_requests).label("successful_requests"),
        func.sum(MetricsRollup.failed_requests).label("failed_requests"),
        func.avg(MetricsRollup.avg_response_time_ms).label("avg_response_time_ms"),
    ).where(
        MetricsRollup.period_granularity == granularity,
        MetricsRollup.period_start >= cutoff,
    )

    if entity_type:
        stmt = stmt.where(MetricsRollup.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(MetricsRollup.entity_id == entity_id)

    stmt = stmt.group_by(MetricsRollup.period_start).order_by(MetricsRollup.period_start)

    rows = await db.execute(stmt)
    data = []
    for row in rows:
        data.append(TimeseriesPoint(
            period_start=row.period_start,
            total_requests=int(row.total_requests or 0),
            successful_requests=int(row.successful_requests or 0),
            failed_requests=int(row.failed_requests or 0),
            avg_response_time_ms=round(row.avg_response_time_ms, 2) if row.avg_response_time_ms is not None else None,
        ))

    return TimeseriesResponse(granularity=granularity, data=data)


# Entity-specific stat endpoints under their respective prefixes
# These are mounted at /api/v1 so they become /api/v1/ips/{id}/stats etc.

ips_stats_router = APIRouter(tags=["stats"])
pools_stats_router = APIRouter(tags=["stats"])
projects_stats_router = APIRouter(tags=["stats"])

@ips_stats_router.get("/ips/{proxy_id}/stats", response_model=EntityStats)
async def get_proxy_stats(
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Performance stats for a single proxy."""
    proxy = await db.get(Proxy, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return await _entity_stats(db, "proxy", proxy_id)


@pools_stats_router.get("/pools/{pool_id}/stats", response_model=EntityStats)
async def get_pool_stats(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Performance stats for a pool."""
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    return await _entity_stats(db, "pool", pool_id)


@projects_stats_router.get("/projects/{project_id}/stats", response_model=EntityStats)
async def get_project_stats(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Performance stats for a project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _entity_stats(db, "project", project_id)
