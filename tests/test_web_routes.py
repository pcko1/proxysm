from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.web.routes import router as web_router

# ---------------------------------------------------------------------------
# Test app — only includes the web router, no DB/Redis startup events.
# ---------------------------------------------------------------------------

_fake_settings = MagicMock()
_fake_settings.pm_admin_password = "testpassword"


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(web_router)
    return app


test_app = _build_test_app()


@pytest.fixture
def client():
    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)


# ---------------------------------------------------------------------------
# Redirect tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_index_redirects_to_dashboard(client):
    resp = await client.get("/")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/dashboard"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_stats_redirects_to_dashboard(client):
    resp = await client.get("/stats")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/dashboard"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_providers_redirects_to_proxies(client):
    resp = await client.get("/providers")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/proxies"


# ---------------------------------------------------------------------------
# HTML page tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_dashboard_returns_html(client):
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_returns_html(client):
    resp = await client.get("/proxies")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_pools_returns_html(client):
    resp = await client.get("/pools")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_projects_returns_html(client):
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_settings_returns_html(client):
    resp = await client.get("/settings")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_setup_returns_html(client):
    resp = await client.get("/setup")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_api_docs_returns_html(client):
    resp = await client.get("/api-docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_dashboard_contains_html_structure(client):
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    body = resp.text
    assert "<html" in body.lower() or "<!doctype" in body.lower() or "<head" in body.lower()
