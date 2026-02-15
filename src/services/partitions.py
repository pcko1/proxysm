"""Partition management service.

Manages daily partitions for time-series tables (request_log, health_check_log).
Creates future partitions and drops partitions beyond retention periods.
"""

from datetime import datetime, timedelta, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from src.config import settings
from src.database import async_session_factory

log = structlog.get_logger()

# Tables that use daily partitioning
PARTITIONED_TABLES = [
    {
        "parent": "request_log",
        "date_column": "created_at",
        "retention_days": None,  # set from settings at runtime
    },
    {
        "parent": "health_check_log",
        "date_column": "checked_at",
        "retention_days": None,  # same as request_log retention
    },
]

# How many days ahead to pre-create partitions
PARTITION_LOOKAHEAD_DAYS = 7


async def ensure_partitions() -> None:
    """Create daily partitions for the next 7 days for partitioned tables.

    Runs daily. Creates partitions named {parent}_YYYY_MM_DD covering
    one day each: [YYYY-MM-DD, YYYY-MM-DD+1).
    Uses CREATE TABLE IF NOT EXISTS to be idempotent.
    """
    try:
        today = datetime.now(timezone.utc).date()
        async with async_session_factory() as session:
            created_count = 0

            for table_config in PARTITIONED_TABLES:
                parent = table_config["parent"]

                for day_offset in range(PARTITION_LOOKAHEAD_DAYS):
                    partition_date = today + timedelta(days=day_offset)
                    next_date = partition_date + timedelta(days=1)

                    partition_name = (
                        f"{parent}_{partition_date.strftime('%Y_%m_%d')}"
                    )
                    range_start = partition_date.isoformat()
                    range_end = next_date.isoformat()

                    # Use raw SQL for DDL - cannot be parameterized
                    create_sql = text(
                        f"CREATE TABLE IF NOT EXISTS {partition_name} "
                        f"PARTITION OF {parent} "
                        f"FOR VALUES FROM ('{range_start}') TO ('{range_end}')"
                    )

                    try:
                        await session.execute(create_sql)
                        created_count += 1
                    except Exception as exc:
                        # Partition may already exist or overlap; log and continue
                        err_msg = str(exc)
                        if "already exists" not in err_msg and "overlap" not in err_msg:
                            log.warning(
                                "partition_create_error",
                                table=parent,
                                partition=partition_name,
                                error=err_msg,
                            )

                await session.commit()

            log.info(
                "partitions_ensured",
                tables=len(PARTITIONED_TABLES),
                days_ahead=PARTITION_LOOKAHEAD_DAYS,
                partitions_checked=created_count,
            )

    except Exception:
        log.exception("ensure_partitions_failed")


async def drop_old_partitions() -> None:
    """Drop partitions older than retention period.

    Runs daily. Looks for partitions named {parent}_YYYY_MM_DD and drops
    those where the date is older than the retention period.
    """
    try:
        retention_days = settings.request_log_retention_days
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=retention_days)

        async with async_session_factory() as session:
            dropped_count = 0

            for table_config in PARTITIONED_TABLES:
                parent = table_config["parent"]

                # Query pg_inherits to find child partitions
                partitions_sql = text("""
                    SELECT c.relname AS partition_name
                    FROM pg_inherits i
                    JOIN pg_class c ON i.inhrelid = c.oid
                    JOIN pg_class p ON i.inhparent = p.oid
                    WHERE p.relname = :parent_table
                    ORDER BY c.relname
                """)
                result = await session.execute(
                    partitions_sql, {"parent_table": parent}
                )
                partitions = result.fetchall()

                for row in partitions:
                    partition_name = row.partition_name
                    # Parse date from partition name: {parent}_YYYY_MM_DD
                    prefix = f"{parent}_"
                    if not partition_name.startswith(prefix):
                        continue

                    date_part = partition_name[len(prefix):]
                    try:
                        partition_date = datetime.strptime(
                            date_part, "%Y_%m_%d"
                        ).date()
                    except ValueError:
                        # Not a date-formatted partition, skip
                        continue

                    if partition_date < cutoff_date:
                        drop_sql = text(f"DROP TABLE IF EXISTS {partition_name}")
                        await session.execute(drop_sql)
                        dropped_count += 1
                        log.info(
                            "partition_dropped",
                            table=parent,
                            partition=partition_name,
                            partition_date=partition_date.isoformat(),
                        )

                await session.commit()

            if dropped_count > 0:
                log.info("old_partitions_dropped", count=dropped_count)

    except Exception:
        log.exception("drop_old_partitions_failed")


def start_partition_service(scheduler: AsyncIOScheduler) -> None:
    """Register partition management jobs on the shared scheduler."""
    # Run partition creation daily at 00:30 UTC
    scheduler.add_job(
        ensure_partitions,
        "cron",
        hour=0,
        minute=30,
        id="partition_ensure",
        max_instances=1,
    )
    # Run partition cleanup daily at 01:00 UTC
    scheduler.add_job(
        drop_old_partitions,
        "cron",
        hour=1,
        minute=0,
        id="partition_drop_old",
        max_instances=1,
    )
    # Also run partition creation immediately on startup
    scheduler.add_job(
        ensure_partitions,
        id="partition_ensure_startup",
        max_instances=1,
    )
    log.info("partition_service_registered")
