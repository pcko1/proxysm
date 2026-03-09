from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.system import router as system_router

# ---------------------------------------------------------------------------
# Test app — only the system router, no DB/Redis lifecycle events.
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "testpassword"

_fake_settings = MagicMock()
_fake_settings.pm_admin_password = ADMIN_PASSWORD
_fake_settings.health_check_interval = 30
_fake_settings.health_check_timeout = 5
_fake_settings.health_check_concurrency = 10
_fake_settings.health_check_url = "http://example.com"
_fake_settings.proxy_http_port = 8080
_fake_settings.proxy_socks5_port = 1080
_fake_settings.request_log_retention_days = 7
_fake_settings.metrics_5min_retention_days = 7
_fake_settings.metrics_1hour_retention_days = 30
_fake_settings.metrics_rollup_interval = 300
_fake_settings.bandwidth_flush_interval = 10
_fake_settings.rate_limit_window_seconds = 60
_fake_settings.prometheus_enabled = False


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(system_router, prefix="/api/v1")
    return app


test_app = _build_test_app()


@pytest.fixture
def client():
    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_returns_ok(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check_contains_version(client):
    resp = await client.get("/api/v1/health")
    assert resp.json()["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# System info — requires admin auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_info_requires_auth(client):
    resp = await client.get("/api/v1/system/info")
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
@patch("src.api.deps.settings", _fake_settings)
@patch("src.api.system.settings", _fake_settings)
async def test_system_info_with_valid_auth(client):
    resp = await client.get(
        "/api/v1/system/info",
        headers={"Authorization": f"Bearer {ADMIN_PASSWORD}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "0.1.0"
    assert "health_check_interval" in data
    assert "proxy_http_port" in data
    assert "prometheus_enabled" in data


@pytest.mark.asyncio
@patch("src.api.deps.settings", _fake_settings)
@patch("src.api.system.settings", _fake_settings)
async def test_system_info_with_invalid_auth(client):
    resp = await client.get(
        "/api/v1/system/info",
        headers={"Authorization": "Bearer wrongtoken"},
    )
    assert resp.status_code == 401
