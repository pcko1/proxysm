"""Prometheus metrics for Proxysm.

Exposes a /metrics endpoint when PROMETHEUS_ENABLED=true.
All metrics use the ``proxysm_`` prefix.
"""

import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Registry (custom to avoid polluting default process metrics)
# ---------------------------------------------------------------------------
REGISTRY = CollectorRegistry()

# ---------------------------------------------------------------------------
# App / system info
# ---------------------------------------------------------------------------
APP_INFO = Info(
    "proxysm",
    "Proxysm application metadata",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# HTTP API metrics (FastAPI / Uvicorn)
# ---------------------------------------------------------------------------
HTTP_REQUESTS_TOTAL = Counter(
    "proxysm_http_requests_total",
    "Total HTTP requests to the management API",
    ["method", "path", "status"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION = Histogram(
    "proxysm_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=REGISTRY,
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "proxysm_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Proxy request metrics (traffic through the rotator)
# ---------------------------------------------------------------------------
PROXY_REQUESTS_TOTAL = Counter(
    "proxysm_proxy_requests_total",
    "Total requests forwarded through the proxy rotator",
    ["project_id", "pool_id", "protocol"],
    registry=REGISTRY,
)

PROXY_REQUESTS_SUCCESS = Counter(
    "proxysm_proxy_requests_success_total",
    "Successful proxy requests (status < 400)",
    ["project_id", "pool_id"],
    registry=REGISTRY,
)

PROXY_REQUESTS_FAILED = Counter(
    "proxysm_proxy_requests_failed_total",
    "Failed proxy requests (status >= 400 or connection error)",
    ["project_id", "pool_id", "error_type"],
    registry=REGISTRY,
)

PROXY_REQUEST_DURATION = Histogram(
    "proxysm_proxy_request_duration_seconds",
    "Proxy request round-trip latency in seconds",
    ["project_id", "pool_id"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
    registry=REGISTRY,
)

PROXY_RESPONSE_STATUS = Counter(
    "proxysm_proxy_response_status_total",
    "Proxy response HTTP status codes",
    ["project_id", "status_code"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Bandwidth metrics
# ---------------------------------------------------------------------------
PROXY_BYTES_SENT = Counter(
    "proxysm_proxy_bytes_sent_total",
    "Total bytes sent through proxies",
    ["project_id", "pool_id"],
    registry=REGISTRY,
)

PROXY_BYTES_RECEIVED = Counter(
    "proxysm_proxy_bytes_received_total",
    "Total bytes received through proxies",
    ["project_id", "pool_id"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Proxy health metrics
# ---------------------------------------------------------------------------
PROXIES_TOTAL = Gauge(
    "proxysm_proxies_total",
    "Total number of proxies by health status",
    ["status"],
    registry=REGISTRY,
)

PROXIES_ACTIVE = Gauge(
    "proxysm_proxies_active_total",
    "Total number of active (enabled) proxies",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Health check metrics
# ---------------------------------------------------------------------------
HEALTH_CHECKS_TOTAL = Counter(
    "proxysm_health_checks_total",
    "Total health checks performed",
    ["result"],
    registry=REGISTRY,
)

HEALTH_CHECK_DURATION = Histogram(
    "proxysm_health_check_duration_seconds",
    "Health check latency in seconds",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
    registry=REGISTRY,
)

HEALTH_CHECK_TRANSITIONS = Counter(
    "proxysm_health_check_transitions_total",
    "Health status transitions",
    ["from_status", "to_status"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Pool metrics
# ---------------------------------------------------------------------------
POOL_SIZE = Gauge(
    "proxysm_pool_size",
    "Number of proxies in each pool",
    ["pool_id", "pool_name"],
    registry=REGISTRY,
)

POOL_HEALTHY_PROXIES = Gauge(
    "proxysm_pool_healthy_proxies",
    "Number of healthy proxies in each pool",
    ["pool_id", "pool_name"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Rotation metrics
# ---------------------------------------------------------------------------
ROTATION_TOTAL = Counter(
    "proxysm_rotation_total",
    "Total proxy rotations performed",
    ["pool_id", "strategy"],
    registry=REGISTRY,
)

ROTATION_EXHAUSTED = Counter(
    "proxysm_rotation_pool_exhausted_total",
    "Times a pool had no available proxies",
    ["pool_id"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Rate limiting metrics
# ---------------------------------------------------------------------------
RATE_LIMIT_HITS = Counter(
    "proxysm_rate_limit_hits_total",
    "Number of requests that hit the rate limit",
    ["project_id"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Connection metrics
# ---------------------------------------------------------------------------
PROXY_ACTIVE_CONNECTIONS = Gauge(
    "proxysm_proxy_active_connections",
    "Currently active proxy connections",
    ["protocol"],
    registry=REGISTRY,
)

PROXY_CONNECTIONS_TOTAL = Counter(
    "proxysm_proxy_connections_total",
    "Total proxy connections accepted",
    ["protocol"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Authentication metrics
# ---------------------------------------------------------------------------
AUTH_ATTEMPTS_TOTAL = Counter(
    "proxysm_auth_attempts_total",
    "Total proxy authentication attempts",
    ["result"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Project & pool gauges
# ---------------------------------------------------------------------------
PROJECTS_TOTAL = Gauge(
    "proxysm_projects_total",
    "Total number of projects",
    registry=REGISTRY,
)

POOLS_TOTAL = Gauge(
    "proxysm_pools_total",
    "Total number of pools",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Target domain tracking
# ---------------------------------------------------------------------------
PROXY_REQUESTS_BY_DOMAIN = Counter(
    "proxysm_proxy_requests_by_domain_total",
    "Proxy requests by target domain",
    ["domain"],
    registry=REGISTRY,
)


# ---------------------------------------------------------------------------
# ASGI middleware for HTTP API metrics
# ---------------------------------------------------------------------------
class PrometheusMiddleware:
    """ASGI middleware that records request count, duration, and in-progress gauge."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Don't instrument the /metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")

        # Normalize path to avoid high-cardinality labels
        normalized = _normalize_path(path)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()
        start = time.monotonic()
        status_code = "500"

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = str(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            HTTP_REQUESTS_TOTAL.labels(method=method, path=normalized, status=status_code).inc()
            HTTP_REQUEST_DURATION.labels(method=method, path=normalized).observe(duration)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()


def _normalize_path(path: str) -> str:
    """Collapse UUID and numeric path segments to reduce cardinality."""
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        # UUID pattern
        if len(part) == 36 and part.count("-") == 4:
            normalized.append("{id}")
        # Pure numeric
        elif part.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


# ---------------------------------------------------------------------------
# /metrics endpoint handler
# ---------------------------------------------------------------------------
async def metrics_endpoint(request: Request) -> Response:
    """Serve Prometheus metrics in text exposition format."""
    body = generate_latest(REGISTRY)
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
