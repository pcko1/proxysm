import asyncio
import hashlib
import struct
import time

import aiohttp
import structlog
from aiohttp_socks import ProxyConnector

from src.config import settings
from src.database import async_session_factory
from src.models.associations import ProjectPool
from src.models.pool import Pool
from src.models.project import Project
from src.redis import get_redis
from src.rotation.engine import PoolExhaustedError, RotationEngine
from sqlalchemy import select

_prom = None

def _get_prom():
    global _prom
    if _prom is None and settings.prometheus_enabled:
        import src.prometheus as p
        _prom = p
    return _prom

log = structlog.get_logger()

# Auth cache: key -> (api_key_hash, pool_id, pool_strategy, expiry_ts)
_auth_cache: dict[str, tuple[str, str, str, float]] = {}
_AUTH_CACHE_TTL = 30.0

# SOCKS5 constants
SOCKS_VERSION = 0x05
AUTH_NONE = 0x00
AUTH_USERPASS = 0x02
AUTH_NO_ACCEPTABLE = 0xFF
CMD_CONNECT = 0x01
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03
ATYP_IPV6 = 0x04
REP_SUCCESS = 0x00
REP_GENERAL_FAILURE = 0x01
REP_NOT_ALLOWED = 0x02
REP_COMMAND_NOT_SUPPORTED = 0x07


async def _authenticate(slug: str, api_key: str) -> tuple[str, str] | None:
    """Authenticate project credentials. Returns (pool_id, rotation_strategy) or None."""
    cache_key = f"{slug}:{api_key}"
    now = time.monotonic()
    cached = _auth_cache.get(cache_key)
    if cached is not None:
        stored_hash, pool_id, strategy, expiry = cached
        if now < expiry:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            if key_hash == stored_hash:
                return pool_id, strategy
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

        pool_id = str(pool.id)
        strategy = pool.rotation_strategy
        _auth_cache[cache_key] = (key_hash, pool_id, strategy, now + _AUTH_CACHE_TTL)
        return pool_id, strategy


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


def _build_socks5_reply(rep: int, bind_addr: bytes = b"\x00\x00\x00\x00", bind_port: int = 0) -> bytes:
    """Build a SOCKS5 reply packet."""
    return struct.pack("!BBBB", SOCKS_VERSION, rep, 0x00, ATYP_IPV4) + bind_addr + struct.pack("!H", bind_port)


async def handle_socks5_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle an incoming SOCKS5 proxy connection (RFC 1928 / 1929)."""
    peername = writer.get_extra_info("peername")
    prom = _get_prom()
    if prom:
        prom.PROXY_CONNECTIONS_TOTAL.labels(protocol="socks5").inc()
        prom.PROXY_ACTIVE_CONNECTIONS.labels(protocol="socks5").inc()
    try:
        # 1. Greeting: version + number of auth methods + methods
        greeting = await asyncio.wait_for(reader.readexactly(2), timeout=30)
        version, nmethods = struct.unpack("!BB", greeting)
        if version != SOCKS_VERSION:
            return
        methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=30)

        # 2. We require username/password auth
        if AUTH_USERPASS not in methods:
            writer.write(struct.pack("!BB", SOCKS_VERSION, AUTH_NO_ACCEPTABLE))
            await writer.drain()
            return
        writer.write(struct.pack("!BB", SOCKS_VERSION, AUTH_USERPASS))
        await writer.drain()

        # 3. Username/password auth (RFC 1929)
        auth_version = await asyncio.wait_for(reader.readexactly(1), timeout=30)
        if auth_version != b"\x01":
            return
        ulen_bytes = await reader.readexactly(1)
        ulen = ulen_bytes[0]
        username = (await reader.readexactly(ulen)).decode("utf-8", errors="replace")
        plen_bytes = await reader.readexactly(1)
        plen = plen_bytes[0]
        password = (await reader.readexactly(plen)).decode("utf-8", errors="replace")

        # Map username -> slug, password -> api_key
        auth_result = await _authenticate(username, password)
        if auth_result is None:
            if prom:
                prom.AUTH_ATTEMPTS_TOTAL.labels(result="failure").inc()
            # Auth failure
            writer.write(b"\x01\x01")  # version 1, status failure
            await writer.drain()
            return
        if prom:
            prom.AUTH_ATTEMPTS_TOTAL.labels(result="success").inc()
        writer.write(b"\x01\x00")  # version 1, status success
        await writer.drain()
        pool_id, strategy = auth_result

        # 4. Request
        req_header = await asyncio.wait_for(reader.readexactly(4), timeout=30)
        ver, cmd, rsv, atyp = struct.unpack("!BBBB", req_header)
        if ver != SOCKS_VERSION or cmd != CMD_CONNECT:
            writer.write(_build_socks5_reply(REP_COMMAND_NOT_SUPPORTED))
            await writer.drain()
            return

        # Parse destination address
        if atyp == ATYP_IPV4:
            raw_addr = await reader.readexactly(4)
            dest_host = ".".join(str(b) for b in raw_addr)
        elif atyp == ATYP_DOMAIN:
            domain_len = (await reader.readexactly(1))[0]
            dest_host = (await reader.readexactly(domain_len)).decode("utf-8", errors="replace")
        elif atyp == ATYP_IPV6:
            raw_addr = await reader.readexactly(16)
            dest_host = ":".join(f"{raw_addr[i]:02x}{raw_addr[i+1]:02x}" for i in range(0, 16, 2))
        else:
            writer.write(_build_socks5_reply(REP_GENERAL_FAILURE))
            await writer.drain()
            return

        dest_port = struct.unpack("!H", await reader.readexactly(2))[0]

        # 5. Get upstream proxy from rotation engine
        redis = await get_redis()
        engine = RotationEngine(redis)
        try:
            upstream = await engine.get_next_proxy(pool_id, strategy)
            if prom:
                prom.ROTATION_TOTAL.labels(pool_id=pool_id, strategy=strategy).inc()
        except PoolExhaustedError:
            if prom:
                prom.ROTATION_EXHAUSTED.labels(pool_id=pool_id).inc()
            writer.write(_build_socks5_reply(REP_GENERAL_FAILURE))
            await writer.drain()
            return

        # 6. Connect to destination through upstream
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
                sock = await asyncio.wait_for(
                    proxy.connect(dest_host, dest_port),
                    timeout=settings.health_check_timeout,
                )
                up_reader, up_writer = await asyncio.open_connection(sock=sock)
            else:
                # HTTP upstream: use CONNECT method
                up_reader, up_writer = await asyncio.wait_for(
                    asyncio.open_connection(up_host, up_port),
                    timeout=settings.health_check_timeout,
                )
                import base64
                connect_req = f"CONNECT {dest_host}:{dest_port} HTTP/1.1\r\nHost: {dest_host}:{dest_port}\r\n"
                if up_user:
                    cred = base64.b64encode(f"{up_user}:{up_pass}".encode()).decode()
                    connect_req += f"Proxy-Authorization: Basic {cred}\r\n"
                connect_req += "\r\n"
                up_writer.write(connect_req.encode())
                await up_writer.drain()

                resp_line = await asyncio.wait_for(up_reader.readline(), timeout=settings.health_check_timeout)
                while True:
                    hdr = await up_reader.readline()
                    if hdr in (b"\r\n", b"\n", b""):
                        break
                if b"200" not in resp_line:
                    writer.write(_build_socks5_reply(REP_GENERAL_FAILURE))
                    await writer.drain()
                    up_writer.close()
                    return
        except Exception:
            writer.write(_build_socks5_reply(REP_GENERAL_FAILURE))
            await writer.drain()
            return

        # 7. Success reply
        writer.write(_build_socks5_reply(REP_SUCCESS))
        await writer.drain()

        if prom:
            prom.PROXY_REQUESTS_TOTAL.labels(project_id="", pool_id=pool_id, protocol="socks5").inc()
            prom.PROXY_REQUESTS_SUCCESS.labels(project_id="", pool_id=pool_id).inc()

        # 8. Bidirectional relay
        await asyncio.gather(
            _relay(reader, up_writer),
            _relay(up_reader, writer),
        )

    except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
        pass
    except Exception:
        log.exception("socks5_proxy_error", peer=str(peername))
    finally:
        if prom:
            prom.PROXY_ACTIVE_CONNECTIONS.labels(protocol="socks5").dec()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
