import asyncio
import base64
import hashlib
import ssl
import time

import aiohttp
import structlog
from aiohttp_socks import ProxyConnector

from src.config import settings
from src.database import async_session_factory
from src.models.project import Project
from src.models.associations import ProjectPool
from src.models.pool import Pool
from src.redis import get_redis
from src.rotation.engine import PoolExhaustedError, RotationEngine
from src.services.request_logger import RequestLogger
from sqlalchemy import select

log = structlog.get_logger()

_request_logger = RequestLogger()

# Auth cache: key -> (api_key_hash, project_id, pool_id, pool_strategy, expiry_ts)
_auth_cache: dict[str, tuple[str, str, str, str, float]] = {}
_AUTH_CACHE_TTL = 30.0


async def _authenticate(slug: str, api_key: str) -> tuple[str, str, str] | None:
    """Authenticate project credentials. Returns (project_id, pool_id, rotation_strategy) or None."""
    cache_key = f"{slug}:{api_key}"
    now = time.monotonic()
    cached = _auth_cache.get(cache_key)
    if cached is not None:
        stored_hash, project_id, pool_id, strategy, expiry = cached
        if now < expiry:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            if key_hash == stored_hash:
                return project_id, pool_id, strategy
        else:
            del _auth_cache[cache_key]

    async with async_session_factory() as session:
        stmt = (
            select(Project, Pool)
            .join(ProjectPool, Project.id == ProjectPool.project_id)
            .join(Pool, ProjectPool.pool_id == Pool.id)
            .where(Project.slug == slug)
            .order_by(ProjectPool.priority.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        project, pool = row

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if project.api_key_hash != key_hash:
            return None

        project_id = str(project.id)
        pool_id = str(pool.id)
        strategy = pool.rotation_strategy
        _auth_cache[cache_key] = (key_hash, project_id, pool_id, strategy, now + _AUTH_CACHE_TTL)
        return project_id, pool_id, strategy


async def _parse_proxy_auth(headers_raw: bytes) -> tuple[str, str] | None:
    """Extract Proxy-Authorization from raw headers. Returns (slug, api_key) or None."""
    for line in headers_raw.split(b"\r\n"):
        if line.lower().startswith(b"proxy-authorization:"):
            value = line.split(b":", 1)[1].strip()
            if value.lower().startswith(b"basic "):
                encoded = value[6:]
                try:
                    decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
                    slug, _, api_key = decoded.partition(":")
                    return slug, api_key
                except Exception:
                    return None
    return None


async def _relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Relay bytes from reader to writer until EOF."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle an incoming HTTP proxy connection."""
    peername = writer.get_extra_info("peername")
    try:
        # Read request line
        request_line = await asyncio.wait_for(reader.readline(), timeout=30)
        if not request_line:
            return

        # Read all headers
        headers_raw = b""
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=30)
            if not line or line == b"\r\n":
                break
            headers_raw += line

        # Authenticate
        creds = await _parse_proxy_auth(headers_raw)
        if creds is None:
            writer.write(b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                         b"Proxy-Authenticate: Basic realm=\"ProxyManager\"\r\n"
                         b"Content-Length: 0\r\n\r\n")
            await writer.drain()
            return

        slug, api_key = creds
        auth_result = await _authenticate(slug, api_key)
        if auth_result is None:
            writer.write(b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                         b"Proxy-Authenticate: Basic realm=\"ProxyManager\"\r\n"
                         b"Content-Length: 0\r\n\r\n")
            await writer.drain()
            return

        project_id, pool_id, strategy = auth_result

        # Get upstream proxy
        redis = await get_redis()
        engine = RotationEngine(redis)
        try:
            upstream = await engine.get_next_proxy(pool_id, strategy)
        except PoolExhaustedError:
            writer.write(b"HTTP/1.1 503 Service Unavailable\r\n"
                         b"Content-Length: 0\r\n\r\n")
            await writer.drain()
            return

        parts = request_line.decode("utf-8", errors="replace").strip().split()
        if len(parts) < 3:
            return
        method = parts[0].upper()
        proxy_id = upstream.get("id", "")

        if method == "CONNECT":
            target = parts[1]
            domain = target.split(":")[0]
            t0 = time.monotonic()
            await _handle_connect(reader, writer, target, upstream)
            elapsed = int((time.monotonic() - t0) * 1000)
            await _request_logger.log_request(
                project_id=project_id, pool_id=pool_id, proxy_id=proxy_id,
                status_code=200, response_time_ms=elapsed,
                bytes_sent=0, bytes_received=0, target_domain=domain,
            )
        else:
            await _handle_http(reader, writer, request_line, headers_raw, upstream, project_id, pool_id)

    except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
        pass
    except Exception:
        log.exception("http_proxy_error", peer=str(peername))
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def _handle_connect(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target: str,
    upstream: dict,
) -> None:
    """Handle HTTPS CONNECT tunneling through upstream proxy."""
    host_port = target.split(":")
    dest_host = host_port[0]
    dest_port = int(host_port[1]) if len(host_port) > 1 else 443

    up_host = upstream["host"]
    up_port = upstream["port"]
    up_proto = upstream["protocol"]
    up_user = upstream.get("username")
    up_pass = upstream.get("password")

    try:
        if up_proto == "socks5":
            from python_socks.async_.asyncio import Proxy
            proxy_url = f"socks5://{up_user}:{up_pass}@{up_host}:{up_port}" if up_user else f"socks5://{up_host}:{up_port}"
            proxy = Proxy.from_url(proxy_url)
            sock = await asyncio.wait_for(proxy.connect(dest_host, dest_port), timeout=settings.health_check_timeout)
            up_reader, up_writer = await asyncio.open_connection(sock=sock)
        else:
            # HTTP/HTTPS upstream: send CONNECT to upstream proxy
            use_ssl = up_proto == "https" or int(up_port) in (443, 8443)
            ssl_ctx = ssl.create_default_context() if use_ssl else None
            up_reader, up_writer = await asyncio.wait_for(
                asyncio.open_connection(up_host, int(up_port), ssl=ssl_ctx), timeout=settings.health_check_timeout
            )
            connect_req = f"CONNECT {dest_host}:{dest_port} HTTP/1.1\r\nHost: {dest_host}:{dest_port}\r\n"
            if up_user:
                cred = base64.b64encode(f"{up_user}:{up_pass}".encode()).decode()
                connect_req += f"Proxy-Authorization: Basic {cred}\r\n"
            connect_req += "\r\n"
            up_writer.write(connect_req.encode())
            await up_writer.drain()

            # Read upstream response
            resp_line = await asyncio.wait_for(up_reader.readline(), timeout=settings.health_check_timeout)
            while True:
                hdr = await up_reader.readline()
                if hdr in (b"\r\n", b"\n", b""):
                    break
            if b"200" not in resp_line:
                log.warning("upstream_connect_failed", upstream=f"{up_host}:{up_port}", response=resp_line.decode(errors="replace").strip())
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                await client_writer.drain()
                up_writer.close()
                return

        # Tunnel established - tell client
        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()

        # Bidirectional relay
        await asyncio.gather(
            _relay(client_reader, up_writer),
            _relay(up_reader, client_writer),
        )
    except Exception as exc:
        log.warning("connect_tunnel_error", upstream=f"{up_host}:{up_port}", error=str(exc))
        try:
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            await client_writer.drain()
        except Exception:
            pass


async def _handle_http(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    request_line: bytes,
    headers_raw: bytes,
    upstream: dict,
    project_id: str = "",
    pool_id: str = "",
) -> None:
    """Handle plain HTTP request forwarding through upstream proxy."""
    up_host = upstream["host"]
    up_port = upstream["port"]
    up_proto = upstream["protocol"]
    up_user = upstream.get("username")
    up_pass = upstream.get("password")
    proxy_id = upstream.get("id", "")

    parts = request_line.decode("utf-8", errors="replace").strip().split()
    if len(parts) < 3:
        return
    method, url, version = parts[0], parts[1], parts[2]
    # Extract domain for logging
    try:
        from urllib.parse import urlparse
        target_domain = urlparse(url).hostname or ""
    except Exception:
        target_domain = ""
    t0 = time.monotonic()

    # Build proxy URL
    if up_proto == "socks5":
        proxy_url = f"socks5://{up_user}:{up_pass}@{up_host}:{up_port}" if up_user else f"socks5://{up_host}:{up_port}"
        connector = ProxyConnector.from_url(proxy_url)
    else:
        use_ssl = up_proto == "https" or int(up_port) in (443, 8443)
        scheme = "https" if use_ssl else "http"
        proxy_url = f"{scheme}://{up_user}:{up_pass}@{up_host}:{up_port}" if up_user else f"{scheme}://{up_host}:{up_port}"
        connector = None

    # Parse forwarded headers (strip proxy-auth)
    forward_headers = {}
    content_length = 0
    for line in headers_raw.split(b"\r\n"):
        if not line:
            continue
        if line.lower().startswith(b"proxy-authorization:"):
            continue
        if b":" in line:
            k, v = line.split(b":", 1)
            key = k.decode("utf-8", errors="replace").strip()
            val = v.decode("utf-8", errors="replace").strip()
            forward_headers[key] = val
            if key.lower() == "content-length":
                content_length = int(val)

    body = None
    if content_length > 0:
        body = await client_reader.readexactly(content_length)

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        ) as session:
            kwargs = {"headers": forward_headers}
            if body:
                kwargs["data"] = body
            if connector is None and up_proto != "socks5":
                kwargs["proxy"] = proxy_url

            async with session.request(method, url, **kwargs) as resp:
                status_line = f"HTTP/1.1 {resp.status} {resp.reason}\r\n"
                client_writer.write(status_line.encode())
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding",):
                        continue
                    client_writer.write(f"{k}: {v}\r\n".encode())

                resp_body = await resp.read()
                client_writer.write(f"Content-Length: {len(resp_body)}\r\n\r\n".encode())
                client_writer.write(resp_body)
                await client_writer.drain()
                elapsed = int((time.monotonic() - t0) * 1000)
                if project_id:
                    await _request_logger.log_request(
                        project_id=project_id, pool_id=pool_id, proxy_id=proxy_id,
                        status_code=resp.status, response_time_ms=elapsed,
                        bytes_sent=len(body) if body else 0,
                        bytes_received=len(resp_body),
                        target_domain=target_domain,
                    )
    except Exception:
        elapsed = int((time.monotonic() - t0) * 1000)
        if project_id:
            await _request_logger.log_request(
                project_id=project_id, pool_id=pool_id, proxy_id=proxy_id,
                status_code=0, response_time_ms=elapsed,
                bytes_sent=0, bytes_received=0,
                target_domain=target_domain, error_type="proxy_error",
            )
        try:
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            await client_writer.drain()
        except Exception:
            pass
