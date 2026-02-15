"""Bandwidth flush service.

Scans Redis for bandwidth counter keys (bw:*), atomically reads and deletes
them, and accumulates the values into the metrics_rollup table.
"""

from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from src.config import settings
from src.database import async_session_factory
from src.redis import get_redis

log = structlog.get_logger()


async def flush_bandwidth() -> None:
    """Flush bandwidth counters from Redis into metrics_rollup.

    Runs every bandwidth_flush_interval seconds (default 30s).
    Scans Redis for keys matching bw:* pattern.
    Key format: bw:{entity_type}:{entity_id}:{sent|recv}
    Atomically reads and deletes each key, then upserts into metrics_rollup.
    """
    try:
        redis = await get_redis()

        # Collect all bw:* keys using SCAN (non-blocking)
        bw_keys: list[str] = []
        async for key in redis.scan_iter(match="bw:*", count=500):
            bw_keys.append(key)

        if not bw_keys:
            return

        # Atomically GET and DELETE each key using a pipeline
        pipe = redis.pipeline()
        for key in bw_keys:
            pipe.getdel(key)
        values = await pipe.execute()

        # Parse and accumulate bandwidth data
        # Key format: bw:{entity_type}:{entity_id}:{sent|recv}
        # Group by (entity_type, entity_id) to merge sent/recv
        accumulator: dict[tuple[str, str], dict[str, int]] = {}

        for key, value in zip(bw_keys, values):
            if value is None:
                continue

            parts = key.split(":")
            if len(parts) != 4:
                log.warning("bandwidth_invalid_key_format", key=key)
                continue

            _, entity_type, entity_id, direction = parts
            if entity_type not in ("proxy", "pool", "project", "provider"):
                log.warning("bandwidth_invalid_entity_type", key=key, entity_type=entity_type)
                continue
            if direction not in ("sent", "recv"):
                log.warning("bandwidth_invalid_direction", key=key, direction=direction)
                continue

            try:
                byte_count = int(value)
            except (ValueError, TypeError):
                log.warning("bandwidth_invalid_value", key=key, value=value)
                continue

            acc_key = (entity_type, entity_id)
            if acc_key not in accumulator:
                accumulator[acc_key] = {"sent": 0, "recv": 0}
            accumulator[acc_key][direction] += byte_count

        if not accumulator:
            return

        # Compute current 5-minute period start
        now = datetime.now(timezone.utc)
        minute_bucket = (now.minute // 5) * 5
        period_start = now.replace(minute=minute_bucket, second=0, microsecond=0)

        # Upsert into metrics_rollup
        async with async_session_factory() as session:
            upsert_sql = text("""
                INSERT INTO metrics_rollup (
                    entity_type, entity_id, period_start, period_granularity,
                    total_requests, successful_requests, failed_requests,
                    bytes_sent, bytes_received,
                    avg_response_time_ms, p95_response_time_ms
                ) VALUES (
                    :entity_type, :entity_id, :period_start, '5min',
                    0, 0, 0,
                    :bytes_sent, :bytes_received,
                    NULL, NULL
                )
                ON CONFLICT (entity_type, entity_id, period_start, period_granularity)
                DO UPDATE SET
                    bytes_sent = metrics_rollup.bytes_sent + EXCLUDED.bytes_sent,
                    bytes_received = metrics_rollup.bytes_received + EXCLUDED.bytes_received
            """)

            flushed_count = 0
            for (entity_type, entity_id), bw in accumulator.items():
                await session.execute(
                    upsert_sql,
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "period_start": period_start,
                        "bytes_sent": bw["sent"],
                        "bytes_received": bw["recv"],
                    },
                )
                flushed_count += 1

            await session.commit()
            log.info(
                "bandwidth_flush_complete",
                keys_processed=len(bw_keys),
                entities_upserted=flushed_count,
                total_sent=sum(bw["sent"] for bw in accumulator.values()),
                total_recv=sum(bw["recv"] for bw in accumulator.values()),
            )

    except Exception:
        log.exception("bandwidth_flush_failed")


def start_bandwidth_service(scheduler: AsyncIOScheduler) -> None:
    """Register bandwidth flush job on the shared scheduler."""
    scheduler.add_job(
        flush_bandwidth,
        "interval",
        seconds=settings.bandwidth_flush_interval,
        id="bandwidth_flush",
        max_instances=1,
    )
    log.info(
        "bandwidth_service_registered",
        flush_interval=settings.bandwidth_flush_interval,
    )
