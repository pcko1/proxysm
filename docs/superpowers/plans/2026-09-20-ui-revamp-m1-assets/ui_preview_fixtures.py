"""Canned API responses for a no-database Proxysm UI preview server.

Every shape below was copied from the real handlers in ``src/api/*.py`` and the
Pydantic response models in ``src/schemas/*.py``; the comment above each entry
cites the file and lines it mirrors.

Serialisation rules that the real API follows and these fixtures reproduce:

* Pydantic response models emit tz-aware datetimes with a ``Z`` suffix
  (``2026-09-20T11:58:03.412907Z``). Raw-dict handlers call ``.isoformat()``
  instead, which yields ``+00:00`` (stats ``period`` keys, source poll result).
* ``None`` fields are always present as ``null`` (no ``exclude_none`` anywhere).
* Paginated lists use the envelope ``{"data": [...], "meta": {"total", "page",
  "per_page"}}``. ``meta.per_page`` echoes the request's query parameter.

Keys of ``FIXTURES`` are ``(METHOD, path_pattern)`` where ``path_pattern`` is the
path after ``/api/v1/`` with ``{id}`` placeholders. ``None`` means 204 No Content.
"""

# ---------------------------------------------------------------------------
# Fixed identifiers
# ---------------------------------------------------------------------------

SOURCE_WEBSHARE_ID = "5a1c0000-0000-4000-8000-000000000001"
SOURCE_PROXYSCRAPE_ID = "5a1c0000-0000-4000-8000-000000000002"
SOURCE_THESPEEDX_ID = "5a1c0000-0000-4000-8000-000000000003"
SOURCE_MANUAL_ID = "5a1c0000-0000-4000-8000-000000000004"

POOL_DATACENTER_US_ID = "b0010000-0000-4000-8000-000000000001"
POOL_PUBLIC_MIX_ID = "b0010000-0000-4000-8000-000000000002"
POOL_RESIDENTIAL_EU_ID = "b0010000-0000-4000-8000-000000000003"

PROJECT_SCRAPER_PROD_ID = "c0de0000-0000-4000-8000-000000000001"
PROJECT_PRICE_MONITOR_ID = "c0de0000-0000-4000-8000-000000000002"
PROJECT_SEO_AUDIT_ID = "c0de0000-0000-4000-8000-000000000003"

ALERT_ERROR_RATE_ID = "a1e70000-0000-4000-8000-000000000001"
ALERT_POOL_LOW_ID = "a1e70000-0000-4000-8000-000000000002"


def _proxy_id(n: int) -> str:
    return f"1b000000-0000-4000-8000-{n:012d}"


# ---------------------------------------------------------------------------
# Sample data: proxies (ProxyResponse, src/schemas/proxy.py:21-32)
# Newest first, matching the default ORDER BY created_at DESC
# (src/api/proxies.py:84). Note the field is `last_health_status`, not `status`,
# and there is no username/password/country/pool information on a proxy.
# ---------------------------------------------------------------------------

PROXIES: list[dict] = [
    {
        "id": _proxy_id(12),
        "source_id": SOURCE_MANUAL_ID,
        "host": "198.51.100.77",
        "port": 1080,
        "protocol": "socks5",
        "provider": "manual",
        "is_active": False,
        "last_health_status": "unknown",
        "last_health_check": None,
        "avg_latency_ms": None,
        "created_at": "2026-09-14T08:12:45.731204Z",
    },
    {
        "id": _proxy_id(11),
        "source_id": SOURCE_MANUAL_ID,
        "host": "203.0.113.50",
        "port": 3128,
        "protocol": "https",
        "provider": "manual",
        "is_active": True,
        "last_health_status": "healthy",
        "last_health_check": "2026-09-20T11:59:12.004518Z",
        "avg_latency_ms": 58.7,
        "created_at": "2026-09-14T08:12:45.731204Z",
    },
    {
        "id": _proxy_id(10),
        "source_id": SOURCE_THESPEEDX_ID,
        "host": "192.0.2.33",
        "port": 4145,
        "protocol": "socks5",
        "provider": "thespeedx",
        "is_active": True,
        "last_health_status": "unknown",
        "last_health_check": None,
        "avg_latency_ms": None,
        "created_at": "2026-09-12T16:40:02.118377Z",
    },
    {
        "id": _proxy_id(9),
        "source_id": SOURCE_THESPEEDX_ID,
        "host": "192.0.2.32",
        "port": 1080,
        "protocol": "socks5",
        "provider": "thespeedx",
        "is_active": True,
        "last_health_status": "dead",
        "last_health_check": "2026-09-20T11:52:40.660291Z",
        "avg_latency_ms": None,
        "created_at": "2026-09-12T16:40:02.118377Z",
    },
    {
        "id": _proxy_id(8),
        "source_id": SOURCE_THESPEEDX_ID,
        "host": "192.0.2.31",
        "port": 1080,
        "protocol": "socks5",
        "provider": "thespeedx",
        "is_active": True,
        "last_health_status": "healthy",
        "last_health_check": "2026-09-20T11:59:10.482116Z",
        "avg_latency_ms": 318.6,
        "created_at": "2026-09-12T16:40:02.118377Z",
    },
    {
        "id": _proxy_id(7),
        "source_id": SOURCE_PROXYSCRAPE_ID,
        "host": "198.51.100.23",
        "port": 80,
        "protocol": "http",
        "provider": "proxyscrape",
        "is_active": True,
        "last_health_status": "dead",
        "last_health_check": "2026-09-20T11:50:18.907733Z",
        "avg_latency_ms": 905.1,
        "created_at": "2026-09-10T09:05:31.442019Z",
    },
    {
        "id": _proxy_id(6),
        "source_id": SOURCE_PROXYSCRAPE_ID,
        "host": "198.51.100.22",
        "port": 8888,
        "protocol": "http",
        "provider": "proxyscrape",
        "is_active": True,
        "last_health_status": "degraded",
        "last_health_check": "2026-09-20T11:59:09.215640Z",
        "avg_latency_ms": 1480.9,
        "created_at": "2026-09-10T09:05:31.442019Z",
    },
    {
        "id": _proxy_id(5),
        "source_id": SOURCE_PROXYSCRAPE_ID,
        "host": "198.51.100.21",
        "port": 3128,
        "protocol": "http",
        "provider": "proxyscrape",
        "is_active": True,
        "last_health_status": "healthy",
        "last_health_check": "2026-09-20T11:59:08.730952Z",
        "avg_latency_ms": 231.4,
        "created_at": "2026-09-10T09:05:31.442019Z",
    },
    {
        "id": _proxy_id(4),
        "source_id": SOURCE_WEBSHARE_ID,
        "host": "203.0.113.13",
        "port": 8080,
        "protocol": "http",
        "provider": "webshare",
        "is_active": True,
        "last_health_status": "degraded",
        "last_health_check": "2026-09-20T11:59:07.301478Z",
        "avg_latency_ms": 640.3,
        "created_at": "2026-09-08T14:22:10.905612Z",
    },
    {
        "id": _proxy_id(3),
        "source_id": SOURCE_WEBSHARE_ID,
        "host": "203.0.113.12",
        "port": 8080,
        "protocol": "http",
        "provider": "webshare",
        "is_active": True,
        "last_health_status": "healthy",
        "last_health_check": "2026-09-20T11:59:06.874209Z",
        "avg_latency_ms": 112.8,
        "created_at": "2026-09-08T14:22:10.905612Z",
    },
    {
        "id": _proxy_id(2),
        "source_id": SOURCE_WEBSHARE_ID,
        "host": "203.0.113.11",
        "port": 8080,
        "protocol": "http",
        "provider": "webshare",
        "is_active": True,
        "last_health_status": "healthy",
        "last_health_check": "2026-09-20T11:59:06.412055Z",
        "avg_latency_ms": 97.5,
        "created_at": "2026-09-08T14:22:10.905612Z",
    },
    {
        "id": _proxy_id(1),
        "source_id": SOURCE_WEBSHARE_ID,
        "host": "203.0.113.10",
        "port": 8080,
        "protocol": "http",
        "provider": "webshare",
        "is_active": True,
        "last_health_status": "healthy",
        "last_health_check": "2026-09-20T11:59:05.998341Z",
        "avg_latency_ms": 84.2,
        "created_at": "2026-09-08T14:22:10.905612Z",
    },
]

PROXIES_BY_ID: dict[str, dict] = {p["id"]: p for p in PROXIES}

# Pool membership is NOT part of any response body; the real API only exposes it
# through the `GET /ips?pool_id=<uuid>` filter (src/api/proxies.py:55-61). The
# preview server can use this map to honour that filter.
POOL_MEMBERS: dict[str, list[str]] = {
    POOL_DATACENTER_US_ID: [_proxy_id(n) for n in (1, 2, 3, 4)],
    POOL_PUBLIC_MIX_ID: [_proxy_id(n) for n in (5, 6, 7, 8, 9, 10)],
    POOL_RESIDENTIAL_EU_ID: [_proxy_id(n) for n in (11, 12)],
}

# ---------------------------------------------------------------------------
# Sample data: pools (PoolResponse, src/schemas/pool.py:24-30)
# Fields are `proxy_count` / `healthy_count`. Allowed rotation_strategy values:
# round_robin | random | weighted_random (src/schemas/pool.py:11).
# ---------------------------------------------------------------------------

POOLS: list[dict] = [
    {
        "id": POOL_RESIDENTIAL_EU_ID,
        "name": "residential-eu",
        "rotation_strategy": "weighted_random",
        "proxy_count": 2,
        "healthy_count": 1,
        "created_at": "2026-09-14T08:20:11.260845Z",
    },
    {
        "id": POOL_PUBLIC_MIX_ID,
        "name": "public-mix",
        "rotation_strategy": "random",
        "proxy_count": 6,
        "healthy_count": 2,
        "created_at": "2026-09-10T09:11:47.013390Z",
    },
    {
        "id": POOL_DATACENTER_US_ID,
        "name": "datacenter-us",
        "rotation_strategy": "round_robin",
        "proxy_count": 4,
        "healthy_count": 3,
        "created_at": "2026-09-08T14:30:55.672101Z",
    },
]

POOLS_BY_ID: dict[str, dict] = {p["id"]: p for p in POOLS}


def _nested_pool(pool_id: str) -> dict:
    """Pool as embedded in a project: the counts are NOT populated there.

    src/api/projects.py:40 and :228 call PoolResponse.model_validate(pool) without
    setting proxy_count/healthy_count, so both serialise as null.
    """
    return {**POOLS_BY_ID[pool_id], "proxy_count": None, "healthy_count": None}


# ---------------------------------------------------------------------------
# Sample data: projects (ProjectResponse, src/schemas/project.py:17-23)
# `api_key` is returned in plain text on every read (src/api/projects.py:39).
# Real keys are secrets.token_urlsafe(32): 43 URL-safe characters.
# ---------------------------------------------------------------------------

PROJECTS: list[dict] = [
    {
        "id": PROJECT_SEO_AUDIT_ID,
        "name": "seo-audit",
        "slug": "seo-audit",
        "api_key": "PREVIEW-seo-audit-key-not-a-real-secret-003",
        "pools": [],
        "created_at": "2026-09-15T10:02:33.587412Z",
    },
    {
        "id": PROJECT_PRICE_MONITOR_ID,
        "name": "price-monitor",
        "slug": "price-monitor",
        "api_key": "PREVIEW-price-monitor-not-a-real-secret-002",
        "pools": [_nested_pool(POOL_RESIDENTIAL_EU_ID)],
        "created_at": "2026-09-11T13:45:09.224876Z",
    },
    {
        "id": PROJECT_SCRAPER_PROD_ID,
        "name": "scraper-prod",
        "slug": "scraper-prod",
        "api_key": "PREVIEW-scraper-prod-not-a-real-secret-0001",
        "pools": [_nested_pool(POOL_DATACENTER_US_ID), _nested_pool(POOL_PUBLIC_MIX_ID)],
        "created_at": "2026-09-08T14:35:20.118093Z",
    },
]

PROJECTS_BY_ID: dict[str, dict] = {p["id"]: p for p in PROJECTS}

# ---------------------------------------------------------------------------
# Sample data: sources (SourceResponse, src/schemas/source.py:24-36)
# `type` is url | file | manual. There are four rows, not three, because every
# proxy needs a source_id: POST /ips and POST /ips/bulk auto-create a source
# named "manual-<YYYY-MM-DD-HH:MM:SS>" (src/api/proxies.py:20-23, 99-105).
# ---------------------------------------------------------------------------

SOURCES: list[dict] = [
    {
        "id": SOURCE_MANUAL_ID,
        "name": "manual-2026-09-14-08:12:45",
        "type": "manual",
        "url": None,
        "provider": "manual",
        "protocol": "http",
        "is_active": True,
        "last_polled_at": None,
        "last_status_code": None,
        "consecutive_failures": 0,
        "proxy_count": 2,
        "created_at": "2026-09-14T08:12:45.702118Z",
    },
    {
        "id": SOURCE_THESPEEDX_ID,
        "name": "thespeedx-socks5",
        "type": "url",
        "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "provider": "thespeedx",
        "protocol": "socks5",
        "is_active": True,
        "last_polled_at": "2026-09-20T11:40:02.551930Z",
        "last_status_code": 503,
        "consecutive_failures": 2,
        "proxy_count": 3,
        "created_at": "2026-09-12T16:39:58.004271Z",
    },
    {
        "id": SOURCE_PROXYSCRAPE_ID,
        "name": "proxyscrape-http",
        "type": "url",
        "url": (
            "https://api.proxyscrape.com/v4/free-proxy-list/get"
            "?request=display_proxies&protocol=http&proxy_format=ipport&format=text"
        ),
        "provider": "proxyscrape",
        "protocol": "http",
        "is_active": True,
        "last_polled_at": "2026-09-20T11:40:01.873004Z",
        "last_status_code": 200,
        "consecutive_failures": 0,
        "proxy_count": 3,
        "created_at": "2026-09-10T09:05:27.330915Z",
    },
    {
        "id": SOURCE_WEBSHARE_ID,
        "name": "webshare-datacenter",
        "type": "url",
        "url": "https://proxy.webshare.io/api/v2/proxy/list/download/EXAMPLE/-/any/sourceip/direct/-/",
        "provider": "webshare",
        "protocol": "http",
        "is_active": True,
        "last_polled_at": "2026-09-20T11:40:01.102266Z",
        "last_status_code": 200,
        "consecutive_failures": 0,
        "proxy_count": 4,
        "created_at": "2026-09-08T14:22:06.481750Z",
    },
]

SOURCES_BY_ID: dict[str, dict] = {s["id"]: s for s in SOURCES}

# ---------------------------------------------------------------------------
# Sample data: alert rules (AlertResponse, src/schemas/alert.py:25-35)
# condition_type: error_rate_above | pool_below_min_healthy | bandwidth_exceeded
# | all_proxies_dead; action_type: webhook (src/models/alert.py:13-21).
# condition_config keys are read in src/services/alerts.py:97-151:
#   error_rate_above       -> {"threshold": 0..1 fraction, "window_seconds": int}
#   pool_below_min_healthy -> {"pool_id": uuid str, "min_healthy": int}
#   bandwidth_exceeded     -> {"limit_bytes": int}
#   all_proxies_dead       -> {}
# action_config for webhook -> {"url": str} (src/services/alerts.py:187).
# ---------------------------------------------------------------------------

ALERTS: list[dict] = [
    {
        "id": ALERT_POOL_LOW_ID,
        "name": "datacenter-us running low",
        "condition_type": "pool_below_min_healthy",
        "condition_config": {"pool_id": POOL_DATACENTER_US_ID, "min_healthy": 3},
        "action_type": "webhook",
        "action_config": {"url": "https://hooks.example.com/proxysm/pool-low"},
        "is_enabled": False,
        "last_triggered_at": None,
        "created_at": "2026-09-16T09:14:27.640031Z",
        "updated_at": "2026-09-18T17:03:52.218754Z",
    },
    {
        "id": ALERT_ERROR_RATE_ID,
        "name": "High error rate",
        "condition_type": "error_rate_above",
        "condition_config": {"threshold": 0.25, "window_seconds": 300},
        "action_type": "webhook",
        "action_config": {"url": "https://hooks.example.com/proxysm/error-rate"},
        "is_enabled": True,
        "last_triggered_at": "2026-09-19T04:21:08.377215Z",
        "created_at": "2026-09-09T11:30:44.905128Z",
        "updated_at": "2026-09-19T04:21:08.377215Z",
    },
]

ALERTS_BY_ID: dict[str, dict] = {a["id"]: a for a in ALERTS}

# ---------------------------------------------------------------------------
# Sample data: hourly series for the 24 h ending 2026-09-20T12:00Z.
# Totals are mutually consistent: sum(_HOURLY_TOTAL) == 48210 and
# sum(_HOURLY_FAILED) == 3083, matching stats/overview, stats/status-codes,
# stats/error-breakdown, stats/pool-metrics and stats/proxy-distribution.
# ---------------------------------------------------------------------------

_HOURS: list[str] = [f"2026-09-19T{h:02d}:00:00" for h in range(12, 24)] + [
    f"2026-09-20T{h:02d}:00:00" for h in range(12)
]
_HOURLY_TOTAL = [
    2830, 3000, 3140, 3075, 2885, 2625, 2360, 2115, 1870, 1625, 1400, 1230,
    1090, 1005, 950, 930, 965, 1110, 1420, 1835, 2295, 2650, 2870, 2935,
]  # fmt: skip
_HOURLY_FAILED = [
    168, 187, 211, 222, 203, 172, 146, 125, 106, 87, 73, 62,
    54, 49, 50, 54, 83, 105, 114, 131, 154, 170, 178, 179,
]  # fmt: skip
_HOURLY_AVG_MS = [
    406.66, 424.08, 446.69, 449.86, 454.33, 435.17, 415.01, 416.88, 421.35, 403.78, 392.4, 396.87,
    384.48, 391.54, 408.97, 398.88, 481.11, 514.08, 468.01, 456.92, 440.35, 422.79, 427.25, 434.31,
]  # fmt: skip
_HOURLY_P50 = [
    282.4, 292.3, 305.8, 305.8, 306.7, 302.2, 286.0, 285.1, 286.0, 271.6, 272.5, 273.4,
    262.6, 265.3, 275.2, 277.0, 331.9, 352.6, 318.4, 308.5, 305.8, 291.4, 292.3, 295.0,
]  # fmt: skip
_HOURLY_P95 = [
    1152.0, 1215.5, 1307.0, 1398.5, 1306.0, 1257.5, 1223.0, 1202.5, 1110.0, 1089.5, 1083.0, 1076.5,
    998.0, 1005.5, 1069.0, 1174.5, 1502.0, 1649.5, 1475.0, 1384.5, 1264.0, 1243.5, 1237.0, 1244.5,
]  # fmt: skip
_HOURLY_SAMPLES = [
    2773, 2936, 3068, 3000, 2816, 2567, 2310, 2073, 1834, 1595, 1375, 1209,
    1072, 988, 933, 912, 937, 1074, 1381, 1790, 2243, 2592, 2809, 2874,
]  # fmt: skip
_HOURLY_BYTES_SENT = [
    3608250, 3825037, 4003574, 3920736, 3678523, 3347060, 3009222, 2696884,
    2384546, 2072208, 1785370, 1568657, 1390194, 1281856, 1211768, 1186305,
    1230967, 1415879, 1811166, 2340328, 2926865, 3379527, 3660064, 3742976,
]  # fmt: skip
_HOURLY_BYTES_RECEIVED = [
    171019730, 181300919, 189769178, 185849082, 174375111, 158670970, 142664674, 127816977,
    113019301, 98221625, 84632569, 74367218, 65914797, 60736060, 57420274, 56219573,
    58342577, 67112991, 85854520, 110891283, 138697462, 160158386, 173461125, 177397059,
]  # fmt: skip


def _ts_point(period_start: str, total: int, failed: int, avg_ms: float | None) -> dict:
    # TimeseriesPoint, src/schemas/stats.py:39-44 (Pydantic datetime -> "Z" suffix)
    return {
        "period_start": period_start,
        "total_requests": total,
        "successful_requests": total - failed,
        "failed_requests": failed,
        "avg_response_time_ms": avg_ms,
    }


# GET stats/timeseries, src/api/stats.py:573-617; TimeseriesResponse
# src/schemas/stats.py:49-51. Query params: entity_type (str, optional),
# entity_id (uuid, optional), granularity ("5min" | "1hour" | "1day", default
# "1hour", anything else -> 400), hours (1..168, default 24). The UI pairs them
# as 5min/1h, 1hour/24h, 1day/168h (src/web/templates/dashboard.html:559-563).
# Hours with no traffic are simply absent; the API does not zero-fill gaps.
TIMESERIES_BY_GRANULARITY: dict[str, dict] = {
    "5min": {
        "granularity": "5min",
        "data": [
            _ts_point(f"2026-09-20T11:{m:02d}:00Z", total, failed, avg)
            for m, total, failed, avg in [
                (0, 238, 14, 431.18),
                (5, 251, 16, 437.92),
                (10, 246, 15, 428.4),
                (15, 259, 17, 442.07),
                (20, 240, 14, 430.55),
                (25, 233, 13, 426.31),
                (30, 247, 15, 433.86),
                (35, 252, 16, 439.2),
                (40, 244, 15, 434.77),
                (45, 249, 15, 432.09),
                (50, 241, 15, 436.5),
                (55, 235, 14, 438.83),
            ]
        ],
    },
    "1hour": {
        "granularity": "1hour",
        "data": [
            _ts_point(f"{hour}Z", total, failed, avg)
            for hour, total, failed, avg in zip(
                _HOURS, _HOURLY_TOTAL, _HOURLY_FAILED, _HOURLY_AVG_MS, strict=True
            )
        ],
    },
    "1day": {
        "granularity": "1day",
        "data": [
            _ts_point(f"2026-09-{day:02d}T00:00:00Z", total, failed, avg)
            for day, total, failed, avg in [
                (14, 41280, 2518, 418.2),
                (15, 44910, 2695, 425.71),
                (16, 46350, 2920, 431.06),
                (17, 47820, 3108, 440.9),
                (18, 45140, 2754, 422.35),
                (19, 49870, 3142, 433.48),
                (20, 20055, 1321, 436.12),
            ]
        ],
    },
}

# EntityStats, src/schemas/stats.py:25-34, built by _entity_stats
# (src/api/stats.py:515-570). NOT a 24 h window: it sums every 5min rollup that
# still exists (7-day retention). `error_rate` is a 0-100 percentage, 2 decimals.
ENTITY_STATS_BY_ID: dict[str, dict] = {
    PROJECT_SCRAPER_PROD_ID: {
        "total_requests": 224310,
        "successful_requests": 208934,
        "failed_requests": 15376,
        "error_rate": 6.85,
        "avg_response_time_ms": 431.27,
        "median_response_time_ms": 292.0,
        "p95_response_time_ms": 3120.5,
        "bytes_sent": 286012440,
        "bytes_received": 13552981774,
    },
    PROJECT_PRICE_MONITOR_ID: {
        "total_requests": 86140,
        "successful_requests": 80974,
        "failed_requests": 5166,
        "error_rate": 6.0,
        "avg_response_time_ms": 402.63,
        "median_response_time_ms": 301.25,
        "p95_response_time_ms": 2488.0,
        "bytes_sent": 109828500,
        "bytes_received": 5205526340,
    },
    PROJECT_SEO_AUDIT_ID: {
        "total_requests": 9870,
        "successful_requests": 9661,
        "failed_requests": 209,
        "error_rate": 2.12,
        "avg_response_time_ms": 355.9,
        "median_response_time_ms": 270.5,
        "p95_response_time_ms": 1410.75,
        "bytes_sent": 12584250,
        "bytes_received": 596453970,
    },
}

_EMPTY_ENTITY_STATS: dict = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "error_rate": 0.0,
    "avg_response_time_ms": None,
    "median_response_time_ms": None,
    "p95_response_time_ms": None,
    "bytes_sent": 0,
    "bytes_received": 0,
}

# GET system/info, src/api/system.py:14-32; values are the defaults from
# src/config.py:13-45. Flat dict, no envelope.
_SYSTEM_INFO: dict = {
    "version": "0.1.0",
    "health_check_interval": 60,
    "health_check_timeout": 10,
    "health_check_concurrency": 200,
    "health_check_url": "http://httpbin.org/ip",
    "proxy_http_port": 9080,
    "proxy_socks5_port": 9081,
    "request_log_retention_days": 7,
    "metrics_5min_retention_days": 7,
    "metrics_1hour_retention_days": 90,
    "metrics_rollup_interval": 300,
    "bandwidth_flush_interval": 30,
    "rate_limit_window_seconds": 60,
    "prometheus_enabled": False,
}

# GET health, src/api/system.py:9-11 (unauthenticated).
_HEALTH: dict = {"status": "ok", "version": "0.1.0"}


def _page(items: list[dict], per_page: int = 50) -> dict:
    # PaginatedResponse / PaginationMeta, src/schemas/common.py:8-18
    return {"data": items, "meta": {"total": len(items), "page": 1, "per_page": per_page}}


_NEW_PROXY: dict = {
    "id": _proxy_id(13),
    "source_id": "5a1c0000-0000-4000-8000-000000000005",
    "host": "203.0.113.90",
    "port": 8080,
    "protocol": "http",
    "provider": "manual",
    "is_active": True,
    "last_health_status": "unknown",
    "last_health_check": None,
    "avg_latency_ms": None,
    "created_at": "2026-09-20T12:00:00.153702Z",
}

_NEW_POOL: dict = {
    "id": "b0010000-0000-4000-8000-000000000004",
    "name": "new-pool",
    "rotation_strategy": "round_robin",
    "proxy_count": 0,
    "healthy_count": 0,
    "created_at": "2026-09-20T12:00:00.153702Z",
}

_NEW_PROJECT: dict = {
    "id": "c0de0000-0000-4000-8000-000000000004",
    "name": "New Project",
    "slug": "new-project",
    "api_key": "PREVIEW-new-project-key-not-a-real-secret-4",
    "pools": [],
    "created_at": "2026-09-20T12:00:00.153702Z",
}

_NEW_SOURCE: dict = {
    "id": "5a1c0000-0000-4000-8000-000000000006",
    "name": "new-source",
    "type": "url",
    "url": "https://example.com/proxies.txt",
    "provider": None,
    "protocol": "http",
    "is_active": True,
    "last_polled_at": None,
    "last_status_code": None,
    "consecutive_failures": 0,
    "proxy_count": 0,
    "created_at": "2026-09-20T12:00:00.153702Z",
}

_NEW_ALERT: dict = {
    "id": "a1e70000-0000-4000-8000-000000000003",
    "name": "All proxies dead",
    "condition_type": "all_proxies_dead",
    "condition_config": {},
    "action_type": "webhook",
    "action_config": {"url": "https://hooks.example.com/proxysm/all-dead"},
    "is_enabled": True,
    "last_triggered_at": None,
    "created_at": "2026-09-20T12:00:00.153702Z",
    "updated_at": "2026-09-20T12:00:00.153702Z",
}


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

FIXTURES: dict[tuple[str, str], object] = {
    # ---- stats -----------------------------------------------------------
    # src/api/stats.py:19-86; OverviewStats src/schemas/stats.py:6-20.
    # Flat object, no envelope. Note `healthy_proxies` etc. and the `_24h` suffixes.
    ("GET", "stats/overview"): {
        "total_proxies": 12,
        "healthy_proxies": 6,
        "degraded_proxies": 2,
        "dead_proxies": 2,
        "unknown_proxies": 2,
        "total_pools": 3,
        "total_projects": 3,
        "total_requests_24h": 48210,
        "successful_requests_24h": 45127,
        "failed_requests_24h": 3083,
        "bytes_sent_24h": 61477962,
        "bytes_received_24h": 2913913461,
        "avg_response_time_ms": 428.82,
        "median_response_time_ms": 289.5,
    },
    # src/api/stats.py:486-512 (return at 508-512). Flat object. Optional
    # ?project_id=. success_rate is a 0-100 percentage.
    ("GET", "stats/throughput"): {
        "requests_5min": 235,
        "requests_per_minute": 47.0,
        "success_rate": 94.0,
    },
    # src/api/stats.py:573-617; see TIMESERIES_BY_GRANULARITY above.
    ("GET", "stats/timeseries"): TIMESERIES_BY_GRANULARITY["1hour"],
    # src/api/stats.py:620-648 (return at 637-648). {"data": [...]}, ordered by
    # total DESC; a NULL provider is reported as "Unknown".
    ("GET", "stats/provider-health"): {
        "data": [
            {
                "provider": "webshare",
                "total": 4,
                "healthy": 3,
                "degraded": 1,
                "dead": 0,
                "unknown": 0,
                "active": 4,
            },
            {
                "provider": "proxyscrape",
                "total": 3,
                "healthy": 1,
                "degraded": 1,
                "dead": 1,
                "unknown": 0,
                "active": 3,
            },
            {
                "provider": "thespeedx",
                "total": 3,
                "healthy": 1,
                "degraded": 0,
                "dead": 1,
                "unknown": 1,
                "active": 3,
            },
            {
                "provider": "manual",
                "total": 2,
                "healthy": 1,
                "degraded": 0,
                "dead": 0,
                "unknown": 1,
                "active": 1,
            },
        ]
    },
    # src/api/stats.py:138-193 (row dict at 185-192). Optional ?project_id=&hours=.
    # error_rate is a 0-100 percentage (1 decimal); keys are `avg_latency_ms` /
    # `median_latency_ms` here, NOT `*_response_time_ms` as in overview.
    ("GET", "stats/pool-metrics"): {
        "data": [
            {
                "pool_id": POOL_DATACENTER_US_ID,
                "pool_name": "datacenter-us",
                "total_requests": 30120,
                "error_rate": 2.9,
                "avg_latency_ms": 263.9,
                "median_latency_ms": 212.4,
            },
            {
                "pool_id": POOL_PUBLIC_MIX_ID,
                "pool_name": "public-mix",
                "total_requests": 14890,
                "error_rate": 13.6,
                "avg_latency_ms": 972.6,
                "median_latency_ms": 742.0,
            },
            {
                "pool_id": POOL_RESIDENTIAL_EU_ID,
                "pool_name": "residential-eu",
                "total_requests": 3200,
                "error_rate": 5.8,
                "avg_latency_ms": 388.4,
                "median_latency_ms": 301.2,
            },
        ]
    },
    # src/api/stats.py:89-135 (return at 122-135); StatusCodeBreakdown
    # src/schemas/stats.py:54-61. One row per PROJECT. status_5xx also counts
    # requests with a NULL status code (proxy errors / timeouts).
    ("GET", "stats/status-codes"): {
        "data": [
            {
                "project_id": PROJECT_SCRAPER_PROD_ID,
                "project_name": "scraper-prod",
                "status_2xx": 29840,
                "status_3xx": 1210,
                "status_4xx": 1335,
                "status_5xx": 905,
                "total": 33290,
            },
            {
                "project_id": PROJECT_PRICE_MONITOR_ID,
                "project_name": "price-monitor",
                "status_2xx": 11620,
                "status_3xx": 402,
                "status_4xx": 498,
                "status_5xx": 300,
                "total": 12820,
            },
            {
                "project_id": PROJECT_SEO_AUDIT_ID,
                "project_name": "seo-audit",
                "status_2xx": 1905,
                "status_3xx": 150,
                "status_4xx": 30,
                "status_5xx": 15,
                "total": 2100,
            },
        ]
    },
    # src/api/stats.py:251-293 (return at 283-293). ?project_id=&hours=&limit=
    # (limit 1..50, default 10). Key is `domain`; `failed` is a count while
    # `success_rate` is a 0-100 percentage.
    ("GET", "stats/top-domains"): {
        "data": [
            {
                "domain": "shop.example.com",
                "total_requests": 14820,
                "success_rate": 95.1,
                "failed": 726,
                "median_latency_ms": 244.5,
                "avg_response_bytes": 84213,
            },
            {
                "domain": "api.example.com",
                "total_requests": 9630,
                "success_rate": 97.4,
                "failed": 250,
                "median_latency_ms": 131.0,
                "avg_response_bytes": 5120,
            },
            {
                "domain": "search.example.net",
                "total_requests": 7215,
                "success_rate": 88.2,
                "failed": 851,
                "median_latency_ms": 512.5,
                "avg_response_bytes": 142884,
            },
            {
                "domain": "listings.example.org",
                "total_requests": 5480,
                "success_rate": 93.6,
                "failed": 351,
                "median_latency_ms": 301.0,
                "avg_response_bytes": 66310,
            },
            {
                "domain": "prices.example.net",
                "total_requests": 4105,
                "success_rate": 96.0,
                "failed": 164,
                "median_latency_ms": 198.5,
                "avg_response_bytes": 23377,
            },
            {
                "domain": "cdn.example.com",
                "total_requests": 2890,
                "success_rate": 99.2,
                "failed": 23,
                "median_latency_ms": 88.0,
                "avg_response_bytes": 412905,
            },
            {
                "domain": "serp.example.org",
                "total_requests": 2100,
                "success_rate": 84.3,
                "failed": 330,
                "median_latency_ms": 933.5,
                "avg_response_bytes": 187450,
            },
            {
                "domain": "httpbin.org",
                "total_requests": 1240,
                "success_rate": 98.9,
                "failed": 14,
                "median_latency_ms": 156.0,
                "avg_response_bytes": None,
            },
        ]
    },
    # src/api/stats.py:296-332 (return at 324-332). Flat object of counts, NOT a
    # {"data": [...]} list. Optional ?project_id=&hours=.
    ("GET", "stats/error-breakdown"): {
        "proxy_errors": 640,
        "timeouts": 415,
        "client_4xx": 1863,
        "server_5xx": 120,
        "other_errors": 45,
        "successful": 45127,
        "total": 48210,
    },
    # src/api/stats.py:416-444 (return at 436-444). Hourly buckets only; ?hours=
    # only (no project_id). `period` comes from .isoformat() -> "+00:00" suffix.
    ("GET", "stats/latency-trend"): {
        "data": [
            {"period": f"{hour}+00:00", "p50": p50, "p95": p95, "sample_count": samples}
            for hour, p50, p95, samples in zip(
                _HOURS, _HOURLY_P50, _HOURLY_P95, _HOURLY_SAMPLES, strict=True
            )
        ]
    },
    # src/api/stats.py:447-483 (return at 476-483). Hourly buckets; optional
    # ?project_id=&hours=. `period` uses .isoformat() -> "+00:00" suffix.
    ("GET", "stats/bandwidth-trend"): {
        "data": [
            {"period": f"{hour}+00:00", "bytes_sent": sent, "bytes_received": received}
            for hour, sent, received in zip(
                _HOURS, _HOURLY_BYTES_SENT, _HOURLY_BYTES_RECEIVED, strict=True
            )
        ]
    },
    # EXTRA (not in the request list, but dashboard.html calls it):
    # src/api/stats.py:196-248 (row dict at 235-247). Six fixed bucket labels.
    ("GET", "stats/pool-latency-histogram"): {
        "data": [
            {
                "pool_id": POOL_DATACENTER_US_ID,
                "pool_name": "datacenter-us",
                "buckets": [
                    {"label": "<100ms", "count": 2980},
                    {"label": "100-300ms", "count": 17890},
                    {"label": "300-500ms", "count": 5960},
                    {"label": "500ms-1s", "count": 2235},
                    {"label": "1-3s", "count": 670},
                    {"label": "3s+", "count": 75},
                ],
                "total": 29810,
            },
            {
                "pool_id": POOL_PUBLIC_MIX_ID,
                "pool_name": "public-mix",
                "buckets": [
                    {"label": "<100ms", "count": 420},
                    {"label": "100-300ms", "count": 2260},
                    {"label": "300-500ms", "count": 2965},
                    {"label": "500ms-1s", "count": 4520},
                    {"label": "1-3s", "count": 3390},
                    {"label": "3s+", "count": 565},
                ],
                "total": 14120,
            },
            {
                "pool_id": POOL_RESIDENTIAL_EU_ID,
                "pool_name": "residential-eu",
                "buckets": [
                    {"label": "<100ms", "count": 190},
                    {"label": "100-300ms", "count": 1385},
                    {"label": "300-500ms", "count": 945},
                    {"label": "500ms-1s", "count": 440},
                    {"label": "1-3s", "count": 170},
                    {"label": "3s+", "count": 20},
                ],
                "total": 3150,
            },
        ]
    },
    # EXTRA (dashboard.html calls it): src/api/stats.py:335-371 (row dict at
    # 365-370). `proxy_addr` is "host:port"; proxies with no traffic are absent.
    ("GET", "stats/proxy-distribution"): {
        "data": [
            {
                "proxy_id": _proxy_id(n),
                "proxy_addr": f"{PROXIES_BY_ID[_proxy_id(n)]['host']}"
                f":{PROXIES_BY_ID[_proxy_id(n)]['port']}",
                "request_count": count,
                "success_rate": rate,
            }
            for n, count, rate in [
                (1, 8120, 98.1),
                (2, 7985, 97.6),
                (3, 7840, 97.9),
                (4, 6175, 90.4),
                (5, 5210, 91.2),
                (6, 3980, 78.5),
                (8, 3890, 93.0),
                (11, 3200, 94.2),
                (7, 1105, 41.3),
                (9, 705, 38.9),
            ]
        ]
    },
    # EXTRA (exists, current UI does not call it): src/api/stats.py:374-413
    # (return at 402-413). Worst success rate first; ?hours=&limit=.
    ("GET", "stats/proxy-ranking"): {
        "data": [
            {
                "proxy_id": _proxy_id(n),
                "proxy_addr": f"{PROXIES_BY_ID[_proxy_id(n)]['host']}"
                f":{PROXIES_BY_ID[_proxy_id(n)]['port']}",
                "status": PROXIES_BY_ID[_proxy_id(n)]["last_health_status"],
                "total_requests": total,
                "success_rate": rate,
                "failed": failed,
                "median_latency_ms": median,
            }
            for n, total, rate, failed, median in [
                (9, 705, 38.9, 431, 2210.5),
                (7, 1105, 41.3, 649, 1875.0),
                (6, 3980, 78.5, 856, 1312.5),
                (4, 6175, 90.4, 593, 588.0),
                (5, 5210, 91.2, 458, 236.5),
            ]
        ]
    },
    # ---- ips (proxies) -----------------------------------------------------
    # src/api/proxies.py:38-90; envelope src/schemas/common.py:8-18. Query:
    # page, per_page (1..100, default 50), pool_id, status, protocol, provider,
    # search (host/provider ILIKE), sort_by (host|port|protocol|provider|status|
    # latency), sort_dir (asc|desc).
    ("GET", "ips"): _page(PROXIES),
    # src/api/proxies.py:223-232; ProxyResponse src/schemas/proxy.py:21-32.
    ("GET", "ips/{id}"): PROXIES[-1],
    # src/api/proxies.py:93-118. 201. Body: ProxyCreate (host, port, protocol,
    # provider?, username?, password?). A new proxy starts as "unknown".
    ("POST", "ips"): _NEW_PROXY,
    # src/api/proxies.py:121-220 (return at 220). 201. Raw dict, not a model.
    ("POST", "ips/bulk"): {
        "created": 25,
        "skipped": 3,
        "source_id": "5a1c0000-0000-4000-8000-000000000007",
    },
    # src/api/proxies.py:235-249. Body: ProxyUpdate, only `is_active` is editable.
    ("PATCH", "ips/{id}"): {**PROXIES[-1], "is_active": False},
    # src/api/proxies.py:252-261. 204.
    ("DELETE", "ips/{id}"): None,
    # src/api/proxies.py:264-300 (return at 296-300). Keys are `status` and
    # `latency_ms` (not last_health_status / avg_latency_ms). On a failed check
    # latency_ms is 0.0, not null. SEE NOTE in the hand-off: the real handler
    # currently raises (tuple-unpack mismatch with check_single_proxy), so this
    # is the intended shape that proxies.html:541-543 consumes.
    ("POST", "ips/{id}/check"): {"id": _proxy_id(1), "status": "healthy", "latency_ms": 87.4},
    # EXTRA (exists, UI does not call it): src/api/stats.py:658-668; EntityStats.
    ("GET", "ips/{id}/stats"): {
        "total_requests": 58240,
        "successful_requests": 57133,
        "failed_requests": 1107,
        "error_rate": 1.9,
        "avg_response_time_ms": 118.46,
        "median_response_time_ms": 84.0,
        "p95_response_time_ms": 912.25,
        "bytes_sent": 74256000,
        "bytes_received": 3519501440,
    },
    # ---- pools -------------------------------------------------------------
    # src/api/pools.py:62-110; PoolResponse src/schemas/pool.py:24-30. Query:
    # page, per_page only. Ordered by created_at DESC.
    ("GET", "pools"): _page(POOLS),
    # src/api/pools.py:113-125. 201. Body: PoolCreate (name, rotation_strategy).
    ("POST", "pools"): _NEW_POOL,
    # src/api/pools.py:128-141.
    ("GET", "pools/{id}"): POOLS_BY_ID[POOL_DATACENTER_US_ID],
    # src/api/pools.py:144-162. Body: PoolUpdate (name?, rotation_strategy?).
    ("PATCH", "pools/{id}"): {**POOLS_BY_ID[POOL_DATACENTER_US_ID], "rotation_strategy": "random"},
    # src/api/pools.py:165-174. 204.
    ("DELETE", "pools/{id}"): None,
    # src/api/pools.py:177-208 (return at 208). 201. Body: {"proxy_ids": [uuid]}.
    # Unknown ids and ids already in the pool are silently skipped.
    ("POST", "pools/{id}/ips"): {"added": 2},
    # src/api/pools.py:211-237 (return at 237). 200 WITH a body (not 204); the
    # DELETE request carries a JSON body {"proxy_ids": [uuid]}.
    ("DELETE", "pools/{id}/ips"): {"removed": 2},
    # EXTRA (exists, UI does not call it): src/api/stats.py:671-681; EntityStats.
    ("GET", "pools/{id}/stats"): {
        "total_requests": 203870,
        "successful_requests": 197958,
        "failed_requests": 5912,
        "error_rate": 2.9,
        "avg_response_time_ms": 263.9,
        "median_response_time_ms": 212.4,
        "p95_response_time_ms": 1844.0,
        "bytes_sent": 259934250,
        "bytes_received": 12320067970,
    },
    # ---- projects ----------------------------------------------------------
    # src/api/projects.py:54-79; ProjectResponse src/schemas/project.py:17-23.
    # Nested pools carry proxy_count/healthy_count = null (projects.py:40).
    ("GET", "projects"): _page(PROJECTS),
    # src/api/projects.py:82-110; ProjectCreateResponse src/schemas/project.py:28-29.
    # 201. Body: {"name"}. Same shape as ProjectResponse; 409 on duplicate name.
    ("POST", "projects"): _NEW_PROJECT,
    # src/api/projects.py:113-123.
    ("GET", "projects/{id}"): PROJECTS_BY_ID[PROJECT_SCRAPER_PROD_ID],
    # src/api/projects.py:126-142. Body: {"name"}; slug is re-derived from name.
    ("PATCH", "projects/{id}"): {
        **PROJECTS_BY_ID[PROJECT_SCRAPER_PROD_ID],
        "name": "Scraper Prod EU",
        "slug": "scraper-prod-eu",
    },
    # src/api/projects.py:145-154. 204.
    ("DELETE", "projects/{id}"): None,
    # src/api/stats.py:684-694; EntityStats src/schemas/stats.py:25-34.
    ("GET", "projects/{id}/stats"): ENTITY_STATS_BY_ID[PROJECT_SCRAPER_PROD_ID],
    # src/api/projects.py:157-185 (return at 185). 201. Body: {"pool_ids": [uuid]}.
    ("POST", "projects/{id}/pools"): {"added": 1},
    # src/api/projects.py:188-204. 204; 404 "Pool not assigned to project".
    ("DELETE", "projects/{id}/pools/{id}"): None,
    # src/api/projects.py:207-231. 200 (not 201). Full project with the new key.
    ("POST", "projects/{id}/rotate-key"): {
        **PROJECTS_BY_ID[PROJECT_SCRAPER_PROD_ID],
        "api_key": "PREVIEW-scraper-prod-rotated-not-a-secret-1",
    },
    # ---- sources -----------------------------------------------------------
    # src/api/sources.py:27-63; SourceResponse src/schemas/source.py:24-36.
    ("GET", "sources"): _page(SOURCES),
    # src/api/sources.py:66-83. 201. Body: SourceCreate (name, type, url?,
    # provider?, protocol).
    ("POST", "sources"): _NEW_SOURCE,
    # EXTRA (exists, UI does not call it): src/api/sources.py:86-95.
    ("GET", "sources/{id}"): SOURCES_BY_ID[SOURCE_WEBSHARE_ID],
    # EXTRA (exists, UI does not call it): src/api/sources.py:98-112.
    ("PATCH", "sources/{id}"): {**SOURCES_BY_ID[SOURCE_WEBSHARE_ID], "is_active": False},
    # src/api/sources.py:115-124. 204.
    ("DELETE", "sources/{id}"): None,
    # src/api/sources.py:127-147 -> src/services/source_poller.py:221-227.
    # Raw dict; key is `source_id` (not `id`) and last_polled_at uses
    # .isoformat() -> "+00:00". 400 if the source type is not "url".
    ("POST", "sources/{id}/poll"): {
        "source_id": SOURCE_WEBSHARE_ID,
        "last_polled_at": "2026-09-20T12:00:01.482215+00:00",
        "last_status_code": 200,
        "consecutive_failures": 0,
        "proxy_count": 4,
    },
    # ---- alerts ------------------------------------------------------------
    # src/api/alerts.py:15-24. BARE LIST: response_model=list[AlertResponse],
    # no {"data", "meta"} envelope and no pagination params.
    ("GET", "alerts"): ALERTS,
    # src/api/alerts.py:27-44. 201. Body: AlertCreate src/schemas/alert.py:7-13.
    ("POST", "alerts"): _NEW_ALERT,
    # src/api/alerts.py:47-57; AlertResponse src/schemas/alert.py:25-35.
    ("GET", "alerts/{id}"): ALERTS_BY_ID[ALERT_ERROR_RATE_ID],
    # src/api/alerts.py:60-75. Body: AlertUpdate (all fields optional).
    ("PATCH", "alerts/{id}"): {
        **ALERTS_BY_ID[ALERT_ERROR_RATE_ID],
        "is_enabled": False,
        "updated_at": "2026-09-20T12:00:00.153702Z",
    },
    # src/api/alerts.py:78-88. 204.
    ("DELETE", "alerts/{id}"): None,
    # ---- system ------------------------------------------------------------
    # src/api/system.py:14-32.
    ("GET", "system/info"): _SYSTEM_INFO,
    # src/api/system.py:9-11. Path is /api/v1/health (no "system/" prefix).
    ("GET", "health"): _HEALTH,
}

# HTTP status per fixture (everything not listed here is 200).
STATUS_CODES: dict[tuple[str, str], int] = {
    ("POST", "ips"): 201,
    ("POST", "ips/bulk"): 201,
    ("DELETE", "ips/{id}"): 204,
    ("POST", "pools"): 201,
    ("DELETE", "pools/{id}"): 204,
    ("POST", "pools/{id}/ips"): 201,
    ("POST", "projects"): 201,
    ("DELETE", "projects/{id}"): 204,
    ("POST", "projects/{id}/pools"): 201,
    ("DELETE", "projects/{id}/pools/{id}"): 204,
    ("POST", "sources"): 201,
    ("DELETE", "sources/{id}"): 204,
    ("POST", "alerts"): 201,
    ("DELETE", "alerts/{id}"): 204,
}

# ---------------------------------------------------------------------------
# EMPTY_FIXTURES: what a brand-new instance returns for every GET list/stats
# endpoint (no proxies, pools, projects, sources, alerts or traffic).
# ---------------------------------------------------------------------------

_EMPTY_DATA: dict = {"data": []}

EMPTY_FIXTURES: dict[tuple[str, str], object] = {
    # src/api/stats.py:71-86: counts 0, both latency fields null.
    ("GET", "stats/overview"): {
        "total_proxies": 0,
        "healthy_proxies": 0,
        "degraded_proxies": 0,
        "dead_proxies": 0,
        "unknown_proxies": 0,
        "total_pools": 0,
        "total_projects": 0,
        "total_requests_24h": 0,
        "successful_requests_24h": 0,
        "failed_requests_24h": 0,
        "bytes_sent_24h": 0,
        "bytes_received_24h": 0,
        "avg_response_time_ms": None,
        "median_response_time_ms": None,
    },
    # src/api/stats.py:507-512: round(0 / 5, 1) -> 0.0, success_rate -> int 0.
    ("GET", "stats/throughput"): {
        "requests_5min": 0,
        "requests_per_minute": 0.0,
        "success_rate": 0,
    },
    # src/api/stats.py:617: granularity is echoed, data is an empty list.
    ("GET", "stats/timeseries"): {"granularity": "1hour", "data": []},
    # src/api/stats.py:637
    ("GET", "stats/provider-health"): _EMPTY_DATA,
    # src/api/stats.py:193
    ("GET", "stats/pool-metrics"): _EMPTY_DATA,
    # src/api/stats.py:122
    ("GET", "stats/status-codes"): _EMPTY_DATA,
    # src/api/stats.py:283
    ("GET", "stats/top-domains"): _EMPTY_DATA,
    # src/api/stats.py:324-332: aggregate without GROUP BY always yields one row
    # of zeros, never nulls.
    ("GET", "stats/error-breakdown"): {
        "proxy_errors": 0,
        "timeouts": 0,
        "client_4xx": 0,
        "server_5xx": 0,
        "other_errors": 0,
        "successful": 0,
        "total": 0,
    },
    # src/api/stats.py:436
    ("GET", "stats/latency-trend"): _EMPTY_DATA,
    # src/api/stats.py:476
    ("GET", "stats/bandwidth-trend"): _EMPTY_DATA,
    # src/api/stats.py:248
    ("GET", "stats/pool-latency-histogram"): _EMPTY_DATA,
    # src/api/stats.py:371
    ("GET", "stats/proxy-distribution"): _EMPTY_DATA,
    # src/api/stats.py:402
    ("GET", "stats/proxy-ranking"): _EMPTY_DATA,
    # src/api/proxies.py:87-90
    ("GET", "ips"): _page([]),
    # src/api/pools.py:107-110
    ("GET", "pools"): _page([]),
    # src/api/projects.py:76-79
    ("GET", "projects"): _page([]),
    # src/api/sources.py:60-63
    ("GET", "sources"): _page([]),
    # src/api/alerts.py:24: bare empty list.
    ("GET", "alerts"): [],
    # src/api/stats.py:560-570 with no rollups: zeros, error_rate 0.0, nulls.
    # (On a truly empty instance there is no project, so the real API would 404;
    # this is the shape for a project that has no traffic yet.)
    ("GET", "projects/{id}/stats"): _EMPTY_ENTITY_STATS,
    # Identical on an empty instance.
    ("GET", "system/info"): _SYSTEM_INFO,
    ("GET", "health"): _HEALTH,
}


# Review Focus 3 of the milestone-1 plan: a hostile, very long name. The UI must render it
# as text, truncate it, and never execute it.
_HOSTILE_POOL = {
    "id": "b0010000-0000-4000-8000-0000000000ff",
    "name": "<script>alert(1)</script>-" + "very-long-pool-name-" * 4,
    "rotation_strategy": "random",
    "proxy_count": 0,
    "healthy_count": 0,
    "created_at": "2026-09-18T10:00:00Z",
}
FIXTURES[("GET", "pools")]["data"].append(_HOSTILE_POOL)
FIXTURES[("GET", "pools")]["meta"]["total"] += 1

_HOSTILE_PROJECT = {
    "id": "c0010000-0000-4000-8000-0000000000ff",
    "name": "<script>alert(2)</script> \" onmouseover=\"alert(3) " + "very-long-project-name-" * 3,
    "slug": "hostile-project",
    "api_key": None,
    "pools": [],
    "created_at": "2026-09-18T10:05:00Z",
}
FIXTURES[("GET", "projects")]["data"].append(_HOSTILE_PROJECT)
FIXTURES[("GET", "projects")]["meta"]["total"] += 1
