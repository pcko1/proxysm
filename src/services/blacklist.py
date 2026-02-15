"""Auto-blacklisting service.

Evaluates proxy error rates per project and auto-blacklists proxies that
exceed the configured threshold. Also cleans up expired blacklist entries.
"""

import uuid

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from src.config import settings
from src.database import async_session_factory
from src.redis import get_redis

log = structlog.get_logger()


async def evaluate_blacklists() -> None:
    """Evaluate proxy error rates and auto-blacklist proxies exceeding threshold.

    Runs every blacklist_eval_interval seconds.
    For each project+pool combination, queries recent request_log entries within
    the pool's blacklist_window_seconds. If the error rate for a proxy exceeds
    the pool's blacklist_threshold, the proxy is blacklisted for that project
    with a cooldown period.
    """
    try:
        async with async_session_factory() as session:
            # Get all project-pool assignments with pool config
            project_pools_sql = text("""
                SELECT pp.project_id, pp.pool_id,
                       p.blacklist_threshold, p.blacklist_window_seconds,
                       p.blacklist_cooldown_seconds
                FROM project_pools pp
                JOIN pools p ON pp.pool_id = p.id
            """)
            result = await session.execute(project_pools_sql)
            project_pools = result.fetchall()

            if not project_pools:
                return

            redis = await get_redis()
            blacklisted_count = 0

            for row in project_pools:
                project_id = row.project_id
                pool_id = row.pool_id
                threshold = row.blacklist_threshold
                window = row.blacklist_window_seconds
                cooldown = row.blacklist_cooldown_seconds

                # Query error rates for proxies in this project within the window
                error_rate_sql = text("""
                    SELECT rl.proxy_id,
                           COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE rl.error_type IS NOT NULL) AS errors
                    FROM request_log rl
                    JOIN pool_proxies pp_link ON pp_link.proxy_id = rl.proxy_id
                        AND pp_link.pool_id = :pool_id
                    WHERE rl.project_id = :project_id
                      AND rl.created_at > NOW() - MAKE_INTERVAL(secs => :window)
                    GROUP BY rl.proxy_id
                    HAVING COUNT(*) >= 5
                """)
                error_result = await session.execute(
                    error_rate_sql,
                    {"project_id": project_id, "pool_id": pool_id, "window": window},
                )
                error_rows = error_result.fetchall()

                for erow in error_rows:
                    proxy_id = erow.proxy_id
                    total = erow.total
                    errors = erow.errors
                    error_rate = errors / total if total > 0 else 0.0

                    if error_rate <= threshold:
                        continue

                    # Check if already blacklisted
                    existing_sql = text("""
                        SELECT id FROM project_proxy_blacklist
                        WHERE project_id = :project_id
                          AND proxy_id = :proxy_id
                          AND (expires_at IS NULL OR expires_at > NOW())
                    """)
                    existing = await session.execute(
                        existing_sql,
                        {"project_id": project_id, "proxy_id": proxy_id},
                    )
                    if existing.fetchone() is not None:
                        continue

                    # Insert blacklist entry
                    bl_id = uuid.uuid4()
                    insert_sql = text("""
                        INSERT INTO project_proxy_blacklist
                            (id, project_id, proxy_id, target_domain, reason,
                             auto_generated, blacklisted_at, expires_at)
                        VALUES
                            (:id, :project_id, :proxy_id, NULL,
                             :reason, TRUE, NOW(),
                             NOW() + MAKE_INTERVAL(secs => :cooldown))
                        ON CONFLICT (project_id, proxy_id, target_domain)
                        DO UPDATE SET
                            expires_at = NOW() + MAKE_INTERVAL(secs => :cooldown),
                            reason = :reason,
                            blacklisted_at = NOW()
                    """)
                    reason = (
                        f"Auto-blacklisted: error_rate={error_rate:.2%} "
                        f"({errors}/{total}) exceeds threshold {threshold:.2%}"
                    )
                    await session.execute(
                        insert_sql,
                        {
                            "id": bl_id,
                            "project_id": project_id,
                            "proxy_id": proxy_id,
                            "reason": reason,
                            "cooldown": cooldown,
                        },
                    )

                    # Add to Redis blacklist set
                    await redis.sadd(f"blacklist:{project_id}", str(proxy_id))

                    blacklisted_count += 1
                    log.info(
                        "proxy_auto_blacklisted",
                        project_id=str(project_id),
                        proxy_id=str(proxy_id),
                        error_rate=f"{error_rate:.2%}",
                        threshold=f"{threshold:.2%}",
                        cooldown_seconds=cooldown,
                    )

            await session.commit()

            if blacklisted_count > 0:
                log.info("blacklist_evaluation_complete", blacklisted=blacklisted_count)

    except Exception:
        log.exception("blacklist_evaluation_failed")


async def cleanup_expired_blacklists() -> None:
    """Remove expired blacklist entries from PostgreSQL and Redis.

    Runs every blacklist_cooldown_check_interval seconds.
    """
    try:
        async with async_session_factory() as session:
            # Find all expired entries
            expired_sql = text("""
                SELECT id, project_id, proxy_id
                FROM project_proxy_blacklist
                WHERE expires_at IS NOT NULL AND expires_at <= NOW()
            """)
            result = await session.execute(expired_sql)
            expired_rows = result.fetchall()

            if not expired_rows:
                return

            redis = await get_redis()
            recovered_count = 0

            for row in expired_rows:
                entry_id = row.id
                project_id = row.project_id
                proxy_id = row.proxy_id

                # Delete from PostgreSQL
                delete_sql = text("""
                    DELETE FROM project_proxy_blacklist WHERE id = :id
                """)
                await session.execute(delete_sql, {"id": entry_id})

                # Remove from Redis blacklist set
                await redis.srem(f"blacklist:{project_id}", str(proxy_id))

                recovered_count += 1
                log.info(
                    "proxy_blacklist_expired",
                    project_id=str(project_id),
                    proxy_id=str(proxy_id),
                )

            await session.commit()
            log.info("blacklist_cleanup_complete", recovered=recovered_count)

    except Exception:
        log.exception("blacklist_cleanup_failed")


def start_blacklist_service(scheduler: AsyncIOScheduler) -> None:
    """Register blacklist evaluation and cleanup jobs on the shared scheduler."""
    scheduler.add_job(
        evaluate_blacklists,
        "interval",
        seconds=settings.blacklist_eval_interval,
        id="blacklist_evaluate",
        max_instances=1,
    )
    scheduler.add_job(
        cleanup_expired_blacklists,
        "interval",
        seconds=settings.blacklist_cooldown_check_interval,
        id="blacklist_cleanup",
        max_instances=1,
    )
    log.info(
        "blacklist_service_registered",
        eval_interval=settings.blacklist_eval_interval,
        cleanup_interval=settings.blacklist_cooldown_check_interval,
    )


def stop_blacklist_service() -> None:
    """No-op: scheduler shutdown is handled centrally."""
    pass
