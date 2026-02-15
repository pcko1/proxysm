"""Metrics rollup service.

Aggregates request_log data into metrics_rollup at 5min, 1hour, and 1day
granularities. Also handles cleanup of old data beyond retention periods.
"""

from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from src.config import settings
from src.database import async_session_factory

log = structlog.get_logger()


async def rollup_metrics() -> None:
    """Aggregate request_log data into metrics_rollup table.

    Runs every metrics_rollup_interval seconds (default 5 min).
    Creates 5min rollups from raw request_log data.
    On the hour boundary, also creates 1hour rollups from 5min data.
    On the day boundary, also creates 1day rollups from 1hour data.
    """
    try:
        now = datetime.now(timezone.utc)

        await _rollup_5min()

        # On the hour boundary (minute 0-4 window), create hourly rollups
        if now.minute < 5:
            await _rollup_1hour()

        # On the day boundary (hour 0, minute 0-4 window), create daily rollups
        if now.hour == 0 and now.minute < 5:
            await _rollup_1day()

    except Exception:
        log.exception("metrics_rollup_failed")


async def _rollup_5min() -> None:
    """Create 5-minute rollups from raw request_log data."""
    async with async_session_factory() as session:
        # Aggregate the last 5 minutes of request_log data by proxy, pool, project
        # Using date_trunc to align to 5-minute boundaries
        rollup_sql = text("""
            WITH period AS (
                SELECT
                    date_trunc('hour', NOW()) +
                    (EXTRACT(minute FROM NOW())::int / 5) * INTERVAL '5 minutes'
                    AS period_start
            ),
            raw_stats AS (
                SELECT
                    proxy_id AS entity_id,
                    'proxy' AS entity_type,
                    COUNT(*) AS total_requests,
                    COUNT(*) FILTER (WHERE status_code IS NOT NULL AND status_code < 400)
                        AS successful_requests,
                    COUNT(*) FILTER (WHERE status_code IS NULL OR status_code >= 400)
                        AS failed_requests,
                    COALESCE(AVG(response_time_ms), 0) AS avg_response_time_ms,
                    COALESCE(
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms), 0
                    ) AS p95_response_time_ms,
                    COALESCE(SUM(bytes_sent), 0) AS bytes_sent,
                    COALESCE(SUM(bytes_received), 0) AS bytes_received
                FROM request_log, period
                WHERE created_at >= period.period_start - INTERVAL '5 minutes'
                  AND created_at < period.period_start
                GROUP BY proxy_id

                UNION ALL

                SELECT
                    pool_id AS entity_id,
                    'pool' AS entity_type,
                    COUNT(*) AS total_requests,
                    COUNT(*) FILTER (WHERE status_code IS NOT NULL AND status_code < 400)
                        AS successful_requests,
                    COUNT(*) FILTER (WHERE status_code IS NULL OR status_code >= 400)
                        AS failed_requests,
                    COALESCE(AVG(response_time_ms), 0) AS avg_response_time_ms,
                    COALESCE(
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms), 0
                    ) AS p95_response_time_ms,
                    COALESCE(SUM(bytes_sent), 0) AS bytes_sent,
                    COALESCE(SUM(bytes_received), 0) AS bytes_received
                FROM request_log, period
                WHERE created_at >= period.period_start - INTERVAL '5 minutes'
                  AND created_at < period.period_start
                GROUP BY pool_id

                UNION ALL

                SELECT
                    project_id AS entity_id,
                    'project' AS entity_type,
                    COUNT(*) AS total_requests,
                    COUNT(*) FILTER (WHERE status_code IS NOT NULL AND status_code < 400)
                        AS successful_requests,
                    COUNT(*) FILTER (WHERE status_code IS NULL OR status_code >= 400)
                        AS failed_requests,
                    COALESCE(AVG(response_time_ms), 0) AS avg_response_time_ms,
                    COALESCE(
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms), 0
                    ) AS p95_response_time_ms,
                    COALESCE(SUM(bytes_sent), 0) AS bytes_sent,
                    COALESCE(SUM(bytes_received), 0) AS bytes_received
                FROM request_log, period
                WHERE created_at >= period.period_start - INTERVAL '5 minutes'
                  AND created_at < period.period_start
                GROUP BY project_id
            )
            INSERT INTO metrics_rollup (
                entity_type, entity_id, period_start, period_granularity,
                total_requests, successful_requests, failed_requests,
                bytes_sent, bytes_received, avg_response_time_ms, p95_response_time_ms
            )
            SELECT
                rs.entity_type, rs.entity_id,
                p.period_start - INTERVAL '5 minutes',
                '5min',
                rs.total_requests, rs.successful_requests, rs.failed_requests,
                rs.bytes_sent, rs.bytes_received,
                rs.avg_response_time_ms, rs.p95_response_time_ms
            FROM raw_stats rs, period p
            ON CONFLICT (entity_type, entity_id, period_start, period_granularity)
            DO UPDATE SET
                total_requests = EXCLUDED.total_requests,
                successful_requests = EXCLUDED.successful_requests,
                failed_requests = EXCLUDED.failed_requests,
                bytes_sent = EXCLUDED.bytes_sent,
                bytes_received = EXCLUDED.bytes_received,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                p95_response_time_ms = EXCLUDED.p95_response_time_ms
        """)
        result = await session.execute(rollup_sql)
        await session.commit()
        count = result.rowcount if result.rowcount else 0
        if count > 0:
            log.info("metrics_rollup_5min_complete", upserted=count)


async def _rollup_1hour() -> None:
    """Create 1-hour rollups from 5-minute rollups."""
    async with async_session_factory() as session:
        rollup_sql = text("""
            WITH hour_periods AS (
                SELECT date_trunc('hour', NOW()) - INTERVAL '1 hour' AS period_start
                UNION ALL
                SELECT date_trunc('hour', NOW()) AS period_start
            )
            INSERT INTO metrics_rollup (
                entity_type, entity_id, period_start, period_granularity,
                total_requests, successful_requests, failed_requests,
                bytes_sent, bytes_received, avg_response_time_ms, p95_response_time_ms
            )
            SELECT
                m.entity_type,
                m.entity_id,
                hp.period_start,
                '1hour',
                SUM(m.total_requests),
                SUM(m.successful_requests),
                SUM(m.failed_requests),
                SUM(m.bytes_sent),
                SUM(m.bytes_received),
                CASE WHEN SUM(m.total_requests) > 0
                    THEN SUM(m.avg_response_time_ms * m.total_requests)
                         / SUM(m.total_requests)
                    ELSE 0
                END,
                MAX(m.p95_response_time_ms)
            FROM metrics_rollup m
            JOIN hour_periods hp ON m.period_start >= hp.period_start
              AND m.period_start < hp.period_start + INTERVAL '1 hour'
            WHERE m.period_granularity = '5min'
            GROUP BY m.entity_type, m.entity_id, hp.period_start
            ON CONFLICT (entity_type, entity_id, period_start, period_granularity)
            DO UPDATE SET
                total_requests = EXCLUDED.total_requests,
                successful_requests = EXCLUDED.successful_requests,
                failed_requests = EXCLUDED.failed_requests,
                bytes_sent = EXCLUDED.bytes_sent,
                bytes_received = EXCLUDED.bytes_received,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                p95_response_time_ms = EXCLUDED.p95_response_time_ms
        """)
        result = await session.execute(rollup_sql)
        await session.commit()
        count = result.rowcount if result.rowcount else 0
        if count > 0:
            log.info("metrics_rollup_1hour_complete", upserted=count)


async def _rollup_1day() -> None:
    """Create 1-day rollups from 1-hour rollups."""
    async with async_session_factory() as session:
        rollup_sql = text("""
            WITH day_periods AS (
                SELECT date_trunc('day', NOW()) - INTERVAL '1 day' AS period_start
                UNION ALL
                SELECT date_trunc('day', NOW()) AS period_start
            )
            INSERT INTO metrics_rollup (
                entity_type, entity_id, period_start, period_granularity,
                total_requests, successful_requests, failed_requests,
                bytes_sent, bytes_received, avg_response_time_ms, p95_response_time_ms
            )
            SELECT
                m.entity_type,
                m.entity_id,
                dp.period_start,
                '1day',
                SUM(m.total_requests),
                SUM(m.successful_requests),
                SUM(m.failed_requests),
                SUM(m.bytes_sent),
                SUM(m.bytes_received),
                CASE WHEN SUM(m.total_requests) > 0
                    THEN SUM(m.avg_response_time_ms * m.total_requests)
                         / SUM(m.total_requests)
                    ELSE 0
                END,
                MAX(m.p95_response_time_ms)
            FROM metrics_rollup m
            JOIN day_periods dp ON m.period_start >= dp.period_start
              AND m.period_start < dp.period_start + INTERVAL '1 day'
            WHERE m.period_granularity = '1hour'
            GROUP BY m.entity_type, m.entity_id, dp.period_start
            ON CONFLICT (entity_type, entity_id, period_start, period_granularity)
            DO UPDATE SET
                total_requests = EXCLUDED.total_requests,
                successful_requests = EXCLUDED.successful_requests,
                failed_requests = EXCLUDED.failed_requests,
                bytes_sent = EXCLUDED.bytes_sent,
                bytes_received = EXCLUDED.bytes_received,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                p95_response_time_ms = EXCLUDED.p95_response_time_ms
        """)
        result = await session.execute(rollup_sql)
        await session.commit()
        count = result.rowcount if result.rowcount else 0
        if count > 0:
            log.info("metrics_rollup_1day_complete", upserted=count)


async def cleanup_old_data() -> None:
    """Delete old request_log and metrics_rollup data beyond retention periods.

    Runs daily. Uses settings for retention configuration.
    """
    try:
        async with async_session_factory() as session:
            # Delete old request_log data
            req_log_sql = text("""
                DELETE FROM request_log
                WHERE created_at < NOW() - MAKE_INTERVAL(days => :retention_days)
            """)
            result = await session.execute(
                req_log_sql,
                {"retention_days": settings.request_log_retention_days},
            )
            req_deleted = result.rowcount if result.rowcount else 0

            # Delete old 5min metrics
            metrics_5min_sql = text("""
                DELETE FROM metrics_rollup
                WHERE period_granularity = '5min'
                  AND period_start < NOW() - MAKE_INTERVAL(days => :retention_days)
            """)
            result = await session.execute(
                metrics_5min_sql,
                {"retention_days": settings.metrics_5min_retention_days},
            )
            m5_deleted = result.rowcount if result.rowcount else 0

            # Delete old 1hour metrics
            metrics_1hour_sql = text("""
                DELETE FROM metrics_rollup
                WHERE period_granularity = '1hour'
                  AND period_start < NOW() - MAKE_INTERVAL(days => :retention_days)
            """)
            result = await session.execute(
                metrics_1hour_sql,
                {"retention_days": settings.metrics_1hour_retention_days},
            )
            m1h_deleted = result.rowcount if result.rowcount else 0

            await session.commit()
            log.info(
                "old_data_cleanup_complete",
                request_log_deleted=req_deleted,
                metrics_5min_deleted=m5_deleted,
                metrics_1hour_deleted=m1h_deleted,
            )

    except Exception:
        log.exception("old_data_cleanup_failed")


def start_metrics_service(scheduler: AsyncIOScheduler) -> None:
    """Register metrics rollup and cleanup jobs on the shared scheduler."""
    scheduler.add_job(
        rollup_metrics,
        "interval",
        seconds=settings.metrics_rollup_interval,
        id="metrics_rollup",
        max_instances=1,
    )
    scheduler.add_job(
        cleanup_old_data,
        "cron",
        hour=3,
        minute=0,
        id="metrics_cleanup",
        max_instances=1,
    )
    log.info(
        "metrics_service_registered",
        rollup_interval=settings.metrics_rollup_interval,
    )
