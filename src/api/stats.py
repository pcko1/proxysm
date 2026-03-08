import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import admin_auth
from src.database import get_db
from src.models.metrics import MetricsRollup
from src.models.pool import Pool
from src.models.project import Project
from src.models.proxy import Proxy
from src.schemas.stats import EntityStats, OverviewStats, StatusCodeBreakdown, TimeseriesPoint, TimeseriesResponse

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

    # Median latency from request_log (more resilient to outliers)
    median_row = await db.execute(
        text("""
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY response_time_ms) AS median
            FROM request_log
            WHERE created_at >= :cutoff AND response_time_ms IS NOT NULL
        """),
        {"cutoff": cutoff},
    )
    median_val = median_row.scalar()

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
        median_response_time_ms=round(median_val, 2) if median_val is not None else None,
    )


@router.get("/status-codes")
async def get_status_codes(
    project_id: uuid.UUID | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Status code breakdown per project from request_log."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    filters = "WHERE rl.created_at >= :cutoff"
    params: dict = {"cutoff": cutoff}
    if project_id:
        filters += " AND rl.project_id = :project_id"
        params["project_id"] = project_id

    sql = text(f"""
        SELECT
            rl.project_id,
            p.name AS project_name,
            COUNT(*) FILTER (WHERE rl.status_code >= 200 AND rl.status_code < 300) AS status_2xx,
            COUNT(*) FILTER (WHERE rl.status_code >= 300 AND rl.status_code < 400) AS status_3xx,
            COUNT(*) FILTER (WHERE rl.status_code >= 400 AND rl.status_code < 500) AS status_4xx,
            COUNT(*) FILTER (WHERE rl.status_code >= 500 OR rl.status_code IS NULL) AS status_5xx,
            COUNT(*) AS total
        FROM request_log rl
        JOIN projects p ON p.id = rl.project_id
        {filters}
        GROUP BY rl.project_id, p.name
        ORDER BY total DESC
    """)

    rows = await db.execute(sql, params)
    return {
        "data": [
            StatusCodeBreakdown(
                project_id=str(row.project_id),
                project_name=row.project_name,
                status_2xx=row.status_2xx,
                status_3xx=row.status_3xx,
                status_4xx=row.status_4xx,
                status_5xx=row.status_5xx,
                total=row.total,
            )
            for row in rows
        ]
    }


@router.get("/pool-metrics")
async def get_pool_metrics(
    project_id: uuid.UUID | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Aggregate metrics per pool from metrics_rollup (24h window)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    project_filter = ""
    params: dict = {"cutoff": cutoff}
    if project_id:
        project_filter = "JOIN project_pools prjp ON prjp.pool_id = m.entity_id AND prjp.project_id = :project_id"
        params["project_id"] = project_id

    sql = text(f"""
        SELECT
            m.entity_id AS pool_id,
            p.name AS pool_name,
            COALESCE(SUM(m.total_requests), 0) AS total_requests,
            COALESCE(SUM(m.successful_requests), 0) AS successful_requests,
            COALESCE(SUM(m.failed_requests), 0) AS failed_requests,
            AVG(m.avg_response_time_ms) AS avg_response_time_ms,
            rl_stats.median_ms
        FROM metrics_rollup m
        JOIN pools p ON p.id = m.entity_id
        {project_filter}
        LEFT JOIN LATERAL (
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY rl.response_time_ms) AS median_ms
            FROM request_log rl
            JOIN pool_proxies pp ON pp.proxy_id = rl.proxy_id AND pp.pool_id = m.entity_id
            WHERE rl.created_at >= :cutoff AND rl.response_time_ms IS NOT NULL
        ) rl_stats ON true
        WHERE m.entity_type = 'pool'
          AND m.period_granularity = '5min'
          AND m.period_start >= :cutoff
        GROUP BY m.entity_id, p.name, rl_stats.median_ms
        ORDER BY total_requests DESC
    """)

    rows = await db.execute(sql, params)
    data = []
    for row in rows:
        total = row.total_requests
        failed = row.failed_requests
        error_rate = round((failed / total * 100), 1) if total > 0 else 0.0
        data.append({
            "pool_id": str(row.pool_id),
            "pool_name": row.pool_name,
            "total_requests": total,
            "error_rate": error_rate,
            "avg_latency_ms": round(row.avg_response_time_ms, 1) if row.avg_response_time_ms else None,
            "median_latency_ms": round(row.median_ms, 1) if row.median_ms else None,
        })
    return {"data": data}


@router.get("/pool-latency-histogram")
async def get_pool_latency_histogram(
    project_id: uuid.UUID | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Latency distribution histogram per pool from request_log."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    project_filter = ""
    params: dict = {"cutoff": cutoff}
    if project_id:
        project_filter = "JOIN project_pools prjp ON prjp.pool_id = pp.pool_id AND prjp.project_id = :project_id"
        params["project_id"] = project_id

    sql = text(f"""
        SELECT
            pp.pool_id,
            p.name AS pool_name,
            COUNT(*) FILTER (WHERE rl.response_time_ms < 100) AS bucket_0_100,
            COUNT(*) FILTER (WHERE rl.response_time_ms >= 100 AND rl.response_time_ms < 300) AS bucket_100_300,
            COUNT(*) FILTER (WHERE rl.response_time_ms >= 300 AND rl.response_time_ms < 500) AS bucket_300_500,
            COUNT(*) FILTER (WHERE rl.response_time_ms >= 500 AND rl.response_time_ms < 1000) AS bucket_500_1000,
            COUNT(*) FILTER (WHERE rl.response_time_ms >= 1000 AND rl.response_time_ms < 3000) AS bucket_1000_3000,
            COUNT(*) FILTER (WHERE rl.response_time_ms >= 3000) AS bucket_3000_plus,
            COUNT(*) AS total
        FROM request_log rl
        JOIN pool_proxies pp ON pp.proxy_id = rl.proxy_id
        JOIN pools p ON p.id = pp.pool_id
        {project_filter}
        WHERE rl.created_at >= :cutoff AND rl.response_time_ms IS NOT NULL
        GROUP BY pp.pool_id, p.name
        ORDER BY total DESC
    """)

    rows = await db.execute(sql, params)
    data = []
    for row in rows:
        data.append({
            "pool_id": str(row.pool_id),
            "pool_name": row.pool_name,
            "buckets": [
                {"label": "<100ms", "count": row.bucket_0_100},
                {"label": "100-300ms", "count": row.bucket_100_300},
                {"label": "300-500ms", "count": row.bucket_300_500},
                {"label": "500ms-1s", "count": row.bucket_500_1000},
                {"label": "1-3s", "count": row.bucket_1000_3000},
                {"label": "3s+", "count": row.bucket_3000_plus},
            ],
            "total": row.total,
        })
    return {"data": data}


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

    # Median latency from request_log
    median_result = await db.execute(
        text("""
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY response_time_ms) AS median
            FROM request_log
            WHERE proxy_id IN (
                SELECT proxy_id FROM pool_proxies WHERE pool_id = :eid
                UNION SELECT id FROM proxies WHERE id = :eid
            )
            AND response_time_ms IS NOT NULL
        """) if entity_type in ("pool", "proxy") else text("""
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY response_time_ms) AS median
            FROM request_log
            WHERE project_id = :eid AND response_time_ms IS NOT NULL
        """),
        {"eid": entity_id},
    )
    median_val = median_result.scalar()

    return EntityStats(
        total_requests=total,
        successful_requests=int(row[1]),
        failed_requests=failed,
        error_rate=round(error_rate, 2),
        avg_response_time_ms=round(row[5], 2) if row[5] is not None else None,
        median_response_time_ms=round(median_val, 2) if median_val is not None else None,
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
