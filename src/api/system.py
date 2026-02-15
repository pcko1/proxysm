from fastapi import APIRouter, Depends

from src.api.deps import admin_auth
from src.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/system/info")
async def system_info(_: None = Depends(admin_auth)):
    """Return current system configuration values."""
    return {
        "version": "0.1.0",
        "health_check_interval": settings.health_check_interval,
        "health_check_timeout": settings.health_check_timeout,
        "health_check_concurrency": settings.health_check_concurrency,
        "health_check_url": settings.health_check_url,
        "proxy_http_port": settings.proxy_http_port,
        "proxy_socks5_port": settings.proxy_socks5_port,
        "request_log_retention_days": settings.request_log_retention_days,
        "metrics_5min_retention_days": settings.metrics_5min_retention_days,
        "metrics_1hour_retention_days": settings.metrics_1hour_retention_days,
        "metrics_rollup_interval": settings.metrics_rollup_interval,
        "bandwidth_flush_interval": settings.bandwidth_flush_interval,
        "blacklist_eval_interval": settings.blacklist_eval_interval,
        "blacklist_cooldown_check_interval": settings.blacklist_cooldown_check_interval,
        "rate_limit_window_seconds": settings.rate_limit_window_seconds,
    }
