from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.web.auth import SESSION_COOKIE, create_session_token
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
    """Authenticated client (carries a valid session cookie)."""
    transport = ASGITransport(app=test_app)
    c = AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)
    c.cookies.set(SESSION_COOKIE, create_session_token())
    return c


@pytest.fixture
def anon_client():
    """Client without a session cookie."""
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
async def test_settings_alert_modal_has_typed_fields(client):
    """Alert modal uses typed per-condition fields instead of raw JSON textareas."""
    resp = await client.get("/settings")
    assert resp.status_code == 200
    body = resp.text
    # Typed condition fields
    assert 'id="alertErrThreshold"' in body
    assert 'id="alertErrWindow"' in body
    assert 'id="alertPoolSelect"' in body
    assert 'id="alertMinHealthy"' in body
    assert 'id="alertBwLimit"' in body
    assert 'id="grpAllDeadHint"' in body
    # Webhook action field
    assert 'id="alertWebhookUrl"' in body
    # Raw JSON textareas removed
    assert 'id="alertCondConfig"' not in body
    assert 'id="alertActionConfig"' not in body


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


# ---------------------------------------------------------------------------
# Navbar order tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_navbar_order(client):
    """Navbar links should appear in order: Dashboard, Proxies, Pools, Projects, API Docs."""
    resp = await client.get("/dashboard")
    body = resp.text
    dashboard_pos = body.index('id="nav-dashboard"')
    proxies_pos = body.index('id="nav-proxies"')
    pools_pos = body.index('id="nav-pools"')
    projects_pos = body.index('id="nav-projects"')
    api_docs_pos = body.index('id="nav-api-docs"')
    assert dashboard_pos < proxies_pos < pools_pos < projects_pos < api_docs_pos


# ---------------------------------------------------------------------------
# Dashboard chart tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_dashboard_has_provider_health_chart(client):
    """Dashboard should have Provider Health Overview chart."""
    resp = await client.get("/dashboard")
    body = resp.text
    assert "Provider Health Overview" in body
    assert "providerHealthBody" in body
    assert "loadProviderHealth" in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_dashboard_has_pool_utilization_chart(client):
    """Dashboard should have Pool Utilization chart."""
    resp = await client.get("/dashboard")
    body = resp.text
    assert "Pool Utilization" in body
    assert "poolUtilBody" in body
    assert "loadPoolUtilization" in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_dashboard_has_onboarding_card(client):
    """Dashboard should have the first-run onboarding card with setup steps."""
    resp = await client.get("/dashboard")
    body = resp.text
    assert 'id="onboardingCard"' in body
    assert "onboardingStepProxies" in body
    assert "onboardingStepPools" in body
    assert "onboardingStepProjects" in body
    assert 'href="/setup"' in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_dashboard_no_old_charts(client):
    """Dashboard should not have the old failing/ranking charts."""
    resp = await client.get("/dashboard")
    body = resp.text
    assert "Top Failing Proxies" not in body
    assert "Worst Performing Proxies" not in body
    assert "loadFailingProxies" not in body
    assert "loadProxyRanking" not in body


# ---------------------------------------------------------------------------
# Proxies page feature tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_has_source_click_to_copy(client):
    """Proxies page should have click-to-copy for source names."""
    resp = await client.get("/proxies")
    body = resp.text
    assert "copySourceName" in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_has_pool_conflict_modal(client):
    """Proxies page should have pool conflict modal for overwrite/merge."""
    resp = await client.get("/proxies")
    body = resp.text
    assert "poolConflictModal" in body
    assert "poolConflictMerge" in body
    assert "poolConflictOverwrite" in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_has_dynamic_pool_placeholder(client):
    """Proxies page should have dynamic pool name placeholder."""
    resp = await client.get("/proxies")
    body = resp.text
    assert "updatePoolPlaceholder" in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_sources_table_no_url_column(client):
    """Sources table should not have a dedicated URL column header."""
    resp = await client.get("/proxies")
    body = resp.text
    # The sources table headers should be: Name, Type, Provider, Date Added, Last Polled, Count
    assert "Date Added" in body
    # Should not have a standalone URL header in the sources table
    # (URL is now shown as part of the Type column)


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_pages_redirect_to_login_without_session(anon_client):
    pages = ["/dashboard", "/proxies", "/pools", "/projects", "/settings", "/api-docs", "/setup"]
    for path in pages:
        resp = await anon_client.get(path)
        assert resp.status_code == 302, path
        assert resp.headers["location"] == "/login", path


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_login_page_renders(anon_client):
    resp = await anon_client.get("/login")
    assert resp.status_code == 200
    assert "password" in resp.text.lower()


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_login_wrong_password_rejected(anon_client):
    resp = await anon_client.post("/login", data={"password": "nope"})
    assert resp.status_code == 401
    assert SESSION_COOKIE not in resp.cookies


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_login_correct_password_sets_session(anon_client):
    resp = await anon_client.post("/login", data={"password": "testpassword"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"
    assert SESSION_COOKIE in resp.cookies
    resp2 = await anon_client.get("/dashboard")
    assert resp2.status_code == 200


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_logout_clears_session(client):
    resp = await client.get("/logout")
    assert resp.status_code == 307 or resp.status_code == 302
    assert resp.headers["location"] == "/login"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_login_page_redirects_when_authenticated(client):
    resp = await client.get("/login")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/dashboard"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_admin_password_not_embedded_in_pages(client):
    for path in ["/dashboard", "/proxies", "/api-docs"]:
        resp = await client.get(path)
        assert "testpassword" not in resp.text, path
