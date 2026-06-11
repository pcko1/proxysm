"""Alert evaluator — periodically checks enabled alert rules and fires webhook actions.

Condition semantics:
    error_rate_above        failed/total requests over the last ``window_seconds``
                            (default 300) exceeds ``threshold`` (fraction 0-1);
                            requires at least one request in the window
    pool_below_min_healthy  healthy proxies in ``pool_id`` < ``min_healthy``
    bandwidth_exceeded      bytes sent+received over the last 24h > ``limit_bytes``
    all_proxies_dead        every proxy is dead (and at least one proxy exists)

A rule re-fires only after ``alert_cooldown_seconds`` since its last trigger.
``last_triggered_at`` records that the condition fired, regardless of whether
webhook delivery succeeded.
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from src.config import settings
from src.database import async_session_factory
from src.models.alert import AlertRule
from src.models.associations import PoolProxy
from src.models.metrics import MetricsRollup
from src.models.pool import Pool
from src.models.proxy import Proxy
from src.models.request_log import RequestLog

log = structlog.get_logger()

WEBHOOK_TIMEOUT_SECONDS = 10


def start_alert_service(scheduler: AsyncIOScheduler) -> None:
    """Register the alert evaluation job on the shared scheduler."""
    scheduler.add_job(
        evaluate_alerts,
        "interval",
        seconds=settings.alert_check_interval,
        id="alert_evaluator",
        max_instances=1,
    )
    log.info("alert_service_started", interval=settings.alert_check_interval)


async def evaluate_alerts() -> None:
    """Evaluate all enabled alert rules and fire actions for triggered ones."""
    async with async_session_factory() as db:
        result = await db.execute(select(AlertRule).where(AlertRule.is_enabled.is_(True)))
        rules = result.scalars().all()
        if not rules:
            return

        now = datetime.now(UTC)
        for rule in rules:
            if (
                rule.last_triggered_at is not None
                and (now - rule.last_triggered_at).total_seconds() < settings.alert_cooldown_seconds
            ):
                continue
            try:
                context = await _evaluate_condition(db, rule)
            except Exception:
                log.exception(
                    "alert_evaluation_failed", alert=rule.name, condition=rule.condition_type
                )
                continue
            if context is None:
                continue

            rule.last_triggered_at = now
            await db.commit()
            log.info("alert_triggered", alert=rule.name, condition=rule.condition_type, **context)
            await _fire_webhook(rule, context, now)


async def _evaluate_condition(db, rule: AlertRule) -> dict | None:
    """Return trigger context if the rule's condition holds, else None."""
    cfg = rule.condition_config or {}
    if rule.condition_type == "error_rate_above":
        return await _check_error_rate(db, cfg)
    if rule.condition_type == "pool_below_min_healthy":
        return await _check_pool_health(db, cfg)
    if rule.condition_type == "bandwidth_exceeded":
        return await _check_bandwidth(db, cfg)
    if rule.condition_type == "all_proxies_dead":
        return await _check_all_dead(db)
    log.warning("alert_unknown_condition", alert=rule.name, condition=rule.condition_type)
    return None


async def _check_error_rate(db, cfg: dict) -> dict | None:
    threshold = float(cfg.get("threshold", 0))
    window = int(cfg.get("window_seconds", 300))
    cutoff = datetime.now(UTC) - timedelta(seconds=window)
    row = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(
                    RequestLog.status_code >= 200, RequestLog.status_code < 400
                ),
            ).where(RequestLog.created_at >= cutoff)
        )
    ).one()
    total, ok = int(row[0]), int(row[1])
    if total == 0:
        return None
    actual = (total - ok) / total
    if actual > threshold:
        return {
            "threshold": threshold,
            "actual": round(actual, 4),
            "window_seconds": window,
            "requests": total,
        }
    return None


async def _check_pool_health(db, cfg: dict) -> dict | None:
    pool_id = cfg.get("pool_id")
    if not pool_id:
        return None
    min_healthy = int(cfg.get("min_healthy", 1))
    pool = await db.get(Pool, uuid.UUID(str(pool_id)))
    if pool is None:
        return None
    healthy = (
        await db.execute(
            select(func.count())
            .select_from(PoolProxy)
            .join(Proxy, Proxy.id == PoolProxy.proxy_id)
            .where(PoolProxy.pool_id == pool.id, Proxy.last_health_status == "healthy")
        )
    ).scalar() or 0
    if healthy < min_healthy:
        return {
            "pool": pool.name,
            "pool_id": str(pool.id),
            "min_healthy": min_healthy,
            "actual": int(healthy),
        }
    return None


async def _check_bandwidth(db, cfg: dict) -> dict | None:
    limit = int(cfg.get("limit_bytes", 0))
    if limit <= 0:
        return None
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(MetricsRollup.bytes_sent), 0),
                func.coalesce(func.sum(MetricsRollup.bytes_received), 0),
            ).where(
                MetricsRollup.entity_type == "proxy",
                MetricsRollup.period_granularity == "5min",
                MetricsRollup.period_start >= cutoff,
            )
        )
    ).one()
    actual = int(row[0]) + int(row[1])
    if actual > limit:
        return {"limit_bytes": limit, "actual_bytes": actual, "window": "24h"}
    return None


async def _check_all_dead(db) -> dict | None:
    rows = (
        await db.execute(
            select(Proxy.last_health_status, func.count()).group_by(Proxy.last_health_status)
        )
    ).all()
    counts = {status: int(n) for status, n in rows}
    total = sum(counts.values())
    if total > 0 and counts.get("dead", 0) == total:
        return {"total_proxies": total}
    return None


async def _fire_webhook(rule: AlertRule, context: dict, triggered_at: datetime) -> None:
    url = (rule.action_config or {}).get("url")
    if not url:
        log.warning("alert_webhook_missing_url", alert=rule.name)
        return
    payload = {
        "event": "alert.triggered",
        "alert_name": rule.name,
        "condition": {"type": rule.condition_type, **context},
        "triggered_at": triggered_at.isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
        log.info("alert_webhook_sent", alert=rule.name, url=url, status=resp.status_code)
    except httpx.HTTPError:
        log.warning("alert_webhook_failed", alert=rule.name, url=url, exc_info=True)
