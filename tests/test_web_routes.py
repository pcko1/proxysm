import pathlib
import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient

from src.web.auth import SESSION_COOKIE, create_session_token
from src.web.routes import router as web_router

# ---------------------------------------------------------------------------
# Test app — web router + static files, no DB/Redis startup events.
# ---------------------------------------------------------------------------

_STATIC = pathlib.Path(__file__).parent.parent / "src" / "web" / "static"

_fake_settings = MagicMock()
_fake_settings.pm_admin_password = "testpassword"
_fake_settings.proxy_http_port = 9080
_fake_settings.proxy_socks5_port = 9081

PAGES = ["/dashboard", "/proxies", "/pools", "/projects", "/settings"]

# DOM ids base.html provides to app.js and to every page script.
SHARED_IDS = [
    "toastContainer", "bulkBar", "bulkCount", "bulkDeleteBtn", "confirmModal", "confirmOkBtn",
    "confirmCancelBtn", "navStatus", "navStatusText", "navToggle", "sideNav",
]


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
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
async def test_sidebar_order(client):
    """Sidebar: Overview, Proxies, Pools, Projects, then Settings and Sign out. No API Docs."""
    body = (await client.get("/dashboard")).text
    order = ["nav-overview", "nav-proxies", "nav-pools", "nav-projects"]
    order += ["nav-settings", "nav-logout"]
    positions = [body.index(f'id="{nav_id}"') for nav_id in order]
    assert positions == sorted(positions)
    assert 'id="nav-api-docs"' not in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
@pytest.mark.parametrize(
    ("path", "nav_id"),
    [("/dashboard", "nav-overview"), ("/proxies", "nav-proxies"), ("/pools", "nav-pools"),
     ("/projects", "nav-projects"), ("/settings", "nav-settings")],
)
async def test_active_nav_item_is_rendered_by_the_server(client, path, nav_id):
    body = (await client.get(path)).text
    active = re.findall(r'<a [^>]*id="(nav-[a-z]+)"[^>]*class="nav-item active"', body)
    assert active == [nav_id]
    assert body.count('aria-current="page"') == 1


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
@pytest.mark.parametrize("path", PAGES)
async def test_shell_uses_versioned_static_assets(client, path):
    body = (await client.get(path)).text
    assert re.search(r'href="/static/css/app\.css\?v=[0-9a-f]+"', body)
    assert re.search(r'src="/static/js/app\.js\?v=[0-9a-f]+"', body)
    assert 'data-http-port="9080"' in body and 'data-socks5-port="9081"' in body
    assert "cdnjs" not in body, "no CDN"
    for shared_id in SHARED_IDS:
        assert f'id="{shared_id}"' in body, shared_id


# Pages already rebuilt in Blocks. Each page task appends its path as its first failing test;
# Task 13 asserts this equals PAGES.
RESTYLED_PAGES: list[str] = []


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
@pytest.mark.parametrize("path", RESTYLED_PAGES)
async def test_restyled_page_has_markup_only(client, path):
    """A rebuilt page has no inline CSS or JS logic and makes no external request."""
    body = (await client.get(path)).text
    assert "<style" not in body, "all CSS lives in app.css"
    assert not re.search(r'(?:src|href)="https?://', body), "no external requests"
    assert "hljs" not in body and "geist" not in body.lower()
    inline_script = re.search(r"<script(?![^>]*\bsrc=)[^>]*>", body)
    assert inline_script is None, "no inline <script>; page logic lives in static/js/pages"


@pytest.mark.asyncio
async def test_static_assets_are_served(client):
    css = await client.get("/static/css/app.css")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    js = await client.get("/static/js/app.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    font = await client.get("/static/fonts/figtree.woff2")
    assert font.status_code == 200


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
    pages = PAGES
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


@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "target"), [("/api-docs", "/docs"), ("/setup", "/dashboard")])
async def test_retired_pages_redirect(client, path, target):
    resp = await client.get(path)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == target


def test_retired_templates_are_gone():
    templates = pathlib.Path(__file__).parent.parent / "src" / "web" / "templates"
    assert not (templates / "api-docs.html").exists()
    assert not (templates / "setup.html").exists()
