"""Enhanced health checker with 3-state health model and adaptive intervals.

Health State Machine:
    unknown --(success)--> healthy
    unknown --(fail)-----> degraded
    healthy --(2 consecutive failures OR latency > 3x avg)--> degraded
    degraded --(5 consecutive failures)--> dead
    dead ----(1 success on periodic recheck)--> degraded
    degraded --(3 consecutive successes)--> healthy

Adaptive Check Intervals:
    healthy:  base_interval + random(0, interval/4)
    degraded: 15s + random jitter
    dead:     120s with exponential backoff up to 600s
"""

import asyncio
import json
import random
import time
from datetime import datetime, timezone

import aiohttp
import structlog
from aiohttp_socks import ProxyConnector
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text, update

from src.config import settings
from src.database import async_session_factory
from src.models.proxy import Proxy
from src.redis import get_redis

log = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None

# -- Redis key helpers --------------------------------------------------------

def _failures_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:failures"

def _successes_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:successes"

def _health_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:health"

def _external_ip_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:external_ip"

def _info_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:info"

def _dead_backoff_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:dead_backoff"

def _next_check_key(proxy_id: str) -> str:
    return f"proxy:{proxy_id}:next_check"


# -- Startup / Shutdown -------------------------------------------------------

async def start_health_checker() -> None:
    """Start the shared APScheduler and register all background services."""
    global _scheduler
    _scheduler = AsyncIOScheduler()

    # Health check job
    _scheduler.add_job(
        check_all_proxies,
        "interval",
        seconds=settings.health_check_interval,
        id="health_check",
        max_instances=1,
    )

    # Register Phase 2 background services on the same scheduler
    from src.services.metrics import start_metrics_service
    from src.services.bandwidth import start_bandwidth_service
    from src.services.partitions import start_partition_service

    start_metrics_service(_scheduler)
    start_bandwidth_service(_scheduler)
    start_partition_service(_scheduler)

    _scheduler.start()
    log.info("health_checker_started", interval=settings.health_check_interval)


async def stop_health_checker() -> None:
    """Shut down the shared scheduler (stops all background services)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("health_checker_stopped")


# -- Main check loop ----------------------------------------------------------

async def check_all_proxies() -> None:
    """Fetch all active proxies from DB and check them concurrently.

    Uses adaptive scheduling: each proxy has a next_check timestamp in Redis.
    Proxies whose next_check is in the future are skipped this cycle.
    """
    async with async_session_factory() as session:
        stmt = select(Proxy).where(Proxy.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        proxies = result.scalars().all()

    if not proxies:
        return

    # Filter proxies that are due for a check
    redis = await get_redis()
    now_ts = time.time()
    proxies_to_check = []

    for proxy in proxies:
        next_check = await redis.get(_next_check_key(str(proxy.id)))
        if next_check is None or float(next_check) <= now_ts:
            proxies_to_check.append(proxy)

    if not proxies_to_check:
        return

    log.info("health_check_starting", total=len(proxies), checking=len(proxies_to_check))
    semaphore = asyncio.Semaphore(500)

    async def _check_with_sem(proxy: Proxy):
        async with semaphore:
            return await check_single_proxy(proxy)

    results = await asyncio.gather(
        *[_check_with_sem(p) for p in proxies_to_check],
        return_exceptions=True,
    )

    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        for proxy, result in zip(proxies_to_check, results):
            proxy_id = str(proxy.id)

            if isinstance(result, Exception):
                log.warning("health_check_exception", proxy_id=proxy_id, error=str(result))
                new_status, latency, external_ip = "unknown", 0.0, None
            else:
                new_status, latency, external_ip = result

            # Update health status in Redis (120s TTL)
            await redis.set(_health_key(proxy_id), new_status, ex=120)

            # Cache proxy info for rotation engine
            await redis.hset(_info_key(proxy_id), mapping={
                "host": proxy.host,
                "port": str(proxy.port),
                "protocol": proxy.protocol,
                "username": proxy.username or "",
                "password": proxy.password_encrypted or "",
            })

            # Store external IP if detected
            if external_ip:
                await redis.set(_external_ip_key(proxy_id), external_ip, ex=3600)

            # Schedule next check with adaptive interval
            await _schedule_next_check(redis, proxy_id, new_status)

            # Update proxy row in PostgreSQL
            update_values = {
                "last_health_check": now,
                "last_health_status": new_status,
            }
            if new_status == "healthy" and latency > 0:
                update_values["avg_latency_ms"] = latency

            stmt = (
                update(Proxy)
                .where(Proxy.id == proxy.id)
                .values(**update_values)
            )
            await session.execute(stmt)

            # Log health check result to health_check_log (partitioned table)
            await _insert_health_log(
                session, proxy.id, new_status, latency, external_ip, now,
            )

        await session.commit()

    log.info("health_check_complete", checked=len(proxies_to_check))


# -- Single proxy check -------------------------------------------------------

async def check_single_proxy(proxy: Proxy) -> tuple[str, float, str | None]:
    """Check a single proxy and determine its new health status.

    Returns (new_status, latency_ms, external_ip).
    Implements the 3-state health model with consecutive failure/success tracking.
    """
    proxy_id = str(proxy.id)
    host = proxy.host
    port = proxy.port
    protocol = proxy.protocol
    username = proxy.username
    password = proxy.password_encrypted
    prev_status = proxy.last_health_status or "unknown"

    try:
        connector = None
        proxy_url = None

        if protocol == "socks5":
            socks_url = (
                f"socks5://{username}:{password}@{host}:{port}"
                if username
                else f"socks5://{host}:{port}"
            )
            connector = ProxyConnector.from_url(socks_url)
        else:
            use_ssl = protocol == "https" or port in (443, 8443)
            scheme = "https" if use_ssl else "http"
            proxy_url = (
                f"{scheme}://{username}:{password}@{host}:{port}"
                if username
                else f"{scheme}://{host}:{port}"
            )

        timeout = aiohttp.ClientTimeout(total=settings.health_check_timeout)
        start = time.monotonic()

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
            kwargs = {}
            if proxy_url and connector is None:
                kwargs["proxy"] = proxy_url
            async with sess.get(settings.health_check_url, **kwargs) as resp:
                body = await resp.read()
                elapsed_ms = (time.monotonic() - start) * 1000

        # Parse external IP from httpbin.org/ip response
        external_ip = _parse_external_ip(body)

        # --- SUCCESS PATH ---
        redis = await get_redis()

        # Reset failure counter, increment success counter
        await redis.delete(_failures_key(proxy_id))
        successes = await redis.incr(_successes_key(proxy_id))

        # Reset dead backoff on success
        await redis.delete(_dead_backoff_key(proxy_id))

        latency = round(elapsed_ms, 1)

        # Determine new status based on previous status
        if prev_status == "unknown":
            new_status = "healthy"
        elif prev_status == "dead":
            # dead -> degraded on first success
            new_status = "degraded"
            await redis.delete(_successes_key(proxy_id))
            await redis.set(_successes_key(proxy_id), "1")
        elif prev_status == "degraded":
            # degraded -> healthy after N consecutive successes
            if successes >= settings.health_recoveries_to_healthy:
                new_status = "healthy"
                await redis.delete(_successes_key(proxy_id))
            else:
                new_status = "degraded"
        else:
            # healthy stays healthy, but check for latency spike
            new_status = "healthy"
            if proxy.avg_latency_ms and proxy.avg_latency_ms > 0:
                if latency > proxy.avg_latency_ms * 3:
                    # Latency spike: healthy -> degraded
                    new_status = "degraded"
                    await redis.delete(_successes_key(proxy_id))
                    log.info(
                        "proxy_latency_spike",
                        proxy_id=proxy_id,
                        latency=latency,
                        avg=proxy.avg_latency_ms,
                    )

        return new_status, latency, external_ip

    except Exception:
        # --- FAILURE PATH ---
        redis = await get_redis()

        # Reset success counter, increment failure counter
        await redis.delete(_successes_key(proxy_id))
        failures = await redis.incr(_failures_key(proxy_id))

        if prev_status == "unknown":
            new_status = "degraded"
        elif prev_status == "healthy":
            # healthy -> degraded after N consecutive failures
            if failures >= settings.health_failures_to_degraded:
                new_status = "degraded"
            else:
                new_status = "healthy"
        elif prev_status == "degraded":
            # degraded -> dead after N consecutive failures
            if failures >= settings.health_failures_to_dead:
                new_status = "dead"
            else:
                new_status = "degraded"
        elif prev_status == "dead":
            # dead stays dead on failure
            new_status = "dead"
            # Increase exponential backoff
            backoff = await redis.get(_dead_backoff_key(proxy_id))
            current_backoff = int(backoff) if backoff else 120
            new_backoff = min(current_backoff * 2, 600)
            await redis.set(_dead_backoff_key(proxy_id), str(new_backoff), ex=3600)
        else:
            new_status = "degraded"

        return new_status, 0.0, None


# -- Helpers -------------------------------------------------------------------

def _parse_external_ip(body: bytes) -> str | None:
    """Try to parse the external IP from httpbin.org/ip JSON response."""
    try:
        data = json.loads(body)
        origin = data.get("origin", "")
        # httpbin may return comma-separated IPs; take the first
        ip = origin.split(",")[0].strip()
        return ip if ip else None
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None


async def _schedule_next_check(
    redis, proxy_id: str, status: str,
) -> None:
    """Set the next_check timestamp in Redis based on proxy health status.

    Adaptive intervals:
        healthy:  base_interval + random(0, interval/4)
        degraded: 15s + random(0, 5)
        dead:     exponential backoff starting at 120s, capped at 600s
    """
    base = settings.health_check_interval

    if status == "healthy":
        interval = base + random.uniform(0, base / 4)
    elif status == "degraded":
        interval = 15 + random.uniform(0, 5)
    elif status == "dead":
        backoff = await redis.get(_dead_backoff_key(proxy_id))
        interval = int(backoff) if backoff else 120
    else:
        # unknown: use base interval
        interval = base

    next_ts = time.time() + interval
    await redis.set(_next_check_key(proxy_id), str(next_ts), ex=int(interval) + 60)


async def _insert_health_log(
    session,
    proxy_id,
    status: str,
    latency_ms: float,
    external_ip: str | None,
    checked_at: datetime,
) -> None:
    """Insert a row into the health_check_log partitioned table."""
    try:
        insert_sql = text("""
            INSERT INTO health_check_log (proxy_id, status, latency_ms, external_ip, checked_at)
            VALUES (:proxy_id, :status, :latency_ms, :external_ip, :checked_at)
        """)
        await session.execute(
            insert_sql,
            {
                "proxy_id": proxy_id,
                "status": status,
                "latency_ms": round(latency_ms) if latency_ms > 0 else None,
                "external_ip": external_ip,
                "checked_at": checked_at,
            },
        )
    except Exception:
        # If the partition doesn't exist yet, log but don't fail the health check
        log.warning(
            "health_log_insert_failed",
            proxy_id=str(proxy_id),
            status=status,
        )
