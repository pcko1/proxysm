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
RESTYLED_PAGES: list[str] = ["/dashboard", "/proxies", "/pools", "/projects", "/settings"]


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


# ---------------------------------------------------------------------------
# Proxies page (Blocks)
# ---------------------------------------------------------------------------

_PROXIES_JS = _STATIC / "js" / "pages" / "proxies.js"
_PROXIES_MODALS = {
    "sourcesModal": "sourcesTitle",
    "addSourceModal": "addSourceTitle",
    "deleteSourceModal": "deleteSourceTitle",
    "importModal": "importTitle",
    "poolConflictModal": "poolConflictTitle",
    "moveToPoolModal": "movePoolTitle",
}


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_page_structure(client):
    body = (await client.get("/proxies")).text
    assert re.search(r'<script src="/static/js/pages/proxies\.js\?v=[0-9a-f]+"></script>', body)
    hooks = [
        "proxyStats", "proxySearch", "statusFilters", "proxyTableWrap", "proxyTableBody",
        "selectAll", "emptyState", "noMatchState", "loadError", "pagination",
    ]
    for hook in hooks:
        assert f'id="{hook}"' in body, hook
    assert 'onclick="openSources()"' in body, "Sources button in the page head"
    assert body.count("openModal('importModal')") == 2, "page head button + empty state button"
    assert "No proxies yet" in body and "No proxies match" in body
    assert "Proxies could not be loaded" in body
    for legacy in ("fpill", "sourcesPanel", "toggleSources", "page-header", "search-field"):
        assert legacy not in body, legacy


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_script_ids_exist_in_the_page(client):
    body = (await client.get("/proxies")).text
    assert_js_ids_exist("proxies.js", body)


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_status_pills_and_search(client):
    """All / Healthy / Degraded / Dead / Unknown, each with a dot and a count; labelled search."""
    body = (await client.get("/proxies")).text
    pills = re.findall(r'<button class="pill[^"]*" type="button" data-status="([a-z]*)"', body)
    assert pills == ["", "healthy", "degraded", "dead", "unknown"]
    for count_id in ("ctAll", "ctHealthy", "ctDegraded", "ctDead", "ctUnknown"):
        assert f'<span class="count" id="{count_id}"></span>' in body, count_id
    for status in ("healthy", "degraded", "dead", "unknown"):
        assert f'<span class="dot dot--{status}"></span>' in body, status
    assert '<label for="proxySearch" class="sr-only">' in body
    assert re.search(r'<input type="search" id="proxySearch" class="on-ground"', body)


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_table_columns(client):
    body = (await client.get("/proxies")).text
    sortable = re.findall(r'<th class="sortable[^"]*" data-sort="([a-z]+)" tabindex="0"', body)
    assert sortable == ["host", "protocol", "provider", "status", "latency"]
    assert '<th class="num">Last check</th>' in body
    assert "Success" not in body, "the success column belongs to milestone 3"
    assert 'aria-label="Proxy detail"' not in body, "the detail panel belongs to milestone 3"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_sources_live_in_a_modal(client):
    """The always-visible sources panel is gone; the same table sits in a wide modal."""
    body = (await client.get("/proxies")).text
    start = body.index('id="sourcesModal"')
    modal = body[start:body.index('id="addSourceModal"')]
    assert 'class="modal modal--wide"' in modal
    headers = re.findall(r"<th(?:\s[^>]*)?>(?:<span[^>]*>)?([^<]+)", modal)
    assert headers == [
        "Name", "Type", "Provider", "Date added", "Last polled", "Proxies", "Actions",
    ], "no URL column: the type links to the feed"
    assert 'id="sourcesTableBody"' in modal and 'id="sourcesEmpty"' in modal
    assert 'onclick="openAddSource()"' in modal
    js = _PROXIES_JS.read_text()
    assert "/api/v1/sources?per_page=100" in js
    assert "/poll`" in js and "function pollSource(" in js
    assert "function confirmDeleteSource(" in js and "function createSource(" in js


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_has_source_click_to_copy(client):
    """Clicking a source name copies it; the name is looked up by id, never interpolated."""
    body = (await client.get("/proxies")).text
    assert 'id="sourcesTableBody"' in body
    assert "Click a name to copy it" in body
    js = _PROXIES_JS.read_text()
    assert "function copySourceName(id, btn)" in js
    assert "copyToClipboard(source.name)" in js
    assert 'data-action="copy"' in js
    assert "copySourceName('${" not in js, "names never go into inline handlers"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_has_pool_conflict_modal(client):
    """Importing into an existing pool asks: Cancel, Merge or Overwrite."""
    body = (await client.get("/proxies")).text
    for hook in ("poolConflictModal", "poolConflictMsg", "poolConflictCancel",
                 "poolConflictMerge", "poolConflictOverwrite"):
        assert f'id="{hook}"' in body, hook
    js = _PROXIES_JS.read_text()
    assert "function askPoolConflict(" in js
    for action in ("'merge'", "'overwrite'", "'cancel'"):
        assert f"finish({action})" in js, action
    assert js.index("askPoolConflict(poolName") < js.index("'/api/v1/ips/bulk'"), (
        "the question is asked before anything is imported, so Cancel cancels everything"
    )


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_has_dynamic_pool_placeholder(client):
    """Typing a provider updates the suggested pool name."""
    body = (await client.get("/proxies")).text
    assert re.search(r'id="importProvider"[^>]*oninput="updatePoolPlaceholder\(\)"', body)
    assert 'id="importPoolName" placeholder="my-provider-001"' in body
    js = _PROXIES_JS.read_text()
    assert "function updatePoolPlaceholder()" in js
    assert "+ '-001'" in js and "'my-provider-001'" in js


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_proxies_modals_are_labelled_dialogs(client):
    body = (await client.get("/proxies")).text
    for modal_id, title_id in _PROXIES_MODALS.items():
        assert re.search(
            rf'id="{modal_id}" role="dialog" aria-modal="true" aria-labelledby="{title_id}"', body
        ), modal_id
        assert f'<h2 id="{title_id}">' in body, title_id
    import_fields = [
        "importProvider", "importProtocol", "importText", "importFile", "importUrl",
        "importCreatePool", "importPoolName", "importPoolStrategy",
    ]
    source_fields = ["sourceName", "sourceType", "sourceProtocol", "sourceUrl", "sourceProvider"]
    for field in [*import_fields, *source_fields, "movePoolSelect"]:
        assert f'id="{field}"' in body, field
        assert f'for="{field}"' in body, f"{field} needs a <label for>"


def test_proxies_script_contract():
    js = _PROXIES_JS.read_text()
    assert "'use strict';" in js
    assert not re.search(r"^\s*(import|export)\s", js, re.M), "classic script"
    assert "{{" not in js and "{%" not in js, "no Jinja in static files"
    for shared in ("function esc(", "function apiCall(", "function timeAgo(", "function showToast(",
                   "function fmtNum(", "function statusBadge(", "function protoTag("):
        assert shared not in js, f"{shared} belongs to app.js"
    assert "Poller.start(refresh, 15000)" in js
    assert "openModalFromQuery({ import: 'importModal' })" in js
    assert "history.replaceState" in js and "params.get('status')" in js
    assert "selectedIds.size > 0" in js and ".modal-overlay.active" in js, "quiet refresh"
    assert "setTimeout(" in js and "}, 300);" in js, "search keeps its 300 ms debounce"
    assert "i += 10" in js, "bulk recheck stays chunked, 10 at a time"
    for needle in ("recheckBtn.className = 'btn btn-sm'", "moveBtn.className = 'btn btn-sm'",
                   "insertBefore(recheckBtn, deleteBtn)", "insertBefore(moveBtn, deleteBtn)",
                   "deleteBtn.onclick = bulkDelete"):
        assert needle in js, needle
    for endpoint in ("/api/v1/stats/overview", "/api/v1/ips?page=", "/api/v1/ips/bulk",
                     "/api/v1/pools?per_page=100", "/api/v1/sources"):
        assert endpoint in js, endpoint
    assert "&status=${encodeURIComponent(statusFilter)}" in js
    assert "&search=${encodeURIComponent(searchQuery)}" in js
    assert "&sort_by=${sortColumn}&sort_dir=${sortDir}" in js


# ---------------------------------------------------------------------------
# Pools page (Blocks)
# ---------------------------------------------------------------------------

_POOLS_JS = _STATIC / "js" / "pages" / "pools.js"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_pools_page_structure(client):
    body = (await client.get("/pools")).text
    assert re.search(r'<script src="/static/js/pages/pools\.js\?v=[0-9a-f]+"></script>', body)
    hooks = [
        "poolsSub", "poolsTableWrap", "poolsBody", "selectAll", "poolsEmpty", "poolsError",
        "createPoolModal", "poolName", "poolStrategy", "createPoolBtn", "manageProxiesModal",
        "manageProxiesInfo", "proxyCheckboxes", "manageProxiesNote", "saveProxiesBtn",
    ]
    for hook in hooks:
        assert f'id="{hook}"' in body, hook
    assert '<table class="tbl">' in body and 'class="table-scroll"' in body
    assert "No pools yet" in body and "Could not load pools" in body
    assert body.count("openModal('createPoolModal')") == 2, "page head button + empty state button"
    for legacy in ("pool-grid", "pool-card", "pc-stat", "Create Pool"):
        assert legacy not in body, legacy


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_pools_create_modal_offers_exactly_the_supported_strategies(client):
    """least_connections is implemented in the engine but never fed; it must not be offered."""
    body = (await client.get("/pools")).text
    assert re.findall(r'<option value="([a-z_]+)"', body) == [
        "round_robin", "random", "weighted_random",
    ]
    for hint in ("sequential through healthy", "random healthy proxy", "weight-proportional"):
        assert hint in body, hint


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_pools_modals_are_labelled_dialogs(client):
    body = (await client.get("/pools")).text
    for modal_id, title_id in (
        ("createPoolModal", "createPoolTitle"),
        ("manageProxiesModal", "manageProxiesTitle"),
    ):
        pattern = (
            rf'id="{modal_id}" role="dialog" aria-modal="true" aria-labelledby="{title_id}"'
        )
        assert re.search(pattern, body), modal_id
        assert f'<h2 id="{title_id}">' in body
    assert '<label for="poolName">' in body and '<label for="poolStrategy">' in body
    assert 'aria-label="Select all pools"' in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_pools_script_ids_exist_in_page(client):
    body = (await client.get("/pools")).text
    assert_js_ids_exist("pools.js", body)


def test_pools_script_contract():
    js = _POOLS_JS.read_text()
    assert "'use strict';" in js
    assert not re.search(r"^\s*(import|export)\s", js, re.M), "classic script"
    for shared in ("function esc(", "function apiCall(", "function fmtDate(", "function showToast(",
                   "function openModal(", "function confirmAction(", "let selectedIds"):
        assert shared not in js, f"pools.js must use the app.js global, not redefine `{shared}`"
    # every endpoint the old page called
    assert "'/api/v1/pools?per_page='" in js
    assert "apiCall('POST', '/api/v1/pools'," in js
    assert "apiCall('DELETE', '/api/v1/pools/' + encodeURIComponent(id))" in js
    assert "'/api/v1/ips?per_page='" in js and "/api/v1/ips?pool_id=" in js
    assert "apiCall('POST', membersUrl, { proxy_ids: toAdd })" in js
    assert "apiCall('DELETE', membersUrl, { proxy_ids: toRemove })" in js
    # onboarding deep link /pools?new=1
    assert "openModalFromQuery({ new: 'createPoolModal' })" in js
    # loading must not toast; the status line reports outages
    load = js[js.index("async function loadPools()"):js.index("async function retryPools(")]
    assert "showToast" not in load
    # a pool name must never reach an inline handler
    assert not re.search(r"on(?:click|change)=\"[^\"]*name", js)


def test_pools_save_never_removes_a_proxy_that_was_not_listed():
    """The modal lists one page of proxies. A member that had no checkbox must survive Save."""
    js = _POOLS_JS.read_text()
    assert "listed.has(id) && !wanted.has(id)" in js


# ---------------------------------------------------------------------------
# Projects page (Blocks): list + detail, Connect
# ---------------------------------------------------------------------------

_PROJECTS_JS = _STATIC / "js" / "pages" / "projects.js"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_projects_page_structure(client):
    body = (await client.get("/projects")).text
    assert re.search(r'<script src="/static/js/pages/projects\.js\?v=[0-9a-f]+"></script>', body)
    assert 'class="split"' in body
    assert 'class="split-list" id="projectList"' in body
    assert re.search(r'class="split-detail" id="projectDetail"[^>]*style="display:none"', body)
    hooks = [
        "apiKeyAlert", "apiKeyProject", "apiKeyValue", "detailName", "detailCreated",
        "deleteProjectBtn", "connectTile", "protoSeg", "langSeg", "connectCode", "connectUser",
        "keyValue", "keyRevealBtn", "keyCopyBtn", "keyRotateBtn", "poolsTile",
        "projectPoolsTable", "projectPoolsBody", "projectPoolsEmpty", "projectsEmpty",
        "projectsError", "createProjectModal", "projectName", "createProjectBtn",
        "managePoolsModal", "managePoolsInfo", "poolCheckboxes", "savePoolsBtn",
    ]
    for hook in hooks:
        assert f'id="{hook}"' in body, hook
    assert '<table class="tbl">' in body and 'class="table-scroll"' in body
    for text in ("No projects yet", "Could not load projects", "No pools assigned"):
        assert text in body, text
    assert body.count("openModal('createProjectModal')") == 2, "page head + empty state"
    assert body.count("openManagePools()") == 2, "Pools tile head + its empty state"


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_projects_connect_block_has_both_switches_and_one_code_block(client):
    body = (await client.get("/projects")).text
    assert re.findall(r'data-proto="([a-z0-9]+)"', body) == ["http", "socks5"]
    assert re.findall(r'data-lang="([a-z]+)"', body) == ["curl", "python", "node"]
    assert body.count('class="code-block"') == 1
    # The code lives in a child element so the Copy button app.js appends to the block survives.
    assert re.search(
        r'<pre class="code-block"[^>]*><code class="mono" id="connectCode"></code></pre>', body
    )


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_projects_page_drops_the_snippet_matrix_and_bulk_selection(client):
    body = (await client.get("/projects")).text
    legacy = [
        "lang-panel", "lang-tabs", "usage-tab", "usage-section", "switchLangTab", "toggleUsage",
        "language-", "proj-card", "selectAll", "row-checkbox", "X-API-Key", "/api/v1/rotate/",
        "YOUR_API_KEY", "localhost",
    ]
    for name in legacy:
        assert name not in body, name
    for lang in ("Rust", "C#", "Java", "C++", ">Go<"):
        assert lang not in body, lang


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_projects_modals_are_labelled_dialogs(client):
    body = (await client.get("/projects")).text
    for modal_id, title_id in (
        ("createProjectModal", "createProjectTitle"),
        ("managePoolsModal", "managePoolsTitle"),
    ):
        pattern = (
            rf'id="{modal_id}" role="dialog" aria-modal="true" aria-labelledby="{title_id}"'
        )
        assert re.search(pattern, body), modal_id
        assert f'<h2 id="{title_id}">' in body
    assert '<label for="projectName">' in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_projects_script_ids_exist_in_page(client):
    body = (await client.get("/projects")).text
    assert_js_ids_exist("projects.js", body)


def test_projects_snippets_use_the_viewing_host_and_never_the_key():
    """Review Focus 4: a copied snippet must work from the machine it was copied on."""
    js = _PROJECTS_JS.read_text()
    assert "localhost" not in js and "127.0.0.1" not in js
    assert "{{" not in js and "{%" not in js, "Jinja does not run in static files"
    builder = re.search(r"\nfunction buildSnippet\(.*?\n}\n", js, re.S)
    assert builder, "projects.js must define buildSnippet()"
    body = builder.group(0)
    for needle in ("APP.host", "APP.httpPort", "APP.socks5Port", "$PROXYSM_KEY",
                   'os.environ["PROXYSM_KEY"]', "process.env.PROXYSM_KEY"):
        assert needle in body, needle
    assert "api_key" not in body, "the real key must never be written into a snippet"
    assert "window.location" not in body, "host comes from APP.host"


def test_projects_script_talks_to_the_existing_endpoints_only():
    js = _PROJECTS_JS.read_text()
    assert not re.search(r"^\s*(import|export)\s", js, re.M), "must stay a classic script"
    assert "'use strict';" in js
    found = re.findall(r"'(/api/v1/[^'?]*)", js) + re.findall(r"`(/api/v1/[^`]*)`", js)
    urls = {re.sub(r"\$\{[^}]*\}", "{id}", url) for url in found}
    assert urls == {
        "/api/v1/projects",
        "/api/v1/pools",
        "/api/v1/projects/{id}",
        "/api/v1/projects/{id}/stats",
        "/api/v1/projects/{id}/rotate-key",
        "/api/v1/projects/{id}/pools",
        "/api/v1/projects/{id}/pools/{id}",
    }
    snippet_fn = js[js.index("function renderSnippet("):js.index("function renderKey(")]
    assert "innerHTML" not in snippet_fn
    assert "proxysm.connect.proto" in js and "proxysm.connect.lang" in js
    assert "history.replaceState" in js and "get('project')" in js
    assert "openModalFromQuery({ new: 'createProjectModal' })" in js
    assert "bulkDeleteBtn" not in js and "selectedIds" not in js, "no bulk bar on this page"


# ---------------------------------------------------------------------------
# Settings page (Blocks)
# ---------------------------------------------------------------------------

_SETTINGS_JS = _STATIC / "js" / "pages" / "settings.js"

_ALERT_CONDITIONS = (
    "error_rate_above",
    "pool_below_min_healthy",
    "bandwidth_exceeded",
    "all_proxies_dead",
)


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_settings_page_structure(client):
    """Four tiles, the rules table with its loading/empty/error states, and the page script."""
    body = (await client.get("/settings")).text
    assert re.search(r'<script src="/static/js/pages/settings\.js\?v=[0-9a-f]+"></script>', body)
    assert "<h1>Settings</h1>" in body
    for hook in (
        "alerts", "alertsLoading", "alertsTable", "alertsList", "alertsEmpty", "alertsError",
        "system", "retention", "apiReference", "alertModal", "alertSaveBtn",
    ):
        assert f'id="{hook}"' in body, hook
    assert body.count('<dl class="kv">') == 3
    assert body.count("Read-only. Configured through environment variables.") == 2
    assert "No alert rules" in body
    # The in-page section menu and its scrollspy are gone.
    assert 'id="settingsNav"' not in body
    assert "set-row" not in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_settings_keeps_every_system_value(client):
    body = (await client.get("/settings")).text
    for value_id in (
        "setVersion", "setHcInterval", "setHcTimeout", "setHcConcurrency", "setHttpPort",
        "setSocksPort", "setPrometheus", "setLogRetention", "set5minRetention",
        "set1hourRetention", "setRollupInterval", "setBwFlush", "systemHint", "retentionHint",
    ):
        assert f'id="{value_id}"' in body, value_id


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_settings_links_to_interactive_api_docs(client):
    """Replaces the retired hand-written API Docs page."""
    body = (await client.get("/settings")).text
    assert '<a class="btn" href="/docs">Open Swagger UI</a>' in body
    assert '<a class="btn" href="/redoc">Open ReDoc</a>' in body
    assert "The REST API is documented interactively." in body
    assert '<span class="mono">Authorization: Bearer &lt;admin password&gt;</span>' in body
    assert 'href="/api-docs"' not in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_settings_alert_modal_is_a_labelled_dialog(client):
    body = (await client.get("/settings")).text
    assert re.search(
        r'id="alertModal"[^>]*role="dialog"[^>]*aria-modal="true"'
        r'[^>]*aria-labelledby="alertModalTitle"',
        body,
    )
    for field in (
        "alertName", "alertCondType", "alertErrThreshold", "alertErrWindow", "alertPoolSelect",
        "alertMinHealthy", "alertBwLimit", "alertActionType", "alertWebhookUrl", "alertEnabled",
    ):
        assert f'id="{field}"' in body, field
        assert re.search(rf'<label[^>]*\bfor="{field}"', body), f"no <label for> for {field}"
    # settings.js shows and hides these groups by id (COND_FIELD_GROUPS).
    for group in (
        "grpErrThreshold", "grpErrWindow", "grpPool", "grpMinHealthy", "grpBwLimit",
        "grpAllDeadHint",
    ):
        assert f'id="{group}"' in body, group
    for cond in _ALERT_CONDITIONS:
        assert f'<option value="{cond}">' in body, cond
    assert '<option value="webhook">' in body
    assert 'id="alertEditId"' in body


@pytest.mark.asyncio
@patch("src.web.routes.settings", _fake_settings)
async def test_settings_script_ids_exist_in_page(client):
    body = (await client.get("/settings")).text
    assert_js_ids_exist("settings.js", body)


def test_settings_script_is_a_classic_script_on_app_js():
    js = _SETTINGS_JS.read_text()
    assert "'use strict';" in js
    assert not re.search(r"^\s*(import|export)\s", js, re.M), "must stay a classic script"
    assert "{{" not in js and "{%" not in js, "no Jinja in static JS"
    for helper in (
        "esc", "apiCall", "showToast", "openModal", "closeModal", "confirmAction", "btnLoading",
        "btnReset", "fmtDate", "timeAgo", "statusBadge",
    ):
        assert not re.search(rf"\bfunction\s+{helper}\s*\(", js), f"must not redefine {helper}"
    assert "Poller.start" not in js, "Settings loads once and after each mutation, no polling"


def test_settings_script_keeps_the_alert_rule_contract():
    """Condition types, the config keys the evaluator reads, and create vs. PATCH."""
    js = _SETTINGS_JS.read_text()
    for cond in _ALERT_CONDITIONS:
        assert f"'{cond}'" in js, cond
    for key in ("threshold", "window_seconds", "pool_id", "min_healthy", "limit_bytes"):
        assert f"condConfig.{key} =" in js, key
    assert "apiCall('GET', '/api/v1/alerts')" in js
    assert "apiCall('GET', `/api/v1/alerts/${id}`)" in js
    assert "apiCall('POST', '/api/v1/alerts', body)" in js
    assert "apiCall('PATCH', `/api/v1/alerts/${editId}`, body)" in js
    assert "apiCall('PATCH', `/api/v1/alerts/${id}`, { is_enabled: enabled })" in js
    assert "apiCall('DELETE', `/api/v1/alerts/${id}`)" in js
    assert "apiCall('GET', '/api/v1/system/info')" in js
    assert "apiCall('GET', '/api/v1/pools?per_page=100')" in js
    assert "confirmAction(" in js
