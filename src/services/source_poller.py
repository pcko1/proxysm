"""Source poller — periodically fetches URL-based proxy sources and syncs the proxy list.

Poll logic:
    - Only sources with type='url' and is_active=True are polled.
    - On 200 OK: sync proxies (add new, deactivate missing+unhealthy, re-activate returning).
    - On error: increment consecutive_failures, skip sync.

Sync logic:
    - Step 1: Build feed_set from parsed response and db_proxies from DB.
    - Step 2: Add new proxies (skip cross-source duplicates).
    - Step 3: Deactivate proxies missing from feed AND already unhealthy (dead/degraded).
    - Step 4: Re-activate proxies that reappear in feed.
    - Step 5: Update credentials if changed.
"""

from datetime import datetime, timezone

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func

from src.config import settings
from src.database import async_session_factory
from src.models.proxy import Proxy
from src.models.source import ProxySource
from src.services.import_parser import parse_proxy_list

log = structlog.get_logger()


def start_source_poller(scheduler: AsyncIOScheduler) -> None:
    """Register the source polling job on the shared scheduler."""
    scheduler.add_job(
        poll_all_sources,
        "interval",
        seconds=settings.source_poll_interval,
        id="source_poller",
        max_instances=1,
    )
    log.info("source_poller_registered", interval=settings.source_poll_interval)


async def poll_all_sources() -> None:
    """Poll all active URL sources and sync their proxy lists."""
    async with async_session_factory() as session:
        stmt = select(ProxySource).where(
            ProxySource.type == "url",
            ProxySource.is_active == True,  # noqa: E712
        )
        sources = (await session.execute(stmt)).scalars().all()

    if not sources:
        return

    log.info("source_poll_starting", count=len(sources))

    for source in sources:
        try:
            await _poll_single_source(source)
        except Exception:
            log.exception("source_poll_error", source_id=str(source.id), name=source.name)

    log.info("source_poll_complete", count=len(sources))


async def _poll_single_source(source: ProxySource) -> None:
    """Fetch a single source URL and sync its proxies."""
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(source.url)
        status_code = resp.status_code
    except (httpx.HTTPError, Exception) as exc:
        log.warning(
            "source_fetch_failed",
            source_id=str(source.id),
            name=source.name,
            error=str(exc),
        )
        async with async_session_factory() as session:
            src = await session.get(ProxySource, source.id)
            src.consecutive_failures += 1
            src.last_polled_at = now
            src.last_status_code = None
            await session.commit()
        return

    async with async_session_factory() as session:
        src = await session.get(ProxySource, source.id)
        src.last_polled_at = now
        src.last_status_code = status_code

        if status_code != 200:
            src.consecutive_failures += 1
            await session.commit()
            log.warning(
                "source_non_200",
                source_id=str(source.id),
                name=source.name,
                status_code=status_code,
            )
            return

        # Success — reset failures and sync
        src.consecutive_failures = 0
        await session.commit()

    # Parse the feed
    try:
        parsed = parse_proxy_list(resp.text)
    except ValueError:
        log.warning("source_parse_failed", source_id=str(source.id), name=source.name)
        return

    await _sync_proxies(source, parsed)


async def _sync_proxies(source: ProxySource, parsed: list) -> None:
    """Sync parsed proxy list against DB proxies for this source."""
    async with async_session_factory() as session:
        # Step 1 — Build lookup sets
        feed_set = {}
        for p in parsed:
            key = (p.host, p.port, source.protocol)
            feed_set[key] = p

        db_stmt = select(Proxy).where(Proxy.source_id == source.id)
        db_proxies = (await session.execute(db_stmt)).scalars().all()
        db_map = {(p.host, p.port, p.protocol): p for p in db_proxies}

        added = 0
        deactivated = 0
        reactivated = 0
        updated = 0

        # Step 2 — Add new proxies (skip cross-source duplicates)
        for key, p in feed_set.items():
            if key not in db_map:
                # Check for cross-source duplicate
                existing = await session.execute(
                    select(Proxy.id).where(
                        Proxy.host == p.host,
                        Proxy.port == p.port,
                        Proxy.protocol == p.protocol,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                proxy = Proxy(
                    source_id=source.id,
                    host=p.host,
                    port=p.port,
                    protocol=source.protocol,
                    provider=source.provider,
                    username=p.username,
                    password_encrypted=p.password,
                )
                session.add(proxy)
                added += 1

        # Step 3 — Handle disappeared proxies
        for key, proxy in db_map.items():
            if key not in feed_set:
                if proxy.last_health_status in ("dead", "degraded"):
                    proxy.is_active = False
                    deactivated += 1

        # Step 4 — Re-activate returning proxies
        for key, p in feed_set.items():
            if key in db_map:
                proxy = db_map[key]
                if not proxy.is_active:
                    proxy.is_active = True
                    proxy.last_health_status = "unknown"
                    reactivated += 1

                # Step 5 — Update credentials if changed
                new_user = p.username
                new_pass = p.password
                if proxy.username != new_user or proxy.password_encrypted != new_pass:
                    proxy.username = new_user
                    proxy.password_encrypted = new_pass
                    updated += 1

        await session.commit()

    log.info(
        "source_sync_complete",
        source_id=str(source.id),
        name=source.name,
        added=added,
        deactivated=deactivated,
        reactivated=reactivated,
        updated=updated,
    )


async def poll_single_source_by_id(source_id) -> dict:
    """Poll a single source by ID (used by the API for manual triggering)."""
    async with async_session_factory() as session:
        source = await session.get(ProxySource, source_id)
        if source is None:
            raise ValueError("Source not found")
        if source.type != "url":
            raise ValueError("Only URL sources can be polled")
        if not source.url:
            raise ValueError("Source has no URL configured")

    await _poll_single_source(source)

    # Return updated source info
    async with async_session_factory() as session:
        source = await session.get(ProxySource, source_id)
        proxy_count = (await session.execute(
            select(func.count(Proxy.id)).where(Proxy.source_id == source_id)
        )).scalar() or 0

    return {
        "source_id": str(source.id),
        "last_polled_at": source.last_polled_at.isoformat() if source.last_polled_at else None,
        "last_status_code": source.last_status_code,
        "consecutive_failures": source.consecutive_failures,
        "proxy_count": proxy_count,
    }
