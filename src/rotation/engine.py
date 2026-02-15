import structlog
from redis.asyncio import Redis

from src.rotation.lua_scripts import (
    RATE_LIMIT_CHECK,
    ROTATE_LEAST_CONNECTIONS,
    ROTATE_RANDOM,
    ROTATE_ROUND_ROBIN,
    ROTATE_WEIGHTED_RANDOM,
)

log = structlog.get_logger()


class PoolExhaustedError(Exception):
    """Raised when no healthy proxy can be found in the requested pool."""


class RateLimitExceededError(Exception):
    """Raised when a project exceeds its configured request rate limit."""


class RotationEngine:
    """Manages proxy rotation across multiple strategies with sticky sessions,
    rate limiting, connection tracking, and per-project blacklists."""

    VALID_STRATEGIES = frozenset({
        "round_robin",
        "random",
        "weighted_random",
        "least_connections",
    })

    def __init__(self, redis: Redis):
        self._redis = redis
        self._rr_script = self._redis.register_script(ROTATE_ROUND_ROBIN)
        self._rand_script = self._redis.register_script(ROTATE_RANDOM)
        self._weighted_script = self._redis.register_script(ROTATE_WEIGHTED_RANDOM)
        self._lc_script = self._redis.register_script(ROTATE_LEAST_CONNECTIONS)
        self._rate_limit_script = self._redis.register_script(RATE_LIMIT_CHECK)

    # ------------------------------------------------------------------
    # Core rotation
    # ------------------------------------------------------------------

    async def get_next_proxy(
        self,
        pool_id: str,
        strategy: str = "round_robin",
        project_id: str | None = None,
        session_key: str | None = None,
    ) -> dict:
        """Get next healthy proxy from pool using the specified rotation strategy.

        If *session_key* is provided, sticky-session logic is applied first:
        a previously pinned proxy is returned when it is still healthy.

        Parameters
        ----------
        pool_id : str
            Identifier of the proxy pool.
        strategy : str
            One of ``round_robin``, ``random``, ``weighted_random``,
            ``least_connections``.
        project_id : str, optional
            Project identifier used for blacklist filtering and rate-limit
            scoping.  When ``None`` or empty, blacklist checks are skipped
            inside the Lua scripts.
        session_key : str, optional
            Opaque key used to pin a proxy to a caller session (sticky
            sessions).  When provided the engine will first check for an
            existing binding in Redis before running the rotation script.
        """
        # --- sticky session check ---
        if session_key:
            sticky_key = f"sticky:{pool_id}:{session_key}"
            sticky_proxy_id = await self._redis.get(sticky_key)
            if sticky_proxy_id:
                health = await self._redis.get(f"proxy:{sticky_proxy_id}:health")
                if health != "dead":
                    # Check blacklist if project_id is provided
                    if project_id:
                        blacklisted = await self._redis.sismember(
                            f"blacklist:{project_id}", sticky_proxy_id
                        )
                        if blacklisted:
                            log.info(
                                "sticky_proxy_blacklisted",
                                pool_id=pool_id,
                                session_key=session_key,
                                proxy_id=sticky_proxy_id,
                            )
                            # Fall through to normal rotation
                        else:
                            return await self._build_proxy_dict(sticky_proxy_id, pool_id)
                    else:
                        return await self._build_proxy_dict(sticky_proxy_id, pool_id)

        # --- rotation via Lua ---
        proj = project_id or ""

        if strategy == "random":
            pool_key = f"pool:{pool_id}:proxies"
            proxy_id = await self._rand_script(keys=[pool_key], args=[proj])
        elif strategy == "weighted_random":
            weighted_key = f"pool:{pool_id}:weighted"
            proxy_id = await self._weighted_script(keys=[weighted_key], args=[proj])
        elif strategy == "least_connections":
            connections_key = f"pool:{pool_id}:connections"
            proxy_id = await self._lc_script(keys=[connections_key], args=[proj])
        else:
            # Default: round_robin
            pool_key = f"pool:{pool_id}:proxies"
            proxy_id = await self._rr_script(keys=[pool_key], args=[proj])

        if proxy_id is None:
            raise PoolExhaustedError(
                f"No healthy proxies available in pool {pool_id}"
            )

        # Decode bytes if needed (decode_responses may already handle this)
        if isinstance(proxy_id, bytes):
            proxy_id = proxy_id.decode()

        return await self._build_proxy_dict(proxy_id, pool_id)

    async def _build_proxy_dict(self, proxy_id: str, pool_id: str) -> dict:
        """Fetch proxy info from Redis and return a standardised dict."""
        info = await self._redis.hgetall(f"proxy:{proxy_id}:info")
        if not info:
            raise PoolExhaustedError(f"Proxy {proxy_id} info not cached")

        return {
            "id": proxy_id,
            "host": info.get("host", ""),
            "port": int(info.get("port", 0)),
            "protocol": info.get("protocol", "http"),
            "username": info.get("username") or None,
            "password": info.get("password") or None,
        }

    # ------------------------------------------------------------------
    # Pool synchronisation
    # ------------------------------------------------------------------

    async def sync_pool(self, pool_id: str, proxy_ids: list[str]) -> None:
        """Rebuild Redis pool list from DB data."""
        pool_key = f"pool:{pool_id}:proxies"
        pipe = self._redis.pipeline()
        pipe.delete(pool_key)
        if proxy_ids:
            pipe.rpush(pool_key, *proxy_ids)
        await pipe.execute()
        log.info("pool_synced", pool_id=pool_id, count=len(proxy_ids))

    async def sync_weighted_pool(
        self, pool_id: str, proxy_weights: dict[str, int]
    ) -> None:
        """Rebuild the weighted ZSET for a pool.

        Parameters
        ----------
        pool_id : str
            Pool identifier.
        proxy_weights : dict[str, int]
            Mapping of proxy_id -> weight (higher weight = more traffic).
        """
        weighted_key = f"pool:{pool_id}:weighted"
        pipe = self._redis.pipeline()
        pipe.delete(weighted_key)
        if proxy_weights:
            # ZADD expects a mapping of {member: score}
            pipe.zadd(weighted_key, {pid: w for pid, w in proxy_weights.items()})
        await pipe.execute()
        log.info(
            "weighted_pool_synced",
            pool_id=pool_id,
            count=len(proxy_weights),
        )

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    async def update_proxy_health(self, proxy_id: str, status: str) -> None:
        """Update health status in Redis with 120s TTL."""
        await self._redis.set(f"proxy:{proxy_id}:health", status, ex=120)

    async def cache_proxy_info(self, proxy_id: str, info: dict) -> None:
        """Cache proxy connection info in a Redis hash."""
        key = f"proxy:{proxy_id}:info"
        mapping = {
            "host": info.get("host", ""),
            "port": str(info.get("port", 0)),
            "protocol": info.get("protocol", "http"),
            "username": info.get("username", ""),
            "password": info.get("password", ""),
        }
        await self._redis.hset(key, mapping=mapping)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def check_rate_limit(self, project_id: str, rpm_limit: int) -> bool:
        """Check whether *project_id* is within its per-minute rate limit.

        Returns ``True`` if the request is **allowed**, ``False`` if the
        project has exceeded its limit for the current window.
        """
        window_seconds = 60
        key = f"ratelimit:{project_id}:{window_seconds}"
        result = await self._rate_limit_script(
            keys=[key], args=[rpm_limit, window_seconds]
        )
        allowed = int(result) == 1
        if not allowed:
            log.warning(
                "rate_limit_exceeded",
                project_id=project_id,
                rpm_limit=rpm_limit,
            )
        return allowed

    # ------------------------------------------------------------------
    # Connection tracking (least-connections strategy)
    # ------------------------------------------------------------------

    async def track_connection(
        self, pool_id: str, proxy_id: str, increment: bool = True
    ) -> None:
        """Increment or decrement the connection counter for a proxy in the
        least-connections ZSET.

        Call with ``increment=True`` when a connection is opened and
        ``increment=False`` when it is closed.
        """
        connections_key = f"pool:{pool_id}:connections"
        delta = 1 if increment else -1
        await self._redis.zincrby(connections_key, delta, proxy_id)
        log.debug(
            "connection_tracked",
            pool_id=pool_id,
            proxy_id=proxy_id,
            delta=delta,
        )

    # ------------------------------------------------------------------
    # Sticky sessions
    # ------------------------------------------------------------------

    async def set_sticky_session(
        self,
        pool_id: str,
        session_key: str,
        proxy_id: str,
        ttl: int = 300,
    ) -> None:
        """Pin *proxy_id* to *session_key* for *ttl* seconds."""
        sticky_key = f"sticky:{pool_id}:{session_key}"
        await self._redis.set(sticky_key, proxy_id, ex=ttl)
        log.info(
            "sticky_session_set",
            pool_id=pool_id,
            session_key=session_key,
            proxy_id=proxy_id,
            ttl=ttl,
        )

    # ------------------------------------------------------------------
    # Blacklist management
    # ------------------------------------------------------------------

    async def add_to_blacklist(self, project_id: str, proxy_id: str) -> None:
        """Add a proxy to the per-project blacklist."""
        await self._redis.sadd(f"blacklist:{project_id}", proxy_id)
        log.info(
            "proxy_blacklisted",
            project_id=project_id,
            proxy_id=proxy_id,
        )

    async def remove_from_blacklist(
        self, project_id: str, proxy_id: str
    ) -> None:
        """Remove a proxy from the per-project blacklist."""
        await self._redis.srem(f"blacklist:{project_id}", proxy_id)
        log.info(
            "proxy_unblacklisted",
            project_id=project_id,
            proxy_id=proxy_id,
        )
