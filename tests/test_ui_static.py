"""Contracts for the static UI assets (stylesheet, shared script, fonts)."""

import pathlib
import re

import pytest

STATIC = pathlib.Path(__file__).parent.parent / "src" / "web" / "static"
CSS = STATIC / "css" / "app.css"
FONTS = STATIC / "fonts"

SPEC_TOKENS = {
    "--ground": "#0E0E10",
    "--tile": "#1C1C21",
    "--tile-2": "#2A2A31",
    "--text": "#FAFAF7",
    "--text-2": "#E4E4E0",
    "--text-3": "#B5B5BD",
    "--lime": "#D4F26A",
    "--on-lime": "#12160A",
    "--amber": "#FFC95C",
    "--on-amber": "#1A1204",
    "--coral": "#FF8A7A",
    "--on-coral": "#1F0A07",
    "--lavender": "#C9B8FF",
    "--on-lavender": "#17122B",
    "--paper": "#FAFAF7",
    "--on-paper": "#0E0E10",
}

REQUIRED_SELECTORS = [
    ".app", ".shell-nav", ".content", ".page-head", ".tile", ".tile--lime", ".tile--amber",
    ".tile--coral", ".tile--lavender", ".tile--paper", ".tile--flush", ".tile-head", ".grid-4",
    ".grid-2", ".grid-2-1", ".kpi-val", ".chip", ".btn", ".btn-primary", ".btn-secondary",
    ".btn-outline", ".btn-danger", ".btn-ghost", ".btn-sm", ".btn-loading", ".pill", ".seg",
    ".badge-healthy", ".badge-degraded", ".badge-dead", ".badge-unknown", ".badge-quiet",
    ".badge-warn", ".badge-bad", ".tag", "table.tbl", ".meter", ".bars", ".bars__req",
    ".bars__err", ".legend", ".form-group", ".on-ground", ".modal-overlay", ".modal",
    ".modal-actions", ".confirm-modal", ".modal--wide", ".toast", ".toast-success",
    ".toast-error", ".empty-state", ".code-block", ".copy-btn", ".bulk-bar", ".pagination",
    ".alert-warning", ".split", ".split-list", ".split-detail", ".list-tile", ".onboarding",
    ".onboarding-step", ".kv", ".skeleton", ".mono", ".muted", ".sr-only", ".truncate",
    ".tile-head--wrap", "td .sub", ".check", ".check-list", ".check-list__group", ".text-warn",
    ".text-bad", ".filter-row", ".dot--healthy", ".dot--dead", ".modal-head", ".nowrap",
]


def test_stylesheet_defines_every_spec_token():
    css = CSS.read_text()
    for name, value in SPEC_TOKENS.items():
        assert re.search(rf"{re.escape(name)}:\s*{value}\s*;", css, re.I), f"{name} != {value}"


@pytest.mark.parametrize("selector", REQUIRED_SELECTORS)
def test_stylesheet_defines_component(selector):
    assert selector in CSS.read_text(), f"app.css has no rule for {selector}"


def test_stylesheet_makes_no_external_requests():
    assert not re.search(r"https?://", CSS.read_text())


def test_sidebar_footer_stays_reachable_in_short_windows():
    """The rail is viewport-pinned: without its own scrolling, Settings / Sign out get cut off."""
    css = CSS.read_text()
    rule = css[css.index("\n.shell-nav {"):]
    rule = rule[:rule.index("}")]
    assert "overflow-y: auto" in rule
    assert "100dvh" in rule


def test_nothing_widens_the_page_on_narrow_screens():
    """Two real overflow bugs found in a 390px browser while planning; keep them fixed."""
    css = CSS.read_text()
    scroll_rule = css[css.index("\n.table-scroll {"):]
    assert "position: relative" in scroll_rule[:scroll_rule.index("}")]
    narrow = css[css.index("@media (max-width: 1100px)"):]
    assert ".split { flex-direction: column; align-items: stretch; }" in narrow


def test_stylesheet_has_focus_ring_and_reduced_motion():
    css = CSS.read_text()
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


@pytest.mark.parametrize(
    "name", ["bricolage-grotesque.woff2", "figtree.woff2", "jetbrains-mono.woff2"]
)
def test_font_is_a_real_woff2(name):
    data = (FONTS / name).read_bytes()
    assert data[:4] == b"wOF2", f"{name} is not a woff2 file"
    assert len(data) > 10_000


def test_font_licenses_documented():
    text = (FONTS / "LICENSES.md").read_text()
    for family in ("Bricolage Grotesque", "Figtree", "JetBrains Mono"):
        assert family in text
    assert "SIL Open Font License" in text


APP_JS = STATIC / "js" / "app.js"

APP_JS_GLOBALS = [
    "const APP =", "async function apiCall(", "const Status =", "const Poller =",
    "function showToast(", "function openModal(", "function closeModal(",
    "function openModalFromQuery(", "function confirmAction(", "function btnLoading(",
    "function btnReset(", "async function copyToClipboard(", "function addCopyButtons(",
    "function esc(", "function fmtNum(", "function fmtBytes(", "function fmtMs(",
    "function fmtPct(", "function fmtDate(", "function timeAgo(", "function protoTag(",
    "function statusBadge(", "let selectedIds", "function toggleRowSelection(",
    "function toggleSelectAll(", "function updateSelectAll(", "function clearSelection(",
    "function updateBulkBar(", "function updateFileInput(",
]


@pytest.mark.parametrize("needle", APP_JS_GLOBALS)
def test_app_js_defines_global(needle):
    assert needle in APP_JS.read_text(), f"app.js is missing `{needle}`"


def test_app_js_is_a_classic_script_with_no_external_requests():
    js = APP_JS.read_text()
    assert not re.search(r"^\s*(import|export)\s", js, re.M), "must stay a classic script"
    assert not re.search(r"https?://", js)
    assert "hljs" not in js


def test_app_js_handles_session_expiry_and_outage():
    js = APP_JS.read_text()
    assert "resp.status === 401" in js and "/login" in js
    assert "Status.offline()" in js and "Status.ok()" in js
    assert "document.hidden" in js, "poller must pause in background tabs"


def test_esc_is_safe_inside_quoted_attributes():
    """A name like `x" onmouseover="alert(1)` must not break out of title="..."."""
    js = APP_JS.read_text()
    body = js[js.index("function esc("):js.index("function fmtNum(")]
    for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert entity in body, f"esc() does not produce {entity}"


def test_app_js_keeps_plain_http_clipboard_fallback():
    js = APP_JS.read_text()
    assert "isSecureContext" in js and "execCommand('copy')" in js


PAGES_JS = STATIC / "js" / "pages"


def assert_js_ids_exist(js_name: str, html: str) -> None:
    """Every id a page script looks up must exist in the rendered page or be created by the script.

    Catches the most common break in a markup rewrite: template and script drifting apart.
    """
    js = (PAGES_JS / js_name).read_text()
    wanted = set(re.findall(r"getElementById\(\s*'([^'$]+)'\s*\)", js))
    created = set(re.findall(r'id="([^"$]+)"', js)) | set(re.findall(r"\.id\s*=\s*'([^']+)'", js))
    missing = sorted(i for i in wanted - created if f'id="{i}"' not in html)
    assert not missing, f"{js_name} looks up ids the page does not render: {missing}"


TEMPLATES = STATIC.parent / "templates"

# Templates already rebuilt in Blocks. Each task that rewrites a template appends its file name;
# Task 13 asserts this covers every template on disk.
RESTYLED_TEMPLATES: list[str] = [
    "base.html",
    "login.html",
    "404.html",
    "dashboard.html",
    "proxies.html",
]

_CLASS_ATTR = re.compile(r'class\s*=\s*"([^"]*)"')
_INTERPOLATION = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\$\{[^}]*\}")


def _used_classes(text: str) -> set[str]:
    used: set[str] = set()
    for value in _CLASS_ATTR.findall(text):
        value = _INTERPOLATION.sub(" ", value)  # drop Jinja and ${...} first (they may hold quotes)
        value = value.split("'")[0]  # JS built with + concatenation: keep the literal prefix only
        for token in value.split():
            if re.fullmatch(r"[_a-zA-Z][\w-]*", token) and not token.endswith("-"):
                used.add(token)
    return used


@pytest.mark.parametrize("template", RESTYLED_TEMPLATES)
def test_template_and_script_use_only_defined_classes(template):
    """A class that app.css does not define is a typo or a leftover from the old design."""
    defined = set(re.findall(r"\.([_a-zA-Z][\w-]*)", CSS.read_text()))
    script_name = template.replace(".html", ".js")
    if template == "dashboard.html":
        script_name = "overview.js"
    sources = [TEMPLATES / template]
    if (PAGES_JS / script_name).exists():
        sources.append(PAGES_JS / script_name)
    for src in sources:
        unknown = sorted(_used_classes(src.read_text()) - defined)
        assert not unknown, f"{src.name} uses classes app.css does not define: {unknown}"
