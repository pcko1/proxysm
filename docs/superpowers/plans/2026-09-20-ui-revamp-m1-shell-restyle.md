# UI Revamp Milestone 1 (Shell + Restyle) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild every existing Proxysm web page in the "Blocks" look on the existing REST endpoints, with one cached stylesheet, shared and per-page static scripts, a left icon sidebar, and no external requests.

**Architecture:** Server-rendered Jinja templates keep only markup. All CSS moves to `static/css/app.css`; shared helpers to `static/js/app.js`; each screen's logic to `static/js/pages/<page>.js` loaded as a classic script (functions stay global because templates use inline `onclick`). A dev-only preview server serves the real templates against canned API fixtures so the UI can be run and smoke-tested without Postgres or Redis. No REST endpoint changes in this milestone.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, vanilla JS (no build step, no npm), pytest + httpx `ASGITransport`, ruff.

**Spec:** `docs/superpowers/specs/2026-09-20-ui-revamp-blocks-design.md` (read "Visual system", "Frontend architecture", "Routes", "Screens", and "Milestones" item 1). **Mockups:** `docs/design/ui-revamp-blocks/*.dc.html` are the visual source of truth. They only render inside the Claude Design canvas, so read their inline styles for exact sizes and colours.

**Verified:** every code block in this plan was applied, in order, to a throwaway worktree of `design/ui-revamp` while the plan was written: the suite went from 217 to about 420 passing tests, the touched files lint clean, every script passes `node --check`, and each page was opened through the Task 3 preview server. If a step's expected result does not match what you see, suspect a transcription slip before suspecting the plan.

**Deliberate differences from the spec:** (1) static URLs carry a token derived from the newest static file's mtime rather than the app version, so browsers refetch exactly when an asset changes; (2) the sidebar ships without the Search pill and the Requests item, which arrive with their milestones (M5, M3); (3) Task 12 fixes one backend bug although the milestone is otherwise frontend-only; (4) per-project numbers are labelled "Requests", not "Requests 24h", because `GET /projects/{id}/stats` sums every retained 5-minute rollup (7 days by default); (5) the Projects and Proxies pages poll so that the status line stays truthful and the page recovers from an outage without a reload.

## Global Constraints

- Branch: work on `design/ui-revamp` (already exists). Commit after every task with a conventional-commit message ending with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- No REST endpoint, schema, model or migration changes, with one exception: Task 12 fixes a one-line bug in `src/api/proxies.py` that makes every Recheck fail today. The only other Python files touched are `src/web/routes.py`, `scripts/ui_preview.py`, `scripts/ui_preview_fixtures.py`, `scripts/fetch_fonts.py` and tests.
- No SPA, framework, bundler or npm. Classic scripts only; no `type="module"`.
- Zero external requests from any rendered page: no CDN, no Google Fonts link, no highlight.js. Fonts are self-hosted woff2.
- Dark only. Tokens, verbatim from the spec: `--ground #0E0E10`, `--tile #1C1C21`, `--tile-2 #2A2A31`, `--text #FAFAF7`, `--text-2 #E4E4E0`, `--text-3 #B5B5BD`, `--lime #D4F26A` / on-lime `#12160A`, `--amber #FFC95C` / on-amber `#1A1204`, `--coral #FF8A7A` / on-coral `#1F0A07`, `--lavender #C9B8FF` / on-lavender `#17122B`, `--paper #FAFAF7` (text on paper `#0E0E10`).
- Radii: tiles 28px, inner blocks 20px, selected table row 14px, every control 999px.
- Type: Bricolage Grotesque 700 (page titles 44px, tile numerals 60px, section titles 22px); Figtree 500/600/700 at 14px for everything else; JetBrains Mono 500/600 for host:port, keys, code. `font-variant-numeric: tabular-nums` globally.
- Colour carries status only. A coloured fill always has dark ("on-") text. Never put `--text` on lime, amber, coral, lavender or paper.
- Every string that came from the API is passed through `esc()` before it is interpolated into HTML.
- Every interactive element is a real `<button>`, `<a href>`, `<input>`+`<label>` or `<select>`+`<label>`; icon-only buttons carry `aria-label`.
- Python style: ruff, line length 100, double quotes. The repo has a pre-existing baseline of about 120 ruff errors in files this plan does not own; do not fix them. Lint only the files you touch: `uv run ruff check --output-format concise <files>` must report nothing for them.
- Run tests with `uv run pytest tests/ -q`. The suite must be green at the end of every task.
- Run the tasks in order. Tasks 7-11 (the five pages) do not depend on each other, but each appends to the same two lists in the tests (`RESTYLED_PAGES`, `RESTYLED_TEMPLATES`): keep entries other tasks added, and keep `RESTYLED_TEMPLATES` one entry per line so it never exceeds the line limit.
- The Playwright MCP browser, if you use it for smoke checks, is shared between agents: another agent's navigation can land in your tab. Re-check `location.href` before trusting a screenshot, and restore the window to 1440x900 when you are done.
- Deferred on purpose (later milestones; do not build): Search pill and Cmd+K palette (M5), Requests page and its nav item (M3), proxy detail panel (M3), "Needs attention" and "vs 1h ago" chips (M3), project Limits and quota bars (M4), project "Last 24h" (M3), Pools list + detail and any rename/weight/order editing (M2).

## Review Focus

Failure modes the spec implies that are most likely to bite an operator. Each is pinned by a pytest assertion where the server can see it, otherwise by a named step in a task's smoke check (run against the preview server, which has `normal`, `empty` and `offline` scenarios for exactly this purpose).

1. **API down or returning 500 while a page polls.** Expected: sidebar status turns coral "Offline, retrying"; tiles keep their last values or show "—"; no toast every 10 seconds; recovery flips the status back without a reload. Pinned: Task 3 tests the `offline` scenario returns 503; Task 7 smoke step "offline".
2. **Brand-new empty instance.** Expected: onboarding card visible, every table shows its empty state, no `NaN`, `undefined`, `Infinity` or `null` text anywhere, percentages over zero totals render "—". Pinned: `fmtPct` contract in Task 2; Task 7-11 smoke step "empty" greps the rendered DOM text for those four words.
3. **Hostile or long names** (project, pool, provider, source names up to 255 chars, names containing `<script>`). Expected: rendered as text, truncated with an ellipsis, never breaking the grid. Pinned: fixtures include one such name (Task 3); each page smoke step asserts no element overflows its tile and no alert fired.
4. **Plain-HTTP origin** (the node2 instance is reached over plain HTTP on the LAN). Expected: every Copy button works through the textarea fallback; connection snippets show the viewing host, not `localhost`. Pinned: Task 2 keeps `copyToClipboard` fallback; Task 10 asserts snippets are built from `APP.host`.
5. **Expired session during a poll.** Expected: one redirect to `/login`, no loop, no offline flash. Pinned: Task 2 test `test_app_js_handles_session_expiry_and_outage`; the existing test that every page 302s to `/login` without a cookie (kept in Task 5).
6. **Narrow or short viewport and keyboard-only use.** Expected: below 720px the nav collapses behind a menu button; in a short window (for example 1440x560, or a zoomed browser) the sidebar scrolls on its own so Settings and Sign out are always reachable; Tab reaches every control with a visible lime focus ring; Esc closes any modal. Pinned: Task 1 test `test_sidebar_footer_stays_reachable_in_short_windows`; Task 4 and Task 13 smoke steps at 1440x560, at 390px and keyboard-only.

---

## File Structure

```
scripts/
  fetch_fonts.py               NEW  one-off downloader for the three OFL woff2 files (provenance)
  ui_preview.py                NEW  dev-only server: real templates + static + canned /api/v1
  ui_preview_fixtures.py       NEW  canned API bodies (normal + empty)
src/api/proxies.py             MOD  one-line fix: recheck endpoint unpacks the checker's 3-tuple (Task 12)
src/web/
  routes.py                    MOD  asset version in context; /api-docs and /setup become redirects
  static/
    css/app.css                NEW  tokens + every component (the only stylesheet)
    js/app.js                  NEW  shared helpers: apiCall, Status, Poller, toasts, modals, formatters...
    js/pages/overview.js       NEW  Overview logic
    js/pages/proxies.js        NEW  Proxies logic (ported)
    js/pages/pools.js          NEW  Pools logic (ported)
    js/pages/projects.js       NEW  Projects logic (list + detail, Connect)
    js/pages/settings.js       NEW  Settings logic (ported)
    fonts/bricolage-grotesque.woff2, figtree.woff2, jetbrains-mono.woff2   NEW
    fonts/LICENSES.md          NEW
    fonts/geist.woff2, geist-mono.woff2                                   DELETED (Task 13)
  templates/
    base.html                  REWRITTEN  sidebar shell, no inline CSS/JS
    dashboard.html             REWRITTEN  Overview markup only
    proxies.html, pools.html, projects.html, settings.html   REWRITTEN  markup only
    login.html, 404.html       REWRITTEN
    api-docs.html, setup.html  DELETED
tests/
  test_web_routes.py           MOD  static mount, nav, redirects, per-page hooks
  test_ui_static.py            NEW  stylesheet/script/fonts contracts, no external URLs, id consistency
  test_ui_preview.py           NEW  preview server scenarios
  test_api_proxies.py          MOD  regression test for the recheck endpoint (Task 12)
```

---

### Task 1: Fonts and the stylesheet

**Files:**
- Create: `scripts/fetch_fonts.py`
- Create: `src/web/static/fonts/bricolage-grotesque.woff2`, `figtree.woff2`, `jetbrains-mono.woff2`, `LICENSES.md`
- Create: `src/web/static/css/app.css`
- Create: `tests/test_ui_static.py`

**Interfaces:**
- Consumes: nothing.
- Produces: the CSS class vocabulary below. Later tasks may use ONLY these classes plus inline `style=""` for one-off grid column templates and widths. If a later task needs a new component, it adds the rule to `app.css` in its own commit and says so.

| Class | Element | Purpose |
|---|---|---|
| `.app`, `.shell-nav`, `.content` | shell | set by `base.html` only |
| `.page-head` > `h1` + `.page-head__sub` + `.page-head__actions` | div | page title row |
| `.tile` (+ `--lime`, `--amber`, `--coral`, `--lavender`, `--paper`, `--flush`) | section | 28px block; `--flush` = no padding (tables that manage their own) |
| `.tile-head` (+ `--wrap`) > `h2` (+ `.tile-head__meta`) | div | tile title row; `--wrap` lets a long meta text drop under the title |
| `.grid-4`, `.grid-2`, `.grid-2-1` | div | 4 equal / 2 equal / 2fr 1fr, gap 14px |
| `.kpi` > `.kpi-top`, `.kpi-val` (+ `.kpi-unit`), `.kpi-foot`; `.chip` | inside `.tile` | big-number tile; `.chip` is the small pill top-right |
| `.btn` + `.btn-primary` (lime) / `.btn-secondary` (tile) / `.btn-outline` (tile-2) / `.btn-danger` (coral text) / `.btn-ghost`; `.btn-sm`; `.btn-loading` | button, a | pill buttons |
| `.filter-row` > field + `.pill` (+ `.active`) > `.dot` (+ `.dot--healthy` / `--degraded` / `--dead` / `--unknown`), `.count` | div, button | wrapping filter line; filter pill with an optional status-coloured dot |
| `.seg` > button (+ `.active`) | div | segmented switch |
| `.badge` + `.badge-healthy` / `-degraded` / `-dead` / `-unknown` / `-quiet` / `-warn` / `-bad` | span | status pill, solid fill |
| `.tag` + `.tag-http` / `-https` / `-socks5` | span | protocol label |
| `.table-scroll` > `table.tbl`; `tr.selected`; `td.num`, `th.num`; `td.actions`; `th.sortable`; `td .sub` | table | data tables; `.sub` is a 12px muted second line inside a cell |
| `.meter` (+ `--lime`, `--amber`, `--coral`, `--paper`) > `i` | div | horizontal bar; set `style="width:NN%"` on `<i>` |
| `.bars` > `.bars__col` > `.bars__err` + `.bars__req` (+ `.is-now`) ; `.bars__axis` | div | stacked bar chart |
| `.legend` > `span` > `i` | div | chart legend |
| `.check` (label wrapping a checkbox + text); `.check-list` > `label` (+ `.check-list__group`) | label, div | single checkbox row; scrollable checkbox list for modals |
| `label`, `.form-group`, inputs, `textarea`, `select`; `.on-ground` | form | fields are pills on `--ground`; add `.on-ground` when the field sits directly on the page ground so it uses `--tile` |
| `.modal-overlay` (+ `.active`) > `.modal` > `h2` … `.modal-actions`; `.confirm-modal`; `.modal--wide`; `.modal-head` | div | dialogs; `.modal-head` = title row with an action on the right |
| `.toast-container`, `.toast`, `.toast-success`, `.toast-error` | div | toasts |
| `.empty-state` > `.empty-state-icon`, `h3`, `p` | div | empty states |
| `.code-block`, `.copy-btn` | pre/div, button | snippets |
| `.bulk-bar` (+ `.visible`) | div | bulk action bar |
| `.pagination`, `.pagination-info` | div | pager |
| `.alert-warning` | div | amber notice (new API key) |
| `.split` > `.split-list` + `.split-detail`; `.list-tile` (+ `.active`) | div, button | list + detail layout |
| `.onboarding` > `.onboarding-step` (+ `.done`) | section, a | first-run card |
| `.kv` > `dt`, `dd` | dl | label/value grid |
| `.skeleton`, `.mono`, `.muted`, `.strong`, `.text-warn`, `.text-bad`, `.sr-only`, `.row`, `.spacer`, `.truncate`, `.nowrap` | any | utilities; `.text-warn` / `.text-bad` colour a number amber / coral on a dark tile |

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ui_static.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_static.py -q`
Expected: every test FAILS with `FileNotFoundError` (no `app.css`, no fonts).

- [ ] **Step 3: Add the font downloader and fetch the fonts**

Create `scripts/fetch_fonts.py`:

```python
"""Download the three OFL UI fonts as latin-subset variable woff2 files.

One-off provenance script: the woff2 files are committed, so this only needs to run
again if a font is updated. Uses the Google Fonts CSS API with a modern browser
User-Agent (that is what makes it return woff2), and takes the block marked `latin`.

Usage: python scripts/fetch_fonts.py
"""

import pathlib
import re
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
OUT = pathlib.Path(__file__).parent.parent / "src" / "web" / "static" / "fonts"
FONTS = {
    "bricolage-grotesque.woff2": "Bricolage+Grotesque:opsz,wght@12..96,400..800",
    "figtree.woff2": "Figtree:wght@400..700",
    "jetbrains-mono.woff2": "JetBrains+Mono:wght@500..600",
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, family in FONTS.items():
        css = _get(f"https://fonts.googleapis.com/css2?family={family}&display=swap").decode()
        match = re.search(r"/\* latin \*/\s*@font-face\s*{[^}]*?url\((https://[^)]+\.woff2)\)", css)
        if match is None:
            raise SystemExit(f"no latin woff2 block found for {family}")
        data = _get(match.group(1))
        if data[:4] != b"wOF2":
            raise SystemExit(f"{family}: not a woff2 file")
        (OUT / filename).write_bytes(data)
        print(f"{filename}: {len(data):,} bytes")


if __name__ == "__main__":
    main()
```

Run: `uv run python scripts/fetch_fonts.py`
Expected: three lines, each `<name>.woff2: NN,NNN bytes` with sizes between 20,000 and 200,000.

Create `src/web/static/fonts/LICENSES.md`:

```markdown
# Bundled fonts

All three families are licensed under the SIL Open Font License 1.1
(https://openfontlicense.org). Latin subset, variable weight, fetched with
`scripts/fetch_fonts.py`.

| File | Family | Source |
|---|---|---|
| `bricolage-grotesque.woff2` | Bricolage Grotesque (opsz 12-96, wght 400-800) | https://github.com/ateliertriay/bricolage |
| `figtree.woff2` | Figtree (wght 400-700) | https://github.com/erikdkennedy/figtree |
| `jetbrains-mono.woff2` | JetBrains Mono (wght 500-600) | https://github.com/JetBrains/JetBrainsMono |
```

- [ ] **Step 4: Write the stylesheet**

Create `src/web/static/css/app.css` with exactly this content:

```css
/* Proxysm "Blocks" design system.
   Spec: docs/superpowers/specs/2026-09-20-ui-revamp-blocks-design.md
   This is the only stylesheet. Colour carries status only; a coloured fill
   always takes its dark "on-" text colour. */

@font-face {
    font-family: "Bricolage Grotesque";
    font-style: normal;
    font-weight: 400 800;
    font-display: optional;
    src: url("/static/fonts/bricolage-grotesque.woff2") format("woff2");
}
@font-face {
    font-family: "Figtree";
    font-style: normal;
    font-weight: 400 700;
    font-display: optional;
    src: url("/static/fonts/figtree.woff2") format("woff2");
}
@font-face {
    font-family: "JetBrains Mono";
    font-style: normal;
    font-weight: 500 600;
    font-display: optional;
    src: url("/static/fonts/jetbrains-mono.woff2") format("woff2");
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
[hidden] { display: none !important; }

:root {
    --ground: #0E0E10;
    --tile: #1C1C21;
    --tile-2: #2A2A31;
    --text: #FAFAF7;
    --text-2: #E4E4E0;
    --text-3: #B5B5BD;
    --lime: #D4F26A;
    --on-lime: #12160A;
    --amber: #FFC95C;
    --on-amber: #1A1204;
    --coral: #FF8A7A;
    --on-coral: #1F0A07;
    --lavender: #C9B8FF;
    --on-lavender: #17122B;
    --paper: #FAFAF7;
    --on-paper: #0E0E10;
    --r-tile: 28px;
    --r-block: 20px;
    --r-row: 14px;
    --r-pill: 999px;
    --font-display: "Bricolage Grotesque", system-ui, sans-serif;
    --font-body: "Figtree", system-ui, -apple-system, "Segoe UI", sans-serif;
    --font-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Consolas, monospace;
    --ease: 0.14s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Dark from the first frame: no white flash between pages */
html { background: var(--ground); color-scheme: dark; }

body {
    min-height: 100vh;
    font-family: var(--font-body);
    font-size: 14px;
    font-weight: 500;
    line-height: 1.45;
    color: var(--text);
    background: var(--ground);
    font-variant-numeric: tabular-nums;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

a { color: var(--lime); text-decoration: none; }
a:hover { color: #E6FA9C; }
h1, h2, h3 { font-family: var(--font-display); font-weight: 700; color: var(--text); }

:focus-visible { outline: 2px solid var(--lime); outline-offset: 2px; border-radius: 6px; }
.tile--lime :focus-visible, .tile--amber :focus-visible, .tile--coral :focus-visible,
.tile--lavender :focus-visible, .tile--paper :focus-visible { outline-color: var(--on-paper); }

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--tile-2); border-radius: 4px; }

/* ===== Shell ===== */
.app { display: flex; min-height: 100vh; }
.content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding: 28px 36px 40px 12px;
    max-width: 1560px;
}

/* Named shell-nav (not side-nav) because the old Settings template defines its own .side-nav.
   The rail is pinned to the viewport, so it must scroll by itself when the window is shorter
   than its content; otherwise Settings and Sign out can never be reached. */
.shell-nav {
    position: sticky;
    top: 0;
    flex-shrink: 0;
    width: 248px;
    height: 100vh;
    height: 100dvh;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: none;
    display: flex;
    flex-direction: column;
    gap: 22px;
    padding: 28px 16px 28px 20px;
    view-transition-name: shell-nav;
}
.shell-nav__brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 8px;
    color: var(--text);
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.04em;
}
.shell-nav__brand:hover { color: var(--text); }
.shell-nav__mark {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 12px;
    background: var(--lime);
}
.shell-nav__links, .shell-nav__foot { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
.shell-nav__foot { margin-top: auto; padding-top: 12px; }
.shell-nav a.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    height: 46px;
    padding: 0 16px;
    border-radius: var(--r-pill);
    color: var(--text-3);
    font-weight: 600;
    transition: background var(--ease), color var(--ease);
}
.shell-nav a.nav-item svg { flex-shrink: 0; }
.shell-nav a.nav-item:hover { color: var(--text); background: var(--tile); }
.shell-nav a.nav-item.active { color: var(--on-paper); background: var(--paper); }
.shell-nav__status {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 32px;
    padding: 0 16px;
    color: var(--text-3);
}
.shell-nav__status .dot { flex-shrink: 0; width: 8px; height: 8px; border-radius: 50%; background: var(--lime); }
.shell-nav__status.is-offline { color: var(--coral); }
.shell-nav__status.is-offline .dot { background: var(--coral); }
.shell-nav__toggle {
    display: none;
    margin-left: auto;
    width: 40px;
    height: 40px;
    border: 0;
    border-radius: 50%;
    background: var(--tile);
    color: var(--text);
    cursor: pointer;
}

@view-transition { navigation: auto; }
@media (prefers-reduced-motion: reduce) {
    ::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) { animation: none !important; }
}

/* ===== Page head ===== */
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.page-head h1 { font-size: 44px; letter-spacing: -0.045em; line-height: 1; }
.page-head__sub { margin-left: 14px; color: var(--text-3); }
.page-head__title { display: flex; align-items: baseline; flex-wrap: wrap; row-gap: 6px; }
.page-head__actions { display: flex; align-items: center; gap: 6px; }

/* ===== Tiles ===== */
.tile { padding: 22px 26px; border-radius: var(--r-tile); background: var(--tile); color: var(--text); min-width: 0; }
.tile--flush { padding: 0; overflow: hidden; }
.tile--lime { background: var(--lime); color: var(--on-lime); }
.tile--amber { background: var(--amber); color: var(--on-amber); }
.tile--coral { background: var(--coral); color: var(--on-coral); }
.tile--lavender { background: var(--lavender); color: var(--on-lavender); }
.tile--paper { background: var(--paper); color: var(--on-paper); }
.tile--lime h2, .tile--amber h2, .tile--coral h2, .tile--lavender h2, .tile--paper h2 { color: inherit; }
.tile-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px 16px; margin-bottom: 14px; }
.tile-head h2 { font-size: 22px; letter-spacing: -0.03em; }
.tile-head__meta { color: var(--text-3); }
/* Tile head whose meta text drops under the title instead of squeezing it */
.tile-head--wrap { flex-wrap: wrap; row-gap: 4px; }

.grid-4 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.grid-2-1 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 14px; }

.kpi { display: flex; flex-direction: column; justify-content: space-between; gap: 18px; min-height: 176px; }
.kpi-top { display: flex; align-items: center; justify-content: space-between; font-weight: 600; }
.kpi-val { font-family: var(--font-display); font-size: 60px; font-weight: 700; letter-spacing: -0.05em; line-height: 0.9; }
.kpi-unit { margin-left: 8px; font-family: var(--font-body); font-size: 14px; font-weight: 600; letter-spacing: 0; }
.kpi-foot { font-weight: 500; opacity: 0.8; }
.chip { padding: 4px 10px; border-radius: var(--r-pill); background: rgba(0, 0, 0, 0.10); font-size: 13px; font-weight: 600; }
.tile:not([class*="tile--"]) .chip { background: var(--tile-2); }

/* ===== Buttons ===== */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 40px;
    padding: 0 18px;
    border: 0;
    border-radius: var(--r-pill);
    background: var(--tile-2);
    color: var(--text);
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition: filter var(--ease), background var(--ease), color var(--ease);
}
.btn:hover { filter: brightness(1.12); color: var(--text); }
.btn:active { transform: scale(0.98); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; filter: none; transform: none; }
.btn-primary, .btn-primary:hover { background: var(--lime); color: var(--on-lime); font-weight: 700; }
.btn-secondary { background: var(--tile); }
.btn-outline { background: var(--tile-2); }
.btn-danger, .btn-danger:hover { background: var(--tile-2); color: var(--coral); }
.btn-danger:hover { background: var(--coral); color: var(--on-coral); filter: none; }
.btn-ghost { background: transparent; color: var(--text-3); }
.btn-ghost:hover { background: var(--tile-2); filter: none; }
.btn-sm { height: 32px; padding: 0 14px; font-size: 13px; }
.tile--paper .btn, .tile--lime .btn, .tile--amber .btn, .tile--coral .btn, .tile--lavender .btn {
    background: rgba(0, 0, 0, 0.12);
    color: inherit;
}
.btn-loading { position: relative; color: transparent !important; pointer-events: none; }
.btn-loading::after {
    content: "";
    position: absolute;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: var(--text);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}
.btn-primary.btn-loading::after { border-color: rgba(18, 22, 10, 0.25); border-top-color: var(--on-lime); }
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== Filter pills and segmented switch ===== */
.pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 40px;
    padding: 0 16px;
    border: 0;
    border-radius: var(--r-pill);
    background: var(--tile);
    color: var(--text-3);
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background var(--ease), color var(--ease);
}
.pill:hover { color: var(--text); }
.pill.active { background: var(--paper); color: var(--on-paper); }
.pill .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.pill .dot--healthy { background: var(--lime); }
.pill .dot--degraded { background: var(--amber); }
.pill .dot--dead { background: var(--coral); }
.pill .dot--unknown { background: #6A6A74; }
/* Search field + filter pills on one wrapping line */
.filter-row { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.pill .count { opacity: 0.65; }
.seg { display: inline-flex; gap: 4px; }
.seg button {
    height: 36px;
    padding: 0 16px;
    border: 0;
    border-radius: var(--r-pill);
    background: var(--tile);
    color: var(--text-3);
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}
.tile .seg button { background: var(--tile-2); }
.seg button:hover { color: var(--text); }
.seg button.active, .tile .seg button.active { background: var(--paper); color: var(--on-paper); }

/* ===== Badges and tags ===== */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 11px;
    border-radius: var(--r-pill);
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
}
.badge-healthy { background: var(--lime); color: var(--on-lime); }
.badge-degraded, .badge-warn { background: var(--amber); color: var(--on-amber); }
.badge-dead, .badge-bad { background: var(--coral); color: var(--on-coral); }
.badge-unknown, .badge-quiet { background: var(--tile-2); color: var(--text-3); }
.badge-quiet { color: var(--text-2); font-weight: 600; }
.tag { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em; color: var(--text-3); }

/* ===== Tables ===== */
/* position: relative so absolutely positioned children (.sr-only headers) are clipped by this
   scroll box instead of widening the whole page on narrow screens. */
.table-scroll { position: relative; overflow-x: auto; -webkit-overflow-scrolling: touch; }
table.tbl { width: 100%; min-width: 640px; border-collapse: separate; border-spacing: 0; }
table.tbl th {
    height: 40px;
    padding: 0 12px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-3);
    white-space: nowrap;
}
table.tbl td {
    height: 50px;
    padding: 0 12px;
    border-top: 1px solid var(--tile-2);
    color: var(--text-2);
    vertical-align: middle;
}
table.tbl th:first-child, table.tbl td:first-child { padding-left: 0; }
table.tbl th:last-child, table.tbl td:last-child { padding-right: 0; }
table.tbl th.num, table.tbl td.num { text-align: right; }
table.tbl td .strong, table.tbl td.strong { color: var(--text); font-weight: 700; }
table.tbl td .sub { display: block; font-size: 12px; font-weight: 500; color: var(--text-3); }
table.tbl td.actions { text-align: right; white-space: nowrap; }
table.tbl td.actions .btn + .btn { margin-left: 4px; }
table.tbl tbody tr:hover td { background: rgba(255, 255, 255, 0.025); }
table.tbl tbody tr.selected td { background: var(--tile-2); border-top-color: transparent; }
table.tbl tbody tr.selected td:first-child { border-radius: var(--r-row) 0 0 var(--r-row); padding-left: 12px; }
table.tbl tbody tr.selected td:last-child { border-radius: 0 var(--r-row) var(--r-row) 0; padding-right: 12px; }
table.tbl th.sortable { cursor: pointer; user-select: none; }
table.tbl th.sortable:hover, table.tbl th.sortable.sorted { color: var(--text); }
th.col-check, td.col-check { width: 30px; }
.row-checkbox { width: 16px; height: 16px; accent-color: var(--lime); cursor: pointer; vertical-align: middle; }

/* ===== Meters, bar chart, legend ===== */
.meter { height: 12px; border-radius: 6px; background: var(--tile-2); overflow: hidden; }
.meter > i { display: block; height: 100%; border-radius: 6px; background: var(--paper); }
.meter--lime > i { background: var(--lime); }
.meter--amber > i { background: var(--amber); }
.meter--coral > i { background: var(--coral); }
.tile--paper .meter { background: #DEDED8; }
.tile--paper .meter > i { background: var(--on-paper); }
.bars { display: flex; align-items: flex-end; gap: 8px; height: 190px; }
.bars__col { flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: flex-end; gap: 3px; height: 100%; }
.bars__req { border-radius: 8px; background: var(--paper); min-height: 2px; }
.bars__req.is-now { background: var(--lime); }
.bars__err { border-radius: 6px; background: var(--coral); }
.bars__axis { display: flex; justify-content: space-between; margin-top: 12px; font-size: 13px; color: var(--text-3); }
.legend { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 18px; color: var(--text-3); }
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.legend i { width: 10px; height: 10px; border-radius: 4px; background: var(--paper); }
.legend i.err { background: var(--coral); }

/* ===== Forms ===== */
label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600; color: var(--text-3); }
.form-group { margin-bottom: 18px; }
input[type="text"], input[type="search"], input[type="password"], input[type="number"],
input[type="url"], select, textarea {
    width: 100%;
    height: 44px;
    padding: 0 18px;
    border: 0;
    border-radius: var(--r-pill);
    background: var(--ground);
    color: var(--text);
    font-family: inherit;
    font-size: 14px;
    font-weight: 500;
}
textarea { height: auto; min-height: 120px; padding: 14px 18px; border-radius: var(--r-block); resize: vertical; line-height: 1.5; }
select { cursor: pointer; font-weight: 600; }
input::placeholder, textarea::placeholder { color: var(--text-3); opacity: 0.75; }
.on-ground { background: var(--tile) !important; height: 40px !important; }
.file-input-wrapper { position: relative; display: flex; align-items: center; gap: 10px; }
.file-input-wrapper input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.file-input-wrapper:focus-within { outline: 2px solid var(--lime); outline-offset: 2px; border-radius: var(--r-pill); }
.file-input-name { color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.form-hint { margin-top: 6px; font-size: 13px; color: var(--text-3); }
/* Checkbox with its text label on one line */
.check { display: flex; align-items: center; gap: 10px; margin: 0; color: var(--text-2); cursor: pointer; }
.check input { flex-shrink: 0; width: 18px; height: 18px; accent-color: var(--lime); cursor: pointer; }
/* Scrollable checkbox list inside a modal (not .row-checkbox: that one is wired to table selection) */
.check-list { display: flex; flex-direction: column; gap: 2px; max-height: 46vh; overflow-y: auto; }
.check-list > * { flex-shrink: 0; }
.check-list label {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 40px;
    margin: 0;
    padding: 0 12px;
    border-radius: var(--r-row);
    color: var(--text-2);
    font-weight: 500;
    cursor: pointer;
}
.check-list label:hover { background: var(--tile-2); }
.check-list input[type="checkbox"] { flex-shrink: 0; width: 16px; height: 16px; accent-color: var(--lime); cursor: pointer; }
.check-list .check-list__group { position: sticky; top: 0; z-index: 1; margin-top: 10px; background: var(--tile); color: var(--text); font-weight: 700; }
.check-list .check-list__group:first-child { margin-top: 0; }

/* ===== Modals ===== */
.modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 200;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 16px;
    background: rgba(6, 6, 7, 0.78);
}
.modal-overlay.active { display: flex; }
.modal {
    width: 100%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
    padding: 28px;
    border-radius: var(--r-tile);
    background: var(--tile);
    box-shadow: 0 32px 80px rgba(0, 0, 0, 0.6);
    animation: modal-in 0.18s ease;
}
.modal--wide { max-width: 860px; }
.modal h2 { margin-bottom: 20px; font-size: 26px; letter-spacing: -0.03em; }
/* Modal title with an action on the right (the Sources modal) */
.modal-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.modal-head h2 { margin-bottom: 0; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }
.confirm-modal .modal { max-width: 400px; text-align: center; }
.confirm-modal .confirm-message { color: var(--text-3); }
.confirm-modal .modal-actions { justify-content: center; }
@keyframes modal-in { from { opacity: 0; transform: translateY(8px) scale(0.98); } to { opacity: 1; transform: none; } }

/* ===== Toasts ===== */
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 300; display: flex; flex-direction: column; gap: 8px; }
.toast {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 260px;
    max-width: 420px;
    padding: 12px 18px;
    border-radius: var(--r-block);
    font-weight: 600;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
    animation: toast-in 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-success { background: var(--lime); color: var(--on-lime); }
.toast-error { background: var(--coral); color: var(--on-coral); }
@keyframes toast-in { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: none; } }

/* ===== Empty state, code, misc blocks ===== */
.empty-state { padding: 48px 24px; text-align: center; color: var(--text-3); }
.empty-state-icon { margin-bottom: 12px; opacity: 0.6; }
.empty-state h3 { margin-bottom: 6px; font-size: 20px; letter-spacing: -0.02em; }
.empty-state .btn { margin-top: 16px; }
.code-block {
    position: relative;
    padding: 18px 20px;
    border-radius: var(--r-block);
    background: var(--ground);
    color: var(--text-2);
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 500;
    line-height: 1.75;
    white-space: pre;
    overflow-x: auto;
}
.copy-btn {
    height: 32px;
    padding: 0 14px;
    border: 0;
    border-radius: var(--r-pill);
    background: var(--paper);
    color: var(--on-paper);
    font-family: var(--font-body);
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
}
.code-block > .copy-btn { position: absolute; top: 12px; right: 12px; }
.alert-warning {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 18px 22px;
    border-radius: var(--r-block);
    background: var(--amber);
    color: var(--on-amber);
    font-weight: 600;
}
.alert-warning code { padding: 2px 8px; border-radius: 8px; background: rgba(0, 0, 0, 0.12); font-family: var(--font-mono); word-break: break-all; }
.alert-warning .btn, .alert-warning .copy-btn { background: var(--on-amber); color: var(--text); }
.bulk-bar {
    position: fixed;
    left: 50%;
    bottom: 24px;
    z-index: 150;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px 10px 22px;
    border-radius: var(--r-pill);
    background: var(--paper);
    color: var(--on-paper);
    font-weight: 700;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
    opacity: 0;
    pointer-events: none;
    transform: translate(-50%, 80px);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s;
}
.bulk-bar.visible { opacity: 1; pointer-events: auto; transform: translate(-50%, 0); }
.bulk-bar .btn { height: 34px; background: rgba(0, 0, 0, 0.10); color: var(--on-paper); }
.bulk-bar .btn-danger { background: var(--coral); color: var(--on-coral); }
.pagination { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-top: 14px; color: var(--text-3); }
.pagination-info { font-size: 13px; }

/* ===== List + detail ===== */
.split { display: flex; align-items: flex-start; gap: 14px; }
.split-list { flex-shrink: 0; width: 380px; display: flex; flex-direction: column; gap: 14px; }
.split-detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.list-tile {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    padding: 20px 24px;
    border: 0;
    border-radius: var(--r-tile);
    background: var(--tile);
    color: var(--text);
    font-family: inherit;
    font-size: 14px;
    text-align: left;
    cursor: pointer;
}
.list-tile h3 { font-size: 24px; letter-spacing: -0.03em; color: inherit; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.list-tile .muted { color: inherit; opacity: 0.75; font-weight: 600; }
.list-tile.active { background: var(--paper); color: var(--on-paper); }

/* ===== Onboarding ===== */
.onboarding { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
.onboarding__text { flex: 1; min-width: 240px; }
.onboarding__text h2 { font-size: 22px; letter-spacing: -0.03em; margin-bottom: 4px; }
.onboarding__steps { display: flex; gap: 8px; flex-wrap: wrap; }
.onboarding-step {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    height: 44px;
    padding: 0 18px 0 8px;
    border-radius: var(--r-pill);
    background: rgba(0, 0, 0, 0.12);
    color: inherit;
    font-weight: 700;
}
.onboarding-step:hover { color: inherit; background: rgba(0, 0, 0, 0.2); }
.onboarding-step .num { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--on-lavender); color: var(--lavender); }
.onboarding-step.done { opacity: 0.55; text-decoration: line-through; }

/* ===== Utilities ===== */
.kv { display: grid; grid-template-columns: 180px minmax(0, 1fr); column-gap: 16px; row-gap: 14px; align-items: center; }
.kv dt { color: var(--text-3); font-weight: 600; }
.kv dd { color: var(--text); min-width: 0; }
.mono { font-family: var(--font-mono); font-size: 13px; font-weight: 500; }
.muted { color: var(--text-3); }
.text-warn { color: var(--amber); }
.text-bad { color: var(--coral); }
.strong { color: var(--text); font-weight: 700; }
.row { display: flex; align-items: center; gap: 10px; }
.spacer { flex: 1; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nowrap { white-space: nowrap; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.skeleton {
    border-radius: 8px;
    background: linear-gradient(90deg, var(--tile-2) 25%, #34343C 50%, var(--tile-2) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* ===== Responsive ===== */
/* Two half-width tiles need about 500px each for a five-column table: stack them earlier. */
@media (max-width: 1320px) {
    .grid-2 { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 1100px) {
    .shell-nav { width: 72px; padding: 28px 12px; align-items: center; }
    .shell-nav .label { display: none; }
    .shell-nav a.nav-item { width: 46px; padding: 0; justify-content: center; }
    .shell-nav__status { padding: 0; justify-content: center; }
    .grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid-2, .grid-2-1 { grid-template-columns: minmax(0, 1fr); }
    .split { flex-direction: column; align-items: stretch; }
    .split-list { width: 100%; }
    .kpi-val { font-size: 48px; }
}
@media (max-width: 720px) {
    .app { flex-direction: column; }
    .shell-nav {
        position: sticky;
        z-index: 100;
        width: 100%;
        height: auto;
        overflow-y: visible;
        flex-direction: row;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 12px 16px;
        background: var(--ground);
    }
    .shell-nav .label { display: inline; }
    .shell-nav__toggle { display: grid; place-items: center; }
    .shell-nav__links, .shell-nav__foot { display: none; width: 100%; margin-top: 0; }
    .shell-nav.open .shell-nav__links, .shell-nav.open .shell-nav__foot { display: flex; }
    .shell-nav a.nav-item { width: 100%; padding: 0 16px; justify-content: flex-start; }
    .shell-nav__status { justify-content: flex-start; padding: 0 16px; }
    .content { padding: 8px 16px 32px; }
    .page-head h1 { font-size: 34px; }
    .grid-4 { grid-template-columns: minmax(0, 1fr); }
    .kv { grid-template-columns: minmax(0, 1fr); row-gap: 4px; }
    .kv dd { margin-bottom: 10px; }
    .modal { padding: 22px; }
    .bulk-bar { left: 12px; right: 12px; transform: translateY(80px); }
    .bulk-bar.visible { transform: none; }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py -q`
Expected: all PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check scripts/fetch_fonts.py tests/test_ui_static.py
git add scripts/fetch_fonts.py src/web/static/fonts/*.woff2 src/web/static/fonts/LICENSES.md src/web/static/css/app.css tests/test_ui_static.py
git commit -m "feat(ui): Blocks stylesheet and self-hosted fonts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(Do not delete the Geist fonts yet; the old templates still load them until Task 13.)

---

### Task 2: Shared script `app.js`

**Files:**
- Create: `src/web/static/js/app.js`
- Modify: `tests/test_ui_static.py` (append)

**Interfaces:**
- Consumes: DOM ids rendered by `base.html` in Task 4: `navStatus`, `navStatusText`, `sideNav`, `navToggle`, `toastContainer`, `bulkBar`, `bulkCount`, `confirmModal`, `confirmTitle`, `confirmMessage`, `confirmOkBtn`, `confirmCancelBtn`; `<body data-http-port data-socks5-port>`. Every function tolerates those elements being absent (login page).
- Produces these globals (exact names; page scripts rely on them):

| Global | Signature | Behaviour |
|---|---|---|
| `APP` | `{httpPort: string, socks5Port: string, host: string}` | ports from `<body>` data attributes; `host` = `location.hostname` |
| `apiCall` | `(method, url, body?) => Promise<any\|null>` | JSON fetch. Network error or status >= 500: `Status.offline()` then throws. 401: redirects to `/login` once and throws. Other non-2xx: throws `Error(detail)`. 204: resolves `null`. Any 2xx-4xx: `Status.ok()` |
| `Status` | `{ok(), offline(), isOffline(): boolean}` | sidebar status line (`#navStatus`, rendered `hidden` until the first API result); re-renders every second |
| `Poller` | `{start(fn, ms), stop(), refresh()}` | runs `fn` now and every `ms`; skips while `document.hidden` or a run is in flight; runs once when the tab becomes visible; swallows rejections (the status line reports them) |
| `showToast` | `(message, type = "success")` | type `"success"` or `"error"` |
| `openModal`, `closeModal` | `(id)` | toggles `.active`; `openModal` focuses the first field |
| `openModalFromQuery` | `(map: {param: modalId})` | opens the modal whose param is present in the URL, then strips the param with `history.replaceState` |
| `confirmAction` | `(message, title = "Are you sure?", okLabel = "Delete") => Promise<boolean>` | styled confirm |
| `btnLoading`, `btnReset` | `(btn)` | spinner state |
| `copyToClipboard` | `(text) => Promise<boolean>` | clipboard API with hidden-textarea fallback for plain-HTTP origins |
| `addCopyButtons` | `()` | adds a Copy button to each `.code-block` lacking one; re-run by a MutationObserver |
| `esc` | `(value) => string` | escapes `& < > " '` so the result is safe in element content and inside quoted attributes; `null`/`undefined` become `""` |
| `fmtNum` | `(n) => string` | `"—"` for null/NaN; `1,284`; `412K` from 10,000; `1.8M`; `2.1B` |
| `fmtBytes` | `(n) => string` | `"—"` for null; `0 B`, `48 KB`, `7.6 GB` |
| `fmtMs` | `(n) => string` | `"—"` for null; `"412 ms"` |
| `fmtPct` | `(part, total, digits = 1) => string` | `"—"` when `total` is 0/null; else `"3.2%"` |
| `fmtDate` | `(iso) => string` | `"Mar 9, 2026"`; `"-"` for null |
| `timeAgo` | `(iso) => string` | `"never"` for null; `"4s"`, `"6m"`, `"3h"`, `"2d"` |
| `protoTag`, `statusBadge` | `(value) => html` | `<span class="tag tag-http">http</span>`, `<span class="badge badge-healthy">healthy</span>` (unknown status -> `unknown`) |
| `selectedIds`, `toggleRowSelection(id, checkbox)`, `toggleSelectAll(master)`, `updateSelectAll()`, `clearSelection()`, `updateBulkBar()` | selection | unchanged behaviour from the old `base.html` |
| `updateFileInput` | `(input, nameSpan)` | shows the chosen file name |

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ui_static.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_static.py -q -k app_js`
Expected: FAIL with `FileNotFoundError: ... app.js`.

- [ ] **Step 3: Write `app.js`**

Create `src/web/static/js/app.js` with exactly this content:

```js
/* Proxysm shared UI helpers. Loaded on every page before the page script.
   Everything here is a global on purpose: templates use inline handlers and
   page scripts are classic scripts, not modules. */
'use strict';

const APP = {
    httpPort: document.body.dataset.httpPort || '',
    socks5Port: document.body.dataset.socks5Port || '',
    host: window.location.hostname,
};

/* ---------- formatting ---------- */
// Safe for element content AND for quoted attribute values (title="...", data-x="...").
function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtNum(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    const v = Number(n);
    const a = Math.abs(v);
    const trim = (x) => x.toFixed(1).replace(/\.0$/, '');
    if (a >= 1e9) return trim(v / 1e9) + 'B';
    if (a >= 1e6) return trim(v / 1e6) + 'M';
    if (a >= 1e4) return Math.round(v / 1e3) + 'K';
    return Math.round(v).toLocaleString('en-US');
}

function fmtBytes(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let v = Number(n);
    let i = 0;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
    const text = i === 0 || v >= 100 ? String(Math.round(v)) : v.toFixed(1).replace(/\.0$/, '');
    return text + ' ' + units[i];
}

function fmtMs(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    return Math.round(Number(n)).toLocaleString('en-US') + ' ms';
}

function fmtPct(part, total, digits) {
    if (!total) return '—';
    return ((Number(part) / Number(total)) * 100).toFixed(digits === undefined ? 1 : digits) + '%';
}

function fmtDate(iso) {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function timeAgo(iso) {
    if (!iso) return 'never';
    const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    return Math.floor(s / 86400) + 'd';
}

function protoTag(protocol) {
    const p = esc(protocol);
    return `<span class="tag tag-${p}">${p}</span>`;
}

function statusBadge(status) {
    const known = ['healthy', 'degraded', 'dead', 'unknown'];
    const s = known.includes(status) ? status : 'unknown';
    return `<span class="badge badge-${s}">${s}</span>`;
}

/* ---------- connection status (sidebar) ---------- */
const Status = (() => {
    let lastOk = null;
    let down = false;
    function render() {
        const root = document.getElementById('navStatus');
        const text = document.getElementById('navStatusText');
        if (!root || !text) return;
        // Hidden until the page has made its first API call (the 404 page never does).
        root.hidden = !down && lastOk === null;
        root.classList.toggle('is-offline', down);
        if (down) { text.textContent = 'Offline, retrying'; return; }
        if (lastOk === null) return;
        const age = Math.round((Date.now() - lastOk) / 1000);
        text.textContent = age < 2 ? 'Updated just now' : 'Updated ' + timeAgo(new Date(lastOk).toISOString()) + ' ago';
    }
    setInterval(render, 1000);
    return {
        ok() { lastOk = Date.now(); down = false; render(); },
        offline() { down = true; render(); },
        isOffline() { return down; },
    };
})();

/* ---------- API ---------- */
let redirectingToLogin = false;

async function apiCall(method, url, body) {
    const opts = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined && body !== null) opts.body = JSON.stringify(body);
    let resp;
    try {
        resp = await fetch(url, opts);
    } catch (e) {
        Status.offline();
        throw e;
    }
    if (resp.status === 401) {
        if (!redirectingToLogin) {
            redirectingToLogin = true;
            window.location.href = '/login';
        }
        throw new Error('Session expired');
    }
    if (resp.status >= 500) {
        Status.offline();
    } else {
        Status.ok();
    }
    if (!resp.ok) {
        let msg = 'Error ' + resp.status;
        try {
            const data = await resp.json();
            msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data);
        } catch (e) { /* non-JSON error body */ }
        throw new Error(msg);
    }
    if (resp.status === 204) return null;
    return resp.json();
}

/* ---------- polling ---------- */
const Poller = (() => {
    let timer = null;
    let fn = null;
    let running = false;
    async function tick() {
        if (!fn || running || document.hidden) return;
        running = true;
        try { await fn(); } catch (e) { /* the status line reports outages */ } finally { running = false; }
    }
    function stop() {
        if (timer) clearInterval(timer);
        timer = null;
    }
    function start(f, ms) {
        stop();
        fn = f;
        tick();
        timer = setInterval(tick, ms);
    }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
    return { start: start, stop: stop, refresh: tick };
})();

/* ---------- toasts ---------- */
function showToast(message, type) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const kind = type === 'error' ? 'error' : 'success';
    const el = document.createElement('div');
    el.className = 'toast toast-' + kind;
    el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.style.transition = 'opacity 0.2s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 200);
    }, 3500);
}

/* ---------- modals ---------- */
let lastFocusBeforeModal = null;

function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    lastFocusBeforeModal = document.activeElement;
    modal.classList.add('active');
    setTimeout(() => {
        const field = modal.querySelector('input:not([type="hidden"]):not([type="file"]), textarea, select');
        if (field) field.focus();
    }, 60);
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('active');
    if (lastFocusBeforeModal && document.contains(lastFocusBeforeModal)) lastFocusBeforeModal.focus();
    lastFocusBeforeModal = null;
}

function openModalFromQuery(map) {
    const params = new URLSearchParams(window.location.search);
    let opened = false;
    Object.keys(map).forEach((param) => {
        if (!params.has(param)) return;
        if (!opened) { openModal(map[param]); opened = true; }
        params.delete(param);
    });
    if (opened) {
        const qs = params.toString();
        history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    }
}

function confirmAction(message, title, okLabel) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        const ok = document.getElementById('confirmOkBtn');
        const cancel = document.getElementById('confirmCancelBtn');
        document.getElementById('confirmMessage').textContent = message;
        document.getElementById('confirmTitle').textContent = title || 'Are you sure?';
        ok.textContent = okLabel || 'Delete';
        modal.classList.add('active');
        cancel.focus();
        function done(result) {
            modal.classList.remove('active');
            ok.removeEventListener('click', onOk);
            cancel.removeEventListener('click', onCancel);
            resolve(result);
        }
        function onOk() { done(true); }
        function onCancel() { done(false); }
        ok.addEventListener('click', onOk);
        cancel.addEventListener('click', onCancel);
    });
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const confirmModal = document.getElementById('confirmModal');
        if (confirmModal && confirmModal.classList.contains('active')) {
            document.getElementById('confirmCancelBtn').click();
            return;
        }
        const active = document.querySelector('.modal-overlay.active');
        if (active) closeModal(active.id);
        return;
    }
    // Enter submits the modal from a field; on a focused button or link it keeps its normal
    // meaning (otherwise Enter on Cancel would save).
    if (e.key === 'Enter' && !['TEXTAREA', 'BUTTON', 'A'].includes(e.target.tagName)) {
        const modal = e.target.closest ? e.target.closest('.modal-overlay.active') : null;
        if (!modal || modal.id === 'confirmModal') return;
        const primary = modal.querySelector('.modal-actions .btn-primary');
        if (primary && !primary.disabled) { e.preventDefault(); primary.click(); }
    }
});

document.addEventListener('click', (e) => {
    const t = e.target;
    if (!t.classList || !t.classList.contains('modal-overlay') || !t.classList.contains('active')) return;
    if (t.id === 'confirmModal') document.getElementById('confirmCancelBtn').click();
    else closeModal(t.id);
});

/* ---------- buttons ---------- */
function btnLoading(btn) { if (btn) { btn.disabled = true; btn.classList.add('btn-loading'); } }
function btnReset(btn) { if (btn) { btn.disabled = false; btn.classList.remove('btn-loading'); } }

/* ---------- clipboard ---------- */
// navigator.clipboard needs a secure context (HTTPS or localhost); on plain-HTTP
// origins fall back to a hidden textarea.
async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (e) { /* fall through */ }
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
}

function addCopyButtons() {
    document.querySelectorAll('.code-block').forEach((block) => {
        if (block.dataset.copyReady) return;
        block.dataset.copyReady = '1';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'copy-btn';
        btn.textContent = 'Copy';
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const clone = block.cloneNode(true);
            clone.querySelectorAll('.copy-btn').forEach((b) => b.remove());
            copyToClipboard(clone.textContent.trim()).then((ok) => {
                if (!ok) { showToast('Copy failed, select the text manually', 'error'); return; }
                btn.textContent = 'Copied';
                setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            });
        });
        block.appendChild(btn);
    });
}

/* ---------- table selection ---------- */
let selectedIds = new Set();

function updateBulkBar() {
    const bar = document.getElementById('bulkBar');
    if (!bar) return;
    const count = selectedIds.size;
    document.getElementById('bulkCount').textContent = count + ' selected';
    bar.classList.toggle('visible', count > 0);
    bar.setAttribute('aria-hidden', String(count === 0));
}

function toggleRowSelection(id, checkbox) {
    const row = checkbox.closest('tr');
    if (checkbox.checked) { selectedIds.add(id); row.classList.add('selected'); }
    else { selectedIds.delete(id); row.classList.remove('selected'); }
    updateSelectAll();
    updateBulkBar();
}

function toggleSelectAll(master) {
    document.querySelectorAll('tbody .row-checkbox').forEach((cb) => {
        cb.checked = master.checked;
        const row = cb.closest('tr');
        if (master.checked) { selectedIds.add(cb.dataset.id); row.classList.add('selected'); }
        else { selectedIds.delete(cb.dataset.id); row.classList.remove('selected'); }
    });
    updateBulkBar();
}

function updateSelectAll() {
    const master = document.getElementById('selectAll');
    if (!master) return;
    const boxes = Array.from(document.querySelectorAll('tbody .row-checkbox'));
    const all = boxes.length > 0 && boxes.every((cb) => cb.checked);
    master.checked = all;
    master.indeterminate = !all && boxes.some((cb) => cb.checked);
}

function clearSelection() {
    selectedIds.clear();
    document.querySelectorAll('.row-checkbox').forEach((cb) => {
        cb.checked = false;
        const row = cb.closest('tr');
        if (row) row.classList.remove('selected');
    });
    const master = document.getElementById('selectAll');
    if (master) { master.checked = false; master.indeterminate = false; }
    updateBulkBar();
}

/* ---------- misc ---------- */
function updateFileInput(input, nameSpan) {
    nameSpan.textContent = input.files.length > 0 ? input.files[0].name : 'No file selected';
}

(function initShell() {
    const toggle = document.getElementById('navToggle');
    const nav = document.getElementById('sideNav');
    if (toggle && nav) {
        toggle.addEventListener('click', () => {
            const open = nav.classList.toggle('open');
            toggle.setAttribute('aria-expanded', String(open));
        });
    }
    // Clicking the page you are already on is a no-op, not a reload
    document.querySelectorAll('.shell-nav a.nav-item').forEach((link) => {
        link.addEventListener('click', (e) => {
            if (window.location.pathname === link.getAttribute('href')) e.preventDefault();
        });
    });
    addCopyButtons();
    new MutationObserver(addCopyButtons).observe(document.body, { childList: true, subtree: true });
})();
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/web/static/js/app.js tests/test_ui_static.py
git commit -m "feat(ui): shared app.js (api, status line, poller, modals, formatters)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: UI preview server with canned API (dev-only)

Without this there is no way to open the UI without Postgres and Redis, and no way to see the empty or offline states at all. It serves the real templates and static files and answers `/api/v1/*` from fixtures.

**Files:**
- Create: `scripts/ui_preview_fixtures.py`
- Create: `scripts/ui_preview.py`
- Create: `tests/test_ui_preview.py`

**Interfaces:**
- Consumes: `src.web.routes.router`, `require_session`, `not_found_handler`.
- Produces: `scripts.ui_preview.build_app(scenario: str = "normal") -> FastAPI`; scenarios `"normal" | "empty" | "offline"`; runtime switch `GET /__scenario/<name>`; run with `uv run python -m scripts.ui_preview` (port 8099, override with `PREVIEW_PORT`; initial scenario from `PREVIEW_SCENARIO`). Fixture keys are `(METHOD, path-after-/api/v1/ with every UUID segment replaced by "{id}")`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ui_preview.py`:

```python
"""The dev-only UI preview server: real templates, canned API."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from scripts.ui_preview import build_app
from scripts.ui_preview_fixtures import EMPTY_FIXTURES, FIXTURES

SOME_ID = "11111111-1111-4111-8111-111111111111"


def _client(scenario: str = "normal") -> AsyncClient:
    transport = ASGITransport(app=build_app(scenario))
    return AsyncClient(transport=transport, base_url="http://preview", follow_redirects=False)


@pytest.mark.parametrize("path", ["/dashboard", "/proxies", "/pools", "/projects", "/settings"])
async def test_pages_render_without_a_session(path):
    resp = await _client().get(path)
    assert resp.status_code == 200
    assert "<html" in resp.text.lower()


async def test_api_answers_from_fixtures():
    resp = await _client().get("/api/v1/stats/overview")
    assert resp.status_code == 200
    assert resp.json() == FIXTURES[("GET", "stats/overview")]


async def test_uuid_segments_match_id_placeholders():
    resp = await _client().get(f"/api/v1/projects/{SOME_ID}/stats")
    assert resp.status_code == 200
    assert resp.json() == FIXTURES[("GET", "projects/{id}/stats")]


async def test_detail_endpoints_answer_with_the_matching_list_item():
    """GET projects/<id> must describe the project that was clicked, not always the first one."""
    projects = FIXTURES[("GET", "projects")]["data"]
    second = projects[1]
    resp = await _client().get(f"/api/v1/projects/{second['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == second["name"]


@pytest.mark.parametrize(("granularity", "count"), [("5min", 12), ("1hour", 24), ("1day", 7)])
async def test_timeseries_is_generated_relative_to_now(granularity, count):
    resp = await _client().get(f"/api/v1/stats/timeseries?granularity={granularity}&hours=24")
    body = resp.json()
    assert body["granularity"] == granularity
    assert len(body["data"]) == count
    point = body["data"][-1]
    assert set(point) == set(FIXTURES[("GET", "stats/timeseries")]["data"][0])
    assert point["successful_requests"] + point["failed_requests"] == point["total_requests"]
    newest = datetime.fromisoformat(point["period_start"].replace("Z", "+00:00"))
    assert datetime.now(UTC) - newest < timedelta(days=2)


async def test_timeseries_is_empty_in_the_empty_scenario():
    resp = await _client("empty").get("/api/v1/stats/timeseries?granularity=1hour")
    assert resp.json() == {"granularity": "1hour", "data": []}


async def test_proxy_list_honours_pool_status_and_search_filters():
    everything = FIXTURES[("GET", "ips")]["data"]
    dead = (await _client().get("/api/v1/ips?status=dead")).json()
    assert dead["data"] and all(p["last_health_status"] == "dead" for p in dead["data"])
    assert dead["meta"]["total"] == len(dead["data"]) < len(everything)
    pool_id = FIXTURES[("GET", "pools")]["data"][0]["id"]
    members = (await _client().get(f"/api/v1/ips?pool_id={pool_id}")).json()
    assert 0 < len(members["data"]) < len(everything)
    host = everything[0]["host"]
    found = (await _client().get(f"/api/v1/ips?search={host}")).json()
    assert [p["host"] for p in found["data"]] == [host]


async def test_no_content_fixture_returns_204():
    resp = await _client().delete(f"/api/v1/ips/{SOME_ID}")
    assert resp.status_code == 204


async def test_empty_scenario_serves_an_empty_instance():
    resp = await _client("empty").get("/api/v1/ips")
    assert resp.status_code == 200
    assert resp.json() == EMPTY_FIXTURES[("GET", "ips")]


async def test_offline_scenario_fails_every_api_call_but_still_serves_pages():
    client = _client("offline")
    assert (await client.get("/api/v1/stats/overview")).status_code == 503
    assert (await client.get("/dashboard")).status_code == 200


async def test_scenario_can_be_switched_at_runtime():
    client = _client()
    assert (await client.get("/__scenario/offline")).status_code == 200
    assert (await client.get("/api/v1/pools")).status_code == 503
    assert (await client.get("/__scenario/bogus")).status_code == 404


async def test_unknown_endpoint_is_a_json_404_not_a_crash():
    resp = await _client().get("/api/v1/does/not/exist")
    assert resp.status_code == 404
    assert "no fixture" in resp.json()["detail"]


def test_every_empty_fixture_has_a_normal_twin():
    assert set(EMPTY_FIXTURES) <= set(FIXTURES)


def test_fixture_keys_use_only_the_id_placeholder():
    """The server turns EVERY uuid segment into {id}; a key like pools/{pool_id} can never match."""
    for _method, pattern in FIXTURES:
        assert "{" not in pattern.replace("{id}", ""), pattern


def test_fixtures_include_a_hostile_long_name():
    """Review Focus 3: the UI must survive markup and very long names."""
    blob = json.dumps(list(FIXTURES.values()))
    assert "<script>" in blob
    assert any(len(p["name"]) > 60 for p in FIXTURES[("GET", "pools")]["data"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_preview.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'scripts.ui_preview'`.

- [ ] **Step 3: Add the fixtures**

The fixtures are about 1,260 lines of plain dicts, so they live beside this plan instead of inline. Copy the file verbatim:

```bash
cp docs/superpowers/plans/2026-09-20-ui-revamp-m1-assets/ui_preview_fixtures.py scripts/ui_preview_fixtures.py
```

It exports `FIXTURES`, `EMPTY_FIXTURES`, `STATUS_CODES`, `POOL_MEMBERS` and `ENTITY_STATS_BY_ID` (all used by the server below). Every entry cites the handler or schema its shape was copied from, and every model-backed entry was round-tripped through the real Pydantic schemas. It deliberately contains one hostile pool name and one hostile project name (markup, a double quote, 60+ characters). If a later task shows the real API differs from a fixture, fix the fixture, not the UI.

- [ ] **Step 4: Add the preview server**

Create `scripts/ui_preview.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_preview.py -q`
Expected: all PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check scripts/ui_preview.py scripts/ui_preview_fixtures.py tests/test_ui_preview.py
git add scripts/ui_preview.py scripts/ui_preview_fixtures.py tests/test_ui_preview.py
git commit -m "chore(dev): UI preview server with canned API fixtures

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

**How every later task uses it (the "smoke check"):** start `uv run python -m scripts.ui_preview` in the background, open `http://127.0.0.1:8099/<page>` with the Playwright MCP browser tools if they are available (otherwise `curl` the page and the static files and say in the task report that no browser was available), and check what the task's smoke step lists. Switch states with `http://127.0.0.1:8099/__scenario/empty` and `/__scenario/offline`. Stop the server when done.

---

### Task 4: Base shell (sidebar, static assets, no inline CSS/JS)

**Files:**
- Modify: `src/web/routes.py` (the `_ctx` function and the two `login.html` renders)
- Rewrite: `src/web/templates/base.html`
- Modify: `tests/test_web_routes.py` (test app, fake settings, nav test; add shell tests)
- Modify: `tests/test_ui_static.py` (append the id-consistency helper)

**Interfaces:**
- Consumes: `app.css` classes (Task 1), `app.js` DOM ids (Task 2).
- Produces:
  - Template context key `asset_version: str` on every page including login.
  - `base.html` blocks: `title`, `content`, `scripts`. Page templates put their modals inside `content` and their script tag inside `scripts`, written as `<script src="/static/js/pages/NAME.js?v={{ asset_version }}"></script>`.
  - Nav ids in DOM order: `nav-overview`, `nav-proxies`, `nav-pools`, `nav-projects`; footer ids `navStatus`, `navStatusText`, `nav-settings`, `nav-logout`. Active item is rendered server-side (`class="nav-item active"` + `aria-current="page"`).
  - Shared DOM: `toastContainer`, `bulkBar` (children `bulkCount`, a Cancel button, `bulkDeleteBtn`; page scripts insert extra `btn btn-sm` buttons before `bulkDeleteBtn`), `confirmModal`.
  - `tests/test_ui_static.py::assert_js_ids_exist(js_name: str, html: str)` for page tasks.
  - `tests/test_ui_static.py::RESTYLED_TEMPLATES` (list of template file names). Every task that rewrites a template appends its file name there; the parametrized test `test_template_and_script_use_only_defined_classes` then checks that template and its page script (`dashboard.html` pairs with `overview.js`) use only classes `app.css` defines.

- [ ] **Step 1: Write the failing tests**

In `tests/test_web_routes.py`, replace the imports, fake settings and `_build_test_app` at the top of the file with:

```python
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
```

Replace `test_navbar_order` with:

```python
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
```

Append to `tests/test_ui_static.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_web_routes.py -q -k "sidebar or active_nav or shell_uses or static_assets"`
Expected: FAIL (`nav-overview` not found; no `app.css` link). `test_restyled_page_has_markup_only` collects zero cases for now.

- [ ] **Step 3: Add the asset version to the template context**

In `src/web/routes.py` replace the `_ctx` function with:

```python
_STATIC_DIR = pathlib.Path(__file__).parent / "static"


def _asset_version() -> str:
    """Cache-busting token that changes whenever any static file changes."""
    newest = max(
        (p.stat().st_mtime_ns for p in _STATIC_DIR.rglob("*") if p.is_file()), default=0
    )
    return format(newest, "x")[-8:]


def _ctx() -> dict:
    return {
        "http_port": settings.proxy_http_port,
        "socks5_port": settings.proxy_socks5_port,
        "asset_version": _asset_version(),
    }
```

and in the same file change both `login.html` renders so they carry the context: `{"error": None}` becomes `{**_ctx(), "error": None}` and `{"error": "Wrong password. Check PM_ADMIN_PASSWORD in your .env."}` becomes `{**_ctx(), "error": "Wrong password. Check PM_ADMIN_PASSWORD in your .env."}`.

- [ ] **Step 4: Rewrite `base.html`**

Replace the whole of `src/web/templates/base.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Proxysm{% endblock %}</title>
    <meta name="color-scheme" content="dark">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='10' fill='%23D4F26A'/><polygon points='16,27 14,12 16,6 18,12' fill='%230E0E10'/></svg>">
    <link rel="preload" href="/static/fonts/figtree.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/static/fonts/bricolage-grotesque.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/static/css/app.css?v={{ asset_version }}">
</head>
{% set path = request.url.path %}
{% macro nav(href, id, label, icon) -%}
<a href="{{ href }}" id="{{ id }}" class="nav-item{{ ' active' if path.startswith(href) }}"{% if path.startswith(href) %} aria-current="page"{% endif %}>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{{ icon }}"/></svg>
    <span class="label">{{ label }}</span>
</a>
{%- endmacro %}
<body data-http-port="{{ http_port }}" data-socks5-port="{{ socks5_port }}">
<div class="app">
    <aside class="shell-nav" id="sideNav">
        <a href="/dashboard" class="shell-nav__brand">
            <span class="shell-nav__mark">
                <svg width="20" height="20" viewBox="0 0 32 32" aria-hidden="true"><g fill="#0E0E10"><polygon points="16,30 13.5,12 16,4 18.5,12"/><polygon points="16,30 13.5,12 16,4 18.5,12" transform="rotate(-24 16 30)"/><polygon points="16,30 13.5,12 16,4 18.5,12" transform="rotate(24 16 30)"/></g></svg>
            </span>
            <span class="label">proxysm</span>
        </a>
        <button class="shell-nav__toggle" id="navToggle" type="button" aria-label="Toggle navigation" aria-expanded="false" aria-controls="navLinks">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
        </button>
        <nav class="shell-nav__links" id="navLinks" aria-label="Primary">
            {{ nav("/dashboard", "nav-overview", "Overview", "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z") }}
            {{ nav("/proxies", "nav-proxies", "Proxies", "M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01") }}
            {{ nav("/pools", "nav-pools", "Pools", "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5") }}
            {{ nav("/projects", "nav-projects", "Projects", "M3 7a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z") }}
        </nav>
        <div class="shell-nav__foot">
            <div class="shell-nav__status" id="navStatus" role="status" hidden>
                <span class="dot"></span><span class="label" id="navStatusText"></span>
            </div>
            {{ nav("/settings", "nav-settings", "Settings", "M4 6h10M18 6h2M4 18h10M18 18h2M4 12h2M10 12h10M14 6a2 2 0 1 0 4 0a2 2 0 1 0-4 0M14 18a2 2 0 1 0 4 0a2 2 0 1 0-4 0M6 12a2 2 0 1 0 4 0a2 2 0 1 0-4 0") }}
            {{ nav("/logout", "nav-logout", "Sign out", "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9") }}
        </div>
    </aside>

    <main class="content">
        {% block content %}{% endblock %}
    </main>
</div>

<div class="toast-container" id="toastContainer"></div>

<div class="bulk-bar" id="bulkBar" aria-hidden="true">
    <span id="bulkCount">0 selected</span>
    <button class="btn btn-sm" type="button" onclick="clearSelection()">Cancel</button>
    <button class="btn btn-sm btn-danger" type="button" id="bulkDeleteBtn">Delete selected</button>
</div>

<div class="modal-overlay confirm-modal" id="confirmModal" role="dialog" aria-modal="true" aria-labelledby="confirmTitle">
    <div class="modal">
        <h2 id="confirmTitle">Are you sure?</h2>
        <p class="confirm-message" id="confirmMessage"></p>
        <div class="modal-actions">
            <button class="btn" type="button" id="confirmCancelBtn">Cancel</button>
            <button class="btn btn-danger" type="button" id="confirmOkBtn">Delete</button>
        </div>
    </div>
</div>

<script src="/static/js/app.js?v={{ asset_version }}"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

Notes for the implementer: the favicon `href` starts with `data:`, so the "no external requests" test does not see it. `/logout` never matches the current path on a rendered page, so Sign out is never marked active.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS, including `test_template_and_script_use_only_defined_classes[base.html]`. The old page templates are untouched, so their existing tests still pass; they now render inside the new shell with their own leftover inline `<style>` and scripts (which keep working because `app.js` exports the same global names). They look half-styled until each page's task lands; that is expected on this branch.

- [ ] **Step 6: Smoke check**

Start the preview server and open `http://127.0.0.1:8099/dashboard`. Expected: near-black page, 248px sidebar with lime logo block, four nav items with the first one a white pill, "Updated just now" above Settings and Sign out at the bottom. Resize to 1000px: sidebar becomes an icon rail. Resize to 390px: top bar with a menu button that opens the links. Resize to 1440x560: the sidebar scrolls on its own and Sign out can be scrolled into view and clicked. Open `/settings` too: the old Settings template is still in place, but the shell sidebar must sit at the top of the window with Settings and Sign out fully visible (this is why the shell class is `shell-nav`, not `side-nav`).

- [ ] **Step 7: Commit**

```bash
uv run ruff check src/web/routes.py tests
git add src/web/routes.py src/web/templates/base.html tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): sidebar shell on static css/js, server-rendered active nav

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Retire `/api-docs` and `/setup`

**Files:**
- Modify: `src/web/routes.py` (the `api_docs_page` and `setup_page` handlers)
- Delete: `src/web/templates/api-docs.html`, `src/web/templates/setup.html`
- Modify: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `GET /api-docs` -> 302 `/docs`; `GET /setup` -> 302 `/dashboard`. Neither needs a session (same as the existing `/stats` and `/providers` redirects).

- [ ] **Step 1: Write the failing tests**

In `tests/test_web_routes.py` delete `test_setup_returns_html` and `test_api_docs_returns_html` and add:

```python
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
```

Also, in `test_pages_redirect_to_login_without_session`, change the list to `pages = PAGES` (the two retired paths no longer require a session; `PAGES` is defined at the top of the file since Task 4).

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py -q -k retired`
Expected: FAIL (200 instead of a redirect; templates exist).

- [ ] **Step 3: Implement**

In `src/web/routes.py` replace the two handlers with:

```python
@router.get("/api-docs", response_class=RedirectResponse)
async def api_docs_redirect():
    return RedirectResponse(url="/docs")


@router.get("/setup", response_class=RedirectResponse)
async def setup_redirect():
    return RedirectResponse(url="/dashboard")
```

Then: `git rm src/web/templates/api-docs.html src/web/templates/setup.html`

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS. (`test_dashboard_has_onboarding_card` still asserts `href="/setup"`: the old dashboard template still has that link and the redirect keeps it working. Task 7 rewrites both.)

- [ ] **Step 5: Commit**

```bash
git add -A src/web/routes.py src/web/templates tests/test_web_routes.py
git commit -m "feat(ui): retire /api-docs and /setup (redirect to /docs and /dashboard)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Login and 404 pages

**Files:**
- Rewrite: `src/web/templates/login.html`, `src/web/templates/404.html`
- Modify: `src/web/static/css/app.css` (append the `.auth` block)
- Modify: `tests/test_web_routes.py`, `tests/test_ui_static.py`

**Interfaces:**
- Consumes: `asset_version` in the login context (Task 4); `app.css`.
- Produces: `.auth`, `.auth__card`, `.auth__error` CSS classes (login only).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_web_routes.py`:

```python
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
```

In `tests/test_ui_static.py` add `"login.html",` and `"404.html",` to `RESTYLED_TEMPLATES` (one entry per line, so the list never exceeds the 100-character line limit however long it grows).

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py tests/test_ui_static.py -q -k "login_page_uses or login_error or defined_classes"`
Expected: FAIL (`<style` present, no label; `login.html` uses classes such as `card` that `app.css` does not define).

- [ ] **Step 3: Implement**

Append to `src/web/static/css/app.css`:

```css

/* ===== Sign-in ===== */
.auth { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.auth__card { width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 18px; padding: 32px; border-radius: var(--r-tile); background: var(--tile); }
.auth__card h1 { font-size: 34px; letter-spacing: -0.04em; }
.auth__error { padding: 12px 18px; border-radius: var(--r-block); background: var(--coral); color: var(--on-coral); font-weight: 600; }
.auth__card .btn { width: 100%; height: 46px; }
```

Replace `src/web/templates/login.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in - Proxysm</title>
    <meta name="color-scheme" content="dark">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='10' fill='%23D4F26A'/><polygon points='16,27 14,12 16,6 18,12' fill='%230E0E10'/></svg>">
    <link rel="preload" href="/static/fonts/figtree.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/static/css/app.css?v={{ asset_version }}">
</head>
<body>
<main class="auth">
    <form class="auth__card" method="post" action="/login">
        <span class="shell-nav__mark">
            <svg width="20" height="20" viewBox="0 0 32 32" aria-hidden="true"><g fill="#0E0E10"><polygon points="16,30 13.5,12 16,4 18.5,12"/><polygon points="16,30 13.5,12 16,4 18.5,12" transform="rotate(-24 16 30)"/><polygon points="16,30 13.5,12 16,4 18.5,12" transform="rotate(24 16 30)"/></g></svg>
        </span>
        <h1>proxysm</h1>
        {% if error %}<div class="auth__error" role="alert">{{ error }}</div>{% endif %}
        <div>
            <label for="password">Admin password</label>
            <input type="password" id="password" name="password" autofocus autocomplete="current-password" required>
        </div>
        <button class="btn btn-primary" type="submit">Sign in</button>
    </form>
</main>
</body>
</html>
```

Replace `src/web/templates/404.html` with:

```html
{% extends "base.html" %}
{% block title %}Page not found - Proxysm{% endblock %}

{% block content %}
<section class="tile">
    <div class="empty-state">
        <h3>Page not found</h3>
        <p>That page does not exist or has moved.</p>
        <a href="/dashboard" class="btn btn-primary">Back to Overview</a>
    </div>
</section>
{% endblock %}
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Smoke check**

Preview server: open `/login` (a centred dark card, lime Sign in button, focus ring on Tab) and `/nope` (404 tile inside the shell).

- [ ] **Step 6: Commit**

```bash
git add src/web/static/css/app.css src/web/templates/login.html src/web/templates/404.html tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): Blocks sign-in and 404 pages

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Overview page

**Files:**
- Rewrite: `src/web/templates/dashboard.html`
- Create: `src/web/static/js/pages/overview.js`
- Modify: `tests/test_web_routes.py`
- Modify: `tests/test_ui_static.py` (one list entry)

**Interfaces:**
- Consumes:
  - `app.js` globals: `apiCall`, `Poller.start` / `Poller.refresh`, `showToast`, `esc` (safe for element content and for quoted attribute values), `fmtNum`, `fmtBytes`, `fmtMs`, `fmtPct`. None is redefined.
  - `base.html`: blocks `title`, `content`, `scripts`; `asset_version`; the sidebar status line (`navStatus`) is driven by `apiCall`, not by this page.
  - CSS: `.page-head`, `.seg`, `.tile` (+ `--lime`, `--amber`, `--coral`, `--lavender`), `.tile-head`, `.tile-head__meta`, `.grid-4`, `.grid-2`, `.kpi*`, `.bars*` + `.is-now`, `.legend`, `.table-scroll` > `table.tbl`, `.num`, `.actions`, `.meter--*`, `.badge-bad` / `.badge-quiet`, `td .sub`, `.text-warn` / `.text-bad`, `.onboarding*` + `.done`, `.empty-state`, `.skeleton`, `.btn*`, `.row`, `.spacer`, `.strong`, `.muted`, `.truncate`, `.sr-only`.
  - API (all `GET`, all existing): `/api/v1/stats/overview`; `/api/v1/stats/throughput` (global, no `project_id`); `/api/v1/stats/timeseries?entity_type=proxy&granularity=<5min|1hour|1day>&hours=<2|25|168>`; `/api/v1/stats/provider-health`; `/api/v1/pools?per_page=100`; `/api/v1/stats/pool-metrics`; `/api/v1/projects?per_page=100`; `/api/v1/projects/{id}/stats`. Lists use the `{"data": [...], "meta": {"total", ...}}` envelope.
- Produces:
  - Links other pages must honour: `/proxies?import=1`, `/pools?new=1`, `/projects?new=1` (open the matching modal, Tasks 8-10) and `/projects?project=<id>` (select that project, Task 10).
  - DOM ids: `rangeSeg`, `onboardingCard`, `onboardingStepProxies`, `onboardingStepPools`, `onboardingStepProjects`, `statHealthy`, `statDegraded`, `statDead`, `statRpm`, `kpiHealthyFoot`, `kpiDeadFoot`, `kpiRpmFoot`, `trafficBars`, `trafficAxis`, `trafficSummary`, `providerHealthBody`, `poolUtilBody`, `projectStatsBody` (the last three keep their old names so history stays readable).
  - `localStorage` key `proxysm.overview.range` (`1h` | `24h` | `7d`).

**What changes for the operator:**
- The page is called Overview (same URL, `/dashboard`). The Proxies / Projects tabs, the manual Refresh button and the whole per-project drill-down are gone (status codes, error breakdown, error-rate and bandwidth charts, top domains, pool performance, latency and rotation distribution, throughput badge). So are the health ring and the response-time and bandwidth charts. A project row now has an Open link to the Projects page.
- Four tiles: Healthy, Degraded, Dead, Requests per minute. "Total proxies" moved into the Healthy footer ("of N proxies"); proxies not checked yet are named under Dead.
- Traffic has a 1h / 24h / 7d switch that is remembered per browser. Requests and errors are stacked per bucket; hover a bar for exact numbers. Traffic totals now agree with the tiles: the old chart summed proxy, pool and project rollups and showed about three times the real count.
- Providers shows Total, Healthy and an availability bar; degraded, dead and unchecked counts are in the bar's tooltip. Bar colour: lime from 50%, amber from 20%, coral below (the old 85% / 65% thresholds painted almost every public-proxy provider red). Pools shows "healthy / size" as a badge, coral when a pool has proxies and none is healthy. Error rates turn amber from 5% and coral from 10%.
- The Projects table is labelled honestly: `/projects/{id}/stats` sums every 5-minute rollup still kept (7 days by default), not 24 hours as the old "Requests (24h)" header claimed. The column is now "Requests", with that explanation in its tooltip and in the tile head. Per-project numbers refresh every 30 seconds; everything else every 10.
- The onboarding card links straight to the import, new-pool and new-project dialogs. "Guided setup" is gone with `/setup`.

Two limits of the existing API that this page works around and does not fix: rollups are written only when a window closes, so the chart ends on the last complete bucket unless the API returns the current one; and `hours` is capped at 168, so the oldest of the seven day-buckets is always empty.

- [ ] **Step 1: Write the failing tests**

In `tests/test_web_routes.py`:

1. Add `"/dashboard"` to the `RESTYLED_PAGES` list literal. After Task 4 it is `[]`, so it becomes `RESTYLED_PAGES: list[str] = ["/dashboard"]`; if another page task landed first, keep its entries.
   In `tests/test_ui_static.py`, append `"dashboard.html"` to `RESTYLED_TEMPLATES` (after Task 6 it is `["base.html", "login.html", "404.html"]`, so it becomes `["base.html", "login.html", "404.html", "dashboard.html"]`). Its parametrized test `test_template_and_script_use_only_defined_classes` then checks `dashboard.html` and `overview.js` against `app.css`. The script builds its HTML with template literals and keeps quotes out of `class="..."`, which is what that test can read.
2. Add this import below the other imports at the top of the file:

```python
from tests.test_ui_static import assert_js_ids_exist
```

3. Delete these four tests. Three assert JavaScript function names inside the HTML, which a markup-only template cannot contain, and the fourth expects the retired `/setup` link. Each has a replacement below.
   - `test_dashboard_has_provider_health_chart` -> `test_overview_has_providers_and_pools_tables`
   - `test_dashboard_has_pool_utilization_chart` -> `test_overview_has_providers_and_pools_tables`
   - `test_dashboard_has_onboarding_card` -> `test_overview_onboarding_card_deep_links`
   - `test_dashboard_no_old_charts` -> `test_overview_drops_the_old_dashboard` (keeps its four assertions)
4. Keep unchanged: `test_dashboard_returns_html`, `test_dashboard_contains_html_structure`, `test_admin_password_not_embedded_in_pages`, the login / logout / redirect tests, and the Task 4 shell tests that fetch `/dashboard`.
5. In place of the deleted "Dashboard chart tests" section, add:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py tests/test_ui_static.py -q -k "overview or restyled or dashboard"`
Expected: the two kept tests (`test_dashboard_returns_html`, `test_dashboard_contains_html_structure`) PASS; everything else selected FAILS. `test_restyled_page_has_markup_only[/dashboard]` fails on `<style` and `test_template_and_script_use_only_defined_classes[dashboard.html]` on the old class names (the old template is still in place); the `overview` tests fail with `FileNotFoundError: .../js/pages/overview.js`, a missing script tag and missing ids.

- [ ] **Step 3: Rewrite the template**

Replace the whole of `src/web/templates/dashboard.html` with:

```html
{% extends "base.html" %}
{% block title %}Overview - Proxysm{% endblock %}

{% block content %}
<div class="page-head">
    <h1>Overview</h1>
    <div class="page-head__actions">
        <div class="seg" id="rangeSeg" role="group" aria-label="Traffic time range">
            <button type="button" data-range="1h" aria-pressed="false" onclick="setRange('1h')">1h</button>
            <button type="button" data-range="24h" class="active" aria-pressed="true" onclick="setRange('24h')">24h</button>
            <button type="button" data-range="7d" aria-pressed="false" onclick="setRange('7d')">7d</button>
        </div>
    </div>
</div>

<!-- First run: shown by overview.js while proxies, pools or projects is still empty -->
<section class="tile tile--lavender" id="onboardingCard" aria-labelledby="onboardingTitle" hidden>
    <div class="onboarding">
        <div class="onboarding__text">
            <h2 id="onboardingTitle">Welcome to Proxysm</h2>
            <p>Three steps to get traffic flowing through your proxies.</p>
        </div>
        <div class="onboarding__steps">
            <a href="/proxies?import=1" class="onboarding-step" id="onboardingStepProxies"><span class="num">1</span>Import proxies</a>
            <a href="/pools?new=1" class="onboarding-step" id="onboardingStepPools"><span class="num">2</span>Create a pool</a>
            <a href="/projects?new=1" class="onboarding-step" id="onboardingStepProjects"><span class="num">3</span>Create a project</a>
        </div>
    </div>
</section>

<div class="grid-4">
    <section class="tile tile--lime kpi" aria-labelledby="kpiHealthyLabel">
        <div class="kpi-top"><span id="kpiHealthyLabel">Healthy</span></div>
        <div class="kpi-val" id="statHealthy">—</div>
        <div class="kpi-foot" id="kpiHealthyFoot">&nbsp;</div>
    </section>
    <section class="tile tile--amber kpi" aria-labelledby="kpiDegradedLabel">
        <div class="kpi-top"><span id="kpiDegradedLabel">Degraded</span></div>
        <div class="kpi-val" id="statDegraded">—</div>
        <div class="kpi-foot">rechecked every 15 seconds</div>
    </section>
    <section class="tile tile--coral kpi" aria-labelledby="kpiDeadLabel">
        <div class="kpi-top"><span id="kpiDeadLabel">Dead</span></div>
        <div class="kpi-val" id="statDead">—</div>
        <div class="kpi-foot" id="kpiDeadFoot">&nbsp;</div>
    </section>
    <section class="tile kpi" aria-labelledby="kpiRpmLabel">
        <div class="kpi-top"><span id="kpiRpmLabel">Requests</span></div>
        <div class="kpi-val" title="Average over the last 5 minutes"><span id="statRpm">—</span><span class="kpi-unit">/ min</span></div>
        <div class="kpi-foot" id="kpiRpmFoot">&nbsp;</div>
    </section>
</div>

<section class="tile" aria-labelledby="trafficTitle">
    <div class="tile-head">
        <div class="row">
            <h2 id="trafficTitle">Traffic</h2>
            <div class="legend"><span><i></i>Requests</span><span><i class="err"></i>Errors</span></div>
        </div>
        <span class="tile-head__meta" id="trafficSummary"></span>
    </div>
    <div class="bars" id="trafficBars" role="img" aria-label="Requests and errors over the selected range"></div>
    <div class="bars__axis" id="trafficAxis"></div>
</section>

<div class="grid-2">
    <section class="tile" aria-labelledby="providersTitle">
        <div class="tile-head">
            <h2 id="providersTitle">Providers</h2>
            <span class="tile-head__meta" id="providerHint"></span>
        </div>
        <div class="table-scroll" id="providerHealthContainer">
            <table class="tbl" style="min-width:420px">
                <thead><tr><th>Provider</th><th class="num">Total</th><th class="num">Healthy</th><th style="width:42%">Availability</th></tr></thead>
                <tbody id="providerHealthBody">
                    <tr><td colspan="4"><div class="skeleton" style="width:55%;height:14px"></div></td></tr>
                </tbody>
            </table>
        </div>
        <div class="empty-state" id="providerHealthEmpty" hidden>
            <h3>No proxies yet</h3>
            <p>Import proxies to see how each provider is holding up.</p>
            <a class="btn btn-primary" href="/proxies?import=1">Import proxies</a>
        </div>
    </section>

    <section class="tile" aria-labelledby="poolsTitle">
        <div class="tile-head">
            <h2 id="poolsTitle">Pools</h2>
            <span class="tile-head__meta" id="poolHint"></span>
        </div>
        <div class="table-scroll" id="poolUtilContainer">
            <table class="tbl" style="min-width:440px">
                <thead><tr><th>Pool</th><th class="num">Healthy</th><th class="num">Req 24h</th><th class="num">Errors</th><th class="num">p50</th></tr></thead>
                <tbody id="poolUtilBody">
                    <tr><td colspan="5"><div class="skeleton" style="width:55%;height:14px"></div></td></tr>
                </tbody>
            </table>
        </div>
        <div class="empty-state" id="poolUtilEmpty" hidden>
            <h3>No pools yet</h3>
            <p>Create a pool to group proxies under a rotation strategy.</p>
            <a class="btn btn-primary" href="/pools?new=1">New pool</a>
        </div>
    </section>
</div>

<section class="tile" aria-labelledby="projectsTitle">
    <div class="tile-head">
        <h2 id="projectsTitle">Projects</h2>
        <span class="tile-head__meta" id="projectHint"></span>
    </div>
    <div class="table-scroll" id="projectStatsContainer">
        <table class="tbl">
            <thead><tr><th>Project</th><th class="num" title="Since the oldest 5-minute metrics still kept (7 days by default)">Requests</th><th class="num">Errors</th><th class="num">p50</th><th class="num">Bandwidth</th><th><span class="sr-only">Open</span></th></tr></thead>
            <tbody id="projectStatsBody">
                <tr><td colspan="6"><div class="skeleton" style="width:55%;height:14px"></div></td></tr>
            </tbody>
        </table>
    </div>
    <div class="empty-state" id="projectStatsEmpty" hidden>
        <h3>No projects yet</h3>
        <p>Create a project to get an API key and start routing requests.</p>
        <a class="btn btn-primary" href="/projects?new=1">New project</a>
    </div>
</section>
{% endblock %}

{% block scripts %}
<script src="/static/js/pages/overview.js?v={{ asset_version }}"></script>
{% endblock %}
```

Notes for the implementer: the script shows and hides the onboarding card, the table wrappers and the empty states with the `hidden` attribute (`app.css` has `[hidden] { display: none !important; }`). The two half-width tables override the stylesheet's 640px table minimum so they do not scroll sideways on a desktop. "Req 24h" is correct for Pools (`/stats/pool-metrics` defaults to 24 hours); Projects says "Requests" because its endpoint has no time window.

- [ ] **Step 4: Write the page script**

Create `src/web/static/js/pages/overview.js`:

```js
/* Overview page (route /dashboard). Read-only: it polls and renders, it never writes.
   Classic script on purpose: the template uses inline handlers, so functions are globals.
   Helpers such as apiCall, Poller, esc and the fmt* formatters come from app.js. */
'use strict';

const RANGE_KEY = 'proxysm.overview.range';
const MINUTE_MS = 60 * 1000;
const BAR_MAX_PX = 170;
const PROJECT_STATS_TTL_MS = 25000; // just under three 10 s ticks: refreshed on every third tick

// Range switch -> GET /stats/timeseries query. `hours` is wider than the visible window
// because the API cuts at `now - hours` while bucket starts are aligned down, which would
// drop the oldest bucket. 168 is the API maximum.
const RANGES = {
    '1h': { granularity: '5min', step: 5 * MINUTE_MS, buckets: 12, hours: 2 },
    '24h': { granularity: '1hour', step: 60 * MINUTE_MS, buckets: 24, hours: 25 },
    '7d': { granularity: '1day', step: 1440 * MINUTE_MS, buckets: 7, hours: 168 },
};

function isRange(value) {
    return Object.prototype.hasOwnProperty.call(RANGES, value);
}

function readStoredRange() {
    try {
        const saved = window.localStorage.getItem(RANGE_KEY);
        if (isRange(saved)) return saved;
    } catch (e) { /* storage blocked: fall back to the default */ }
    return '24h';
}

let currentRange = readStoredRange();
let trafficPoints = [];
let projectStats = { at: 0, byId: {} };
const loaded = { providers: false, pools: false, projects: false };

/* ---------- small helpers ---------- */

function isMissing(n) {
    return n === null || n === undefined || Number.isNaN(Number(n));
}

function exact(n) {
    return isMissing(n) ? '—' : Number(n).toLocaleString('en-US');
}

function plural(n, word) {
    return fmtNum(n) + ' ' + word + (Number(n) === 1 ? '' : 's');
}

function proxiesWord(n) {
    return Number(n) === 1 ? 'proxy' : 'proxies';
}

function fmtRate(n) {
    if (isMissing(n)) return '—';
    const v = Number(n);
    return v > 0 && v < 10 ? v.toFixed(1).replace(/\.0$/, '') : fmtNum(v);
}

function setNumber(el, n) {
    el.textContent = fmtNum(n);
    el.title = isMissing(n) ? '' : exact(n);
}

// Error rate as the API reports it (0-100). No traffic means no rate, not "0%".
function errCell(ratePct, totalRequests) {
    if (!Number(totalRequests) || isMissing(ratePct)) return '—';
    const v = Number(ratePct);
    const text = v.toFixed(1) + '%';
    if (v >= 10) return `<span class="text-bad">${text}</span>`;
    if (v >= 5) return `<span class="text-warn">${text}</span>`;
    return text;
}

function countLabel(shown, meta, word) {
    const total = meta && Number(meta.total) > shown ? Number(meta.total) : shown;
    return total > shown ? 'first ' + shown + ' of ' + plural(total, word) : plural(shown, word);
}

function loadErrorRow(colspan, what) {
    return `<tr><td colspan="${colspan}"><div class="row">
        <span class="muted">Could not load ${what}. Retrying every 10 seconds.</span>
        <button class="btn btn-sm" type="button" onclick="Poller.refresh()">Retry now</button>
    </div></td></tr>`;
}

/* ---------- status tiles and onboarding (GET /stats/overview) ---------- */

function renderOnboarding(d) {
    const steps = [
        [document.getElementById('onboardingStepProxies'), d.total_proxies, '1'],
        [document.getElementById('onboardingStepPools'), d.total_pools, '2'],
        [document.getElementById('onboardingStepProjects'), d.total_projects, '3'],
    ];
    const incomplete = steps.some((step) => !(Number(step[1]) > 0));
    document.getElementById('onboardingCard').hidden = !incomplete;
    steps.forEach((step) => {
        const done = Number(step[1]) > 0;
        step[0].classList.toggle('done', done);
        step[0].querySelector('.num').textContent = done ? '✓' : step[2];
    });
}

function renderFleet(d) {
    setNumber(document.getElementById('statHealthy'), d.healthy_proxies);
    setNumber(document.getElementById('statDegraded'), d.degraded_proxies);
    setNumber(document.getElementById('statDead'), d.dead_proxies);

    document.getElementById('kpiHealthyFoot').textContent =
        'of ' + fmtNum(d.total_proxies) + ' ' + proxiesWord(d.total_proxies);
    const unknown = Number(d.unknown_proxies) || 0;
    document.getElementById('kpiDeadFoot').textContent =
        unknown > 0 ? fmtNum(unknown) + ' more not checked yet' : '\u00a0'; // keeps the footer line height

    const total = Number(d.total_requests_24h) || 0;
    document.getElementById('kpiRpmFoot').textContent = total > 0
        ? fmtPct(d.failed_requests_24h, total) + ' errors · ' + fmtMs(d.median_response_time_ms) + ' p50 · last 24h'
        : 'No requests in the last 24 hours';

    renderOnboarding(d);
}

async function loadFleet() {
    renderFleet(await apiCall('GET', '/api/v1/stats/overview'));
}

/* ---------- requests per minute (GET /stats/throughput, global) ---------- */

async function loadThroughput() {
    // The API already divides the last five minutes by 5 (src/api/stats.py get_throughput).
    const t = await apiCall('GET', '/api/v1/stats/throughput');
    document.getElementById('statRpm').textContent = fmtRate(t ? t.requests_per_minute : null);
}

/* ---------- traffic (GET /stats/timeseries) ---------- */

// The API omits buckets with no traffic, so lay the points onto a fixed grid of buckets.
function buildSlots(points, cfg, nowMs) {
    const current = Math.floor(nowMs / cfg.step) * cfg.step;
    const stamped = [];
    points.forEach((p) => {
        const t = Date.parse(p.period_start);
        if (!Number.isNaN(t)) stamped.push({ t: t, p: p });
    });
    // Rollups are written when a window closes, so the in-progress bucket is normally
    // absent. End on it only if the API returned it; otherwise end on the last full one.
    const end = stamped.some((x) => x.t >= current) ? current : current - cfg.step;
    const start = end - (cfg.buckets - 1) * cfg.step;
    const slots = [];
    for (let i = 0; i < cfg.buckets; i += 1) slots.push({ t: start + i * cfg.step, total: 0, failed: 0 });
    stamped.forEach((x) => {
        const i = Math.floor((x.t - start) / cfg.step);
        if (i < 0 || i >= cfg.buckets) return;
        slots[i].total += Number(x.p.total_requests) || 0;
        slots[i].failed += Number(x.p.failed_requests) || 0;
    });
    return slots;
}

function slotLabel(t, cfg, long) {
    const d = new Date(t);
    if (cfg.granularity === '1day') {
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
    }
    const clock = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    if (!long) return clock;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + clock;
}

function drawBars(slots) {
    const cfg = RANGES[currentRange];
    const max = slots.reduce((m, s) => Math.max(m, s.total), 1);
    const last = slots.length - 1;
    document.getElementById('trafficBars').innerHTML = slots.map((s, i) => {
        const totalPx = (s.total / max) * BAR_MAX_PX;
        const errPx = s.total > 0 ? Math.max(0, Math.min(totalPx, totalPx * (s.failed / s.total))) : 0;
        const reqPx = totalPx - errPx;
        const tip = `${slotLabel(s.t, cfg, true)} · ${exact(s.total)} requests · ${exact(s.failed)} errors`;
        const err = errPx > 0 ? `<div class="bars__err" style="height:${errPx.toFixed(1)}px"></div>` : '';
        const now = i === last ? ' is-now' : ''; // kept out of the attribute: the class test reads quotes in class="..." as string ends
        return `<div class="bars__col" title="${esc(tip)}">${err}<div class="bars__req${now}" style="height:${reqPx.toFixed(1)}px"></div></div>`;
    }).join('');
    const picks = [0, Math.floor(slots.length / 2), last];
    document.getElementById('trafficAxis').innerHTML =
        picks.map((i) => `<span>${esc(slotLabel(slots[i].t, cfg, false))}</span>`).join('');
}

function renderTraffic(points) {
    const slots = buildSlots(points, RANGES[currentRange], Date.now());
    drawBars(slots);
    const total = slots.reduce((sum, s) => sum + s.total, 0);
    const failed = slots.reduce((sum, s) => sum + s.failed, 0);
    const summary = total > 0
        ? fmtNum(total) + ' requests · ' + fmtPct(failed, total) + ' errors'
        : 'No requests in this range';
    document.getElementById('trafficSummary').textContent = summary;
    document.getElementById('trafficBars').setAttribute(
        'aria-label', 'Requests and errors, last ' + currentRange + ': ' + summary);
}

async function loadTraffic() {
    const range = currentRange;
    const cfg = RANGES[range];
    let resp;
    try {
        // entity_type=proxy: without it the endpoint adds the proxy, pool and project
        // rollups together, counting every request three times. /stats/overview scopes
        // its 24h totals the same way, so the two tiles agree.
        resp = await apiCall('GET', '/api/v1/stats/timeseries?entity_type=proxy&granularity='
            + cfg.granularity + '&hours=' + cfg.hours);
    } catch (e) {
        if (range === currentRange) {
            document.getElementById('trafficSummary').textContent = 'Could not load traffic, retrying';
        }
        throw e;
    }
    if (range !== currentRange) return; // the range was switched while this was in flight
    trafficPoints = (resp && resp.data) || [];
    renderTraffic(trafficPoints);
}

function syncRangeButtons() {
    document.querySelectorAll('#rangeSeg button').forEach((btn) => {
        const on = btn.dataset.range === currentRange;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-pressed', String(on));
    });
}

function drawTrafficPlaceholder() {
    trafficPoints = [];
    drawBars(buildSlots([], RANGES[currentRange], Date.now()));
    document.getElementById('trafficSummary').textContent = '';
}

async function setRange(range) {
    if (!isRange(range) || range === currentRange) return;
    currentRange = range;
    try { window.localStorage.setItem(RANGE_KEY, range); } catch (e) { /* storage blocked */ }
    syncRangeButtons();
    drawTrafficPlaceholder();
    try {
        await loadTraffic();
    } catch (e) {
        showToast('Could not load traffic: ' + e.message, 'error');
    }
}

/* ---------- providers (GET /stats/provider-health) ---------- */

function renderProviders(rows) {
    const hasRows = rows.length > 0;
    document.getElementById('providerHealthContainer').hidden = !hasRows;
    document.getElementById('providerHealthEmpty').hidden = hasRows;
    const proxies = rows.reduce((sum, p) => sum + (Number(p.total) || 0), 0);
    document.getElementById('providerHint').textContent = hasRows
        ? plural(rows.length, 'provider') + ' · ' + fmtNum(proxies) + ' ' + proxiesWord(proxies)
        : '';
    document.getElementById('providerHealthBody').innerHTML = rows.map((p) => {
        const total = Number(p.total) || 0;
        const healthy = Number(p.healthy) || 0;
        const pct = total > 0 ? Math.round((healthy / total) * 100) : 0;
        const tone = pct >= 50 ? 'lime' : pct >= 20 ? 'amber' : 'coral';
        const detail = `${exact(healthy)} healthy · ${exact(Number(p.degraded) || 0)} degraded · `
            + `${exact(Number(p.dead) || 0)} dead · ${exact(Number(p.unknown) || 0)} not checked yet`;
        return `<tr>
            <td class="strong truncate" style="max-width:200px" title="${esc(p.provider)}">${esc(p.provider)}</td>
            <td class="num">${fmtNum(total)}</td>
            <td class="num">${fmtNum(healthy)}</td>
            <td title="${esc(detail)}"><div class="row">
                <div class="meter meter--${tone} spacer" aria-hidden="true"><i style="width:${pct}%"></i></div>
                <span style="width:44px;text-align:right">${fmtPct(healthy, total, 0)}</span>
            </div></td>
        </tr>`;
    }).join('');
}

async function loadProviders() {
    let resp;
    try {
        resp = await apiCall('GET', '/api/v1/stats/provider-health');
    } catch (e) {
        if (!loaded.providers) document.getElementById('providerHealthBody').innerHTML = loadErrorRow(4, 'providers');
        throw e;
    }
    loaded.providers = true;
    renderProviders((resp && resp.data) || []);
}

/* ---------- pools (GET /pools + GET /stats/pool-metrics) ---------- */

// `metrics` is null when the metrics call failed: the pools still render, with "—".
function renderPools(pools, meta, metrics) {
    const hasRows = pools.length > 0;
    document.getElementById('poolUtilContainer').hidden = !hasRows;
    document.getElementById('poolUtilEmpty').hidden = hasRows;
    document.getElementById('poolHint').textContent = hasRows ? countLabel(pools.length, meta, 'pool') : '';
    const byPool = {};
    (metrics || []).forEach((m) => { byPool[m.pool_id] = m; });
    document.getElementById('poolUtilBody').innerHTML = pools.map((p) => {
        const m = metrics === null ? null : (byPool[p.id] || { total_requests: 0 });
        const size = Number(p.proxy_count) || 0;
        const healthy = Number(p.healthy_count) || 0;
        const badge = healthy === 0 && size > 0 ? 'badge-bad' : 'badge-quiet';
        const strategy = String(p.rotation_strategy || '').replace(/_/g, ' ');
        return `<tr>
            <td style="max-width:220px">
                <div class="strong truncate" title="${esc(p.name)}">${esc(p.name)}</div>
                <div class="sub">${esc(strategy)}</div>
            </td>
            <td class="num"><span class="badge ${badge}">${fmtNum(healthy)} / ${fmtNum(size)}</span></td>
            <td class="num">${fmtNum(m ? m.total_requests : null)}</td>
            <td class="num">${m ? errCell(m.error_rate, m.total_requests) : '—'}</td>
            <td class="num">${fmtMs(m ? m.median_latency_ms : null)}</td>
        </tr>`;
    }).join('');
}

async function loadPools() {
    const results = await Promise.allSettled([
        apiCall('GET', '/api/v1/pools?per_page=100'),
        apiCall('GET', '/api/v1/stats/pool-metrics'),
    ]);
    if (results[0].status === 'rejected') {
        if (!loaded.pools) document.getElementById('poolUtilBody').innerHTML = loadErrorRow(5, 'pools');
        throw results[0].reason;
    }
    loaded.pools = true;
    const poolsResp = results[0].value || {};
    const metrics = results[1].status === 'fulfilled' ? ((results[1].value && results[1].value.data) || []) : null;
    renderPools(poolsResp.data || [], poolsResp.meta, metrics);
}

/* ---------- projects (GET /projects + GET /projects/{id}/stats per project) ---------- */

function renderProjects(projects, meta, statsById) {
    const hasRows = projects.length > 0;
    document.getElementById('projectStatsContainer').hidden = !hasRows;
    document.getElementById('projectStatsEmpty').hidden = hasRows;
    document.getElementById('projectHint').textContent = hasRows
        ? countLabel(projects.length, meta, 'project') + ' · since the oldest metrics still kept (7 days by default)'
        : '';
    document.getElementById('projectStatsBody').innerHTML = projects.map((p) => {
        const s = statsById[p.id] || null;
        const latency = s ? (isMissing(s.median_response_time_ms) ? s.avg_response_time_ms : s.median_response_time_ms) : null;
        const bytes = s ? (Number(s.bytes_sent) || 0) + (Number(s.bytes_received) || 0) : null;
        return `<tr>
            <td class="strong truncate" style="max-width:280px" title="${esc(p.name)}">${esc(p.name)}</td>
            <td class="num">${fmtNum(s ? s.total_requests : null)}</td>
            <td class="num">${s ? errCell(s.error_rate, s.total_requests) : '—'}</td>
            <td class="num">${fmtMs(latency)}</td>
            <td class="num">${fmtBytes(bytes)}</td>
            <td class="actions"><a class="btn btn-sm btn-outline" href="/projects?project=${encodeURIComponent(p.id)}" aria-label="Open project ${esc(p.name)}">Open</a></td>
        </tr>`;
    }).join('');
}

async function loadProjects() {
    let resp;
    try {
        resp = await apiCall('GET', '/api/v1/projects?per_page=100');
    } catch (e) {
        if (!loaded.projects) document.getElementById('projectStatsBody').innerHTML = loadErrorRow(6, 'projects');
        throw e;
    }
    loaded.projects = true;
    const projects = (resp && resp.data) || [];
    // One stats call per project, and each runs a percentile over request_log: refresh
    // these on every third tick (30 s) instead of every 10 s. A failed call keeps the last value.
    if (Date.now() - projectStats.at >= PROJECT_STATS_TTL_MS) {
        const results = await Promise.allSettled(
            projects.map((p) => apiCall('GET', '/api/v1/projects/' + encodeURIComponent(p.id) + '/stats')));
        const byId = {};
        let failed = false;
        results.forEach((r, i) => {
            const id = projects[i].id;
            if (r.status === 'fulfilled' && r.value) byId[id] = r.value;
            else {
                failed = true;
                if (projectStats.byId[id]) byId[id] = projectStats.byId[id];
            }
        });
        projectStats = { at: failed ? 0 : Date.now(), byId: byId };
    }
    renderProjects(projects, resp && resp.meta, projectStats.byId);
}

/* ---------- main ---------- */

// Run by the Poller: never toasts (the sidebar status line reports outages) and one
// failing endpoint must not blank the others.
async function loadOverview() {
    await Promise.allSettled([
        loadFleet(),
        loadThroughput(),
        loadTraffic(),
        loadProviders(),
        loadPools(),
        loadProjects(),
    ]);
}

syncRangeButtons();
drawTrafficPlaceholder();
Poller.start(loadOverview, 10000);
```

Notes for the implementer: `.text-warn` / `.text-bad` (Task 1) go on a `<span>` inside the cell, because a class on the `<td>` itself would lose to `table.tbl td`. Keep quotes out of `class="..."` in the script (hence the `now` variable in `drawBars`): the class-vocabulary test cuts a class attribute at the first `'`.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS, including `test_restyled_page_has_markup_only[/dashboard]`.
Also run: `node --check src/web/static/js/pages/overview.js` (expected: no output) and `uv run ruff check tests`.

- [ ] **Step 6: Smoke check (preview server)**

Start `uv run python -m scripts.ui_preview` and open `http://127.0.0.1:8099/dashboard`. This page only reads: it sends no POST, PATCH or DELETE, so nothing here is "visible only as a success toast".

`normal` scenario:
1. Title "Overview", the Overview nav item is the white pill, no tabs, no Refresh button, no onboarding card.
2. Tiles: Healthy **6** on lime, "of 12 proxies"; Degraded **2** on amber, "rechecked every 15 seconds"; Dead **2** on coral, "2 more not checked yet"; Requests **47 / min** on a neutral tile, "6.4% errors · 290 ms p50 · last 24h". Text on the three coloured tiles is dark.
3. Traffic: exactly 24 columns, every one with a bar and a coral cap, the tallest about 170px, the last one lime; three axis labels (first, middle and last bucket, local time); legend Requests / Errors. The head reads "N requests · X% errors" with X between 3% and 8% (the preview generates the series relative to now, so N changes with the clock). Hover a bar: a tooltip like "Sep 20 16:00 · 2,204 requests · 110 errors".
4. Click 1h: 12 columns, all populated, labels five minutes apart, a smaller N. Click 7d: 7 columns, all populated, date labels ("Sep 14"). The clicked button becomes the white pill and each click sends one `GET /api/v1/stats/timeseries?entity_type=proxy&granularity=5min&hours=2` (or `1hour` / `25`, `1day` / `168`). Reload: the chosen range is still selected (`localStorage["proxysm.overview.range"]`). Against a real instance the oldest 7d bar is always empty (the API's `hours` cap, see above); the preview does not reproduce that.
5. Providers: 4 rows; webshare 75% lime bar, proxyscrape 33% amber, thespeedx 33% amber, manual 50% lime; hovering a bar cell lists healthy / degraded / dead / not checked yet. Head reads "4 providers · 12 proxies".
6. Pools: 4 rows with the strategy ("weighted random", "random", "round robin") in small muted text under the name; badges "1 / 2", "2 / 6", "3 / 4", "0 / 0", all quiet grey (the coral badge needs a pool with proxies and zero healthy, which the fixtures do not have); errors 5.8% amber, 13.6% coral, 2.9% plain, "—" for the pool with no traffic.
7. Projects: 4 rows, each "224K", "6.8%" in amber, "292 ms", "12.9 GB" (the preview answers every `/projects/{id}/stats` with the same fixture). The first numeric column is headed "Requests" and its tooltip reads "Since the oldest 5-minute metrics still kept (7 days by default)"; the tile head ends with "since the oldest metrics still kept (7 days by default)". Open on the first row goes to `/projects?project=c0de0000-0000-4000-8000-000000000003`.
8. Network tab over 30 seconds: the seven list/stats calls repeat every 10 seconds, the four `/projects/{id}/stats` calls only every third time. Switch to another tab for 30 seconds: no calls while hidden, one round when you come back.

Hostile names (still `normal`): the pool `<script>alert(1)</script>-very-long-pool-name-...` and the project `<script>alert(2)</script> " onmouseover="alert(3) very-long-project-name-...` render as literal text ending in an ellipsis, the full name is in the tooltip, no dialog opens, and moving the mouse over the project row and its Open button does nothing. In the console, `[...document.querySelectorAll('.tile')].every(t => t.scrollWidth <= t.clientWidth + 1)` is `true`, and `document.querySelector('#projectStatsBody tr:last-child a').getAttributeNames()` is exactly `["class", "href", "aria-label"]` (an `onmouseover` there means attribute injection).

`empty` scenario (open `http://127.0.0.1:8099/__scenario/empty`, then reload `/dashboard`):
9. The lavender onboarding card is above the tiles with steps 1, 2, 3, none struck through, linking to `/proxies?import=1`, `/pools?new=1`, `/projects?new=1`. Tab to a step: the focus ring is dark, not lime (Task 1 rule for coloured tiles).
10. Tiles read 0 / 0 / 0 with "of 0 proxies" and an empty Dead footer; Requests reads "0 / min" with "No requests in the last 24 hours". Traffic shows 24 two-pixel stubs and "No requests in this range". Each of the three tables is replaced by its empty state with a lime button (Import proxies, New pool, New project).
11. `/NaN|undefined|null|Infinity/.test(document.body.innerText)` is `false`.

`offline` scenario (open `/__scenario/offline`, then reload `/dashboard`):
12. The sidebar status turns coral "Offline, retrying". Tiles show "—", Traffic shows stubs and "Could not load traffic, retrying", each table shows one row "Could not load … Retrying every 10 seconds." with a Retry now button. The page is not blank and the onboarding card stays hidden.
13. Wait 30 seconds: `document.querySelectorAll('.toast').length` stays `0`. Click a range button: exactly one coral toast "Could not load traffic: …" (that click is the operator's own action).
14. Without reloading, open `/__scenario/normal` in another tab: within 10 seconds every tile and table fills in and the status line returns to "Updated just now".

Stop the preview server.

- [ ] **Step 7: Commit**

```bash
git add src/web/templates/dashboard.html src/web/static/js/pages/overview.js tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): overview page in Blocks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Proxies page

**Files:**
- Rewrite: `src/web/templates/proxies.html`
- Create: `src/web/static/js/pages/proxies.js`
- Modify: `tests/test_web_routes.py`
- Modify: `tests/test_ui_static.py` (one line: `RESTYLED_TEMPLATES`)

**Interfaces:**
- Consumes:
  - `app.js` globals: `apiCall`, `Poller`, `showToast`, `openModal`, `closeModal`, `openModalFromQuery`, `confirmAction`, `btnLoading`, `btnReset`, `copyToClipboard`, `esc`, `fmtNum`, `fmtMs`, `fmtDate`, `timeAgo`, `protoTag`, `statusBadge`, `selectedIds`, `toggleRowSelection`, `toggleSelectAll`, `clearSelection`, `updateFileInput`.
  - `base.html`: blocks `title`, `content`, `scripts`; `asset_version`; shared ids `bulkBar`, `bulkDeleteBtn`, `confirmModal`, `toastContainer`.
  - CSS from Task 1: `.page-head` (+ `__title`, `__sub`, `__actions`), `.btn` (+ `-primary`, `-secondary`, `-danger`, `-ghost`, `-sm`), `.pill` > `.dot`, `.count`, `.on-ground`, `.tile`, `.table-scroll` > `table.tbl`, `th.sortable` (+ `.sorted`), `th/td.col-check`, `.row-checkbox`, `.num`, `td.actions`, `.badge-quiet` / `-bad`, `.skeleton`, `.empty-state`, `.pagination`, `.pagination-info`, `.modal-overlay` > `.modal` (+ `.modal--wide`, `.confirm-modal`, `.confirm-message`), `.modal-actions`, `.form-group`, `.form-hint`, `.grid-2`, `.file-input-wrapper` (with its `:focus-within` ring), `.file-input-name`, `.check` (the import checkbox with its label), `.filter-row` (wrapping row: search field + pills), `.pill .dot--healthy` / `--degraded` / `--dead` / `--unknown` (status colour of a pill's dot; the "All" pill keeps the default `currentColor` dot), `.modal-head` (modal title with an action on the right), `.text-warn` (amber text for a slow latency), `.nowrap`, `.mono`, `.muted`, `.strong`, `.truncate`, `.row`, `.sr-only`, and the `[hidden]` rule. All of these exist in Task 1's `app.css`; this task does not touch the stylesheet.
  - API (all existing, unchanged):
    - `GET /api/v1/stats/overview` (reads `total_proxies`, `healthy_proxies`, `degraded_proxies`, `dead_proxies`, `unknown_proxies`)
    - `GET /api/v1/ips?page=&per_page=50[&status=][&search=][&sort_by=&sort_dir=]`; also `GET /api/v1/ips?per_page=100&pool_id={id}` and `GET /api/v1/ips?per_page=100[&provider=]` inside the import flow. Envelope `{data, meta: {total, page, per_page}}`. Proxy fields read: `id`, `host`, `port`, `protocol`, `provider` (nullable), `last_health_status`, `last_health_check` (nullable), `avg_latency_ms` (nullable). `sort_by` is one of `host`, `protocol`, `provider`, `status`, `latency`.
    - `POST /api/v1/ips/bulk` `{provider, protocol, proxies?, url?, filename?}` -> `{created, skipped, source_id}`
    - `DELETE /api/v1/ips/{id}` -> 204; `POST /api/v1/ips/{id}/check` -> `{id, status, latency_ms}` (the handler is repaired in Task 12; until then it answers 500 and the page shows "Check failed")
    - `GET /api/v1/pools?per_page=100`; `POST /api/v1/pools` `{name, rotation_strategy}`; `POST /api/v1/pools/{id}/ips` `{proxy_ids}` -> `{added}`; `DELETE /api/v1/pools/{id}/ips` `{proxy_ids}` (a DELETE with a JSON body)
    - `GET /api/v1/sources?per_page=100`; `POST /api/v1/sources` `{name, type, url, provider, protocol}`; `DELETE /api/v1/sources/{id}` -> 204; `POST /api/v1/sources/{id}/poll`. Source fields read: `id`, `name`, `type`, `url`, `provider`, `last_polled_at`, `last_status_code`, `consecutive_failures`, `proxy_count`, `created_at`.
- Produces:
  - URL parameters: `/proxies?status=healthy|degraded|dead|unknown` and `/proxies?search=<text>` preselect the filters (the Overview links to `/proxies?status=dead`); both are kept in sync with `history.replaceState`. `/proxies?import=1` opens the import modal and is stripped after opening (the Overview onboarding card and the Pools page link to it).
  - The bulk action label is exactly "Move to pool" (the Pools page refers to it by that name).
  - DOM ids: `proxyStats`, `proxySearch`, `statusFilters`, `ctAll`, `ctHealthy`, `ctDegraded`, `ctDead`, `ctUnknown`, `proxyTableWrap`, `proxyTableBody`, `selectAll`, `emptyState`, `noMatchState`, `loadError`, `pagination`, `sourcesModal`, `sourcesTableWrap`, `sourcesTableBody`, `sourcesEmpty`, `sourcesCloseBtn`, `addSourceModal`, `createSourceBtn`, `deleteSourceModal`, `deleteSourceMsg`, `deleteSourceConfirmBtn`, `importModal`, `importBtn`, `poolConflictModal` (+ `poolConflictMsg`, `poolConflictCancel`, `poolConflictMerge`, `poolConflictOverwrite`), `moveToPoolModal`, `movePoolMsg`, `movePoolSelect`, `movePoolConfirmBtn`; created by the script: `bulkRecheckBtn`, `bulkMoveBtn`.

**What changes for the operator:**
- The always-visible Sources panel is gone. "Sources" in the page head opens the same table in a modal (copy a name by clicking it, open the feed from the Type column, poll now, delete with the same confirmation). "Add source" now lives inside that modal; after adding, deleting or cancelling you land back on the source list. The coloured health dot becomes text: a coral "failing" badge (hover: how many polls failed and the last HTTP status), "static" for non-URL sources, "never" for a feed that has not been polled.
- The status filter gains an "Unknown" pill, every pill shows a coloured dot and a live count, and the filter and search are written into the URL, so `/proxies?status=dead` can be bookmarked or linked from the Overview. The head reads "2,162 from 3 sources"; the healthy count moved into its pill.
- The table and the counts refresh by themselves every 15 seconds, but never while a modal is open, a row is selected, or keyboard focus is inside the table. A failed background refresh is silent (the sidebar status line turns coral); a failed first load shows "Proxies could not be loaded" with Retry inside the tile instead of a toast.
- Two empty states instead of one: "No proxies yet" with an Import button on an empty instance, and "No proxies match" with "Clear filters" when the filter hides everything.
- Import, fixed while porting: the pool name is validated and the "Pool already exists" question is asked before anything is imported, so Cancel really cancels (before, the proxies had already been imported when the question appeared). Esc or a click outside that question now counts as Cancel (before, it left the Import button spinning forever). Only one modal is open at a time.
- Unchanged on purpose: server-side sorting (the active header shows an arrow; headers also react to Enter and Space), pagination of 50, per-row Recheck and Delete, the bulk bar with Recheck (10 at a time), Move to pool and Delete, every toast text. Slow proxies (above 500 ms) keep their amber latency.
- Not part of this milestone (milestone 3): the "Success 24h" column and the proxy detail panel.

- [ ] **Step 1: Write the failing tests**

In `tests/test_ui_static.py`, append `"proxies.html"` to the `RESTYLED_TEMPLATES` list (keep whatever earlier tasks already put there).

In `tests/test_web_routes.py`:

1. Append `"/proxies"` to the `RESTYLED_PAGES` list (keep whatever earlier tasks already put there).
2. If an earlier page task has not already added it, add this import under `from src.web.routes import router as web_router`:

```python
from tests.test_ui_static import assert_js_ids_exist
```

3. Delete the four old tests under the "Proxies page feature tests" banner, and the banner itself: `test_proxies_has_source_click_to_copy`, `test_proxies_has_pool_conflict_modal`, `test_proxies_has_dynamic_pool_placeholder` (all three looked for JavaScript names inside the HTML, which is now markup only; each is rewritten below under the same name, asserting the DOM hook in the HTML and the behaviour in `proxies.js`) and `test_proxies_sources_table_no_url_column` (replaced by `test_proxies_sources_live_in_a_modal`, which checks the exact column list instead of only "Date Added").
4. Keep as they are: `test_proxies_returns_html`, `test_providers_redirects_to_proxies`, and the shared tests that loop over `/proxies` (`test_pages_redirect_to_login_without_session`, `test_admin_password_not_embedded_in_pages`, the Task 4 shell tests).
5. Append at the end of the file:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py tests/test_ui_static.py -q -k "proxies"`

Expected: `test_proxies_returns_html` and `test_providers_redirects_to_proxies` PASS; everything else selected FAILS:
- `test_restyled_page_has_markup_only[/proxies]`: the old page still has an inline `<style>` and `<script>`.
- `test_template_and_script_use_only_defined_classes[proxies.html]`: the old template uses `page-header`, `fpill`, `panel` and other classes `app.css` does not define.
- `test_proxies_script_ids_exist_in_the_page`, `test_proxies_script_contract` and every test that reads the script: `FileNotFoundError` (no `proxies.js`).
- `test_proxies_page_structure`, `test_proxies_status_pills_and_search`, `test_proxies_table_columns`, `test_proxies_modals_are_labelled_dialogs`: the new ids and attributes are missing.

- [ ] **Step 3: Rewrite the template**

Replace the whole of `src/web/templates/proxies.html` with:

```html
{% extends "base.html" %}
{% block title %}Proxies - Proxysm{% endblock %}

{% block content %}
<div class="page-head">
    <div class="page-head__title">
        <h1>Proxies</h1>
        <span class="page-head__sub" id="proxyStats"></span>
    </div>
    <div class="page-head__actions">
        <button class="btn btn-secondary" type="button" onclick="openSources()">Sources</button>
        <button class="btn btn-primary" type="button" onclick="openModal('importModal')">Import</button>
    </div>
</div>

<div class="filter-row">
    <label for="proxySearch" class="sr-only">Search proxies</label>
    <input type="search" id="proxySearch" class="on-ground" placeholder="Search host or provider" autocomplete="off" style="width:270px">
    <div class="filter-row" id="statusFilters" role="group" aria-label="Filter by status">
        <button class="pill active" type="button" data-status="" aria-pressed="true" onclick="setStatusFilter('')"><span class="dot"></span>All <span class="count" id="ctAll"></span></button>
        <button class="pill" type="button" data-status="healthy" aria-pressed="false" onclick="setStatusFilter('healthy')"><span class="dot dot--healthy"></span>Healthy <span class="count" id="ctHealthy"></span></button>
        <button class="pill" type="button" data-status="degraded" aria-pressed="false" onclick="setStatusFilter('degraded')"><span class="dot dot--degraded"></span>Degraded <span class="count" id="ctDegraded"></span></button>
        <button class="pill" type="button" data-status="dead" aria-pressed="false" onclick="setStatusFilter('dead')"><span class="dot dot--dead"></span>Dead <span class="count" id="ctDead"></span></button>
        <button class="pill" type="button" data-status="unknown" aria-pressed="false" onclick="setStatusFilter('unknown')"><span class="dot dot--unknown"></span>Unknown <span class="count" id="ctUnknown"></span></button>
    </div>
</div>

<section class="tile" aria-label="Proxy list">
    <div class="table-scroll" id="proxyTableWrap">
        <table class="tbl">
            <thead>
                <tr>
                    <th class="col-check"><input type="checkbox" class="row-checkbox" id="selectAll" aria-label="Select all proxies on this page" onchange="toggleSelectAll(this)"></th>
                    <th class="sortable" data-sort="host" tabindex="0" aria-sort="none" onclick="toggleSort('host')">Host : port</th>
                    <th class="sortable" data-sort="protocol" tabindex="0" aria-sort="none" onclick="toggleSort('protocol')">Protocol</th>
                    <th class="sortable" data-sort="provider" tabindex="0" aria-sort="none" onclick="toggleSort('provider')">Provider</th>
                    <th class="sortable" data-sort="status" tabindex="0" aria-sort="none" onclick="toggleSort('status')">Status</th>
                    <th class="sortable num" data-sort="latency" tabindex="0" aria-sort="none" onclick="toggleSort('latency')">Latency</th>
                    <th class="num">Last check</th>
                    <th><span class="sr-only">Actions</span></th>
                </tr>
            </thead>
            <tbody id="proxyTableBody">
                {% for _ in range(6) %}
                <tr><td colspan="8"><div class="skeleton" style="height:14px"></div></td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="empty-state" id="emptyState" hidden>
        <div class="empty-state-icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01"/></svg></div>
        <h3>No proxies yet</h3>
        <p>Import a list or add a source feed to get started.</p>
        <button class="btn btn-primary" type="button" onclick="openModal('importModal')">Import proxies</button>
    </div>
    <div class="empty-state" id="noMatchState" hidden>
        <h3>No proxies match</h3>
        <p>Nothing matches the current search and status filter.</p>
        <button class="btn" type="button" onclick="clearFilters()">Clear filters</button>
    </div>
    <div class="empty-state" id="loadError" hidden>
        <h3>Proxies could not be loaded</h3>
        <p>The API is not responding. Retrying automatically.</p>
        <button class="btn" type="button" onclick="retryLoad()">Retry now</button>
    </div>
    <div class="pagination" id="pagination"></div>
</section>

<!-- Sources -->
<div class="modal-overlay" id="sourcesModal" role="dialog" aria-modal="true" aria-labelledby="sourcesTitle">
    <div class="modal modal--wide" style="max-width:1000px">
        <div class="modal-head">
            <h2 id="sourcesTitle">Sources</h2>
            <button class="btn btn-primary btn-sm" type="button" onclick="openAddSource()">Add source</button>
        </div>
        <p class="form-group muted">Auto-polled feeds and manual imports. Click a name to copy it.</p>
        <div class="table-scroll" id="sourcesTableWrap">
            <table class="tbl">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Provider</th>
                        <th>Date added</th>
                        <th>Last polled</th>
                        <th class="num">Proxies</th>
                        <th><span class="sr-only">Actions</span></th>
                    </tr>
                </thead>
                <tbody id="sourcesTableBody">
                    <tr><td colspan="7"><div class="skeleton" style="height:14px"></div></td></tr>
                </tbody>
            </table>
        </div>
        <div class="empty-state" id="sourcesEmpty" hidden>
            <h3>No sources yet</h3>
            <p>Add a feed URL and Proxysm will import from it on a schedule.</p>
            <button class="btn btn-primary" type="button" onclick="openAddSource()">Add source</button>
        </div>
        <div class="modal-actions">
            <button class="btn" type="button" id="sourcesCloseBtn" onclick="closeModal('sourcesModal')">Close</button>
        </div>
    </div>
</div>

<!-- Add source (opened from the Sources modal) -->
<div class="modal-overlay" id="addSourceModal" role="dialog" aria-modal="true" aria-labelledby="addSourceTitle">
    <div class="modal">
        <h2 id="addSourceTitle">Add source</h2>
        <p class="form-group muted">Auto-poll a provider feed on a schedule.</p>
        <div class="form-group">
            <label for="sourceName">Name</label>
            <input type="text" id="sourceName" placeholder="e.g. my-proxy-feed" autocomplete="off">
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label for="sourceType">Type</label>
                <select id="sourceType" onchange="toggleSourceUrl()">
                    <option value="url" selected>URL (auto-polled)</option>
                    <option value="manual">Manual</option>
                </select>
            </div>
            <div class="form-group">
                <label for="sourceProtocol">Protocol</label>
                <select id="sourceProtocol">
                    <option value="http" selected>HTTP</option>
                    <option value="https">HTTPS</option>
                    <option value="socks5">SOCKS5</option>
                </select>
            </div>
        </div>
        <div class="form-group" id="sourceUrlGroup">
            <label for="sourceUrl">URL</label>
            <input type="text" id="sourceUrl" placeholder="https://provider.com/api/proxies" autocomplete="off">
        </div>
        <div class="form-group">
            <label for="sourceProvider">Provider</label>
            <input type="text" id="sourceProvider" placeholder="e.g. BrightData" autocomplete="off">
        </div>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('addSourceModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="createSourceBtn" onclick="createSource()">Create</button>
        </div>
    </div>
</div>

<!-- Delete source confirmation (opened from the Sources modal) -->
<div class="modal-overlay confirm-modal" id="deleteSourceModal" role="dialog" aria-modal="true" aria-labelledby="deleteSourceTitle">
    <div class="modal">
        <h2 id="deleteSourceTitle">Delete source</h2>
        <p class="confirm-message" id="deleteSourceMsg">This will permanently delete this source and all its proxies. Are you sure?</p>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('deleteSourceModal')">Cancel</button>
            <button class="btn btn-danger" type="button" id="deleteSourceConfirmBtn" onclick="confirmDeleteSource()">Delete</button>
        </div>
    </div>
</div>

<!-- Import -->
<div class="modal-overlay" id="importModal" role="dialog" aria-modal="true" aria-labelledby="importTitle">
    <div class="modal">
        <h2 id="importTitle">Import proxies</h2>
        <p class="form-group muted">Paste a list, upload a file, or fetch from a provider URL.</p>
        <div class="grid-2">
            <div class="form-group">
                <label for="importProvider">Provider (optional label)</label>
                <input type="text" id="importProvider" placeholder="e.g. BrightData, IPRoyal" autocomplete="off" oninput="updatePoolPlaceholder()">
            </div>
            <div class="form-group">
                <label for="importProtocol">Protocol</label>
                <select id="importProtocol">
                    <option value="http" selected>HTTP</option>
                    <option value="https">HTTPS</option>
                    <option value="socks5">SOCKS5</option>
                </select>
            </div>
        </div>
        <div class="form-group">
            <label for="importText">Proxy list (one per line)</label>
            <textarea id="importText" class="mono" rows="5" placeholder="host:port@user:pass&#10;socks5://user:pass@host:port&#10;host:port:user:pass"></textarea>
        </div>
        <div class="form-group">
            <label for="importFile">Or upload a file</label>
            <div class="file-input-wrapper">
                <input type="file" id="importFile" accept=".txt,.csv" onchange="updateFileInput(this, document.getElementById('fileName'))">
                <span class="btn btn-sm" aria-hidden="true">Choose file</span>
                <span class="file-input-name" id="fileName">No file selected</span>
            </div>
        </div>
        <div class="form-group">
            <label for="importUrl">Or fetch from URL</label>
            <input type="text" id="importUrl" placeholder="https://provider.com/api/getproxy/?format=txt" autocomplete="off">
        </div>
        <div class="form-group">
            <label class="check" for="importCreatePool">
                <input type="checkbox" id="importCreatePool" onchange="togglePoolFields()">
                Also create a pool from this import
            </label>
        </div>
        <div id="importPoolFields" hidden>
            <div class="form-group">
                <label for="importPoolName">Pool name</label>
                <input type="text" id="importPoolName" placeholder="my-provider-001" autocomplete="off">
            </div>
            <div class="form-group">
                <label for="importPoolStrategy">Rotation strategy</label>
                <select id="importPoolStrategy">
                    <option value="round_robin" selected>Round robin</option>
                    <option value="random">Random</option>
                </select>
            </div>
        </div>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('importModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="importBtn" onclick="doImport()">Import</button>
        </div>
    </div>
</div>

<!-- Pool conflict (asked by the import flow when the pool name is taken) -->
<div class="modal-overlay confirm-modal" id="poolConflictModal" role="dialog" aria-modal="true" aria-labelledby="poolConflictTitle">
    <div class="modal">
        <h2 id="poolConflictTitle">Pool already exists</h2>
        <p class="confirm-message" id="poolConflictMsg"></p>
        <p class="form-hint"><strong>Merge</strong> adds the new proxies alongside the existing ones. <strong>Overwrite</strong> removes the existing proxies from the pool first.</p>
        <div class="modal-actions">
            <button class="btn" type="button" id="poolConflictCancel">Cancel</button>
            <button class="btn btn-primary" type="button" id="poolConflictMerge">Merge</button>
            <button class="btn btn-danger" type="button" id="poolConflictOverwrite">Overwrite</button>
        </div>
    </div>
</div>

<!-- Move to pool (bulk action) -->
<div class="modal-overlay" id="moveToPoolModal" role="dialog" aria-modal="true" aria-labelledby="movePoolTitle">
    <div class="modal">
        <h2 id="movePoolTitle">Move to pool</h2>
        <p class="form-group muted" id="movePoolMsg"></p>
        <div class="form-group">
            <label for="movePoolSelect">Pool</label>
            <select id="movePoolSelect"></select>
        </div>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('moveToPoolModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="movePoolConfirmBtn" onclick="confirmMoveToPool()">Add to pool</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/pages/proxies.js?v={{ asset_version }}"></script>
{% endblock %}
```

Notes for the implementer:
- The import checkbox uses the shared `.check` label and must NOT get `.row-checkbox`: `clearSelection()` in `app.js` unticks every `.row-checkbox` in the document, and the table re-render calls it.
- Visibility is switched with the `hidden` attribute only (`app.css` has `[hidden] { display: none !important; }`).
- The Sources modal overrides the 860px `.modal--wide` cap with `max-width:1000px` because seven columns do not fit in 860px; below that width the table scrolls inside `.table-scroll`.
- The six skeleton rows are what the operator sees until the first response arrives.

- [ ] **Step 4: Write the page script**

Create `src/web/static/js/pages/proxies.js`:

```js
/* Proxies page: status pills + search (both server-side, mirrored in the URL), sortable
   paginated table, bulk actions, and the Sources / Import / Move-to-pool modals.
   Classic script. Uses the globals from app.js; never redefines them. */
'use strict';

const PAGE_SIZE = 50;
const STATUSES = ['healthy', 'degraded', 'dead', 'unknown'];

let currentPage = 1;
let sortColumn = null;
let sortDir = 'asc';
let statusFilter = '';
let searchQuery = '';
let searchTimer = null;

let loadSeq = 0;           // responses that arrive out of order are dropped
let userLoads = 0;         // user-initiated table loads in flight
let loadedOnce = false;
let firstRefresh = true;

let overview = null;       // last good GET /stats/overview body
let sources = null;        // last good source list; null = never loaded
let sourcesTotal = null;

let deleteSourceId = null;
let moveIds = [];

/* ---------- small helpers ---------- */
function shorten(text, max) {
    const s = String(text);
    return s.length > max ? s.slice(0, max) + '…' : s;
}

function proxyWord(n) { return n === 1 ? 'proxy' : 'proxies'; }

// True while a background refresh would disturb the operator
function isBusy() {
    if (selectedIds.size > 0) return true;
    if (document.querySelector('.modal-overlay.active')) return true;
    return document.getElementById('proxyTableBody').contains(document.activeElement);
}

// Runs fn once, the next time the modal loses .active (button, Esc or a click outside)
function onceClosed(modalId, fn) {
    const modal = document.getElementById(modalId);
    const observer = new MutationObserver(() => {
        if (modal.classList.contains('active')) return;
        observer.disconnect();
        fn();
    });
    observer.observe(modal, { attributes: true, attributeFilter: ['class'] });
}

/* ---------- URL state: ?status=dead&search=foo ---------- */
function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    statusFilter = STATUSES.includes(status) ? status : '';
    searchQuery = (params.get('search') || '').trim();
    document.getElementById('proxySearch').value = searchQuery;
}

function syncUrl() {
    const params = new URLSearchParams(window.location.search);
    if (statusFilter) params.set('status', statusFilter); else params.delete('status');
    if (searchQuery) params.set('search', searchQuery); else params.delete('search');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
}

/* ---------- filters and sorting ---------- */
function renderPills() {
    document.querySelectorAll('#statusFilters .pill').forEach((pill) => {
        const on = pill.dataset.status === statusFilter;
        pill.classList.toggle('active', on);
        pill.setAttribute('aria-pressed', String(on));
    });
}

function setStatusFilter(status) {
    statusFilter = STATUSES.includes(status) ? status : '';
    renderPills();
    syncUrl();
    currentPage = 1;
    reloadTable();
}

function clearFilters() {
    clearTimeout(searchTimer);
    statusFilter = '';
    searchQuery = '';
    document.getElementById('proxySearch').value = '';
    renderPills();
    syncUrl();
    currentPage = 1;
    reloadTable();
}

function renderSortHeaders() {
    document.querySelectorAll('th.sortable').forEach((th) => {
        if (!th.dataset.label) th.dataset.label = th.textContent.trim();
        const on = th.dataset.sort === sortColumn;
        const arrow = sortDir === 'asc' ? ' ↑' : ' ↓';
        th.classList.toggle('sorted', on);
        th.setAttribute('aria-sort', on ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none');
        th.textContent = th.dataset.label + (on ? arrow : '');
    });
}

function toggleSort(col) {
    if (sortColumn === col) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = col;
        sortDir = 'asc';
    }
    renderSortHeaders();
    currentPage = 1;
    reloadTable();
}

function goPage(p) {
    currentPage = p;
    reloadTable();
}

/* ---------- page head and pill counts ---------- */
function renderHead() {
    const el = document.getElementById('proxyStats');
    if (!overview) { el.textContent = ''; return; }
    const total = fmtNum(overview.total_proxies);
    if (sourcesTotal === null) { el.textContent = total + ' total'; return; }
    el.textContent = total + ' from ' + fmtNum(sourcesTotal) + (sourcesTotal === 1 ? ' source' : ' sources');
}

function renderCounts() {
    if (!overview) return;
    document.getElementById('ctAll').textContent = fmtNum(overview.total_proxies);
    document.getElementById('ctHealthy').textContent = fmtNum(overview.healthy_proxies);
    document.getElementById('ctDegraded').textContent = fmtNum(overview.degraded_proxies);
    document.getElementById('ctDead').textContent = fmtNum(overview.dead_proxies);
    document.getElementById('ctUnknown').textContent = fmtNum(overview.unknown_proxies);
}

/* ---------- proxy table ---------- */
function showState(state) {
    document.getElementById('proxyTableWrap').hidden = state !== 'rows';
    document.getElementById('emptyState').hidden = state !== 'empty';
    document.getElementById('noMatchState').hidden = state !== 'nomatch';
    document.getElementById('loadError').hidden = state !== 'error';
    if (state !== 'rows') document.getElementById('pagination').innerHTML = '';
}

function latencyCell(p) {
    if (!p.avg_latency_ms) return '<span class="muted">—</span>';
    const text = fmtMs(p.avg_latency_ms);
    return p.avg_latency_ms > 500 ? `<span class="text-warn">${text}</span>` : text;
}

function proxyRow(p) {
    return `<tr>
        <td class="col-check"><input type="checkbox" class="row-checkbox" aria-label="Select proxy"></td>
        <td><div class="mono strong truncate" data-cell="host" style="max-width:300px">${esc(p.host)}<span class="muted">:${esc(p.port)}</span></div></td>
        <td>${protoTag(p.protocol)}</td>
        <td><div class="truncate" data-cell="provider" style="max-width:180px">${p.provider ? esc(p.provider) : '<span class="muted">—</span>'}</div></td>
        <td>${statusBadge(p.last_health_status)}</td>
        <td class="num nowrap">${latencyCell(p)}</td>
        <td class="num nowrap"><span class="muted" data-cell="checked">${esc(timeAgo(p.last_health_check))}</span></td>
        <td class="actions">
            <button class="btn btn-ghost btn-sm" type="button" data-action="recheck" aria-label="Recheck" title="Recheck"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>
            <button class="btn btn-danger btn-sm" type="button" data-action="delete">Delete</button>
        </td>
    </tr>`;
}

// Anything from the API that lands in an attribute is set as a DOM property, never interpolated
function hydrateProxyRow(tr, p) {
    const addr = p.host + ':' + p.port;
    const checkbox = tr.querySelector('.row-checkbox');
    tr.dataset.id = p.id;
    checkbox.dataset.id = p.id;
    checkbox.setAttribute('aria-label', 'Select ' + addr);
    tr.querySelector('[data-cell="host"]').title = addr;
    if (p.provider) tr.querySelector('[data-cell="provider"]').title = p.provider;
    if (p.last_health_check) {
        tr.querySelector('[data-cell="checked"]').title = new Date(p.last_health_check).toLocaleString();
    }
    tr.querySelector('[data-action="recheck"]').setAttribute('aria-label', 'Recheck ' + addr);
    tr.querySelector('[data-action="delete"]').setAttribute('aria-label', 'Delete ' + addr);
}

function renderProxies(proxies) {
    const tbody = document.getElementById('proxyTableBody');
    if (proxies.length === 0) {
        tbody.innerHTML = '';
        showState(statusFilter || searchQuery ? 'nomatch' : 'empty');
        clearSelection();
        return;
    }
    showState('rows');
    tbody.innerHTML = proxies.map(proxyRow).join('');
    Array.from(tbody.rows).forEach((tr, i) => hydrateProxyRow(tr, proxies[i]));
    clearSelection();
}

function renderPagination(total, shownCount) {
    const el = document.getElementById('pagination');
    if (total === 0) { el.innerHTML = ''; return; }
    const focused = el.contains(document.activeElement) ? document.activeElement.dataset.dir : null;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const from = (currentPage - 1) * PAGE_SIZE + 1;
    const to = (currentPage - 1) * PAGE_SIZE + shownCount;
    el.innerHTML = `
        <span>Showing <span class="strong">${from.toLocaleString('en-US')}–${to.toLocaleString('en-US')}</span> of <span class="strong">${total.toLocaleString('en-US')}</span></span>
        <div class="row">
            <button class="btn btn-sm" type="button" data-dir="prev" ${currentPage <= 1 ? 'disabled' : ''} onclick="goPage(${currentPage - 1})">Previous</button>
            <span class="pagination-info">Page ${currentPage} of ${totalPages}</span>
            <button class="btn btn-sm" type="button" data-dir="next" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goPage(${currentPage + 1})">Next</button>
        </div>`;
    if (focused) {
        const again = el.querySelector(`[data-dir="${focused}"]`);
        if (again && !again.disabled) again.focus();
    }
}

/* ---------- loaders (silent: they throw, the caller decides whether to toast) ---------- */
async function loadOverview() {
    overview = await apiCall('GET', '/api/v1/stats/overview');
    renderCounts();
    renderHead();
}

async function loadProxies(background, retried) {
    loadSeq += 1;
    const seq = loadSeq;
    let url = `/api/v1/ips?page=${currentPage}&per_page=${PAGE_SIZE}`;
    if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
    if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;
    if (sortColumn) url += `&sort_by=${sortColumn}&sort_dir=${sortDir}`;
    let data;
    try {
        data = await apiCall('GET', url);
    } catch (e) {
        if (seq === loadSeq && !loadedOnce) showState('error');
        throw e;
    }
    if (seq !== loadSeq) return;                          // a newer request is on its way
    if (background && loadedOnce && isBusy()) return;     // the operator started working meanwhile
    const proxies = data.data || [];
    const total = data.meta && typeof data.meta.total === 'number' ? data.meta.total : proxies.length;
    if (proxies.length === 0 && total > 0 && currentPage > 1 && !retried) {
        // The last page emptied (deletes): step back to the new last page
        currentPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
        await loadProxies(background, true);
        return;
    }
    loadedOnce = true;
    renderProxies(proxies);
    renderPagination(total, proxies.length);
}

// After a user action: reload the table and say so if that fails
function reloadTable() {
    userLoads += 1;
    return loadProxies(false)
        .catch((e) => showToast('Failed to load proxies: ' + e.message, 'error'))
        .finally(() => { userLoads -= 1; });
}

function reloadCounts() {
    loadOverview().catch(() => { /* the status line reports outages */ });
}

function retryLoad() {
    reloadTable();
    reloadCounts();
    loadSources().catch(() => { /* the status line reports outages */ });
}

// Poller target. Never toasts; skipped while a modal is open, a row is selected,
// focus is inside the table, or a user-initiated load is still in flight.
async function refresh() {
    if (!firstRefresh && (isBusy() || userLoads > 0)) return;
    firstRefresh = false;
    const jobs = [loadProxies(true), loadOverview()];
    if (sources === null) jobs.push(loadSources());   // first run, or still missing after an outage
    await Promise.all(jobs);
}

/* ---------- row actions ---------- */
async function deleteProxy(id) {
    if (!(await confirmAction('This proxy will be permanently removed.'))) return;
    try {
        await apiCall('DELETE', `/api/v1/ips/${id}`);
        showToast('Proxy deleted', 'success');
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

async function checkProxy(id, btn) {
    btnLoading(btn);
    try {
        const result = await apiCall('POST', `/api/v1/ips/${id}/check`);
        const latency = result.latency_ms ? ` (${fmtMs(result.latency_ms)})` : '';
        showToast(`Check complete: ${result.status}${latency}`, 'success');
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Check failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

/* ---------- bulk actions ---------- */
async function bulkDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!(await confirmAction(`Delete ${ids.length} ${proxyWord(ids.length)}? This cannot be undone.`))) return;
    let deleted = 0;
    for (const id of ids) {
        try {
            await apiCall('DELETE', `/api/v1/ips/${id}`);
            deleted += 1;
        } catch (e) { /* counted as not deleted */ }
    }
    showToast(`Deleted ${deleted} ${proxyWord(deleted)}`, 'success');
    clearSelection();
    reloadTable();
    reloadCounts();
}

async function bulkRecheck() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    showToast(`Rechecking ${ids.length} ${proxyWord(ids.length)}...`, 'success');
    let done = 0;
    for (let i = 0; i < ids.length; i += 10) {
        const chunk = ids.slice(i, i + 10);
        const results = await Promise.all(chunk.map((id) =>
            apiCall('POST', `/api/v1/ips/${id}/check`).then(() => true).catch(() => false)
        ));
        done += results.filter(Boolean).length;
    }
    showToast(`Rechecked ${done} of ${ids.length} ${proxyWord(ids.length)}`, 'success');
    clearSelection();
    reloadTable();
    reloadCounts();
}

async function openMoveToPool() {
    moveIds = Array.from(selectedIds);
    if (moveIds.length === 0) return;
    const select = document.getElementById('movePoolSelect');
    select.innerHTML = '<option value="">Loading pools...</option>';
    document.getElementById('movePoolMsg').textContent =
        `Add ${moveIds.length} selected ${proxyWord(moveIds.length)} to a pool.`;
    openModal('moveToPoolModal');
    try {
        const data = await apiCall('GET', '/api/v1/pools?per_page=100');
        const pools = data.data || [];
        if (pools.length === 0) {
            select.innerHTML = '<option value="">No pools available</option>';
            return;
        }
        select.innerHTML = pools.map((p) =>
            `<option>${esc(p.name)} (${fmtNum(p.proxy_count || 0)} proxies)</option>`
        ).join('');
        Array.from(select.options).forEach((option, i) => { option.value = pools[i].id; });
    } catch (e) {
        select.innerHTML = '<option value="">Failed to load pools</option>';
        showToast('Failed to load pools: ' + e.message, 'error');
    }
}

async function confirmMoveToPool() {
    const poolId = document.getElementById('movePoolSelect').value;
    if (!poolId) { showToast('Please select a pool', 'error'); return; }
    if (moveIds.length === 0) { closeModal('moveToPoolModal'); return; }
    const btn = document.getElementById('movePoolConfirmBtn');
    btnLoading(btn);
    try {
        const result = await apiCall('POST', `/api/v1/pools/${poolId}/ips`, { proxy_ids: moveIds });
        closeModal('moveToPoolModal');
        showToast(`Added ${result.added} ${proxyWord(result.added)} to pool`, 'success');
        clearSelection();
    } catch (e) {
        showToast('Move to pool failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

function injectBulkButtons() {
    const deleteBtn = document.getElementById('bulkDeleteBtn');
    const recheckBtn = document.createElement('button');
    recheckBtn.type = 'button';
    recheckBtn.id = 'bulkRecheckBtn';
    recheckBtn.className = 'btn btn-sm';
    recheckBtn.textContent = 'Recheck';
    recheckBtn.onclick = bulkRecheck;
    const moveBtn = document.createElement('button');
    moveBtn.type = 'button';
    moveBtn.id = 'bulkMoveBtn';
    moveBtn.className = 'btn btn-sm';
    moveBtn.textContent = 'Move to pool';
    moveBtn.onclick = openMoveToPool;
    deleteBtn.parentNode.insertBefore(recheckBtn, deleteBtn);
    deleteBtn.parentNode.insertBefore(moveBtn, deleteBtn);
    deleteBtn.onclick = bulkDelete;
}

/* ---------- sources (modal) ---------- */
function lastPolledCell(s) {
    if (s.type !== 'url') return '<span class="badge badge-quiet">static</span>';
    const when = s.last_polled_at ? esc(timeAgo(s.last_polled_at)) + ' ago' : 'never';
    if (s.consecutive_failures > 0) {
        return `${when} <span class="badge badge-bad" data-cell="failing">failing</span>`;
    }
    return when;
}

function sourceRow(s) {
    const pollBtn = s.type === 'url'
        ? '<button class="btn btn-ghost btn-sm" type="button" data-action="poll" aria-label="Poll now" title="Poll now"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>'
        : '';
    return `<tr>
        <td><button class="btn btn-ghost btn-sm" type="button" data-action="copy" style="max-width:220px"><span class="mono strong truncate" data-cell="name">${esc(s.name)}</span></button></td>
        <td data-cell="type">${esc(s.type)}</td>
        <td><div class="truncate" data-cell="provider" style="max-width:130px">${s.provider ? esc(s.provider) : '<span class="muted">—</span>'}</div></td>
        <td class="nowrap">${s.created_at ? esc(fmtDate(s.created_at)) : '<span class="muted">—</span>'}</td>
        <td class="nowrap">${lastPolledCell(s)}</td>
        <td class="num strong">${fmtNum(s.proxy_count)}</td>
        <td class="actions">${pollBtn}<button class="btn btn-danger btn-sm" type="button" data-action="delete">Delete</button></td>
    </tr>`;
}

function feedUrl(s) {
    if (s.type !== 'url' || !s.url) return null;
    try {
        const parsed = new URL(s.url);
        return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null;
    } catch (e) {
        return null;
    }
}

function hydrateSourceRow(tr, s) {
    tr.dataset.id = s.id;
    tr.querySelector('[data-action="copy"]').title = s.name + '\nClick to copy';
    if (s.provider) tr.querySelector('[data-cell="provider"]').title = s.provider;
    const failing = tr.querySelector('[data-cell="failing"]');
    if (failing) {
        failing.title = s.consecutive_failures + ' failed polls in a row'
            + (s.last_status_code ? ', last HTTP ' + s.last_status_code : '');
    }
    const href = feedUrl(s);
    if (href) {
        // The type doubles as a link to the feed, as before (there is no URL column)
        const link = document.createElement('a');
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.title = s.url;
        link.textContent = s.type + ' ↗';
        const cell = tr.querySelector('[data-cell="type"]');
        cell.textContent = '';
        cell.appendChild(link);
    }
}

function renderSources() {
    const wrap = document.getElementById('sourcesTableWrap');
    const empty = document.getElementById('sourcesEmpty');
    const tbody = document.getElementById('sourcesTableBody');
    if (sources === null) {
        wrap.hidden = false;
        empty.hidden = true;
        tbody.innerHTML = '<tr><td colspan="7"><span class="muted">Sources could not be loaded.</span></td></tr>';
        return;
    }
    wrap.hidden = sources.length === 0;
    empty.hidden = sources.length > 0;
    tbody.innerHTML = sources.map(sourceRow).join('');
    Array.from(tbody.rows).forEach((tr, i) => hydrateSourceRow(tr, sources[i]));
}

async function loadSources() {
    const data = await apiCall('GET', '/api/v1/sources?per_page=100');
    sources = data.data || [];
    sourcesTotal = data.meta && typeof data.meta.total === 'number' ? data.meta.total : sources.length;
    renderSources();
    renderHead();
}

function findSource(id) {
    return (sources || []).find((s) => s.id === id) || null;
}

function openSources() {
    openModal('sourcesModal');
    document.getElementById('sourcesCloseBtn').focus();
    loadSources().catch((e) => {
        renderSources();
        showToast('Failed to load sources: ' + e.message, 'error');
    });
}

// One modal at a time: hide the Sources list, show the child, come back when the child closes
function openFromSources(childId) {
    closeModal('sourcesModal');
    openModal(childId);
    onceClosed(childId, openSources);
}

function openAddSource() {
    openFromSources('addSourceModal');
}

function toggleSourceUrl() {
    document.getElementById('sourceUrlGroup').hidden = document.getElementById('sourceType').value !== 'url';
}

function copySourceName(id, btn) {
    const source = findSource(id);
    if (!source) return;
    copyToClipboard(source.name).then((ok) => {
        if (!ok) { showToast('Copy failed, select the text manually', 'error'); return; }
        const label = btn.querySelector('[data-cell="name"]');
        label.textContent = 'Copied!';
        setTimeout(() => { label.textContent = source.name; }, 1500);
        showToast('Source name copied', 'success');
    });
}

async function createSource() {
    const name = document.getElementById('sourceName').value.trim();
    const type = document.getElementById('sourceType').value;
    const url = document.getElementById('sourceUrl').value.trim() || null;
    const protocol = document.getElementById('sourceProtocol').value;
    const provider = document.getElementById('sourceProvider').value.trim() || null;
    if (!name) { showToast('Please enter a name', 'error'); return; }
    if (type === 'url' && !url) { showToast('Please enter a URL for URL sources', 'error'); return; }
    const btn = document.getElementById('createSourceBtn');
    btnLoading(btn);
    try {
        await apiCall('POST', '/api/v1/sources', {
            name: name, type: type, url: url, provider: provider, protocol: protocol,
        });
        showToast('Source created', 'success');
        document.getElementById('sourceName').value = '';
        document.getElementById('sourceUrl').value = '';
        document.getElementById('sourceProvider').value = '';
        closeModal('addSourceModal');     // the Sources list reopens and reloads (openFromSources)
        reloadCounts();
    } catch (e) {
        showToast('Failed to create source: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

function promptDeleteSource(id) {
    const source = findSource(id);
    if (!source) return;
    deleteSourceId = id;
    document.getElementById('deleteSourceMsg').textContent =
        `This will permanently delete source "${shorten(source.name, 60)}" and all ${fmtNum(source.proxy_count || 0)} proxies imported from it. Are you sure?`;
    openFromSources('deleteSourceModal');
}

async function confirmDeleteSource() {
    if (!deleteSourceId) return;
    const btn = document.getElementById('deleteSourceConfirmBtn');
    btnLoading(btn);
    try {
        await apiCall('DELETE', `/api/v1/sources/${deleteSourceId}`);
        deleteSourceId = null;
        showToast('Source and its proxies deleted', 'success');
        closeModal('deleteSourceModal');  // the Sources list reopens and reloads (openFromSources)
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

async function pollSource(id, btn) {
    btnLoading(btn);
    showToast('Polling source...', 'success');
    try {
        await apiCall('POST', `/api/v1/sources/${id}/poll`);
        showToast('Poll complete', 'success');
        loadSources().catch(() => { /* the status line reports outages */ });
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Poll failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

/* ---------- import ---------- */
function updatePoolPlaceholder() {
    const provider = document.getElementById('importProvider').value.trim();
    document.getElementById('importPoolName').placeholder =
        provider ? provider.toLowerCase().replace(/\s+/g, '-') + '-001' : 'my-provider-001';
}

function togglePoolFields() {
    document.getElementById('importPoolFields').hidden = !document.getElementById('importCreatePool').checked;
}

// Resolves 'merge', 'overwrite' or 'cancel'. One modal at a time: the import modal is
// hidden while the question is open and comes back when it is answered.
function askPoolConflict(poolName, proxyCount) {
    return new Promise((resolve) => {
        let settled = false;
        function finish(action) {
            if (settled) return;
            settled = true;
            closeModal('poolConflictModal');
            openModal('importModal');
            resolve(action);
        }
        document.getElementById('poolConflictMsg').textContent =
            `A pool named "${shorten(poolName, 60)}" already exists with ${fmtNum(proxyCount)} proxies.`;
        document.getElementById('poolConflictMerge').onclick = () => finish('merge');
        document.getElementById('poolConflictOverwrite').onclick = () => finish('overwrite');
        document.getElementById('poolConflictCancel').onclick = () => finish('cancel');
        closeModal('importModal');
        openModal('poolConflictModal');
        document.getElementById('poolConflictCancel').focus();
        onceClosed('poolConflictModal', () => finish('cancel'));   // Esc or a click outside
    });
}

function resetImportForm() {
    document.getElementById('importText').value = '';
    document.getElementById('importProvider').value = '';
    document.getElementById('importUrl').value = '';
    document.getElementById('importFile').value = '';
    document.getElementById('fileName').textContent = 'No file selected';
    document.getElementById('importCreatePool').checked = false;
    document.getElementById('importPoolName').value = '';
    togglePoolFields();
    updatePoolPlaceholder();
}

async function doImport() {
    const importBtn = document.getElementById('importBtn');
    const fileInput = document.getElementById('importFile');
    const provider = document.getElementById('importProvider').value.trim() || null;
    const importUrl = document.getElementById('importUrl').value.trim() || null;
    const createPool = document.getElementById('importCreatePool').checked;
    const poolName = document.getElementById('importPoolName').value.trim();
    const strategy = document.getElementById('importPoolStrategy').value;
    let text = document.getElementById('importText').value.trim();

    btnLoading(importBtn);
    try {
        if (!text && fileInput.files.length > 0) text = (await fileInput.files[0].text()).trim();
        if (!text && !importUrl) {
            showToast('Please paste proxies, upload a file, or enter a URL', 'error');
            return;
        }
        if (createPool && !poolName) {
            showToast('Please enter a pool name', 'error');
            return;
        }

        // Settle the pool question before anything is written, so Cancel cancels everything
        let existingPool = null;
        let poolAction = 'created';
        if (createPool) {
            try {
                const poolsData = await apiCall('GET', '/api/v1/pools?per_page=100');
                existingPool = (poolsData.data || []).find((p) => p.name === poolName) || null;
            } catch (e) { /* treated as "no such pool"; creating it reports the real error */ }
            if (existingPool) {
                const action = await askPoolConflict(poolName, existingPool.proxy_count || 0);
                if (action === 'cancel') return;
                poolAction = action === 'overwrite' ? 'overwritten' : 'merged';
            }
        }

        const payload = { provider: provider, protocol: document.getElementById('importProtocol').value };
        if (text) payload.proxies = text;
        if (importUrl) payload.url = importUrl;
        if (fileInput.files.length > 0) payload.filename = fileInput.files[0].name;
        const result = await apiCall('POST', '/api/v1/ips/bulk', payload);

        let poolMsg = '';
        if (createPool) {
            let pool = existingPool;
            if (!pool) {
                pool = await apiCall('POST', '/api/v1/pools', { name: poolName, rotation_strategy: strategy });
            } else if (poolAction === 'overwritten') {
                // Remove the pool's current members first
                try {
                    const poolIps = await apiCall('GET', `/api/v1/ips?per_page=100&pool_id=${pool.id}`);
                    const existingIds = (poolIps.data || []).map((p) => p.id);
                    if (existingIds.length > 0) {
                        await apiCall('DELETE', `/api/v1/pools/${pool.id}/ips`, { proxy_ids: existingIds });
                    }
                } catch (e) { /* as before: a failed clean-up still adds the new proxies */ }
            }
            const filterParam = provider ? `&provider=${encodeURIComponent(provider)}` : '';
            const proxyData = await apiCall('GET', `/api/v1/ips?per_page=100${filterParam}`);
            const proxyIds = (proxyData.data || []).map((p) => p.id);
            if (proxyIds.length > 0) {
                await apiCall('POST', `/api/v1/pools/${pool.id}/ips`, { proxy_ids: proxyIds });
            }
            poolMsg = `, pool "${shorten(poolName, 40)}" ${poolAction} with ${proxyIds.length} proxies`;
        }

        showToast(`Imported ${result.created} proxies` + (result.skipped ? `, ${result.skipped} skipped` : '') + poolMsg, 'success');
        closeModal('importModal');
        resetImportForm();
        reloadTable();
        reloadCounts();
        loadSources().catch(() => { /* the status line reports outages */ });
    } catch (e) {
        showToast('Import failed: ' + e.message, 'error');
    } finally {
        btnReset(importBtn);
    }
}

/* ---------- wiring ---------- */
(function init() {
    injectBulkButtons();

    document.getElementById('proxySearch').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            searchQuery = e.target.value.trim();
            syncUrl();
            currentPage = 1;
            reloadTable();
        }, 300);
    });

    document.querySelectorAll('th.sortable').forEach((th) => {
        th.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            e.preventDefault();
            toggleSort(th.dataset.sort);
        });
    });

    const proxyBody = document.getElementById('proxyTableBody');
    proxyBody.addEventListener('change', (e) => {
        if (e.target.classList.contains('row-checkbox')) toggleRowSelection(e.target.dataset.id, e.target);
    });
    proxyBody.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const id = btn.closest('tr').dataset.id;
        if (btn.dataset.action === 'recheck') checkProxy(id, btn);
        if (btn.dataset.action === 'delete') deleteProxy(id);
    });

    document.getElementById('sourcesTableBody').addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const id = btn.closest('tr').dataset.id;
        if (btn.dataset.action === 'copy') copySourceName(id, btn);
        if (btn.dataset.action === 'poll') pollSource(id, btn);
        if (btn.dataset.action === 'delete') promptDeleteSource(id);
    });

    readUrlState();
    renderPills();
    renderSortHeaders();
    syncUrl();
    openModalFromQuery({ import: 'importModal' });

    Poller.start(refresh, 15000);
})();
```

Notes for the implementer:
- Rows are built in two passes. `proxyRow` / `sourceRow` interpolate API strings only as element text, through `esc()`. `hydrateProxyRow` / `hydrateSourceRow` then set everything that lands in an attribute (`title`, `aria-label`, `data-id`, the feed link's `href`) as DOM properties. Nothing from the API is ever interpolated into an attribute or an inline handler; row buttons are handled by one delegated listener per table and find their object through `tr.dataset.id`. A feed URL becomes a link only if it parses as `http:` or `https:`.
- `onceClosed(modalId, fn)` watches the modal's `class` with a `MutationObserver`, so it fires however the modal is closed: its own button, Esc, or a click on the overlay (the last two live in `app.js` and cannot be hooked any other way). It is what brings the Sources list back after Add / Delete, and what turns Esc in the pool-conflict question into "cancel".
- `refresh` is the only function the `Poller` runs and it never toasts. Its first run is unconditional (so `/proxies?import=1` still loads the table behind the modal); later runs are skipped while `isBusy()`. `loadProxies(true)` checks `isBusy()` again after the response arrives, because the operator may have ticked a row while the request was in flight. `loadSeq` drops responses that arrive out of order (fast typing in the search field); `userLoads` stops a background refresh from superseding a load the operator asked for.
- `reloadTable()` is the user-initiated path and does toast. `renderProxies` ends with `clearSelection()` exactly as before: re-rendered rows have fresh checkboxes.
- One call of the old script was dropped: in the Overwrite branch it fetched `GET /api/v1/pools/{id}` and never used the result. Everything else the old script called is still called, in the same order, except that the pool lookup and the conflict question moved ahead of `POST /api/v1/ips/bulk`.
- Known limits carried over unchanged (they need an API change, which this milestone forbids): "Also create a pool" adds the newest 100 proxies of that provider (or of all providers when the provider field is empty), not exactly the imported ones; Overwrite removes at most 100 existing members; the Sources list shows the first 100 sources.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q` and `uv run ruff check tests`
Expected: all PASS, no lint errors.

- [ ] **Step 6: Smoke check (preview server)**

Start `uv run python -m scripts.ui_preview` and open `http://127.0.0.1:8099/proxies`. The preview's `GET /api/v1/ips` honours `status`, `search` and `pool_id` (not `sort_by`, `provider` or `page`), so the pills and the search change the rows for real, while sorting is verified through the request URL (browser network panel, or Playwright `browser_network_requests`) and the header's state. POST / PATCH / DELETE return canned bodies without changing any list, so every mutation is verified through its toast only.

`normal` scenario:
1. Head reads "12 from 4 sources". Pills: All 12 (paper, dark dot), Healthy 6 (lime dot), Degraded 2 (amber), Dead 2 (coral), Unknown 2 (grey). 12 rows; host:port in mono with a dimmer port; latencies above 500 ms are amber; a proxy without a measured latency shows "—" and the two never-checked ones show "never"; footer "Showing 1–12 of 12", Previous and Next disabled. The browser console has no errors.
2. Click "Dead": the pill turns paper, the address bar shows `?status=dead`, the last request is `/api/v1/ips?page=1&per_page=50&status=dead`, 2 dead rows remain and the footer reads "Showing 1–2 of 2". Type `web` in the search field: exactly one request about 300 ms after the last keystroke, with `&search=web`; the address bar gains `search=web`; the tile shows "No proxies match" (no dead webshare proxy). Reload the page: the Dead pill, the search text and "No proxies match" are restored. "Clear filters": 12 rows, empty search field, the address bar is back to `/proxies`. Type `web` again with "All" active: the 4 webshare rows.
3. Click "Latency": header shows "Latency ↑" in bright text, request has `sort_by=latency&sort_dir=asc`; click again: "↓" and `sort_dir=desc`. Tab to "Provider" and press Enter: it sorts; the focus ring is visible on the header.
4. Tick one row: the row gets the rounded selected background and the bulk bar slides up with "1 selected", Cancel, Recheck, Move to pool, Delete selected. Wait 20 seconds: no `/api/v1/ips` request is sent while the row is selected. "Recheck": toasts "Rechecking 1 proxy..." then "Rechecked 1 of 1 proxy"; the selection clears. Tick the header checkbox (12 selected) and "Recheck" again: the check requests go out in one batch of 10, then one of 2.
5. Tick a row, "Move to pool": the select lists the four pools. The hostile fixture pool (`<script>alert(1)</script>-very-long-pool-name-...`) is one plain text option, no alert fires, the modal keeps its width. "Add to pool": toast "Added 2 proxies to pool" (canned), modal closes, selection clears. "Delete selected" asks "Delete 1 proxy? This cannot be undone."; Cancel keeps the selection.
6. First row, "Recheck" icon (accessible name "Recheck 198.51.100.77:1080"): spinner, then toast "Check complete: healthy (87 ms)". Row "Delete": confirm, toast "Proxy deleted"; the row stays (canned).
7. "Sources": a wide modal with 4 rows and focus on Close. `thespeedx-socks5` shows "... ago" plus a coral "failing" badge whose tooltip reads "2 failed polls in a row, last HTTP 503"; the manual source shows "static" and has no poll button; the three URL sources show "url ↗" linking to the feed in a new tab. Click a name: it reads "Copied!" for 1.5 seconds and a toast says "Source name copied" (the preview is plain HTTP on 127.0.0.1, so also try `http://<LAN address>:8099` if reachable: copy must still work there). Poll icon: toasts "Polling source..." then "Poll complete".
8. In Sources click "Add source": the list closes and the Add source modal opens. Press Esc: the list is back. "Add source" again, "Create" with an empty name: toast "Please enter a name"; a name but no URL: "Please enter a URL for URL sources"; switch Type to Manual: the URL field disappears. Fill name and URL, "Create": toast "Source created", the list is back (unchanged, canned). "Delete" on a row: the list closes, the confirmation names the source and its proxy count; "Delete": toast "Source and its proxies deleted", the list is back.
9. "Import" with nothing filled in: toast "Please paste proxies, upload a file, or enter a URL", the button is usable again. Type "Bright Data" as provider, tick "Also create a pool": the pool name placeholder reads `bright-data-001`. Paste two lines, leave the pool name empty, "Import": toast "Please enter a pool name" and no request to `/api/v1/ips/bulk`. Pool name `public-mix`, "Import": the import modal is replaced by "Pool already exists" ("... already exists with 6 proxies."), focus on Cancel. Press Esc: the import modal is back with everything still filled in, and still no `/api/v1/ips/bulk` request. "Import" again, "Overwrite": requests in this order: `POST ips/bulk`, `GET ips?per_page=100&pool_id=...` (the pool's 6 members), `DELETE pools/{id}/ips` with those 6 ids, `GET ips?per_page=100&provider=Bright%20Data` (the preview ignores `provider` and returns all 12), `POST pools/{id}/ips`; toast "Imported 25 proxies, 3 skipped, pool "public-mix" overwritten with 12 proxies"; the modal closes and reopens empty.
10. Open `http://127.0.0.1:8099/proxies?import=1&status=dead`: the import modal is open, the table behind it has loaded, the Dead pill is active and the address bar reads `/proxies?status=dead`.
11. Resize to 390px wide: the pills wrap under the search field, the table scrolls sideways inside its tile, the page itself does not scroll sideways, the Sources modal fits the screen.

`empty` scenario (open `/__scenario/empty`, then `/proxies`):
12. Head "0 from 0 sources", every pill count 0, the tile shows "No proxies yet" with an "Import proxies" button that opens the import modal; no pagination. Click "Dead": "No proxies match" with "Clear filters", which returns to "No proxies yet" and cleans the address bar. "Sources" shows "No sources yet" with an "Add source" button. `document.body.innerText` contains none of `NaN`, `undefined`, `null`, `Infinity`.

`offline` scenario (open `/__scenario/offline`, then `/proxies`):
13. The sidebar status is coral "Offline, retrying". The tile shows "Proxies could not be loaded" with "Retry now"; the head sub text is empty; no toast appears, also not after 30 seconds. "Retry now" shows exactly one toast ("Failed to load proxies: ..."). Open `/__scenario/normal` in another tab: within 15 seconds the rows, counts and "12 from 4 sources" appear without a reload and the status line returns to "Updated just now".

Stop the preview server.

- [ ] **Step 7: Commit**

```bash
uv run ruff check tests
git add src/web/templates/proxies.html src/web/static/js/pages/proxies.js tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): proxies page in Blocks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Pools page

**Files:**
- Rewrite: `src/web/templates/pools.html`
- Create: `src/web/static/js/pages/pools.js`
- Modify: `tests/test_web_routes.py`
- Modify: `tests/test_ui_static.py` (one line: `RESTYLED_TEMPLATES`)

**Interfaces:**
- Consumes:
  - `app.js` globals: `apiCall`, `showToast`, `openModal`, `closeModal`, `openModalFromQuery`, `confirmAction`, `btnLoading`, `btnReset`, `esc`, `fmtNum`, `fmtPct`, `fmtDate`, `protoTag`, `statusBadge`, `selectedIds`, `toggleRowSelection`, `toggleSelectAll`, `clearSelection`. No `Poller` (the page loads once and reloads after each mutation, as before).
  - `base.html`: blocks `title`, `content`, `scripts`; `asset_version`; shared ids `bulkDeleteBtn`, `bulkBar`, `confirmModal`, `toastContainer`.
  - CSS: `.page-head` (+ `__title`, `__sub`, `__actions`), `.tile`, `.table-scroll` > `table.tbl`, `th/td.col-check`, `.row-checkbox`, `.num`, `td.actions`, `.strong`, `.muted`, `.truncate`, `.badge-quiet` / `-warn` / `-bad`, `.meter` (+ `--lime`, `--amber`, `--coral`), `td .sub`, `.check-list` > `label` (+ `.check-list__group`), `.skeleton`, `.empty-state`, `.modal-overlay` > `.modal`, `.form-group`, `.form-hint`, `.modal-actions`, `.btn` (+ `-primary`, `-danger`, `-sm`), `.tag`, `.mono`, `.spacer`, `.sr-only`.
  - API (all existing, unchanged): `GET /api/v1/pools?per_page=100`, `POST /api/v1/pools` `{name, rotation_strategy}`, `DELETE /api/v1/pools/{id}`, `GET /api/v1/ips?per_page=100`, `GET /api/v1/ips?pool_id={id}&per_page=100`, `POST /api/v1/pools/{id}/ips` `{proxy_ids}`, `DELETE /api/v1/pools/{id}/ips` `{proxy_ids}` (a DELETE with a JSON body). Lists use the envelope `{data: [...], meta: {total, page, per_page}}`. Pool fields read: `id`, `name`, `rotation_strategy`, `proxy_count` (nullable), `healthy_count` (nullable), `created_at`. Proxy fields read: `id`, `host`, `port`, `protocol`, `provider` (nullable), `last_health_status`.
- Produces:
  - URL parameter `/pools?new=1` opens the New pool modal (the Overview onboarding card links to it). The parameter is stripped after opening.
  - Links out to `/proxies?import=1` (from the manage modal's empty state; Task 8 owns that parameter).
  - DOM ids: `poolsSub`, `poolsTableWrap`, `poolsBody`, `selectAll`, `poolsEmpty`, `poolsError`, `createPoolModal`, `createPoolTitle`, `poolName`, `poolStrategy`, `createPoolBtn`, `manageProxiesModal`, `manageProxiesTitle`, `manageProxiesInfo`, `proxyCheckboxes`, `manageProxiesNote`, `saveProxiesBtn`.

**What changes for the operator:**
- The two-column pool cards become one table in a tile: select, Pool (name, strategy under it), Proxies, Healthy as an "H / N" badge (coral when a pool has proxies and none is healthy, amber when fewer than half are, quiet otherwise), a healthy-share meter (lime from 50%, amber below, coral at 0), Created, then "Manage proxies" and "Delete". The health percentage is the meter's tooltip. The proxy count is no longer a second click target for "Manage proxies"; the button in the same row does that.
- The page head shows "N pools". "Create Pool" is now "New pool" (same modal: name + the same three strategies with the same explanations). `/pools?new=1` opens it directly.
- "Manage proxies" opens at once with a loading skeleton instead of after the data arrives. Same provider groups with a group checkbox (now also showing the partial state when it opens). The coloured dot per proxy becomes the standard status badge, so degraded is visible too. When the instance has more proxies than the one page of 100 the modal can list, it says so and points to Proxies > Move to pool.
- Fixed while porting: Save no longer removes a pool member that was not listed in the modal (before, a member outside the first 100 proxies was silently dropped on every Save). A failed membership read during Save no longer leaves the Save button spinning forever.
- A failed page load shows "Could not load pools" with Retry inside the tile instead of an error toast; the sidebar status line reports the outage. Bulk delete says "Deleted 2 of 3 pools" in coral when some deletes failed, instead of always reporting success.
- Not part of this milestone (milestone 2): pool list + detail, rename, changing the strategy of an existing pool, minimum healthy, weights.

- [ ] **Step 1: Write the failing tests**

In `tests/test_ui_static.py`, append `"pools.html"` to the `RESTYLED_TEMPLATES` list (keep whatever earlier tasks already put there).

In `tests/test_web_routes.py`:

1. Append `"/pools"` to the `RESTYLED_PAGES` list (keep whatever earlier tasks already put there).
2. If an earlier page task has not already added it, add this import under `from src.web.routes import router as web_router`:

```python
from tests.test_ui_static import assert_js_ids_exist
```

3. Append at the end of the file:

```python
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
```

Existing tests that fetch `/pools`, all kept as they are: `test_pools_returns_html`; the `/pools` cases of `test_active_nav_item_is_rendered_by_the_server` and `test_shell_uses_versioned_static_assets` (Task 4); the `/pools` entry of `PAGES` used by `test_pages_redirect_to_login_without_session` (Task 5). None is rewritten or deleted: no old test asserted anything about the pool cards.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py tests/test_ui_static.py -q -k pools`
Expected: 7 FAIL, the rest PASS.
- `test_restyled_page_has_markup_only[/pools]`: the old template has a `<style>` block and an inline script.
- `test_template_and_script_use_only_defined_classes[pools.html]`: the old template uses `pool-card`, `pc-stat` and other classes `app.css` does not define.
- `test_pools_page_structure`, `test_pools_modals_are_labelled_dialogs`: no `pools.js` script tag, no dialog roles.
- `test_pools_script_ids_exist_in_page`, `test_pools_script_contract`, `test_pools_save_never_removes_a_proxy_that_was_not_listed`: `FileNotFoundError`, `pools.js` does not exist yet.
- `test_pools_create_modal_offers_exactly_the_supported_strategies` already PASSES: it pins behaviour the old page has and the new page must keep.

- [ ] **Step 3: Rewrite the template**

Replace the whole of `src/web/templates/pools.html` with:

```html
{% extends "base.html" %}
{% block title %}Pools - Proxysm{% endblock %}

{% block content %}
<div class="page-head">
    <div class="page-head__title">
        <h1>Pools</h1>
        <span class="page-head__sub" id="poolsSub">Loading</span>
    </div>
    <div class="page-head__actions">
        <button class="btn btn-primary" type="button" onclick="openModal('createPoolModal')">New pool</button>
    </div>
</div>

<section class="tile" aria-label="Pools">
    <div class="table-scroll" id="poolsTableWrap">
        <table class="tbl">
            <thead>
                <tr>
                    <th class="col-check"><input type="checkbox" class="row-checkbox" id="selectAll" aria-label="Select all pools" onchange="toggleSelectAll(this)"></th>
                    <th>Pool</th>
                    <th class="num">Proxies</th>
                    <th class="num">Healthy</th>
                    <th style="width:22%;min-width:120px"><span class="sr-only">Healthy share</span></th>
                    <th>Created</th>
                    <th><span class="sr-only">Actions</span></th>
                </tr>
            </thead>
            <tbody id="poolsBody">
                <tr><td colspan="7"><div class="skeleton" style="height:18px"></div></td></tr>
                <tr><td colspan="7"><div class="skeleton" style="height:18px"></div></td></tr>
                <tr><td colspan="7"><div class="skeleton" style="height:18px"></div></td></tr>
            </tbody>
        </table>
    </div>
    <div class="empty-state" id="poolsEmpty" hidden>
        <div class="empty-state-icon" aria-hidden="true"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5"/></svg></div>
        <h3>No pools yet</h3>
        <p>Create a pool to group proxies for rotation, then assign it to a project.</p>
        <button class="btn btn-primary" type="button" onclick="openModal('createPoolModal')">New pool</button>
    </div>
    <div class="empty-state" id="poolsError" hidden>
        <h3>Could not load pools</h3>
        <p>The API did not answer. Nothing was changed.</p>
        <button class="btn" type="button" onclick="retryPools(this)">Retry</button>
    </div>
</section>

<div class="modal-overlay" id="createPoolModal" role="dialog" aria-modal="true" aria-labelledby="createPoolTitle">
    <div class="modal">
        <h2 id="createPoolTitle">New pool</h2>
        <p class="muted form-group">Group proxies and pick how requests rotate through them.</p>
        <div class="form-group">
            <label for="poolName">Pool name</label>
            <input type="text" id="poolName" placeholder="e.g. us-residential" maxlength="255" autocomplete="off">
        </div>
        <div class="form-group">
            <label for="poolStrategy">Rotation strategy</label>
            <select id="poolStrategy">
                <option value="round_robin" selected>Round Robin &mdash; sequential through healthy</option>
                <option value="random">Random &mdash; random healthy proxy</option>
                <option value="weighted_random">Weighted Random &mdash; weight-proportional traffic</option>
            </select>
        </div>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('createPoolModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="createPoolBtn" onclick="createPool()">Create</button>
        </div>
    </div>
</div>

<div class="modal-overlay" id="manageProxiesModal" role="dialog" aria-modal="true" aria-labelledby="manageProxiesTitle">
    <div class="modal" style="max-width:560px">
        <h2 id="manageProxiesTitle">Manage proxies</h2>
        <p class="muted truncate form-group" id="manageProxiesInfo"></p>
        <div class="check-list" id="proxyCheckboxes" role="group" aria-labelledby="manageProxiesTitle"></div>
        <p class="form-hint" id="manageProxiesNote" hidden></p>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('manageProxiesModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="saveProxiesBtn" onclick="saveProxyAssignments()">Save</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/pages/pools.js?v={{ asset_version }}"></script>
{% endblock %}
```

Notes for the implementer: both modals sit inside `content` (they are `position: fixed`, and `display: none` while closed, so they take no space in the flex column). `hidden` works on `#poolsTableWrap`, `#poolsEmpty`, `#poolsError` and `#manageProxiesNote` because none of their classes sets `display`. The manage modal stays at 560px (today's width) rather than `.modal--wide`: a row is only "host:port, protocol, status", and a wider box would just add empty space between them.

- [ ] **Step 4: Write the page script**

Create `src/web/static/js/pages/pools.js`:

```js
/* Pools page: pools table, create modal, manage-proxies modal.
   Classic script. Functions are globals because pools.html uses inline handlers.
   Only a pool id (a UUID) is ever passed to an inline handler, never a name. */
'use strict';

const LIST_PAGE_SIZE = 100; // the API caps per_page at 100

let pools = null;         // last list that loaded; null until the first success
let currentPoolId = null; // pool open in the manage-proxies modal
let manageSeq = 0;        // drops a slow response that lands in a reopened modal

/* ---------- pools table ---------- */
function showPoolsState(state) {
    document.getElementById('poolsTableWrap').hidden = state !== 'table';
    document.getElementById('poolsEmpty').hidden = state !== 'empty';
    document.getElementById('poolsError').hidden = state !== 'error';
}

function metaTotal(data, fallback) {
    return data && data.meta && typeof data.meta.total === 'number' ? data.meta.total : fallback;
}

function strategyLabel(strategy) {
    return String(strategy || '').replace(/_/g, ' ');
}

// Badge and meter for one pool. The counts are nullable in the API schema, so
// "unknown" is a real state: a dash and an empty meter, never "null / null".
function poolHealth(p) {
    const n = p.proxy_count;
    const h = p.healthy_count;
    if (typeof n !== 'number' || typeof h !== 'number') {
        return { known: false, share: 0, badge: 'badge-quiet', meter: '', label: 'Health unknown' };
    }
    const share = n > 0 ? Math.max(0, Math.min(100, Math.round((h / n) * 100))) : 0;
    let badge = 'badge-quiet';
    let meter = 'meter--lime';
    if (n > 0 && h <= 0) { badge = 'badge-bad'; meter = 'meter--coral'; }
    else if (n > 0 && h / n < 0.5) { badge = 'badge-warn'; meter = 'meter--amber'; }
    const label = n > 0 ? fmtPct(h, n, 0) + ' healthy' : 'No proxies in this pool';
    return { known: true, share: share, badge: badge, meter: meter, label: label };
}

function poolRow(p) {
    const id = esc(p.id);
    const name = esc(p.name);
    const health = poolHealth(p);
    const healthy = health.known
        ? `<span class="badge ${health.badge}">${fmtNum(p.healthy_count)} / ${fmtNum(p.proxy_count)}</span>`
        : '<span class="muted">—</span>';
    return `<tr data-id="${id}">
        <td class="col-check"><input type="checkbox" class="row-checkbox" data-id="${id}" aria-label="Select pool ${name}" onchange="toggleRowSelection('${id}', this)"></td>
        <td><div class="strong truncate" style="max-width:320px" title="${name}">${name}</div><span class="sub">${esc(strategyLabel(p.rotation_strategy))}</span></td>
        <td class="num">${fmtNum(p.proxy_count)}</td>
        <td class="num">${healthy}</td>
        <td><div class="meter ${health.meter}" role="img" aria-label="${health.label}" title="${health.label}"><i style="width:${health.share}%"></i></div></td>
        <td class="muted">${esc(fmtDate(p.created_at))}</td>
        <td class="actions">
            <button class="btn btn-sm" type="button" aria-label="Manage proxies in ${name}" onclick="manageProxies('${id}')">Manage proxies</button>
            <button class="btn btn-sm btn-danger" type="button" aria-label="Delete pool ${name}" onclick="deletePool('${id}')">Delete</button>
        </td>
    </tr>`;
}

function renderPools(total) {
    const count = total === 1 ? '1 pool' : fmtNum(total) + ' pools';
    document.getElementById('poolsSub').textContent =
        total > pools.length ? count + ', showing the first ' + pools.length : count;
    document.getElementById('poolsBody').innerHTML = pools.map(poolRow).join('');
    showPoolsState(pools.length === 0 ? 'empty' : 'table');
    clearSelection();
}

// One-off load, re-run after every mutation. No toast on failure: the sidebar
// status line reports outages. A table that already loaded stays on screen.
async function loadPools() {
    let data;
    try {
        data = await apiCall('GET', '/api/v1/pools?per_page=' + LIST_PAGE_SIZE);
    } catch (e) {
        if (pools === null) {
            document.getElementById('poolsSub').textContent = 'Unavailable';
            showPoolsState('error');
        }
        return;
    }
    pools = (data && data.data) || [];
    renderPools(metaTotal(data, pools.length));
}

async function retryPools(btn) {
    btnLoading(btn);
    await loadPools();
    btnReset(btn);
}

/* ---------- create ---------- */
async function createPool() {
    const input = document.getElementById('poolName');
    const name = input.value.trim();
    if (!name) { showToast('Pool name is required', 'error'); input.focus(); return; }
    const strategy = document.getElementById('poolStrategy').value;
    const btn = document.getElementById('createPoolBtn');
    btnLoading(btn);
    try {
        await apiCall('POST', '/api/v1/pools', { name: name, rotation_strategy: strategy });
        btnReset(btn);
        showToast('Pool created', 'success');
        closeModal('createPoolModal');
        input.value = '';
        loadPools();
    } catch (e) {
        btnReset(btn);
        showToast('Create failed: ' + e.message, 'error');
    }
}

/* ---------- delete ---------- */
async function deletePool(id) {
    if (!(await confirmAction('This pool will be permanently deleted.'))) return;
    try {
        await apiCall('DELETE', '/api/v1/pools/' + encodeURIComponent(id));
        showToast('Pool deleted', 'success');
        loadPools();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

async function bulkDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const noun = ids.length === 1 ? 'pool' : 'pools';
    if (!(await confirmAction(`Delete ${ids.length} ${noun}? This cannot be undone.`))) return;
    let deleted = 0;
    for (const id of ids) {
        try {
            await apiCall('DELETE', '/api/v1/pools/' + encodeURIComponent(id));
            deleted += 1;
        } catch (e) { /* counted below */ }
    }
    if (deleted === ids.length) showToast(`Deleted ${deleted} ${noun}`, 'success');
    else showToast(`Deleted ${deleted} of ${ids.length} pools`, 'error');
    clearSelection();
    loadPools();
}

/* ---------- manage proxies ---------- */
function providerRow(name, group, count) {
    const label = esc(name);
    return `<label class="check-list__group">
        <input type="checkbox" data-kind="provider" data-group="${group}">
        <span class="truncate" title="${label}">${label}</span>
        <span class="muted">${count}</span>
    </label>`;
}

function proxyRow(p, group, checked) {
    const address = esc(p.host) + ':' + esc(p.port);
    return `<label>
        <input type="checkbox" data-kind="proxy" data-group="${group}" value="${esc(p.id)}"${checked ? ' checked' : ''}>
        <span class="mono truncate" title="${address}">${address}</span>
        ${protoTag(p.protocol)}
        <span class="spacer"></span>
        ${statusBadge(p.last_health_status)}
    </label>`;
}

function proxyBoxes(group) {
    const scope = group ? `[data-group="${group}"]` : '';
    return Array.from(document.querySelectorAll('#proxyCheckboxes input[data-kind="proxy"]' + scope));
}

function toggleProviderProxies(group, checked) {
    proxyBoxes(group).forEach((box) => { box.checked = checked; });
}

function updateProviderToggle(group) {
    const toggle = document.querySelector(`#proxyCheckboxes input[data-kind="provider"][data-group="${group}"]`);
    if (!toggle) return;
    const boxes = proxyBoxes(group);
    const all = boxes.length > 0 && boxes.every((box) => box.checked);
    toggle.checked = all;
    toggle.indeterminate = !all && boxes.some((box) => box.checked);
}

// Returns true when there is at least one proxy to tick.
function renderProxyChecklist(allData, memberData) {
    const list = document.getElementById('proxyCheckboxes');
    const note = document.getElementById('manageProxiesNote');
    const proxies = (allData && allData.data) || [];
    const assigned = new Set(((memberData && memberData.data) || []).map((p) => p.id));
    if (proxies.length === 0) {
        list.innerHTML = '<div class="empty-state"><h3>No proxies yet</h3>'
            + '<p>Import proxies first, then add them to this pool.</p>'
            + '<a class="btn btn-primary" href="/proxies?import=1">Import proxies</a></div>';
        return false;
    }
    // A Map, not a plain object: a provider may be called "constructor"
    const byProvider = new Map();
    proxies.forEach((p) => {
        const name = p.provider || 'No provider';
        if (!byProvider.has(name)) byProvider.set(name, []);
        byProvider.get(name).push(p);
    });
    const groups = [];
    let html = '';
    byProvider.forEach((members, name) => {
        const group = 'g' + groups.length;
        groups.push(group);
        html += providerRow(name, group, members.length);
        html += members.map((p) => proxyRow(p, group, assigned.has(p.id))).join('');
    });
    list.innerHTML = html;
    groups.forEach(updateProviderToggle);
    const total = metaTotal(allData, proxies.length);
    if (total > proxies.length) {
        note.textContent = `Showing the first ${proxies.length} of ${fmtNum(total)} proxies. `
            + 'For the rest, select them on the Proxies page and use Move to pool.';
        note.hidden = false;
    }
    return true;
}

async function manageProxies(poolId) {
    const pool = (pools || []).find((p) => p.id === poolId);
    if (!pool) return;
    currentPoolId = poolId;
    manageSeq += 1;
    const seq = manageSeq;
    const modal = document.getElementById('manageProxiesModal');
    const info = document.getElementById('manageProxiesInfo');
    const list = document.getElementById('proxyCheckboxes');
    const saveBtn = document.getElementById('saveProxiesBtn');
    info.textContent = 'Assign proxies to ' + pool.name;
    info.title = pool.name;
    document.getElementById('manageProxiesNote').hidden = true;
    list.innerHTML = '<div class="skeleton" style="height:40px"></div>'.repeat(5);
    btnReset(saveBtn);
    saveBtn.disabled = true;
    openModal('manageProxiesModal');
    try {
        const [allData, memberData] = await Promise.all([
            apiCall('GET', '/api/v1/ips?per_page=' + LIST_PAGE_SIZE),
            apiCall('GET', `/api/v1/ips?pool_id=${encodeURIComponent(poolId)}&per_page=${LIST_PAGE_SIZE}`),
        ]);
        // Closed or reopened for another pool while loading: drop this response
        if (seq !== manageSeq || !modal.classList.contains('active')) return;
        saveBtn.disabled = !renderProxyChecklist(allData, memberData);
        const first = list.querySelector('input');
        if (first) first.focus();
    } catch (e) {
        if (seq !== manageSeq || !modal.classList.contains('active')) return;
        closeModal('manageProxiesModal');
        showToast('Failed to load proxies: ' + e.message, 'error');
    }
}

async function saveProxyAssignments() {
    if (!currentPoolId) return;
    const poolId = currentPoolId;
    const boxes = proxyBoxes();
    const listed = new Set(boxes.map((box) => box.value));
    const wanted = new Set(boxes.filter((box) => box.checked).map((box) => box.value));
    const btn = document.getElementById('saveProxiesBtn');
    const membersUrl = '/api/v1/pools/' + encodeURIComponent(poolId) + '/ips';
    btnLoading(btn);
    try {
        // Diff against membership as it is now, not as it was when the modal opened
        const current = await apiCall(
            'GET', `/api/v1/ips?pool_id=${encodeURIComponent(poolId)}&per_page=${LIST_PAGE_SIZE}`
        );
        const currentIds = new Set(((current && current.data) || []).map((p) => p.id));
        const toAdd = [...wanted].filter((id) => !currentIds.has(id));
        // Only a proxy that had a checkbox can be removed. A member beyond the
        // first page was never shown, so it must not be dropped silently.
        const toRemove = [...currentIds].filter((id) => listed.has(id) && !wanted.has(id));
        if (toAdd.length > 0) await apiCall('POST', membersUrl, { proxy_ids: toAdd });
        if (toRemove.length > 0) await apiCall('DELETE', membersUrl, { proxy_ids: toRemove });
        btnReset(btn);
        if (toAdd.length + toRemove.length > 0) {
            showToast(`Updated pool: ${toAdd.length} added, ${toRemove.length} removed`, 'success');
        } else {
            showToast('No changes made', 'success');
        }
        closeModal('manageProxiesModal');
        loadPools();
    } catch (e) {
        btnReset(btn);
        showToast('Update failed: ' + e.message, 'error');
        loadPools(); // the add may have gone through before the remove failed
    }
}

/* ---------- init ---------- */
document.getElementById('proxyCheckboxes').addEventListener('change', (e) => {
    const box = e.target;
    if (!box.dataset || !box.dataset.group) return;
    if (box.dataset.kind === 'provider') toggleProviderProxies(box.dataset.group, box.checked);
    else updateProviderToggle(box.dataset.group);
});
document.getElementById('bulkDeleteBtn').addEventListener('click', bulkDelete);
openModalFromQuery({ new: 'createPoolModal' });
loadPools();
```

Notes for the implementer:
- A pool id is the only API value that reaches an inline handler; it is a UUID. `esc()` is not a defence inside an inline handler (the HTML parser decodes `&#39;` back to a quote before the JS runs), which is why `manageProxies(id)` looks the pool up in `pools` instead of taking its name as an argument.
- The modal checkboxes deliberately do not use `.row-checkbox`: `toggleSelectAll` and `clearSelection` in `app.js` act on every `.row-checkbox` in the document and would otherwise tick or wipe the modal's boxes. `.check-list input[type="checkbox"]` (Task 1) styles them instead, and `data-kind` / `data-group` are the script's hooks.
- `loadPools` never toasts and never throws. `retryPools` relies on that.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q` then `node --check src/web/static/js/pages/pools.js`
Expected: all PASS; `node --check` prints nothing.

- [ ] **Step 6: Smoke check (preview server)**

Start `uv run python -m scripts.ui_preview`, open `http://127.0.0.1:8099/pools`.

Scenario `normal`:
1. Page head reads "Pools" with "4 pools" beside it and a lime "New pool" button on the right. "Pools" is the white pill in the sidebar.
2. One tile with four rows from the fixtures: `residential-eu` (weighted random) 2, quiet "1 / 2", lime meter at 50%; `public-mix` (random) 6, amber "2 / 6", amber meter at 33%; `datacenter-us` (round robin) 4, quiet "3 / 4", lime meter at 75%; the hostile pool 0, quiet "0 / 0", empty meter. Hovering a meter shows "75% healthy" (or "No proxies in this pool").
3. Hostile name: the `<script>alert(1)</script>-very-long-pool-name-...` row shows the name as literal text, cut with an ellipsis at 320px, the full name in its tooltip; no dialog fired; the tile does not scroll sideways at 1440px.
4. Tick one row: the row gets the rounded selected background and the bulk bar slides up with "1 selected". Tick the header box: "4 selected". Cancel on the bar clears everything.
5. "New pool": modal opens with focus in "Pool name". Create with an empty name: coral toast "Pool name is required", modal stays open. Type a name, press Enter: lime toast "Pool created", modal closes, the field is empty next time. (The preview's POST returns a canned body and the list does not change, so the toast is the only visible result.)
6. "Manage proxies" on `public-mix`: the modal opens immediately with five skeleton rows and a disabled Save, then lists 12 proxies under four provider headers (`manual` 2, `thespeedx` 3, `proxyscrape` 3, `webshare` 4), each row "host:port, PROTOCOL, status badge" (lime healthy, amber degraded, coral dead, quiet unknown). Exactly the pool's six members are ticked: all of `thespeedx` and all of `proxyscrape`, so those two header boxes are ticked and `manual` and `webshare` are not. The list scrolls inside the modal; the header of the current group sticks to the top; Cancel and Save stay visible. On the hostile pool (0 proxies) the same list opens with nothing ticked.
7. Still on `public-mix`: untick one `thespeedx` proxy: the `thespeedx` header box shows the partial (dash) state. Tick the `manual` header box: its two proxies tick. Save: lime toast "Updated pool: 2 added, 1 removed", modal closes. The preview does not store the change, so opening the modal again shows the original six members; Save without touching anything then toasts "No changes made".
8. "Delete" on a row: confirm dialog "This pool will be permanently deleted."; Cancel does nothing; Delete shows "Pool deleted". Select two rows, "Delete selected": "Delete 2 pools? This cannot be undone.", then "Deleted 2 pools". (Preview: rows do not disappear.)
9. Open `http://127.0.0.1:8099/pools?new=1`: the New pool modal is open and the address bar reads `/pools`.
10. States the preview cannot produce, checked from the browser console. With the manage modal open, `renderProxyChecklist({data: []}, {data: []})` shows "No proxies yet" with an "Import proxies" button linking to `/proxies?import=1`. With it closed, `document.getElementById('poolsBody').innerHTML = poolRow({id: 'b0010000-0000-4000-8000-0000000000aa', name: 'n', rotation_strategy: 'random', proxy_count: null, healthy_count: null, created_at: null})` renders dashes and an empty meter, never the word `null`.

Scenario `empty` (`/__scenario/empty`, then reload `/pools`):
11. "0 pools"; the tile shows the layers icon, "No pools yet", one sentence and a "New pool" button that opens the modal; no table header is visible. In the console `/(NaN|undefined|null|Infinity)/.test(document.querySelector('.content').innerText)` is `false`.

Scenario `offline` (`/__scenario/offline`, then reload `/pools`):
12. Sidebar status turns coral "Offline, retrying"; the head reads "Unavailable"; the tile shows "Could not load pools" with a Retry button; no toast appears. Create a pool: exactly one coral toast "Create failed: ...". Switch to `/__scenario/normal` in another tab and press Retry: the table appears and the status line returns to "Updated just now" without a reload.

Stop the preview server.

- [ ] **Step 7: Commit**

```bash
uv run ruff check tests/test_web_routes.py tests/test_ui_static.py
git add src/web/templates/pools.html src/web/static/js/pages/pools.js tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): pools page in Blocks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Projects page

**Files:**
- Rewrite: `src/web/templates/projects.html`
- Create: `src/web/static/js/pages/projects.js`
- Modify: `tests/test_web_routes.py`
- Modify: `tests/test_ui_static.py` (one line: `RESTYLED_TEMPLATES`)

**Interfaces:**
- Consumes:
  - `app.js` globals: `APP` (`host`, `httpPort`, `socks5Port`), `apiCall`, `Poller`, `showToast`, `openModal`, `closeModal`, `openModalFromQuery`, `confirmAction`, `btnLoading`, `btnReset`, `copyToClipboard`, `esc`, `fmtNum`, `fmtPct`, `fmtDate`. `addCopyButtons()` is not called; its MutationObserver puts the Copy button into the one `.code-block`. Not used: `selectedIds` and the bulk bar (this page has no table selection any more).
  - `base.html`: blocks `title`, `content`, `scripts`; `asset_version`; shared ids `confirmModal` (+ `confirmTitle`, `confirmMessage`, `confirmOkBtn`, `confirmCancelBtn`), `toastContainer`, `navStatus`.
  - CSS (Task 1): `.split` > `.split-list` + `.split-detail`, `.list-tile` (+ `.active`), `.page-head` (+ `__actions`), `.tile`, `.tile-head` (+ `--wrap`), `.seg`, `.code-block` / `.copy-btn`, `.kv`, `.alert-warning`, `.table-scroll` > `table.tbl`, `td.actions`, `.badge-quiet` / `.badge-bad`, `.empty-state` (+ `-icon`), `.skeleton`, `.modal-overlay` > `.modal`, `.form-group`, `.form-hint`, `.modal-actions`, `.btn` (+ `-primary`, `-outline`, `-danger`, `-ghost`, `-sm`), `.row`, `.spacer`, `.mono`, `.muted`, `.strong`, `.truncate`, and `.check-list` > `label` (the checkbox rows of the pools modal). Task 1's narrow-viewport rule `.split { flex-direction: column; align-items: stretch; }` is what lets the detail column fill the width below 1100px.
  - API (all existing, unchanged). Lists use the envelope `{data: [...], meta: {total, page, per_page}}`.
    - `GET /api/v1/projects?per_page=100`: project fields read: `id`, `name`, `slug`, `api_key` (nullable: null on rows created before keys were stored), `pools[]` (`id`, `name`, `rotation_strategy`; their `proxy_count` / `healthy_count` are always null here), `created_at`.
    - `GET /api/v1/pools?per_page=100`: `id`, `name`, `rotation_strategy`, `proxy_count`, `healthy_count`. This is where the "H / N healthy" badge gets its numbers (joined to the project's pools by `id`).
    - `GET /api/v1/projects/{id}/stats`: `total_requests`, `failed_requests`. Not a 24h window: it sums every 5-minute rollup still kept (7 days by default), so the tile says "N requests", never "24h".
    - `GET /api/v1/projects/{id}` (fresh assignments when the pools modal opens), `POST /api/v1/projects` `{name}` (201, returns `api_key`; 409 on a duplicate name), `DELETE /api/v1/projects/{id}` (204), `POST /api/v1/projects/{id}/rotate-key` (returns the project with the new `api_key`), `POST /api/v1/projects/{id}/pools` `{pool_ids}` (adds only, never removes), `DELETE /api/v1/projects/{id}/pools/{pool_id}` (204).
- Produces:
  - URL parameter `/projects?project=<id>` selects that project (the Overview projects table links to it). Unknown or missing id: the first project is selected and the URL is rewritten with `history.replaceState`.
  - URL parameter `/projects?new=1` opens the New project modal (the onboarding card links to it); stripped after opening.
  - Links out to `/pools?new=1` (pools modal when no pool exists; Task 9 owns that parameter).
  - `localStorage` keys `proxysm.connect.proto` (`http` | `socks5`) and `proxysm.connect.lang` (`curl` | `python` | `node`).
  - DOM ids: `apiKeyAlert`, `apiKeyProject`, `apiKeyValue`, `projectList`, `projectDetail`, `detailName`, `detailCreated`, `deleteProjectBtn`, `connectTile`, `connectTitle`, `protoSeg`, `langSeg`, `connectBlock`, `connectCode`, `connectUser`, `keyValue`, `keyRevealBtn`, `keyCopyBtn`, `keyRotateBtn`, `poolsTile`, `poolsTitle`, `projectPoolsTable`, `projectPoolsBody`, `projectPoolsEmpty`, `projectsEmpty`, `projectsError`, `createProjectModal`, `createProjectTitle`, `projectName`, `createProjectBtn`, `managePoolsModal`, `managePoolsTitle`, `managePoolsInfo`, `poolCheckboxes`, `savePoolsBtn`. No new CSS.

**What changes for the operator:**
- The stack of project cards becomes list + detail. Left: one tile per project with its name and "N requests · X% errors" ("No traffic yet" at zero); the selected tile is white. Right: the selected project. The selection is in the address bar (`?project=<id>`), so a project can be bookmarked or linked from Overview.
- New **Connect** block: HTTP / SOCKS5 and curl / Python / Node switches over one snippet that uses the host you are viewing the UI on and reads the key from `PROXYSM_KEY`. The real key is never written into a snippet, so a snippet can be pasted into a ticket. The two choices are remembered. Removed: the 8-language x 2 snippet matrix, the "Get Proxy" REST variant, the per-card Usage expander and the one-line curl strip whose Copy button put the real key on the clipboard.
- Under the snippet: Username (the slug, which is the proxy username) and the API key, masked, with Reveal / Hide, Copy (once revealed) and Rotate. Rotate confirms first ("Rotate API key?"), then shows the new key in the amber banner exactly as creation does; Reveal shows the new key at once (before, the card kept showing the old key until a reload). A project whose key was never stored (`api_key: null`) says "Not available. Rotate to get a new key." and offers only Rotate.
- **Pools** block: a table of the assigned pools (name, strategy, "H / N healthy", coral when the pool has proxies and none is healthy) with Remove per row (confirms), and "Add pool", which opens the same checkbox modal as before. Fixed while porting: unticking a pool in that modal now really removes it. Before, Save only sent the ticked ids to an endpoint that only adds, so unticking silently did nothing. Save with no change just closes.
- Deleting a project selects the next one. Bulk delete with checkboxes is gone (there is no table to tick); delete is per project, with the project's name in the confirmation.
- The page refreshes itself every 30 seconds (stats at most every 5 minutes, which is how often they change). A failed first load shows "Could not load projects" with "Retry now" instead of an error toast; a failed refresh keeps what is on screen and the sidebar status line reports the outage.
- Not in this milestone: Limits, Last 24h, rename, pool ordering, quota bars.

- [ ] **Step 1: Write the failing tests**

In `tests/test_ui_static.py`, add `"projects.html",` to the `RESTYLED_TEMPLATES` list, on its own line like the other entries (keep whatever earlier tasks already put there).

In `tests/test_web_routes.py`:

1. Append `"/projects"` to the `RESTYLED_PAGES` list (keep whatever earlier tasks already put there).
2. If an earlier page task has not already added it, add this import under `from src.web.routes import router as web_router`:

```python
from tests.test_ui_static import assert_js_ids_exist
```

3. Append at the end of the file:

```python
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
```

Existing tests that fetch `/projects`, none of which changes: `test_projects_returns_html` (kept as is), `test_pages_redirect_to_login_without_session` (kept as is; `/projects` stays in its list), and Task 4's parametrized `test_active_nav_item_is_rendered_by_the_server`, `test_shell_uses_versioned_static_assets` and `test_restyled_page_has_markup_only` (the last one starts covering `/projects` through edit 1). Nothing is deleted: no old test asserted the snippet matrix.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py tests/test_ui_static.py -q -k "projects or restyled or defined_classes"`
Expected: 9 FAIL. `test_restyled_page_has_markup_only[/projects]` (the old template has a `<style>` block and an inline script), `test_template_and_script_use_only_defined_classes[projects.html]` (`proj-card`, `usage-tab`, `language-bash`...), `test_projects_page_structure`, `..._connect_block_...`, `..._drops_the_snippet_matrix_...`, `..._modals_are_labelled_dialogs` (old markup), and `test_projects_script_ids_exist_in_page`, `test_projects_snippets_...`, `test_projects_script_talks_...` with `FileNotFoundError` (no `projects.js`). `test_projects_returns_html` and the Task 4 shell tests keep passing.

- [ ] **Step 3: Rewrite the template**

Replace the whole of `src/web/templates/projects.html` with:

```html
{% extends "base.html" %}
{% block title %}Projects — Proxysm{% endblock %}

{% block content %}
<div class="alert-warning" id="apiKeyAlert" role="status" style="display:none">
    <div class="spacer" style="min-width:0">
        <strong>Your new API key for <span id="apiKeyProject"></span></strong>
        <div class="row" style="flex-wrap:wrap">
            <code id="apiKeyValue"></code>
            <button class="copy-btn" type="button" onclick="copyApiKey(this)">Copy</button>
        </div>
        <div>Export it as <code>PROXYSM_KEY</code> where your client runs. The snippets below read it from there.</div>
    </div>
    <button class="btn btn-sm" type="button" onclick="dismissApiKeyAlert()">Dismiss</button>
</div>

<div class="split">
    <div class="split-list" id="projectList">
        <div class="page-head">
            <h1>Projects</h1>
            <div class="page-head__actions">
                <button class="btn btn-primary" type="button" onclick="openModal('createProjectModal')">New project</button>
            </div>
        </div>
        <div class="skeleton" style="height:92px"></div>
        <div class="skeleton" style="height:92px"></div>
    </div>

    <section class="split-detail" id="projectDetail" aria-label="Project detail" style="display:none">
        <div class="row" style="flex-wrap:wrap;min-height:44px">
            <div class="row" style="flex:1 1 240px;min-width:0">
                <h2 class="truncate" id="detailName" style="font-size:30px;letter-spacing:-0.04em"></h2>
                <span class="muted" id="detailCreated" style="flex-shrink:0"></span>
            </div>
            <button class="btn btn-danger" type="button" id="deleteProjectBtn" onclick="deleteProject()">Delete project</button>
        </div>

        <section class="tile" id="connectTile" aria-labelledby="connectTitle">
            <div class="tile-head tile-head--wrap">
                <h2 id="connectTitle">Connect</h2>
                <div class="row" style="flex-wrap:wrap;justify-content:flex-end">
                    <div class="seg" id="protoSeg" role="group" aria-label="Proxy protocol">
                        <button type="button" class="active" data-proto="http" aria-pressed="true">HTTP</button>
                        <button type="button" data-proto="socks5" aria-pressed="false">SOCKS5</button>
                    </div>
                    <div class="seg" id="langSeg" role="group" aria-label="Snippet language">
                        <button type="button" class="active" data-lang="curl" aria-pressed="true">curl</button>
                        <button type="button" data-lang="python" aria-pressed="false">Python</button>
                        <button type="button" data-lang="node" aria-pressed="false">Node</button>
                    </div>
                </div>
            </div>
            <pre class="code-block" id="connectBlock"><code class="mono" id="connectCode"></code></pre>
            <dl class="kv" style="margin-top:16px">
                <dt>Username</dt>
                <dd class="mono truncate" id="connectUser"></dd>
                <dt>API key</dt>
                <dd class="row" style="flex-wrap:wrap">
                    <span class="mono" id="keyValue" style="word-break:break-all"></span>
                    <button class="btn btn-sm" type="button" id="keyRevealBtn" aria-pressed="false" onclick="toggleKeyReveal()">Reveal</button>
                    <button class="btn btn-sm" type="button" id="keyCopyBtn" style="display:none" onclick="copyKey(this)">Copy</button>
                    <button class="btn btn-sm" type="button" id="keyRotateBtn" onclick="rotateKey()">Rotate</button>
                </dd>
            </dl>
        </section>

        <section class="tile" id="poolsTile" aria-labelledby="poolsTitle">
            <div class="tile-head">
                <h2 id="poolsTitle">Pools</h2>
                <button class="btn btn-sm" type="button" onclick="openManagePools()">Add pool</button>
            </div>
            <div class="table-scroll" id="projectPoolsTable">
                <table class="tbl">
                    <thead>
                        <tr>
                            <th>Pool</th>
                            <th>Strategy</th>
                            <th>Health</th>
                            <th aria-label="Actions"></th>
                        </tr>
                    </thead>
                    <tbody id="projectPoolsBody"></tbody>
                </table>
            </div>
            <div class="empty-state" id="projectPoolsEmpty" style="display:none">
                <h3>No pools assigned</h3>
                <p>Requests for this project will fail until you add one.</p>
                <button class="btn btn-primary" type="button" onclick="openManagePools()">Add pool</button>
            </div>
        </section>
    </section>
</div>

<section class="tile" id="projectsEmpty" style="display:none">
    <div class="empty-state">
        <div class="empty-state-icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></div>
        <h3>No projects yet</h3>
        <p>A project gives your client a username and an API key for the rotating proxy.</p>
        <button class="btn btn-primary" type="button" onclick="openModal('createProjectModal')">New project</button>
    </div>
</section>

<section class="tile" id="projectsError" style="display:none">
    <div class="empty-state">
        <h3>Could not load projects</h3>
        <p>The API did not answer. This page keeps retrying on its own.</p>
        <button class="btn" type="button" onclick="retryLoad(this)">Retry now</button>
    </div>
</section>

<div class="modal-overlay" id="createProjectModal" role="dialog" aria-modal="true" aria-labelledby="createProjectTitle">
    <div class="modal">
        <h2 id="createProjectTitle">New project</h2>
        <div class="form-group">
            <label for="projectName">Project name</label>
            <input type="text" id="projectName" placeholder="e.g. price-monitor" maxlength="255" autocomplete="off">
            <div class="form-hint">A slug and an API key are generated automatically.</div>
        </div>
        <div class="modal-actions">
            <button class="btn btn-outline" type="button" onclick="closeModal('createProjectModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="createProjectBtn" onclick="createProject()">Create</button>
        </div>
    </div>
</div>

<div class="modal-overlay" id="managePoolsModal" role="dialog" aria-modal="true" aria-labelledby="managePoolsTitle">
    <div class="modal">
        <h2 id="managePoolsTitle">Manage pools</h2>
        <div class="form-group"><p class="muted" id="managePoolsInfo"></p></div>
        <div class="check-list" id="poolCheckboxes" role="group" aria-labelledby="managePoolsTitle"></div>
        <div class="modal-actions">
            <button class="btn btn-outline" type="button" onclick="closeModal('managePoolsModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="savePoolsBtn" onclick="savePoolAssignments()">Save</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/pages/projects.js?v={{ asset_version }}"></script>
{% endblock %}
```

Notes for the implementer:
- `style="display:none"` (not the `hidden` attribute) because `.split-detail` and `.alert-warning` set `display: flex`, which beats `[hidden]`. The script shows an element with `el.style.display = ''`.
- The project tiles are inserted by the script as siblings of the page head inside `#projectList`, so the column's own 14px gap spaces them. The two `.skeleton` blocks are the loading state; the first render removes them.
- The Actions header is `<th aria-label="Actions">`, not an `.sr-only` span: nothing absolutely positioned inside the scrolling table.
- `<pre class="code-block">` and its `<code>` are on one line on purpose: whitespace inside `<pre>` is rendered.

- [ ] **Step 4: Write the page script**

Create `src/web/static/js/pages/projects.js`:

```js
/* Projects page: project tiles on the left; the selected project's Connect
   snippet, API key and pools on the right. The selection lives in ?project=<id>. */
'use strict';

const POLL_MS = 30000;
// Project stats are built from 5-minute rollups, so refetching sooner is wasted work.
const STATS_TTL_MS = 5 * 60 * 1000;
const PROTOS = ['http', 'socks5'];
const LANGS = ['curl', 'python', 'node'];
const STATS_HINT = 'Since the oldest 5-minute metrics still kept (7 days by default)';

let projects = [];
let allPools = [];
let stats = {};
let statsLoadedAt = 0;
let selectedProjectId = new URLSearchParams(window.location.search).get('project');
let loadedOnce = false;
let loadSeq = 0;
let keyRevealed = false;
let connectProto = readPref('proxysm.connect.proto', PROTOS);
let connectLang = readPref('proxysm.connect.lang', LANGS);
let modalProjectId = null;
let modalAssigned = new Set();
const lastHtml = {};

/* ---------- small helpers ---------- */
function readPref(key, allowed) {
    try {
        const value = window.localStorage.getItem(key);
        if (allowed.includes(value)) return value;
    } catch (e) { /* storage blocked */ }
    return allowed[0];
}

function writePref(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* storage blocked */ }
}

function setVisible(el, on) {
    el.style.display = on ? '' : 'none';
}

// Skip identical re-renders so a background poll never steals focus from a button.
function setHtml(el, html) {
    if (lastHtml[el.id] === html) return;
    lastHtml[el.id] = html;
    el.innerHTML = html;
}

function selectedProject() {
    return projects.find((p) => p.id === selectedProjectId) || null;
}

function writeSelectionToUrl() {
    const params = new URLSearchParams(window.location.search);
    if (selectedProjectId) params.set('project', selectedProjectId);
    else params.delete('project');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
}

function maskKey(key) {
    return '••••••••••••' + String(key).slice(-4);
}

function copyWithFeedback(text, btn, message) {
    copyToClipboard(text).then((ok) => {
        if (!ok) { showToast('Copy failed, select the text manually', 'error'); return; }
        btn.textContent = 'Copied';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
        showToast(message);
    });
}

/* ---------- loading ---------- */
// Run by the Poller: never toasts. A failed first load shows the error tile;
// a failed later poll keeps the last good data on screen.
async function loadProjects() {
    const seq = ++loadSeq;
    const [projRes, poolRes] = await Promise.allSettled([
        apiCall('GET', '/api/v1/projects?per_page=100'),
        apiCall('GET', '/api/v1/pools?per_page=100'),
    ]);
    if (seq !== loadSeq) return;
    if (projRes.status !== 'fulfilled') {
        if (!loadedOnce) renderLoadError();
        throw projRes.reason;
    }
    projects = projRes.value.data || [];
    if (poolRes.status === 'fulfilled') allPools = poolRes.value.data || [];
    loadedOnce = true;
    if (!selectedProject()) {
        selectedProjectId = projects.length > 0 ? projects[0].id : null;
        keyRevealed = false;
        writeSelectionToUrl();
    }
    renderPage();
    await loadStats();
}

async function loadStats() {
    const stale = Date.now() - statsLoadedAt > STATS_TTL_MS;
    const ids = projects.map((p) => p.id).filter((id) => stale || !stats[id]);
    if (ids.length === 0) return;
    const results = await Promise.allSettled(
        ids.map((id) => apiCall('GET', `/api/v1/projects/${id}/stats`))
    );
    ids.forEach((id, i) => {
        if (results[i].status === 'fulfilled') stats[id] = results[i].value;
        else if (!stats[id]) stats[id] = null;
    });
    if (stale) statsLoadedAt = Date.now();
    paintStats();
}

function reloadProjects() {
    return loadProjects().catch(() => { /* the status line reports outages */ });
}

async function retryLoad(btn) {
    btnLoading(btn);
    try {
        await loadProjects();
    } catch (e) {
        showToast('Still not reachable: ' + e.message, 'error');
    }
    btnReset(btn);
}

/* ---------- rendering ---------- */
function clearListTiles() {
    document.getElementById('projectList')
        .querySelectorAll('.list-tile, .skeleton')
        .forEach((el) => el.remove());
}

function renderLoadError() {
    clearListTiles();
    delete lastHtml.projectList;
    setVisible(document.getElementById('projectsError'), true);
}

function renderPage() {
    const has = projects.length > 0;
    setVisible(document.getElementById('projectsError'), false);
    setVisible(document.getElementById('projectsEmpty'), !has);
    setVisible(document.getElementById('projectDetail'), has);
    renderList();
    if (has) renderDetail();
}

function statsLine(id) {
    const s = stats[id];
    if (s === undefined) return 'Loading…';
    if (s === null) return '—';
    if (!s.total_requests) return 'No traffic yet';
    return fmtNum(s.total_requests) + ' requests · ' + fmtPct(s.failed_requests, s.total_requests) + ' errors';
}

function renderList() {
    const html = projects.map((p) => `
        <button type="button" class="list-tile" data-project-id="${esc(p.id)}">
            <h3 class="truncate" title="${esc(p.name)}">${esc(p.name)}</h3>
            <span class="muted" title="${STATS_HINT}"></span>
        </button>`).join('');
    // The tiles are siblings of the page head inside #projectList, so replace only them.
    if (lastHtml.projectList !== html) {
        lastHtml.projectList = html;
        clearListTiles();
        document.getElementById('projectList').insertAdjacentHTML('beforeend', html);
    }
    markActiveTile();
    paintStats();
}

function markActiveTile() {
    document.querySelectorAll('#projectList .list-tile').forEach((tile) => {
        const on = tile.dataset.projectId === selectedProjectId;
        tile.classList.toggle('active', on);
        if (on) tile.setAttribute('aria-current', 'true');
        else tile.removeAttribute('aria-current');
    });
}

function paintStats() {
    document.querySelectorAll('#projectList .list-tile').forEach((tile) => {
        const line = tile.querySelector('.muted');
        if (line) line.textContent = statsLine(tile.dataset.projectId);
    });
}

function renderDetail() {
    const p = selectedProject();
    if (!p) return;
    const name = document.getElementById('detailName');
    name.textContent = p.name;
    name.title = p.name;
    document.getElementById('detailCreated').textContent = 'created ' + fmtDate(p.created_at);
    const user = document.getElementById('connectUser');
    user.textContent = p.slug;
    user.title = p.slug;
    renderSnippet();
    renderKey();
    renderPools();
}

/* ---------- Connect ---------- */
// The snippet never contains the real key: it reads PROXYSM_KEY from the
// environment, so it can be pasted into a ticket or a repo as it is.
function buildSnippet(slug, proto, lang) {
    const socks = proto === 'socks5';
    const base = (socks ? 'socks5' : 'http') + '://' + slug + ':';
    const at = '@' + APP.host + ':' + (socks ? APP.socks5Port : APP.httpPort);
    if (lang === 'python') {
        return [
            'import os, requests',
            '',
            'key = os.environ["PROXYSM_KEY"]',
            'proxy = f"' + base + '{key}' + at + '"',
            'r = requests.get("https://httpbin.org/ip", proxies={"all": proxy})',
        ].join('\n');
    }
    if (lang === 'node') {
        return (socks ? [
            'import { SocksProxyAgent } from "socks-proxy-agent";',
            '',
            'const key = process.env.PROXYSM_KEY;',
            'const url = `' + base + '${key}' + at + '`;',
            'const agent = new SocksProxyAgent(url);',
            'const res = await fetch("https://httpbin.org/ip", { agent });',
        ] : [
            'import { ProxyAgent, fetch } from "undici";',
            '',
            'const key = process.env.PROXYSM_KEY;',
            'const url = `' + base + '${key}' + at + '`;',
            'const dispatcher = new ProxyAgent(url);',
            'const res = await fetch("https://httpbin.org/ip", { dispatcher });',
        ]).join('\n');
    }
    return [
        'curl --proxy ' + base + '$PROXYSM_KEY' + at + ' \\',
        '     https://httpbin.org/ip',
    ].join('\n');
}

function syncSeg(rootId, attr, current) {
    document.querySelectorAll('#' + rootId + ' button').forEach((btn) => {
        const on = btn.dataset[attr] === current;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-pressed', String(on));
    });
}

function renderSnippet() {
    const p = selectedProject();
    syncSeg('protoSeg', 'proto', connectProto);
    syncSeg('langSeg', 'lang', connectLang);
    // Only the <code> child is rewritten, and only with textContent: the Copy button
    // that addCopyButtons() appended to the .code-block stays in place.
    document.getElementById('connectCode').textContent = p ? buildSnippet(p.slug, connectProto, connectLang) : '';
}

function renderKey() {
    const p = selectedProject();
    const hasKey = Boolean(p && p.api_key);
    if (!hasKey) keyRevealed = false;
    const value = document.getElementById('keyValue');
    value.classList.toggle('mono', hasKey);
    value.classList.toggle('muted', !hasKey);
    if (hasKey) value.textContent = keyRevealed ? p.api_key : maskKey(p.api_key);
    else value.textContent = 'Not available. Rotate to get a new key.';
    const reveal = document.getElementById('keyRevealBtn');
    setVisible(reveal, hasKey);
    reveal.textContent = keyRevealed ? 'Hide' : 'Reveal';
    reveal.setAttribute('aria-pressed', String(keyRevealed));
    setVisible(document.getElementById('keyCopyBtn'), hasKey && keyRevealed);
}

function toggleKeyReveal() {
    keyRevealed = !keyRevealed;
    renderKey();
}

function copyKey(btn) {
    const p = selectedProject();
    if (!p || !p.api_key) return;
    copyWithFeedback(p.api_key, btn, 'API key copied');
}

async function rotateKey() {
    const p = selectedProject();
    if (!p) return;
    const question = `Generate a new API key for "${p.name}"? The current key stops working immediately.`;
    if (!(await confirmAction(question, 'Rotate API key?', 'Rotate'))) return;
    const btn = document.getElementById('keyRotateBtn');
    btnLoading(btn);
    try {
        const result = await apiCall('POST', `/api/v1/projects/${p.id}/rotate-key`);
        if (result && result.api_key) {
            p.api_key = result.api_key;
            showApiKey(p.name, result.api_key);
        }
        keyRevealed = false;
        renderKey();
        showToast('API key rotated');
    } catch (e) {
        showToast('Failed to rotate key: ' + e.message, 'error');
    }
    btnReset(btn);
}

/* ---------- new-key banner ---------- */
function showApiKey(projectName, key) {
    document.getElementById('apiKeyProject').textContent = projectName;
    document.getElementById('apiKeyValue').textContent = key;
    const alertBox = document.getElementById('apiKeyAlert');
    setVisible(alertBox, true);
    alertBox.scrollIntoView({ block: 'nearest' });
}

function copyApiKey(btn) {
    copyWithFeedback(document.getElementById('apiKeyValue').textContent, btn, 'API key copied');
}

function dismissApiKeyAlert() {
    setVisible(document.getElementById('apiKeyAlert'), false);
    document.getElementById('apiKeyValue').textContent = '';
}

/* ---------- Pools ---------- */
// Pools nested in a project carry no counts (the API leaves them null), so join
// them with the full pool list, which has proxy_count and healthy_count.
function poolsOf(project) {
    const byId = {};
    allPools.forEach((pool) => { byId[pool.id] = pool; });
    return (project.pools || []).map((pool) => byId[pool.id] || pool);
}

function healthBadge(pool) {
    const total = pool.proxy_count;
    const healthy = pool.healthy_count;
    if (total === null || total === undefined || healthy === null || healthy === undefined) {
        return '<span class="muted">—</span>';
    }
    const cls = total > 0 && healthy === 0 ? 'badge-bad' : 'badge-quiet';
    return `<span class="badge ${cls}">${esc(fmtNum(healthy))} / ${esc(fmtNum(total))} healthy</span>`;
}

function renderPools() {
    const p = selectedProject();
    const pools = p ? poolsOf(p) : [];
    setVisible(document.getElementById('projectPoolsTable'), pools.length > 0);
    setVisible(document.getElementById('projectPoolsEmpty'), pools.length === 0);
    setHtml(document.getElementById('projectPoolsBody'), pools.map((pool) => `
        <tr>
            <td class="strong"><div class="truncate" style="max-width:340px" title="${esc(pool.name)}">${esc(pool.name)}</div></td>
            <td><span class="muted">${esc(pool.rotation_strategy)}</span></td>
            <td>${healthBadge(pool)}</td>
            <td class="actions"><button class="btn btn-ghost btn-sm" type="button" data-remove-pool="${esc(pool.id)}" aria-label="Remove ${esc(pool.name)} from this project">Remove</button></td>
        </tr>`).join(''));
}

async function removePool(poolId, btn) {
    const p = selectedProject();
    if (!p) return;
    const pool = poolsOf(p).find((x) => x.id === poolId);
    const question = `Remove "${pool ? pool.name : 'this pool'}" from "${p.name}"? Requests will stop using it.`;
    if (!(await confirmAction(question, 'Remove pool?', 'Remove'))) return;
    btnLoading(btn);
    try {
        await apiCall('DELETE', `/api/v1/projects/${p.id}/pools/${poolId}`);
        showToast('Pool removed');
    } catch (e) {
        showToast('Remove failed: ' + e.message, 'error');
    }
    btnReset(btn);
    reloadProjects();
}

async function openManagePools() {
    const p = selectedProject();
    if (!p) return;
    try {
        const [poolsData, fresh] = await Promise.all([
            apiCall('GET', '/api/v1/pools?per_page=100'),
            apiCall('GET', `/api/v1/projects/${p.id}`),
        ]);
        allPools = poolsData.data || [];
        modalProjectId = p.id;
        modalAssigned = new Set((fresh.pools || []).map((pool) => pool.id));
        document.getElementById('managePoolsInfo').textContent = 'Tick the pools that "' + p.name + '" may use.';
        const box = document.getElementById('poolCheckboxes');
        if (allPools.length === 0) {
            box.innerHTML = '<p class="muted">No pools exist yet. <a href="/pools?new=1">Create a pool</a> first.</p>';
        } else {
            box.innerHTML = allPools.map((pool) => `
                <label for="poolcb-${esc(pool.id)}">
                    <input type="checkbox" id="poolcb-${esc(pool.id)}" value="${esc(pool.id)}"${modalAssigned.has(pool.id) ? ' checked' : ''}>
                    <span class="strong truncate spacer" title="${esc(pool.name)}">${esc(pool.name)}</span>
                    <span class="muted">${esc(fmtNum(pool.proxy_count || 0))} proxies · ${esc(pool.rotation_strategy)}</span>
                </label>`).join('');
        }
        document.getElementById('savePoolsBtn').disabled = allPools.length === 0;
        openModal('managePoolsModal');
    } catch (e) {
        showToast('Failed to load pools: ' + e.message, 'error');
    }
}

// POST /pools only ever adds, so removals go through DELETE one by one.
async function savePoolAssignments() {
    if (!modalProjectId) return;
    const checked = new Set(
        Array.from(document.querySelectorAll('#poolCheckboxes input[type="checkbox"]'))
            .filter((box) => box.checked)
            .map((box) => box.value)
    );
    const adds = Array.from(checked).filter((id) => !modalAssigned.has(id));
    const removes = Array.from(modalAssigned).filter((id) => !checked.has(id));
    if (adds.length === 0 && removes.length === 0) {
        closeModal('managePoolsModal');
        return;
    }
    const btn = document.getElementById('savePoolsBtn');
    btnLoading(btn);
    try {
        if (adds.length > 0) {
            await apiCall('POST', `/api/v1/projects/${modalProjectId}/pools`, { pool_ids: adds });
        }
        for (const poolId of removes) {
            await apiCall('DELETE', `/api/v1/projects/${modalProjectId}/pools/${poolId}`);
        }
        showToast('Pools updated');
        closeModal('managePoolsModal');
    } catch (e) {
        showToast('Update failed: ' + e.message, 'error');
    }
    btnReset(btn);
    reloadProjects();
}

/* ---------- create, select, delete ---------- */
async function createProject() {
    const input = document.getElementById('projectName');
    const name = input.value.trim();
    if (!name) { showToast('Project name is required', 'error'); return; }
    const btn = document.getElementById('createProjectBtn');
    btnLoading(btn);
    try {
        const result = await apiCall('POST', '/api/v1/projects', { name: name });
        closeModal('createProjectModal');
        input.value = '';
        if (result.api_key) showApiKey(result.name, result.api_key);
        // Show it at once (the list is newest first); the reload below confirms it.
        projects = [result].concat(projects.filter((x) => x.id !== result.id));
        selectedProjectId = result.id;
        keyRevealed = false;
        writeSelectionToUrl();
        renderPage();
        showToast('Project created');
        reloadProjects();
    } catch (e) {
        showToast('Create failed: ' + e.message, 'error');
    }
    btnReset(btn);
}

function selectProject(id) {
    if (id === selectedProjectId) return;
    selectedProjectId = id;
    keyRevealed = false;
    writeSelectionToUrl();
    markActiveTile();
    renderDetail();
}

async function deleteProject() {
    const p = selectedProject();
    if (!p) return;
    const question = `Delete "${p.name}"? Its API key stops working immediately.`;
    if (!(await confirmAction(question, 'Delete project?', 'Delete'))) return;
    const btn = document.getElementById('deleteProjectBtn');
    btnLoading(btn);
    try {
        await apiCall('DELETE', `/api/v1/projects/${p.id}`);
        const idx = projects.findIndex((x) => x.id === p.id);
        const next = projects[idx + 1] || projects[idx - 1] || null;
        projects = projects.filter((x) => x.id !== p.id);
        delete stats[p.id];
        selectedProjectId = next ? next.id : null;
        keyRevealed = false;
        writeSelectionToUrl();
        renderPage();
        showToast('Project deleted');
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
    btnReset(btn);
    reloadProjects();
}

/* ---------- wiring ---------- */
document.getElementById('projectList').addEventListener('click', (e) => {
    const tile = e.target.closest('.list-tile');
    if (tile) selectProject(tile.dataset.projectId);
});

document.getElementById('projectPoolsBody').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-remove-pool]');
    if (btn) removePool(btn.dataset.removePool, btn);
});

document.getElementById('protoSeg').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-proto]');
    if (!btn || !PROTOS.includes(btn.dataset.proto)) return;
    connectProto = btn.dataset.proto;
    writePref('proxysm.connect.proto', connectProto);
    renderSnippet();
});

document.getElementById('langSeg').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-lang]');
    if (!btn || !LANGS.includes(btn.dataset.lang)) return;
    connectLang = btn.dataset.lang;
    writePref('proxysm.connect.lang', connectLang);
    renderSnippet();
});

openModalFromQuery({ new: 'createProjectModal' });
renderSnippet();
Poller.start(loadProjects, POLL_MS);
```

Notes for the implementer:
- Names only ever reach the DOM through `esc()` (HTML positions and quoted attributes) or `textContent` (detail head, banner, modal intro). `confirmAction` puts its message in with `textContent`, so a name inside the question is safe. Inline handlers take no arguments except `this`; tiles and Remove buttons are wired by delegation on `data-project-id` / `data-remove-pool`.
- Every URL is built from `p.id` / `pool.id` that came from the API. The `?project=` value from the address bar is only ever compared with those ids, never put into a URL or into HTML.
- `renderList()` and `setHtml()` skip the DOM write when the HTML did not change, and selection only toggles `.active`. That is what lets a 30-second poll run without taking focus away from a tile or a Remove button.
- The literal text `https://httpbin.org/ip` and `'://'` are snippet text, not requests. If a later gate greps page scripts for `https?://`, this file is the expected exception.

- [ ] **Step 5: Run the suite**

Run: `node --check src/web/static/js/pages/projects.js && uv run ruff check tests && uv run pytest tests/ -q`
Expected: no output from `node`, "All checks passed!", all tests PASS.

- [ ] **Step 6: Smoke check (preview server)**

Start `uv run python -m scripts.ui_preview`, open `http://127.0.0.1:8099/projects`. The preview's POST and DELETE return canned bodies and never change the lists; `GET /projects/{id}` and `GET /projects/{id}/stats` answer with the clicked project's own fixture (the hostile project has no stats fixture and gets `scraper-prod`'s numbers).

Scenario `normal`:
1. Left column: "Projects" with a lime "New project" button, then four tiles: `seo-audit` "9,870 requests · 2.1% errors", `price-monitor` "86K requests · 6.0% errors", `scraper-prod` "224K requests · 6.9% errors" and the hostile one (hover a stats line: "Since the oldest 5-minute metrics still kept (7 days by default)"). `seo-audit` is white (selected) and the address bar now ends `?project=c0de0000-0000-4000-8000-000000000003`. "Projects" is the white pill in the sidebar.
2. Right column for `seo-audit`: "seo-audit", "created Sep 15, 2026", coral-text "Delete project"; a Connect tile; a Pools tile showing "No pools assigned" / "Requests for this project will fail until you add one." with a lime "Add pool".
3. Click `scraper-prod`: the tile turns white without the list being rebuilt (keyboard focus stays on it), the URL changes to `...000000000001`, Pools lists `datacenter-us` / `round_robin` / "3 / 4 healthy" and `public-mix` / `random` / "2 / 6 healthy" (both quiet badges), each with a ghost "Remove".
4. Connect: with HTTP + curl the block reads exactly `curl --proxy http://scraper-prod:$PROXYSM_KEY@127.0.0.1:9080 \` and `     https://httpbin.org/ip`. SOCKS5 switches scheme and port to `socks5://...:9081`. Python shows five lines ending `proxies={"all": proxy})`; Node + HTTP imports `ProxyAgent, fetch` from `undici` and passes `{ dispatcher }`; Node + SOCKS5 imports `SocksProxyAgent` and passes `{ agent }`. The host is whatever is in the address bar: open the page as `http://localhost:8099/projects` and the snippet says `localhost`. No snippet ever contains the text `PREVIEW-`. The block's Copy button survives every switch, turns to "Copied", and the clipboard holds the snippet without the word "Copy". Reload: the last protocol and language are still selected.
5. API key row: "Username scraper-prod", then `••••••••••••0001`, "Reveal", "Rotate". Reveal shows `PREVIEW-scraper-prod-not-a-real-secret-0001`, the button reads "Hide" and a "Copy" button appears (toast "API key copied"). Selecting another project masks again.
6. Rotate: dialog "Rotate API key?" with a "Rotate" button; Cancel sends nothing. Rotate: the amber banner appears at the top: "Your new API key for scraper-prod", `PREVIEW-scraper-prod-rotated-not-a-secret-1`, Copy, and the `PROXYSM_KEY` hint; lime toast "API key rotated"; the row now masks to `••••••••••••et-1`. "Dismiss" hides the banner. (Preview: the next 30-second refresh brings the old key back, because the list never changes.)
7. "Add pool" (on `scraper-prod`): modal "Manage pools", intro `Tick the pools that "scraper-prod" may use.`, four rows with "N proxies · strategy" on the right; `public-mix` and `datacenter-us` are ticked; focus is on the first checkbox. Tick `residential-eu`, untick `public-mix`, Save: the network panel shows one `POST .../pools` with `{"pool_ids":["b0010000-0000-4000-8000-000000000003"]}` and one `DELETE .../pools/b0010000-0000-4000-8000-000000000002`; toast "Pools updated"; modal closes. Open it again and press Save without touching anything: it closes with no request. (Preview: the table does not change.)
8. "Remove" on `datacenter-us`: dialog "Remove pool?" / `Remove "datacenter-us" from "scraper-prod"? Requests will stop using it.` / "Remove". Confirm: one `DELETE .../pools/b0010000-...0001`, toast "Pool removed". (Preview: the row stays.)
9. "New project": modal with focus in "Project name". Create with an empty name: coral toast "Project name is required", modal stays. Type a name, press Enter: modal closes, the amber banner shows "Your new API key for New Project" and `PREVIEW-new-project-key-not-a-real-secret-4`, toast "Project created". (Preview: a "New Project" tile flashes at the top and disappears again on the reload that follows, and the first project is selected. On a real instance it stays, selected.)
10. "Delete project" on `price-monitor`: dialog "Delete project?" / `Delete "price-monitor"? Its API key stops working immediately.`; Cancel does nothing; Delete: toast "Project deleted" and `scraper-prod` (the next one) is selected. (Preview: the deleted tile comes back on the reload.)
11. Hostile names: the fourth tile shows `<script>alert(2)</script> " onmouseover="alert(3) very-long-...` as literal text cut with an ellipsis; its tooltip has the full name; hovering it fires nothing. Select it: the 30px heading is cut with an ellipsis and "created" and "Delete project" stay inside the column; Username is `hostile-project`; the API key row reads "Not available. Rotate to get a new key." with only "Rotate" (its `api_key` is null). In "Add pool" the `<script>alert(1)</script>-very-long-pool-name-...` row is literal text with an ellipsis and the modal does not scroll sideways. No dialog fired at any point, and `document.documentElement.scrollWidth === document.documentElement.clientWidth`.
12. `http://127.0.0.1:8099/projects?new=1&project=c0de0000-0000-4000-8000-000000000002`: the New project modal is open, `price-monitor` is selected, and the address bar keeps only `?project=...`. `?project=not-an-id` selects the first project and rewrites the URL.
13. States the preview cannot produce, from the browser console. `stats[projects[0].id] = {total_requests: 0, failed_requests: 0}; paintStats()`: the first tile reads "No traffic yet". Select `price-monitor`, then `allPools[0].healthy_count = 0; renderPools()`: its `residential-eu` row shows a coral "0 / 2 healthy". `allPools = []; renderPools()`: the Health cell is a dash, never the word `null`.
14. Width 1000px: the tiles stack above the detail and both fill the width. Width 390px: same, "Delete project" wraps under the name, the Connect switches wrap under the title, the code block and the pools table scroll inside their tile, and the page itself does not scroll sideways.

Scenario `empty` (`http://127.0.0.1:8099/__scenario/empty`, then reload `/projects?project=c0de0000-0000-4000-8000-000000000002`):
15. The head with "New project", no tiles, no detail column, and one full-width tile: "No projects yet" / "A project gives your client a username and an API key for the rotating proxy." / lime "New project" (opens the same modal). The `project` parameter is removed from the address bar. `document.body.innerText` contains none of `NaN`, `undefined`, `null`, `Infinity`.

Scenario `offline` (`/__scenario/offline`, then reload `/projects`):
16. The skeletons are replaced by a tile "Could not load projects" / "The API did not answer. This page keeps retrying on its own." / "Retry now". The sidebar status line is coral "Offline, retrying". No toast appears, however long you wait. "Retry now" shows exactly one coral toast, "Still not reachable: preview: simulated outage".
17. Recovery without a reload: switch to `/__scenario/normal` in a second tab. Within 30 seconds (or at once with "Retry now") the tiles and the detail appear and the status line returns to "Updated just now".
18. Outage after a good load: with the page loaded, switch to `offline` and wait for the next refresh: the status line turns coral, tiles and detail stay as they were, no toast. Rotate, confirm: one coral toast "Failed to rotate key: preview: simulated outage". Switch back to `normal` and stop the preview server.

- [ ] **Step 7: Commit**

```bash
git add src/web/templates/projects.html src/web/static/js/pages/projects.js tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): projects page in Blocks

List + detail with ?project=<id>, Connect snippet built from the viewing
host and PROXYSM_KEY, assigned pools table. Unticking a pool in the
pools modal now removes it.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Settings page

**Files:**
- Rewrite: `src/web/templates/settings.html`
- Create: `src/web/static/js/pages/settings.js`
- Modify: `tests/test_web_routes.py`
- Modify: `tests/test_ui_static.py` (one list entry)

**Interfaces:**
- Consumes (`app.js` globals): `APP.httpPort`, `APP.socks5Port`, `apiCall`, `esc`, `timeAgo`, `fmtDate`, `showToast`, `openModal`, `closeModal`, `confirmAction`, `btnLoading`, `btnReset`. The shared Enter-submits / Esc-closes modal handlers in `app.js` are relied on: the Save button keeps `class="btn btn-primary"` inside `.modal-actions`.
- Consumes (CSS, all defined by Task 1): `.page-head`, `.tile`, `.tile-head` (+ `.tile-head--wrap`), `.tile-head__meta`, `.table-scroll`, `table.tbl`, `td.actions`, `.badge-healthy`, `.badge-quiet`, `.tag`, `.btn` (+ `-primary`, `-outline`, `-ghost`, `-danger`, `-sm`), `.empty-state`, `.empty-state-icon`, `.kv`, `.row`, `.mono`, `.muted`, `.strong`, `.truncate`, `.form-group`, `.check`, `.modal-overlay`, `.modal`, `.modal-actions`.
- Consumes (`base.html`): blocks `title`, `content`, `scripts`; `asset_version`; `toastContainer`, `confirmModal`, `navStatus`.
- Consumes (API, all existing, none changed):
  - `GET /api/v1/alerts` -> bare list of rules (no `{data, meta}` envelope)
  - `GET /api/v1/alerts/{id}`, `POST /api/v1/alerts`, `PATCH /api/v1/alerts/{id}`, `DELETE /api/v1/alerts/{id}` (204)
  - `GET /api/v1/pools?per_page=100` -> `{data: [{id, name, ...}], meta}` (fills the Pool select)
  - `GET /api/v1/system/info` -> flat object
- Produces: tile anchors `#alerts`, `#system`, `#retention` (unchanged from the old page, so existing deep links keep working) and the new `#apiReference`. No URL parameters.

**What changes for the operator:**
- Same page, Blocks look: four stacked tiles (Alert rules, System, Data retention, API reference). The in-page section menu on the left (Alerts / System / Retention) and its scroll highlighting are gone; the page is short and the anchors still work.
- Alert rules: the per-row on/off switch becomes an **Enable** / **Disable** button (same one-click `PATCH {is_enabled}`, same toasts). Status reads **Enabled** / **Disabled** instead of Active / Paused. "Last triggered" is relative ("1d ago", "never") with the date in the tooltip.
- The create / edit modal works exactly as before: same four condition types, the same fields appearing per type, the same validation messages, percent <-> fraction and GB <-> bytes conversion, unknown config keys preserved when the type is unchanged, create = `POST`, edit = `PATCH`.
- New **API reference** tile with "Open Swagger UI" (`/docs`) and "Open ReDoc" (`/redoc`) and the auth header format. It replaces the retired hand-written API Docs page.
- If the API is down the page no longer throws an error toast on load: the rules tile says "Could not load alert rules" with a **Retry** button, and the two read-only tiles show the built-in defaults (as before) but now say so ("API unreachable. Showing the built-in defaults.").
- An empty instance shows "No alert rules" with an **Add rule** button.

- [ ] **Step 1: Write the failing tests**

Existing tests that fetch `/settings`:

| Test | Decision |
|---|---|
| `test_settings_returns_html` | Kept as is. |
| `test_settings_alert_modal_has_typed_fields` | Kept as is, unchanged. Every id it pins (`alertErrThreshold`, `alertErrWindow`, `alertPoolSelect`, `alertMinHealthy`, `alertBwLimit`, `grpAllDeadHint`, `alertWebhookUrl`) is still in the template markup, and the two ids it forbids (`alertCondConfig`, `alertActionConfig`) are still absent. Nothing it asserts moved into JS. |
| `test_pages_redirect_to_login_without_session` | Kept as is (it iterates `PAGES` since Task 5; `/settings` stays in it). |
| `test_active_nav_item_is_rendered_by_the_server[/settings-nav-settings]`, `test_shell_uses_versioned_static_assets[/settings]` (Task 4) | Kept as is; they pass before and after. |

No test is deleted.

In `tests/test_web_routes.py`:

1. Add `"/settings"` to the `RESTYLED_PAGES` list literal (keep whatever earlier tasks already put there). This turns on `test_restyled_page_has_markup_only[/settings]`.
2. Add this import directly under `from src.web.routes import router as web_router` (skip it if an earlier page task already added it):

```python
from tests.test_ui_static import assert_js_ids_exist
```

3. Append at the end of the file (`re`, `pathlib`, `_STATIC`, `_fake_settings` and the `client` fixture exist since Task 4):

```python
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
```

In `tests/test_ui_static.py` add `"settings.html"` to the `RESTYLED_TEMPLATES` list literal (keep the existing entries). This turns on `test_template_and_script_use_only_defined_classes[settings.html]`, which checks `settings.html` and `settings.js` against `app.css`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_web_routes.py tests/test_ui_static.py -q -k settings`

Expected: 9 FAIL, the rest PASS.
- `test_restyled_page_has_markup_only[/settings]`: the old template has an inline `<style>` and an inline `<script>`.
- `test_settings_page_structure`, `test_settings_keeps_every_system_value`, `test_settings_links_to_interactive_api_docs`, `test_settings_alert_modal_is_a_labelled_dialog`: no `settings.js` script tag, no `setVersion` / `systemHint` ids, no `/docs` link, no `role="dialog"`.
- `test_settings_script_ids_exist_in_page`, `test_settings_script_is_a_classic_script_on_app_js`, `test_settings_script_keeps_the_alert_rule_contract`: `FileNotFoundError`, `settings.js` does not exist yet.
- `test_template_and_script_use_only_defined_classes[settings.html]`: the old template uses `panel`, `set-row`, `switch`, ... which `app.css` does not define.
- Still passing: `test_settings_returns_html`, `test_settings_alert_modal_has_typed_fields` and the two Task 4 shell tests for `/settings`.

- [ ] **Step 3: Rewrite the template**

Replace the whole of `src/web/templates/settings.html` with:

```html
{% extends "base.html" %}
{% block title %}Settings - Proxysm{% endblock %}

{% block content %}
<div class="page-head">
    <h1>Settings</h1>
</div>

<section class="tile" id="alerts" aria-labelledby="alertsTitle">
    <div class="tile-head">
        <h2 id="alertsTitle">Alert rules</h2>
        <button class="btn btn-outline btn-sm" type="button" onclick="openCreateAlert()">Add rule</button>
    </div>
    <p class="muted" id="alertsLoading">Loading alert rules…</p>
    <div class="table-scroll" id="alertsTable" hidden>
        <table class="tbl">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Trigger</th>
                    <th>Action</th>
                    <th>Last triggered</th>
                    <th>Status</th>
                    <th aria-label="Actions"></th>
                </tr>
            </thead>
            <tbody id="alertsList"></tbody>
        </table>
    </div>
    <div class="empty-state" id="alertsEmpty" hidden>
        <div class="empty-state-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        </div>
        <h3>No alert rules</h3>
        <p>Add a rule to get a webhook call when proxies fail, a pool runs low or bandwidth runs out.</p>
        <button class="btn btn-primary" type="button" onclick="openCreateAlert()">Add rule</button>
    </div>
    <div class="empty-state" id="alertsError" hidden>
        <h3>Could not load alert rules</h3>
        <p>The API did not answer. Your rules are untouched.</p>
        <button class="btn" type="button" onclick="retryLoad(this)">Retry</button>
    </div>
</section>

<section class="tile" id="system" aria-labelledby="systemTitle">
    <div class="tile-head tile-head--wrap">
        <h2 id="systemTitle">System</h2>
        <span class="tile-head__meta" id="systemHint">Read-only. Configured through environment variables.</span>
    </div>
    <dl class="kv">
        <dt>Version</dt>
        <dd>
            <div class="mono" id="setVersion">—</div>
            <div class="muted">Current Proxysm release.</div>
        </dd>
        <dt>Health check interval</dt>
        <dd>
            <div class="mono" id="setHcInterval">—</div>
            <div class="muted">Healthy proxies are rechecked at this cadence; degraded and dead ones adapt automatically.</div>
        </dd>
        <dt>Health check timeout</dt>
        <dd>
            <div class="mono" id="setHcTimeout">—</div>
            <div class="muted">Maximum time to wait for a proxy to respond during a check.</div>
        </dd>
        <dt>Health check concurrency</dt>
        <dd>
            <div class="mono" id="setHcConcurrency">—</div>
            <div class="muted">Number of proxies checked in parallel.</div>
        </dd>
        <dt>HTTP proxy port</dt>
        <dd>
            <div class="mono" id="setHttpPort">—</div>
            <div class="muted">Listening port for the HTTP forward proxy.</div>
        </dd>
        <dt>SOCKS5 proxy port</dt>
        <dd>
            <div class="mono" id="setSocksPort">—</div>
            <div class="muted">Listening port for the SOCKS5 proxy.</div>
        </dd>
        <dt>Prometheus metrics</dt>
        <dd>
            <div class="mono" id="setPrometheus">—</div>
            <div class="muted">Expose metrics at <span class="mono">/metrics</span> for scraping.</div>
        </dd>
    </dl>
</section>

<section class="tile" id="retention" aria-labelledby="retentionTitle">
    <div class="tile-head tile-head--wrap">
        <h2 id="retentionTitle">Data retention</h2>
        <span class="tile-head__meta" id="retentionHint">Read-only. Configured through environment variables.</span>
    </div>
    <dl class="kv">
        <dt>Request log retention</dt>
        <dd>
            <div class="mono" id="setLogRetention">—</div>
            <div class="muted">How long individual request log entries are kept.</div>
        </dd>
        <dt>5-min metrics retention</dt>
        <dd>
            <div class="mono" id="set5minRetention">—</div>
            <div class="muted">Retention window for 5-minute metric rollups.</div>
        </dd>
        <dt>1-hour metrics retention</dt>
        <dd>
            <div class="mono" id="set1hourRetention">—</div>
            <div class="muted">Retention window for hourly metric rollups.</div>
        </dd>
        <dt>Metrics rollup interval</dt>
        <dd>
            <div class="mono" id="setRollupInterval">—</div>
            <div class="muted">How often raw request logs are aggregated into rollups.</div>
        </dd>
        <dt>Bandwidth flush interval</dt>
        <dd>
            <div class="mono" id="setBwFlush">—</div>
            <div class="muted">How often bandwidth counters are persisted to the database.</div>
        </dd>
    </dl>
</section>

<section class="tile" id="apiReference" aria-labelledby="apiReferenceTitle">
    <div class="tile-head tile-head--wrap">
        <h2 id="apiReferenceTitle">API reference</h2>
        <span class="tile-head__meta">The REST API is documented interactively.</span>
    </div>
    <dl class="kv">
        <dt>Interactive docs</dt>
        <dd class="row">
            <a class="btn" href="/docs">Open Swagger UI</a>
            <a class="btn" href="/redoc">Open ReDoc</a>
        </dd>
        <dt>Authentication</dt>
        <dd>
            <span class="muted">Send the header <span class="mono">Authorization: Bearer &lt;admin password&gt;</span> with every request.</span>
        </dd>
    </dl>
</section>

<div class="modal-overlay" id="alertModal" role="dialog" aria-modal="true" aria-labelledby="alertModalTitle">
    <div class="modal">
        <h2 id="alertModalTitle">Create alert rule</h2>
        <input type="hidden" id="alertEditId" value="">
        <div class="form-group">
            <label for="alertName">Name</label>
            <input type="text" id="alertName" maxlength="255" autocomplete="off" placeholder="e.g. High error rate">
        </div>
        <div class="form-group">
            <label for="alertCondType">Condition type</label>
            <select id="alertCondType" onchange="updateCondFields()">
                <option value="error_rate_above">Error rate above threshold</option>
                <option value="pool_below_min_healthy">Pool below min healthy</option>
                <option value="bandwidth_exceeded">Bandwidth exceeded</option>
                <option value="all_proxies_dead">All proxies dead</option>
            </select>
        </div>
        <div class="form-group" id="grpErrThreshold">
            <label for="alertErrThreshold">Error rate threshold (%)</label>
            <input type="number" id="alertErrThreshold" min="0" max="100" step="any" placeholder="e.g. 50">
        </div>
        <div class="form-group" id="grpErrWindow">
            <label for="alertErrWindow">Window (seconds)</label>
            <input type="number" id="alertErrWindow" min="1" step="1" placeholder="e.g. 300">
        </div>
        <div class="form-group" id="grpPool" hidden>
            <label for="alertPoolSelect">Pool</label>
            <select id="alertPoolSelect"></select>
        </div>
        <div class="form-group" id="grpMinHealthy" hidden>
            <label for="alertMinHealthy">Min healthy proxies</label>
            <input type="number" id="alertMinHealthy" min="1" step="1" placeholder="e.g. 2">
        </div>
        <div class="form-group" id="grpBwLimit" hidden>
            <label for="alertBwLimit">Bandwidth limit (GB)</label>
            <input type="number" id="alertBwLimit" min="0" step="any" placeholder="e.g. 100">
        </div>
        <div class="form-group" id="grpAllDeadHint" hidden>
            <p class="muted">Triggers when every proxy is marked dead. No configuration needed.</p>
        </div>
        <div class="form-group">
            <label for="alertActionType">Action type</label>
            <select id="alertActionType">
                <option value="webhook">Webhook</option>
            </select>
        </div>
        <div class="form-group">
            <label for="alertWebhookUrl">Webhook URL</label>
            <input type="url" id="alertWebhookUrl" autocomplete="off" placeholder="https://hooks.example.com/alert">
        </div>
        <label class="check" for="alertEnabled">
            <input type="checkbox" id="alertEnabled" checked>
            Enabled
        </label>
        <div class="modal-actions">
            <button class="btn" type="button" onclick="closeModal('alertModal')">Cancel</button>
            <button class="btn btn-primary" type="button" id="alertSaveBtn" onclick="saveAlert()">Save</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/pages/settings.js?v={{ asset_version }}"></script>
{% endblock %}
```

Notes for the implementer:
- Visibility is switched with the `hidden` attribute, never with inline `display`. That works because none of `.table-scroll`, `.empty-state`, `.form-group` or `p` sets `display` in `app.css`. Do not put `hidden` on an element whose class sets `display` (`.row`, `.check`, `.tile-head`): the class would win.
- The Enabled checkbox uses `.check`. Do not reuse `.row-checkbox` for it: `clearSelection()` in `app.js` unchecks every `.row-checkbox` on the page.
- The two read-only tiles and the API reference tile use `.tile-head--wrap` so the hint drops under the title on narrow screens instead of squeezing it.
- The webhook placeholder contains `https://` inside a `placeholder` attribute; `test_restyled_page_has_markup_only` only looks at `src` / `href`, so it is fine.

- [ ] **Step 4: Write the page script**

Create `src/web/static/js/pages/settings.js`:

```js
/* Settings page: alert rules (table + typed create/edit modal) and the read-only
   system and retention values. Nothing polls: data loads once and again after
   each mutation. Uses the app.js globals (apiCall, esc, timeAgo, modals, toasts). */
'use strict';

const HINT_LIVE = 'Read-only. Configured through environment variables.';
const HINT_DEFAULTS = 'API unreachable. Showing the built-in defaults.';

/* ---------- system + retention values ---------- */
// Every field falls back to the shipped default, so an empty object renders the
// same values the old page showed when /system/info could not be reached.
function renderSystemInfo(data) {
    document.getElementById('setVersion').textContent = data.version || '0.1.0';
    document.getElementById('setHcInterval').textContent = (data.health_check_interval || 60) + 's';
    document.getElementById('setHcTimeout').textContent = (data.health_check_timeout || 10) + 's';
    document.getElementById('setHcConcurrency').textContent = data.health_check_concurrency || 200;
    document.getElementById('setHttpPort').textContent = data.proxy_http_port || APP.httpPort || 9080;
    document.getElementById('setSocksPort').textContent = data.proxy_socks5_port || APP.socks5Port || 9081;
    document.getElementById('setPrometheus').textContent = data.prometheus_enabled ? 'Enabled (/metrics)' : 'Disabled';
    document.getElementById('setLogRetention').textContent = (data.request_log_retention_days || 7) + ' days';
    document.getElementById('set5minRetention').textContent = (data.metrics_5min_retention_days || 7) + ' days';
    document.getElementById('set1hourRetention').textContent = (data.metrics_1hour_retention_days || 90) + ' days';
    document.getElementById('setRollupInterval').textContent = (data.metrics_rollup_interval || 300) + 's';
    document.getElementById('setBwFlush').textContent = (data.bandwidth_flush_interval || 30) + 's';
}

async function loadSystemInfo() {
    let data = {};
    let live = true;
    try {
        data = (await apiCall('GET', '/api/v1/system/info')) || {};
    } catch (e) {
        live = false; // no toast: the sidebar status line reports outages
    }
    renderSystemInfo(data);
    const hint = live ? HINT_LIVE : HINT_DEFAULTS;
    document.getElementById('systemHint').textContent = hint;
    document.getElementById('retentionHint').textContent = hint;
}

/* ---------- alert rules table ---------- */
let rules = [];

function formatCondType(t) {
    const map = {
        'error_rate_above': 'Error rate',
        'pool_below_min_healthy': 'Pool health',
        'bandwidth_exceeded': 'Bandwidth',
        'all_proxies_dead': 'All proxies dead',
    };
    return map[t] || t;
}

function formatActionType(t) {
    const map = {
        'webhook': 'Webhook',
    };
    return map[t] || t;
}

function ruleStatusBadge(enabled) {
    return enabled
        ? '<span class="badge badge-healthy">Enabled</span>'
        : '<span class="badge badge-quiet">Disabled</span>';
}

// state: 'loading' | 'table' | 'empty' | 'error'
function showRulesState(state) {
    document.getElementById('alertsLoading').hidden = state !== 'loading';
    document.getElementById('alertsTable').hidden = state !== 'table';
    document.getElementById('alertsEmpty').hidden = state !== 'empty';
    document.getElementById('alertsError').hidden = state !== 'error';
}

function ruleRow(a) {
    const id = esc(a.id);
    const last = a.last_triggered_at
        ? `<span title="${esc(fmtDate(a.last_triggered_at))}">${esc(timeAgo(a.last_triggered_at))} ago</span>`
        : '<span class="muted">never</span>';
    return `<tr>
        <td><div class="strong truncate" style="max-width:320px" title="${esc(a.name)}">${esc(a.name)}</div></td>
        <td>${esc(formatCondType(a.condition_type))}</td>
        <td><span class="tag">${esc(formatActionType(a.action_type))}</span></td>
        <td>${last}</td>
        <td>${ruleStatusBadge(a.is_enabled)}</td>
        <td class="actions">
            <button class="btn btn-ghost btn-sm" type="button" data-rule="${id}" onclick="toggleAlert('${id}', ${a.is_enabled ? 'false' : 'true'}, this)">${a.is_enabled ? 'Disable' : 'Enable'}</button>
            <button class="btn btn-sm" type="button" onclick="editAlert('${id}')">Edit</button>
            <button class="btn btn-danger btn-sm" type="button" onclick="deleteAlert('${id}')">Delete</button>
        </td>
    </tr>`;
}

function renderRules() {
    const tbody = document.getElementById('alertsList');
    if (rules.length === 0) {
        tbody.innerHTML = '';
        showRulesState('empty');
        return;
    }
    tbody.innerHTML = rules.map(ruleRow).join('');
    showRulesState('table');
}

// announce = true for user-initiated reloads (after a mutation, Retry): those toast
// their failure. The first load stays quiet; the sidebar status line reports outages.
async function loadAlerts(announce) {
    let data;
    try {
        data = await apiCall('GET', '/api/v1/alerts');
    } catch (e) {
        showRulesState('error');
        if (announce) showToast('Failed to load alerts: ' + e.message, 'error');
        return;
    }
    rules = Array.isArray(data) ? data : [];
    renderRules();
}

async function retryLoad(btn) {
    btnLoading(btn);
    await Promise.all([loadAlerts(true), loadSystemInfo()]);
    btnReset(btn);
}

/* ---------- typed condition fields ---------- */
const COND_FIELD_GROUPS = {
    'error_rate_above': ['grpErrThreshold', 'grpErrWindow'],
    'pool_below_min_healthy': ['grpPool', 'grpMinHealthy'],
    'bandwidth_exceeded': ['grpBwLimit'],
    'all_proxies_dead': ['grpAllDeadHint'],
};
const ALL_COND_GROUPS = [...new Set(Object.values(COND_FIELD_GROUPS).flat())];
const BYTES_PER_GB = 1e9;

// Originals of the rule being edited, so unknown config keys are preserved.
let origCondType = null;
let origCondConfig = {};
let origActionConfig = {};
let poolOptionsPromise = null;

function updateCondFields() {
    const type = document.getElementById('alertCondType').value;
    const visible = COND_FIELD_GROUPS[type] || [];
    ALL_COND_GROUPS.forEach((id) => {
        document.getElementById(id).hidden = !visible.includes(id);
    });
}

// Pools are fetched once per page view; a failed fetch is retried on the next open.
function loadPoolOptions() {
    if (!poolOptionsPromise) {
        poolOptionsPromise = apiCall('GET', '/api/v1/pools?per_page=100').then((resp) => {
            const pools = (resp && resp.data) || [];
            const sel = document.getElementById('alertPoolSelect');
            sel.innerHTML = '';
            if (pools.length === 0) sel.add(new Option('No pools available', ''));
            pools.forEach((p) => sel.add(new Option(p.name, p.id)));
            return pools;
        }).catch((e) => {
            poolOptionsPromise = null; // allow retry next time
            throw e;
        });
    }
    return poolOptionsPromise;
}

// The "(unknown pool)" option belongs to one edit session only.
function dropUnknownPoolOption() {
    document.querySelectorAll('#alertPoolSelect option[data-unknown]').forEach((o) => o.remove());
}

/* ---------- create / edit modal ---------- */
function openCreateAlert() {
    document.getElementById('alertModalTitle').textContent = 'Create alert rule';
    document.getElementById('alertEditId').value = '';
    document.getElementById('alertName').value = '';
    document.getElementById('alertCondType').value = 'error_rate_above';
    origCondType = null;
    origCondConfig = {};
    origActionConfig = {};
    document.getElementById('alertErrThreshold').value = '';
    document.getElementById('alertErrWindow').value = '300';
    document.getElementById('alertMinHealthy').value = '';
    document.getElementById('alertBwLimit').value = '';
    document.getElementById('alertWebhookUrl').value = '';
    document.getElementById('alertActionType').value = 'webhook';
    document.getElementById('alertEnabled').checked = true;
    dropUnknownPoolOption();
    loadPoolOptions().catch(() => {});
    updateCondFields();
    openModal('alertModal');
}

async function editAlert(id) {
    try {
        const rule = await apiCall('GET', `/api/v1/alerts/${id}`);
        document.getElementById('alertModalTitle').textContent = 'Edit alert rule';
        document.getElementById('alertEditId').value = id;
        document.getElementById('alertName').value = rule.name;
        document.getElementById('alertCondType').value = rule.condition_type;
        document.getElementById('alertActionType').value = rule.action_type;

        origCondType = rule.condition_type;
        origCondConfig = rule.condition_config || {};
        origActionConfig = rule.action_config || {};
        const cfg = origCondConfig;

        // Stored as a 0..1 fraction and as bytes; edited as a percentage and as GB.
        document.getElementById('alertErrThreshold').value =
            cfg.threshold != null ? parseFloat((cfg.threshold * 100).toFixed(4)) : '';
        document.getElementById('alertErrWindow').value =
            cfg.window_seconds != null ? cfg.window_seconds : '300';
        document.getElementById('alertMinHealthy').value =
            cfg.min_healthy != null ? cfg.min_healthy : '';
        document.getElementById('alertBwLimit').value =
            cfg.limit_bytes != null ? parseFloat((cfg.limit_bytes / BYTES_PER_GB).toFixed(4)) : '';

        try { await loadPoolOptions(); } catch (e) { /* pool list optional */ }
        dropUnknownPoolOption();
        const poolSel = document.getElementById('alertPoolSelect');
        if (cfg.pool_id) {
            if (![...poolSel.options].some((o) => o.value === String(cfg.pool_id))) {
                const opt = new Option(cfg.pool_id + ' (unknown pool)', cfg.pool_id);
                opt.dataset.unknown = '1';
                poolSel.add(opt);
            }
            poolSel.value = cfg.pool_id;
        }

        document.getElementById('alertWebhookUrl').value = origActionConfig.url != null ? origActionConfig.url : '';
        document.getElementById('alertEnabled').checked = rule.is_enabled;
        updateCondFields();
        openModal('alertModal');
    } catch (e) {
        showToast('Failed to load alert: ' + e.message, 'error');
    }
}

async function saveAlert() {
    const name = document.getElementById('alertName').value.trim();
    if (!name) { showToast('Please enter a name', 'error'); return; }

    const condType = document.getElementById('alertCondType').value;
    // Preserve unknown keys from the original config when the type is unchanged.
    const condConfig = condType === origCondType ? { ...origCondConfig } : {};

    if (condType === 'error_rate_above') {
        const pct = parseFloat(document.getElementById('alertErrThreshold').value);
        const win = parseInt(document.getElementById('alertErrWindow').value, 10);
        if (!isFinite(pct) || pct <= 0 || pct > 100) { showToast('Enter an error rate threshold between 0 and 100%', 'error'); return; }
        if (!isFinite(win) || win <= 0) { showToast('Enter a window in seconds (greater than 0)', 'error'); return; }
        condConfig.threshold = pct / 100;
        condConfig.window_seconds = win;
    } else if (condType === 'pool_below_min_healthy') {
        const poolId = document.getElementById('alertPoolSelect').value;
        const minHealthy = parseInt(document.getElementById('alertMinHealthy').value, 10);
        if (!poolId) { showToast('Select a pool', 'error'); return; }
        if (!isFinite(minHealthy) || minHealthy < 1) { showToast('Enter a min healthy count of at least 1', 'error'); return; }
        condConfig.pool_id = poolId;
        condConfig.min_healthy = minHealthy;
    } else if (condType === 'bandwidth_exceeded') {
        const gb = parseFloat(document.getElementById('alertBwLimit').value);
        if (!isFinite(gb) || gb <= 0) { showToast('Enter a bandwidth limit in GB (greater than 0)', 'error'); return; }
        condConfig.limit_bytes = Math.round(gb * BYTES_PER_GB);
    }
    // all_proxies_dead: no fields.

    const webhookUrl = document.getElementById('alertWebhookUrl').value.trim();
    if (!/^https?:\/\/\S+$/i.test(webhookUrl)) { showToast('Enter a valid webhook URL (http:// or https://)', 'error'); return; }
    const actionConfig = { ...origActionConfig, url: webhookUrl };

    const body = {
        name: name,
        condition_type: condType,
        condition_config: condConfig,
        action_type: document.getElementById('alertActionType').value,
        action_config: actionConfig,
        is_enabled: document.getElementById('alertEnabled').checked,
    };

    const editId = document.getElementById('alertEditId').value;
    const btn = document.getElementById('alertSaveBtn');
    btnLoading(btn);

    try {
        if (editId) {
            await apiCall('PATCH', `/api/v1/alerts/${editId}`, body);
            showToast('Alert updated', 'success');
        } else {
            await apiCall('POST', '/api/v1/alerts', body);
            showToast('Alert created', 'success');
        }
        btnReset(btn);
        closeModal('alertModal');
        loadAlerts(true);
    } catch (e) {
        btnReset(btn);
        showToast('Failed to save alert: ' + e.message, 'error');
    }
}

/* ---------- row actions ---------- */
async function toggleAlert(id, enabled, btn) {
    btnLoading(btn);
    try {
        await apiCall('PATCH', `/api/v1/alerts/${id}`, { is_enabled: enabled });
        const rule = rules.find((r) => r.id === id);
        if (rule) rule.is_enabled = enabled;
        renderRules();
        // The row was re-rendered: hand keyboard focus to the new toggle button.
        const again = document.querySelector('button[data-rule="' + id + '"]');
        if (again) again.focus();
        showToast(enabled ? 'Alert enabled' : 'Alert disabled', 'success');
    } catch (e) {
        btnReset(btn);
        showToast('Failed to toggle alert: ' + e.message, 'error');
        loadAlerts(); // re-sync the row with the server
    }
}

async function deleteAlert(id) {
    if (!(await confirmAction('Delete this alert rule? This cannot be undone.'))) return;
    try {
        await apiCall('DELETE', `/api/v1/alerts/${id}`);
        showToast('Alert deleted', 'success');
        loadAlerts(true);
    } catch (e) {
        showToast('Failed to delete alert: ' + e.message, 'error');
    }
}

loadSystemInfo();
loadAlerts();
```

Notes for the implementer:
- `rules`, `renderRules`, `loadAlerts` and the modal functions are top-level on purpose: inline handlers call them, and the smoke step below pokes `rules` from the console.
- `loadAlerts()` and `loadSystemInfo()` never toast on the first load; `loadAlerts(true)` (after a mutation, or Retry) does. Every other failure path is a user action and toasts.
- The toggle updates the row locally from the value it sent (as the old page did) instead of refetching, then puts focus back on the re-rendered button so keyboard users do not lose their place.
- The validation message `'Enter a valid webhook URL (http:// or https://)'` is carried over verbatim; it is the only place the script contains `http://`.
- Run `node --check src/web/static/js/pages/settings.js`. Expected: no output.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS.

Run: `uv run ruff check --output-format concise tests/test_web_routes.py tests/test_ui_static.py`
Expected: nothing reported for these files.

- [ ] **Step 6: Smoke check (preview server)**

Start `uv run python -m scripts.ui_preview` and open `http://127.0.0.1:8099/settings`.

Scenario `normal` (open `http://127.0.0.1:8099/__scenario/normal` first):
1. Four tiles under a 44px "Settings" title: Alert rules, System, Data retention, API reference. Sidebar: Settings is the white pill. No toast appears on load. The browser console has no errors and every request goes to `127.0.0.1:8099`.
2. Alert rules lists two rows: "datacenter-us running low" (Pool health, WEBHOOK, never, grey **Disabled** badge, buttons Enable / Edit / Delete) and "High error rate" (Error rate, WEBHOOK, "Nd ago" with the date in its tooltip, lime **Enabled** badge, buttons Disable / Edit / Delete).
3. System shows `0.1.0`, `60s`, `10s`, `200`, `9080`, `9081`, `Disabled`; Data retention shows `7 days`, `7 days`, `90 days`, `300s`, `30s`. Both heads read "Read-only. Configured through environment variables."
4. Click **Disable** on "High error rate": toast "Alert disabled", the badge turns grey **Disabled**, the button now reads **Enable** and still has keyboard focus. (This change is local, so it is visible in the preview; it resets on reload.)
5. Click **Edit** on any row: the preview always answers `GET alerts/{id}` with the "High error rate" rule, so the modal opens as "Edit alert rule" with name "High error rate", condition "Error rate above threshold", threshold `25`, window `300`, the `.../error-rate` webhook URL and Enabled ticked; focus is in the Name field. Click **Save**: toast "Alert updated", modal closes. The list does not change (canned API), so the success toast is the only visible result; in the Network panel the `PATCH` body has `"condition_config":{"threshold":0.25,"window_seconds":300}`.
6. **Edit** again and switch Condition type to "Pool below min healthy": Threshold and Window disappear, Pool and Min healthy proxies appear. The Pool select lists `residential-eu`, `public-mix`, `datacenter-us` and the fixtures' hostile pool name as literal text starting `<script>alert(1)</script>-very-long-pool-name-`; no dialog pops up and the modal does not get wider. **Save** with Min healthy empty: toast "Enter a min healthy count of at least 1". Enter `2`, **Save**: toast "Alert updated"; the `PATCH` body's `condition_config` has only `pool_id` and `min_healthy` (the old `threshold` / `window_seconds` are dropped because the type changed).
7. Click **Add rule**: title "Create alert rule", empty name, window prefilled `300`. **Save** right away: "Please enter a name". Type a name, **Save**: "Enter an error rate threshold between 0 and 100%". Threshold `12.5`, window `0`: "Enter a window in seconds (greater than 0)". Window `120`, webhook `ftp://nope`: "Enter a valid webhook URL (http:// or https://)". Switch to "Bandwidth exceeded" with an `https://` webhook: "Enter a bandwidth limit in GB (greater than 0)". Enter `1.5` and press Enter in the field: toast "Alert created", modal closes, `POST` body has `"condition_config":{"limit_bytes":1500000000}`. The new rule does not appear in the list (canned API).
8. **Add rule**, choose "All proxies dead": only the sentence "Triggers when every proxy is marked dead. No configuration needed." shows. Press Esc: the modal closes and focus returns to the Add rule button.
9. Click **Delete** on a row: confirm dialog "Delete this alert rule? This cannot be undone." with Cancel focused. **Delete**: toast "Alert deleted"; the row stays (canned API).
10. Hostile alert name (the alert fixtures have none, so inject one). Run in the console:
    `rules = [{ id: '00000000-0000-4000-8000-000000000000', name: '<script>alert(1)</script>" onmouseover="alert(2) ' + 'x'.repeat(200), condition_type: 'all_proxies_dead', action_type: 'webhook', is_enabled: true, last_triggered_at: null }]; renderRules();`
    Expected: the name shows as literal text cut with an ellipsis at 320px, the full text is in its tooltip, hovering it does nothing, no dialog pops up, neither the tile nor the page scrolls sideways.
11. API reference: the two buttons point at `/docs` and `/redoc` (hover to check). In the preview both lead to the 404 tile, because the preview app is built with `docs_url=None`; in the real app they open Swagger UI and ReDoc.
12. Resize to 390px: the page does not scroll sideways; the rules table scrolls inside its tile; the System and Data retention hints sit under their titles; the modal fits the screen and scrolls.

Scenario `empty` (open `/__scenario/empty`, then reload `/settings`):
13. Alert rules shows the bell icon, "No alert rules", one sentence and a lime **Add rule** button that opens the modal. System and Data retention show the same values as before. In the console `/(NaN|undefined|null|Infinity)/.test(document.querySelector('.content').innerText)` is `false`.
14. In the modal choose "Pool below min healthy": the Pool select shows "No pools available". Fill a name, Min healthy `1`, **Save**: toast "Select a pool".

Scenario `offline` (open `/__scenario/offline`, then reload `/settings`):
15. No toast on load. The sidebar status turns coral "Offline, retrying". Alert rules shows "Could not load alert rules" with a **Retry** button; System and Data retention still show the default values and both heads read "API unreachable. Showing the built-in defaults." The page is not blank.
16. Click **Retry**: exactly one coral toast "Failed to load alerts: preview: simulated outage".
17. Open `/__scenario/normal` in another tab, come back and click **Retry** without reloading: the two rules appear, both hints return to "Read-only. Configured through environment variables.", the sidebar status goes back to lime "Updated ...".

Stop the preview server.

- [ ] **Step 7: Commit**

```bash
git add src/web/templates/settings.html src/web/static/js/pages/settings.js tests/test_web_routes.py tests/test_ui_static.py
git commit -m "feat(ui): settings page in Blocks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Fix the Recheck endpoint (`POST /api/v1/ips/{id}/check` always returns 500)

Found while preparing this plan. `check_single_proxy` in `src/health/checker.py` returns three values `(new_status, latency_ms, external_ip)`, but the handler in `src/api/proxies.py` unpacks two, so it raises `ValueError: too many values to unpack (expected 2)` on every call. Both the per-row Recheck button and the bulk Recheck on the Proxies page hit this endpoint, so today they can only ever show an error. It is a one-line fix and the rebuilt Proxies page should not ship with a button that cannot work.

**Files:**
- Modify: `src/api/proxies.py` (the `check_proxy` handler)
- Modify: `tests/test_api_proxies.py`

**Interfaces:**
- Consumes: `src.health.checker.check_single_proxy(proxy) -> tuple[str, float, str | None]`.
- Produces: `POST /api/v1/ips/{id}/check` -> 200 `{"id": str, "status": str, "latency_ms": float}` (the shape `proxies.js` and the preview fixture already expect). No schema change.

- [ ] **Step 1: Write the failing test**

In `tests/test_api_proxies.py` add `import uuid` as the first import line, and append:

```python
@pytest.mark.asyncio
@patch("src.api.deps.settings", _fake_settings)
async def test_check_proxy_accepts_the_checkers_three_values():
    """check_single_proxy returns (status, latency_ms, external_ip); the handler must not 500."""
    proxy = MagicMock()
    proxy.id = uuid.UUID("a0010000-0000-4000-8000-000000000001")
    proxy.host, proxy.port, proxy.protocol = "203.0.113.18", 8080, "http"
    proxy.username = None
    proxy.password_encrypted = None
    session = AsyncMock()
    session.get = AsyncMock(return_value=proxy)
    engine = MagicMock()
    engine.update_proxy_health = AsyncMock()
    engine.cache_proxy_info = AsyncMock()
    checker = AsyncMock(return_value=("healthy", 182.0, "198.51.100.9"))

    transport = ASGITransport(app=_build_test_app(session))
    with (
        patch("src.health.checker.check_single_proxy", checker),
        patch("src.api.proxies.get_redis", AsyncMock(return_value=MagicMock())),
        patch("src.api.proxies.RotationEngine", return_value=engine),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/ips/{proxy.id}/check",
                headers={"Authorization": f"Bearer {ADMIN_PASSWORD}"},
            )

    assert resp.status_code == 200
    assert resp.json() == {"id": str(proxy.id), "status": "healthy", "latency_ms": 182.0}
    assert proxy.last_health_status == "healthy"
    assert proxy.avg_latency_ms == 182.0
    engine.update_proxy_health.assert_awaited_once_with(str(proxy.id), "healthy")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_api_proxies.py -q -k three_values`
Expected: FAIL with `ValueError: too many values to unpack (expected 2)` raised at `src/api/proxies.py` in `check_proxy`.

- [ ] **Step 3: Fix the handler**

In `src/api/proxies.py`, in `check_proxy`, change

```python
    health_status, latency = await check_single_proxy(proxy)
```

to

```python
    health_status, latency, _external_ip = await check_single_proxy(proxy)
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --output-format concise src/api/proxies.py tests/test_api_proxies.py
git add src/api/proxies.py tests/test_api_proxies.py
git commit -m "fix(api): recheck endpoint unpacks the checker's three return values

POST /api/v1/ips/{id}/check raised ValueError on every call because
check_single_proxy returns (status, latency_ms, external_ip).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Remove the leftovers and run the full smoke pass

**Files:**
- Delete: `src/web/static/fonts/geist.woff2`, `src/web/static/fonts/geist-mono.woff2`
- Modify: `tests/test_web_routes.py`, `tests/test_ui_static.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `PAGES`, `RESTYLED_PAGES` (`tests/test_web_routes.py`); `RESTYLED_TEMPLATES`, `TEMPLATES`, `PAGES_JS`, `STATIC` (`tests/test_ui_static.py`).
- Produces: nothing new. This task is the gate that proves the milestone is complete.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_routes.py`:

```python
def test_every_page_is_restyled():
    assert sorted(RESTYLED_PAGES) == sorted(PAGES)
```

Append to `tests/test_ui_static.py`:

```python
LEGACY_NAMES = [
    "dash-card", "dash-tab", "dash-section", "metrics-table", "dashboard-grid", "kpi-grid",
    "navbar", "live-pill", "api-banner", "table-card", "stat-pill", "panel-head", "panel-body",
    "throughput-badge", "usage-tab", "hljs", "language-", "Geist", "cdnjs", "showApiBanner",
    '"/setup"', '"/api-docs"',
]


def test_every_template_is_restyled():
    on_disk = sorted(p.name for p in TEMPLATES.glob("*.html"))
    assert on_disk == sorted(RESTYLED_TEMPLATES)


def test_no_legacy_names_survive():
    sources = list(TEMPLATES.glob("*.html")) + list(PAGES_JS.glob("*.js"))
    sources += [STATIC / "js" / "app.js", STATIC / "css" / "app.css"]
    for src in sources:
        text = src.read_text()
        found = [name for name in LEGACY_NAMES if name in text]
        assert not found, f"{src.name} still contains legacy names: {found}"


def test_only_the_three_blocks_fonts_ship():
    fonts = sorted(p.name for p in FONTS.glob("*.woff2"))
    assert fonts == ["bricolage-grotesque.woff2", "figtree.woff2", "jetbrains-mono.woff2"]


def test_page_scripts_never_use_jinja_or_localhost():
    for src in PAGES_JS.glob("*.js"):
        text = src.read_text()
        assert "{{" not in text and "{%" not in text, f"{src.name}: no Jinja in static files"
        assert "localhost" not in text, f"{src.name}: use APP.host"
```

- [ ] **Step 2: Run to verify what fails**

Run: `uv run pytest tests/test_ui_static.py tests/test_web_routes.py -q -k "restyled or legacy or three_blocks or jinja_or_localhost"`
Expected: `test_only_the_three_blocks_fonts_ship` FAILS (Geist files still present). The others should already PASS; if `test_every_page_is_restyled`, `test_every_template_is_restyled` or `test_no_legacy_names_survive` fails, a page task was left incomplete: go back and finish it (do not weaken the test).

- [ ] **Step 3: Delete the Geist fonts**

```bash
git rm src/web/static/fonts/geist.woff2 src/web/static/fonts/geist-mono.woff2
```

- [ ] **Step 4: Bring the README in line with the UI**

Run this from the repo root (each replacement asserts its target exists exactly once, so a drifted README fails loudly instead of silently):

```bash
uv run python - <<'EOF'
import pathlib

path = pathlib.Path("README.md")
text = path.read_text()
replacements = [
    (
        "Dashboard (http://localhost:8080/dashboard) — explain what each stat card means: total proxies, healthy/degraded/dead counts, request throughput, error rates, bandwidth usage, latency percentiles, and the interactive charts.",
        "Overview (http://localhost:8080/dashboard) — explain the four tiles (healthy, degraded, dead, requests per minute with error rate and median latency), the traffic chart with its 1h / 24h / 7d switch, and the provider, pool and project tables.",
    ),
    (
        "API Docs (http://localhost:8080/api-docs) — the REST API endpoint reference (with links to interactive Swagger UI at /docs and ReDoc at /redoc), covering all endpoints:",
        "API reference (http://localhost:8080/docs, also linked from Settings) — the interactive Swagger UI (ReDoc at /redoc), covering all endpoints:",
    ),
    (
        "go to Proxies page, click Add Proxy, enter a proxy address",
        "go to Proxies page, click Import, paste a proxy address",
    ),
    ("go to Pools page, click Create Pool, name it", "go to Pools page, click New pool, name it"),
    (
        "go to Projects page, click Create Project, name it",
        "go to Projects page, click New project, name it",
    ),
]
for old, new in replacements:
    assert text.count(old) == 1, f"README drifted, not found exactly once: {old[:60]}..."
    text = text.replace(old, new)
path.write_text(text)
EOF
```

- [ ] **Step 5: Run everything**

```bash
uv run pytest tests/ -q
uv run ruff check --output-format concise src/web/routes.py src/api/proxies.py tests/test_api_proxies.py scripts/ui_preview.py scripts/ui_preview_fixtures.py \
  scripts/fetch_fonts.py tests/test_web_routes.py tests/test_ui_static.py tests/test_ui_preview.py
for f in src/web/static/js/app.js src/web/static/js/pages/*.js; do node --check "$f" || exit 1; done
```

Expected: all tests PASS, ruff reports nothing for these files, `node --check` prints nothing. (If `node` is not installed, skip the last line and say so in the report.)

- [ ] **Step 6: Full smoke pass on the preview server**

Start `uv run python -m scripts.ui_preview`. For each of `/dashboard`, `/proxies`, `/pools`, `/projects`, `/settings`:

1. **1440px wide, scenario `normal`:** the page matches its mockup's structure; the browser console has no errors; the Network panel shows requests to `127.0.0.1:8099` only (no other host).
2. **Hostile name:** the pool named with `<script>` and 60+ characters shows as literal text, is cut with an ellipsis, and no dialog popped up.
3. **1000px wide:** sidebar is an icon rail; tiles reflow to one or two columns; nothing overflows horizontally except tables, which scroll inside their tile.
4. **390px wide:** top bar with a menu button; the menu opens and closes; every modal fits the screen and scrolls.
   **1440x560 (short window):** the sidebar scrolls on its own; Settings and Sign out can be scrolled fully into view and clicked; the page content scrolls independently.
5. **Keyboard only:** Tab reaches every control in a sensible order with a visible lime ring; Enter submits a modal's primary button; Esc closes the top modal and focus returns to the button that opened it.
6. **`/__scenario/empty`:** onboarding card on Overview with three steps; every table shows its empty state; run in the console `/(NaN|undefined|null|Infinity)/.test(document.querySelector('.content').innerText)` and expect `false`.
7. **`/__scenario/offline`:** within 15 seconds the sidebar status turns coral "Offline, retrying"; no toast appears from polling; clicking an action (for example Recheck) shows one error toast. Then `/__scenario/normal`: status returns to "Updated ..." without reloading.
8. **Expired session:** in the real app this cannot be simulated by the preview (it bypasses login); instead confirm by reading `apiCall` that the 401 branch redirects once (`redirectingToLogin`).

Write the results as a checklist in the task report. Any failed check is a bug to fix in the owning page task's files before committing.

- [ ] **Step 7: Commit**

```bash
git add -A src/web/static/fonts tests/test_web_routes.py tests/test_ui_static.py README.md
git commit -m "chore(ui): drop Geist fonts, final restyle gates, README in line with the new UI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## After this milestone

Not part of this plan: deploying to node2 (the operator's call), and milestones 2-5 of the spec, each of which gets its own plan.
