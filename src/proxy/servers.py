import asyncio

import structlog

from src.config import settings

log = structlog.get_logger()

_http_server: asyncio.AbstractServer | None = None
_socks5_server: asyncio.AbstractServer | None = None


async def start_proxy_servers() -> None:
    global _http_server, _socks5_server
    from src.proxy.http_proxy import handle_client
    from src.proxy.socks5_proxy import handle_socks5_client

    _http_server = await asyncio.start_server(
        handle_client, "0.0.0.0", settings.proxy_http_port
    )
    log.info("http_proxy_started", port=settings.proxy_http_port)

    _socks5_server = await asyncio.start_server(
        handle_socks5_client, "0.0.0.0", settings.proxy_socks5_port
    )
    log.info("socks5_proxy_started", port=settings.proxy_socks5_port)


async def stop_proxy_servers() -> None:
    global _http_server, _socks5_server
    if _http_server is not None:
        _http_server.close()
        await _http_server.wait_closed()
        log.info("http_proxy_stopped")
        _http_server = None
    if _socks5_server is not None:
        _socks5_server.close()
        await _socks5_server.wait_closed()
        log.info("socks5_proxy_stopped")
        _socks5_server = None
