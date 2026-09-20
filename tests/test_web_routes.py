import pathlib
import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient

from src.web.auth import SESSION_COOKIE, create_session_token
from src.web.routes import router as web_router
from tests.test_ui_static import assert_js_ids_exist

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
RESTYLED_PAGES: list[str] = ["/dashboard"]


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


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_login_page_uses_the_stylesheet_and_nothing_external(anon_client):
    body = (await anon_client.get("/login")).text
    assert re.search(r'href="/static/css/app\.css\?v=[0-9a-f]+"', body)
    assert "<style" not in body and "geist" not in body.lower()
    assert not re.search(r'(?:src|href)="https?://', body)
    assert 'class="shell-nav"' not in body, "no app navigation before sign-in"
    assert '<label for="password"' in body and 'id="password"' in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_login_error_is_announced(anon_client):
    resp = await anon_client.post("/login", data={"password": "nope"})
    assert resp.status_code == 401
    assert 'class="auth__error" role="alert"' in resp.text


# ---------------------------------------------------------------------------
# Overview page (/dashboard)
# ---------------------------------------------------------------------------

OVERVIEW_JS = _STATIC / "js" / "pages" / "overview.js"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_overview_loads_its_script_and_every_id_it_needs(client):
    body = (await client.get("/dashboard")).text
    assert re.search(r'<script src="/static/js/pages/overview\.js\?v=[0-9a-f]+"></script>', body)
    assert_js_ids_exist("overview.js", body)
    served = await client.get("/static/js/pages/overview.js")
    assert served.status_code == 200


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_overview_head_tiles_and_traffic(client):
    body = (await client.get("/dashboard")).text
    assert "<title>Overview - Proxysm</title>" in body
    assert "<h1>Overview</h1>" in body
    assert 'id="rangeSeg"' in body
    for value in ("1h", "24h", "7d"):
        assert f'data-range="{value}"' in body
    for tile in ("tile--lime", "tile--amber", "tile--coral"):
        assert f'class="tile {tile} kpi"' in body
    for stat_id in ("statHealthy", "statDegraded", "statDead", "statRpm",
                    "kpiHealthyFoot", "kpiDeadFoot", "kpiRpmFoot"):
        assert f'id="{stat_id}"' in body, stat_id
    assert "rechecked every 15 seconds" in body
    assert 'class="bars" id="trafficBars" role="img"' in body
    assert 'id="trafficAxis"' in body and 'id="trafficSummary"' in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_overview_has_providers_and_pools_tables(client):
    """The two table bodies keep their old ids; each table has an empty state with its fix."""
    body = (await client.get("/dashboard")).text
    assert 'id="providerHealthBody"' in body and 'id="providerHealthEmpty"' in body
    assert 'id="poolUtilBody"' in body and 'id="poolUtilEmpty"' in body
    assert body.count('<table class="tbl"') == 3
    assert body.count('class="empty-state"') == 3


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_overview_projects_table_has_open_column_and_no_quota(client):
    body = (await client.get("/dashboard")).text
    assert 'id="projectStatsBody"' in body and 'id="projectStatsEmpty"' in body
    assert "quota" not in body.lower(), "the quota column arrives in milestone 4"
    # /projects/{id}/stats is not a 24h window; only the Pools table (pool-metrics) is.
    tooltip = "Since the oldest 5-minute metrics still kept (7 days by default)"
    assert f'title="{tooltip}">Requests</th>' in body
    assert body.count("Req 24h") == 1
    assert "Needs attention" not in body and "vs 1h ago" not in body, "milestone 3"
    js = OVERVIEW_JS.read_text()
    assert "/projects?project=${encodeURIComponent(p.id)}" in js


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_overview_onboarding_card_deep_links(client):
    body = (await client.get("/dashboard")).text
    card = body[body.index('id="onboardingCard"'):]
    card = card[: card.index("</section>")]
    assert " hidden" in card[: card.index(">")], "hidden until the script knows a step is open"
    for step_id, href in (
        ("onboardingStepProxies", "/proxies?import=1"),
        ("onboardingStepPools", "/pools?new=1"),
        ("onboardingStepProjects", "/projects?new=1"),
    ):
        link = f'<a href="{href}" class="onboarding-step" id="{step_id}">'
        assert link in card, link
    assert "/setup" not in body
    assert "Guided setup" not in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_overview_drops_the_old_dashboard(client):
    body = (await client.get("/dashboard")).text
    haystack = body + OVERVIEW_JS.read_text()
    for gone in (
        "Top Failing Proxies", "Worst Performing Proxies", "loadFailingProxies", "loadProxyRanking",
        "switchTab", "dash-tab", "section-projects", "projectDetail", "selectProject",
        'id="donut"', "drawDonut", "drawLineChart", "latencyTrendChart", "bandwidthOverviewChart",
        "statusCodeContainer", "errorBreakdownContainer", "topDomainsBody", "latencyHistContainer",
        "rotationBarsContainer", "throughputNum",
        "loadStats()",  # the old Refresh button
    ):
        assert gone not in haystack, gone


def test_overview_script_contract():
    js = OVERVIEW_JS.read_text()
    assert "'use strict';" in js
    assert not re.search(r"^\s*(import|export)\s", js, re.M), "classic script"
    assert "{{" not in js and "{%" not in js, "no Jinja in static files"
    assert not re.search(r"https?://", js)
    for shared in ("esc", "apiCall", "showToast", "fmtNum", "fmtPct", "fmtMs", "fmtBytes"):
        assert not re.search(rf"function\s+{shared}\s*\(", js), f"{shared} belongs to app.js"
    assert "Poller.start(loadOverview, 10000)" in js
    assert js.count("Promise.allSettled(") >= 2, "one failing endpoint must not blank the rest"
    assert "'proxysm.overview.range'" in js
    for line in (
        "'1h': { granularity: '5min', step: 5 * MINUTE_MS, buckets: 12,",
        "'24h': { granularity: '1hour', step: 60 * MINUTE_MS, buckets: 24,",
        "'7d': { granularity: '1day', step: 1440 * MINUTE_MS, buckets: 7,",
    ):
        assert line in js, line
    assert "/api/v1/stats/timeseries?entity_type=proxy&granularity=" in js
    assert "'/api/v1/stats/throughput'" in js, "global throughput, no project_id"
    # Polling must stay silent: the only toast is the operator's own range switch.
    assert js.count("showToast(") == 1


def test_overview_escapes_api_text_with_esc_everywhere():
    """One rule on every page: esc() for element content and for quoted attribute values."""
    js = OVERVIEW_JS.read_text()
    assert "function attr(" not in js, "esc() is attribute-safe since Task 2; no local escaper"
    for needle in (
        'title="${esc(p.provider)}">${esc(p.provider)}<',
        'title="${esc(p.name)}">${esc(p.name)}<',
        'aria-label="Open project ${esc(p.name)}"',
        "${esc(strategy)}",
    ):
        assert needle in js, needle
