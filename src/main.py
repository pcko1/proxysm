import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.redis import close_redis, get_redis

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()

app = FastAPI(
    title="Proxysm",
    version="0.1.0",
    description="Self-hosted proxy management platform",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Prometheus metrics (conditional on config flag)
if settings.prometheus_enabled:
    from src.prometheus import APP_INFO, PrometheusMiddleware, metrics_endpoint

    APP_INFO.info({"version": "0.1.0", "app": "proxysm"})
    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])
    log.info("prometheus_enabled", endpoint="/metrics")


@app.on_event("startup")
async def startup() -> None:
    log.info("starting_proxysm", version="0.1.0")
    await get_redis()

    # Import and start background health checker
    from src.health.checker import start_health_checker

    await start_health_checker()

    # Import and start proxy servers
    from src.proxy.servers import start_proxy_servers

    await start_proxy_servers()


@app.on_event("shutdown")
async def shutdown() -> None:
    log.info("shutting_down_proxysm")

    from src.proxy.servers import stop_proxy_servers

    await stop_proxy_servers()

    from src.health.checker import stop_health_checker

    await stop_health_checker()

    await close_redis()


# Register API routers
from src.api.proxies import router as proxies_router  # noqa: E402
from src.api.pools import router as pools_router  # noqa: E402
from src.api.projects import router as projects_router  # noqa: E402
from src.api.rotation import router as rotation_router  # noqa: E402
from src.api.system import router as system_router  # noqa: E402
from src.api.stats import router as stats_router  # noqa: E402
from src.api.stats import ips_stats_router, pools_stats_router, projects_stats_router  # noqa: E402
from src.api.sources import router as sources_router  # noqa: E402
from src.api.alerts import router as alerts_router  # noqa: E402

app.include_router(proxies_router, prefix="/api/v1")
app.include_router(pools_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(rotation_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(ips_stats_router, prefix="/api/v1")
app.include_router(pools_stats_router, prefix="/api/v1")
app.include_router(projects_stats_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")

# Register web UI routes
from src.web.routes import router as web_router  # noqa: E402

app.include_router(web_router)

# Register custom 404 handler
from src.web.routes import not_found_handler  # noqa: E402

app.add_exception_handler(404, not_found_handler)
