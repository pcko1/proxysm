"""Dev-only UI preview: real templates and static files, canned /api/v1 responses.

Runs without Postgres or Redis so the web UI can be opened, clicked through and
smoke-tested, including the empty and offline states. Never imported by the app.

    uv run python -m scripts.ui_preview                         # http://127.0.0.1:8099
    PREVIEW_SCENARIO=empty uv run python -m scripts.ui_preview

Switch scenario at runtime: GET /__scenario/normal | empty | offline
"""

import math
import os
import pathlib
import re
import time
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from scripts.ui_preview_fixtures import (
    EMPTY_FIXTURES,
    ENTITY_STATS_BY_ID,
    FIXTURES,
    POOL_MEMBERS,
    STATUS_CODES,
)
from src.web.routes import not_found_handler, require_session
from src.web.routes import router as web_router

SCENARIOS = ("normal", "empty", "offline")
_STATIC = pathlib.Path(__file__).parent.parent / "src" / "web" / "static"
_UUID = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


_STEP = {"5min": 300, "1hour": 3600, "1day": 86400}
_BUCKETS = {"5min": 12, "1hour": 24, "1day": 7}


def _pattern(path: str) -> str:
    """'ips/3f2a…/check' -> 'ips/{id}/check'."""
    return "/".join("{id}" if _UUID.match(seg) else seg for seg in path.strip("/").split("/"))


def _list_item(path: str) -> dict | None:
    """For 'projects/<uuid>' return that project from the list fixture, so a detail view shows
    the item that was clicked; for 'projects/<uuid>/stats' return that project's own numbers."""
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "projects" and parts[2] == "stats":
        return ENTITY_STATS_BY_ID.get(parts[1])
    if len(parts) != 2 or not _UUID.match(parts[1]):
        return None
    page = FIXTURES.get(("GET", parts[0]))
    items = page.get("data", []) if isinstance(page, dict) else []
    return next((item for item in items if item.get("id") == parts[1]), None)


def _filter_ips(params) -> dict:
    """Honour the list filters the UI relies on: pool_id, status and search."""
    page = FIXTURES[("GET", "ips")]
    data = page["data"]
    if pool_id := params.get("pool_id"):
        members = set(POOL_MEMBERS.get(pool_id, []))
        data = [p for p in data if p["id"] in members]
    if status := params.get("status"):
        data = [p for p in data if p["last_health_status"] == status]
    if search := params.get("search"):
        needle = search.lower()
        data = [p for p in data if needle in f"{p['host']}:{p['port']} {p['provider']}".lower()]
    return {"data": data, "meta": {**page["meta"], "total": len(data)}}


def _timeseries(granularity: str) -> dict:
    """Complete buckets ending now, like the real endpoint (which never has the open bucket)."""
    step = _STEP.get(granularity, 3600)
    end = int(time.time()) // step * step
    data = []
    for i in range(_BUCKETS.get(granularity, 24), 0, -1):
        start = end - i * step
        n = start // step
        total = int((1500 + 900 * math.sin(n / 3.0)) * step / 3600)
        failed = total * (3 + n % 6) // 100
        data.append(
            {
                "period_start": datetime.fromtimestamp(start, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total_requests": total,
                "successful_requests": total - failed,
                "failed_requests": failed,
                "avg_response_time_ms": 380.0 + n % 7 * 12,
            }
        )
    return {"granularity": granularity, "data": data}


def build_app(scenario: str = "normal") -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    app.state.scenario = scenario if scenario in SCENARIOS else "normal"
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
    app.dependency_overrides[require_session] = lambda: None

    @app.get("/__scenario/{name}")
    async def set_scenario(name: str) -> PlainTextResponse:
        if name not in SCENARIOS:
            return PlainTextResponse(f"unknown scenario: {name}", status_code=404)
        app.state.scenario = name
        return PlainTextResponse(f"scenario = {name}")

    @app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def fake_api(path: str, request: Request) -> Response:
        if app.state.scenario == "offline":
            return JSONResponse({"detail": "preview: simulated outage"}, status_code=503)
        key = (request.method, _pattern(path))
        empty = app.state.scenario == "empty"
        if key == ("GET", "stats/timeseries"):
            granularity = request.query_params.get("granularity", "1hour")
            body = {"granularity": granularity, "data": []} if empty else _timeseries(granularity)
            return JSONResponse(body)
        if empty and key in EMPTY_FIXTURES:
            return JSONResponse(EMPTY_FIXTURES[key])
        if key == ("GET", "ips"):
            return JSONResponse(_filter_ips(request.query_params))
        if request.method == "GET" and not empty and (item := _list_item(path)) is not None:
            return JSONResponse(item)
        if key not in FIXTURES:
            detail = f"preview: no fixture for {key[0]} {key[1]}"
            return JSONResponse({"detail": detail}, status_code=404)
        body = FIXTURES[key]
        if body is None:
            return Response(status_code=204)
        return JSONResponse(body, status_code=STATUS_CODES.get(key, 200))

    app.include_router(web_router)
    app.add_exception_handler(404, not_found_handler)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        build_app(os.environ.get("PREVIEW_SCENARIO", "normal")),
        host="127.0.0.1",
        port=int(os.environ.get("PREVIEW_PORT", "8099")),
    )
