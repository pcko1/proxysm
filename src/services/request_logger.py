import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from src.database import async_session_factory
from src.redis import get_redis

log = structlog.get_logger()


class RequestLogger:
    """Logs proxy requests to PostgreSQL and tracks bandwidth in Redis.

    All write operations are executed in a fire-and-forget fashion via
    ``asyncio.create_task`` so that the caller is never blocked by logging
    I/O.
    """

    # Raw SQL for the partitioned request_log table.  Using raw SQL because
    # SQLAlchemy ORM inserts do not play well with partitioned tables.
    _INSERT_SQL = text(
        """
        INSERT INTO request_log (
            project_id,
            pool_id,
            proxy_id,
            status_code,
            response_time_ms,
            bytes_sent,
            bytes_received,
            target_domain,
            error_type,
            created_at
        ) VALUES (
            :project_id,
            :pool_id,
            :proxy_id,
            :status_code,
            :response_time_ms,
            :bytes_sent,
            :bytes_received,
            :target_domain,
            :error_type,
            :created_at
        )
        """
    )

    async def log_request(
        self,
        project_id: str,
        pool_id: str,
        proxy_id: str,
        status_code: int,
        response_time_ms: int,
        bytes_sent: int,
        bytes_received: int,
        target_domain: str,
        error_type: str | None = None,
    ) -> None:
        """Log a completed proxy request.

        This method spawns two background tasks (database insert and Redis
        counter updates) and returns immediately so the calling request
        handler is never delayed.

        Parameters
        ----------
        project_id : str
            Owning project identifier.
        pool_id : str
            Pool from which the proxy was selected.
        proxy_id : str
            The proxy that handled the request.
        status_code : int
            Upstream HTTP status code (0 if connection failed).
        response_time_ms : int
            Round-trip time in milliseconds.
        bytes_sent : int
            Request payload size in bytes.
        bytes_received : int
            Response payload size in bytes.
        target_domain : str
            The target domain the request was sent to.
        error_type : str, optional
            Short error classification (e.g. ``timeout``, ``conn_refused``).
        """
        now = datetime.now(timezone.utc)

        # Fire-and-forget database insert
        asyncio.create_task(
            self._insert_db_record(
                project_id=project_id,
                pool_id=pool_id,
                proxy_id=proxy_id,
                status_code=status_code,
                response_time_ms=response_time_ms,
                bytes_sent=bytes_sent,
                bytes_received=bytes_received,
                target_domain=target_domain,
                error_type=error_type,
                created_at=now,
            )
        )

        # Fire-and-forget bandwidth counter update
        asyncio.create_task(
            self._update_bandwidth_counters(
                project_id=project_id,
                pool_id=pool_id,
                proxy_id=proxy_id,
                bytes_sent=bytes_sent,
                bytes_received=bytes_received,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _insert_db_record(
        self,
        *,
        project_id: str,
        pool_id: str,
        proxy_id: str,
        status_code: int,
        response_time_ms: int,
        bytes_sent: int,
        bytes_received: int,
        target_domain: str,
        error_type: str | None,
        created_at: datetime,
    ) -> None:
        """Insert a row into the partitioned ``request_log`` table."""
        try:
            async with async_session_factory() as session:
                await session.execute(
                    self._INSERT_SQL,
                    {
                        "project_id": project_id,
                        "pool_id": pool_id,
                        "proxy_id": proxy_id,
                        "status_code": status_code,
                        "response_time_ms": response_time_ms,
                        "bytes_sent": bytes_sent,
                        "bytes_received": bytes_received,
                        "target_domain": target_domain,
                        "error_type": error_type,
                        "created_at": created_at,
                    },
                )
                await session.commit()
        except Exception:
            log.exception(
                "request_log_insert_failed",
                project_id=project_id,
                proxy_id=proxy_id,
            )

    async def _update_bandwidth_counters(
        self,
        *,
        project_id: str,
        pool_id: str,
        proxy_id: str,
        bytes_sent: int,
        bytes_received: int,
    ) -> None:
        """Atomically increment bandwidth counters in Redis."""
        try:
            redis = await get_redis()
            pipe = redis.pipeline()

            # Project-level counters
            pipe.incrby(f"bw:project:{project_id}:sent", bytes_sent)
            pipe.incrby(f"bw:project:{project_id}:recv", bytes_received)

            # Proxy-level counters
            pipe.incrby(f"bw:proxy:{proxy_id}:sent", bytes_sent)
            pipe.incrby(f"bw:proxy:{proxy_id}:recv", bytes_received)

            # Pool-level counters
            pipe.incrby(f"bw:pool:{pool_id}:sent", bytes_sent)
            pipe.incrby(f"bw:pool:{pool_id}:recv", bytes_received)

            await pipe.execute()
        except Exception:
            log.exception(
                "bandwidth_counter_update_failed",
                project_id=project_id,
                proxy_id=proxy_id,
            )
