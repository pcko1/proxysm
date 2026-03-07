# Structure Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify ProxyManager by demoting Provider to a text label, consolidating nav from 7 to 4 items, moving Blacklist into Project detail, and renaming Stats to Dashboard.

**Architecture:** Remove the `providers` table entirely. Add a `provider` text column to `proxies`. Remove all Provider CRUD endpoints and UI. Consolidate nav to Dashboard | Proxies | Pools | Projects. Move blacklist UI into project detail page.

**Tech Stack:** Python, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Jinja2 templates

---

### Task 1: Alembic Migration — Demote Provider to Text Label

**Files:**
- Create: `alembic/versions/002_provider_to_text.py`

**Step 1: Create migration file**

```python
"""Demote provider from entity to text label on proxies

Revision ID: 002_provider_to_text
Revises: 001_phase2
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002_provider_to_text"
down_revision = "001_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new text column
    op.add_column("proxies", sa.Column("provider", sa.String(255), nullable=True))

    # 2. Copy provider names from providers table into proxies.provider
    op.execute("""
        UPDATE proxies
        SET provider = providers.name
        FROM providers
        WHERE proxies.provider_id = providers.id
    """)

    # 3. Drop the FK constraint and provider_id column
    op.drop_constraint("proxies_provider_id_fkey", "proxies", type_="foreignkey")
    op.drop_index("idx_proxies_provider", "proxies", if_exists=True)
    op.drop_column("proxies", "provider_id")

    # 4. Drop the providers table
    op.drop_table("providers")


def downgrade() -> None:
    # Recreate providers table
    op.create_table(
        "providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("api_endpoint", sa.Text(), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add provider_id back
    op.add_column("proxies", sa.Column("provider_id", UUID(as_uuid=True), nullable=True))

    # We can't perfectly restore the FK data, but at least recreate the column
    op.create_index("idx_proxies_provider", "proxies", ["provider_id"])

    # Drop the text column
    op.drop_column("proxies", "provider")
```

**Step 2: Verify migration file is valid**

Run: `cd /Users/admin/Repositories/proxymanager && python -c "import alembic.versions" 2>&1 || echo "File created, will test with DB later"`

**Step 3: Commit**

```bash
git add alembic/versions/002_provider_to_text.py
git commit -m "feat: add migration to demote provider from entity to text label"
```

---

### Task 2: Update Proxy Model — Replace provider FK with text field

**Files:**
- Modify: `src/models/proxy.py`
- Delete: `src/models/provider.py`
- Modify: `src/models/__init__.py`

**Step 1: Update Proxy model**

In `src/models/proxy.py`:
- Remove `provider_id` FK column (line 40-42)
- Remove `provider` relationship (line 63)
- Remove `from src.models.provider import Provider` TYPE_CHECKING import (line 23)
- Add `provider: Mapped[str | None] = mapped_column(String(255), nullable=True)`

The full updated file:

```python
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.associations import PoolProxy


class Proxy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "proxies"
    __table_args__ = (
        UniqueConstraint("host", "port", "protocol", name="uq_proxy_host_port_protocol"),
        CheckConstraint("port >= 0 AND port <= 65535", name="ck_proxy_port_range"),
        CheckConstraint(
            "protocol IN ('http', 'https', 'socks5')", name="ck_proxy_protocol"
        ),
        CheckConstraint(
            "last_health_status IN ('healthy', 'degraded', 'dead', 'unknown')",
            name="ck_proxy_health_status",
        ),
    )

    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_health_status: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown"
    )
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Phase 2: Geo-detection fields
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asn: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    pool_proxies: Mapped[list["PoolProxy"]] = relationship(
        "PoolProxy", back_populates="proxy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Proxy {self.protocol}://{self.host}:{self.port}>"
```

**Step 2: Delete provider model**

Delete `src/models/provider.py` entirely.

**Step 3: Update models __init__.py**

In `src/models/__init__.py`, remove the `Provider` import and export.

**Step 4: Commit**

```bash
git add src/models/proxy.py src/models/__init__.py
git rm src/models/provider.py
git commit -m "feat: replace provider FK with text label on Proxy model"
```

---

### Task 3: Update Schemas — Replace provider_id with provider string

**Files:**
- Modify: `src/schemas/proxy.py`
- Delete: `src/schemas/provider.py`
- Modify: `src/schemas/__init__.py`

**Step 1: Update proxy schemas**

Replace `src/schemas/proxy.py` with:

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProxyCreate(BaseModel):
    host: str
    port: int = Field(ge=0, le=65535)
    protocol: Literal["http", "https", "socks5"]
    provider: str | None = None
    username: str | None = None
    password: str | None = None


class ProxyUpdate(BaseModel):
    is_active: bool | None = None


class ProxyResponse(BaseModel):
    id: uuid.UUID
    host: str
    port: int
    protocol: str
    provider: str | None = None
    is_active: bool
    last_health_status: str | None = None
    avg_latency_ms: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProxyBulkImport(BaseModel):
    provider: str | None = None
    proxies: str | None = None
    proxy_list: list[ProxyCreate] | None = None
```

**Step 2: Delete provider schema**

Delete `src/schemas/provider.py` entirely.

**Step 3: Update schemas __init__.py**

Remove all `Provider*` imports and exports from `src/schemas/__init__.py`:

```python
from src.schemas.common import PaginatedResponse, PaginationMeta
from src.schemas.pool import PoolAddProxies, PoolCreate, PoolRemoveProxies, PoolResponse, PoolUpdate
from src.schemas.project import (
    ProjectAssignPools,
    ProjectCreate,
    ProjectCreateResponse,
    ProjectResponse,
    ProjectUpdate,
)
from src.schemas.proxy import ProxyBulkImport, ProxyCreate, ProxyResponse, ProxyUpdate

__all__ = [
    "PaginatedResponse",
    "PaginationMeta",
    "PoolAddProxies",
    "PoolCreate",
    "PoolRemoveProxies",
    "PoolResponse",
    "PoolUpdate",
    "ProjectAssignPools",
    "ProjectCreate",
    "ProjectCreateResponse",
    "ProjectResponse",
    "ProjectUpdate",
    "ProxyBulkImport",
    "ProxyCreate",
    "ProxyResponse",
    "ProxyUpdate",
]
```

**Step 4: Commit**

```bash
git add src/schemas/proxy.py src/schemas/__init__.py
git rm src/schemas/provider.py
git commit -m "feat: update schemas — provider is now a text field, remove Provider schemas"
```

---

### Task 4: Update Proxies API — Use provider string instead of provider_id

**Files:**
- Modify: `src/api/proxies.py`

**Step 1: Update proxies API**

Key changes to `src/api/proxies.py`:
- Line 24: Change sort column from `Proxy.provider_id` to `Proxy.provider`
- Line 37: Change `provider_id: uuid.UUID | None` to `provider: str | None = Query(None)`
- Lines 55-57: Filter by `Proxy.provider == provider` instead of `Proxy.provider_id == provider_id`
- Line 85: Change `provider_id=body.provider_id` to `provider=body.provider`
- Line 145: Same change for bulk import

Full updated `_SORT_COLUMNS` and endpoint filter:

```python
_SORT_COLUMNS = {
    "host": Proxy.host,
    "port": Proxy.port,
    "protocol": Proxy.protocol,
    "provider": Proxy.provider,
    "status": Proxy.last_health_status,
    "latency": Proxy.avg_latency_ms,
}
```

In `list_proxies`, change param from `provider_id: uuid.UUID | None = Query(None)` to `provider: str | None = Query(None)`, and filter: `base = base.where(Proxy.provider == provider)`.

In `create_proxy`, change `provider_id=body.provider_id` to `provider=body.provider`.

In `bulk_import_proxies`, change `provider_id=body.provider_id` to `provider=body.provider`.

**Step 2: Commit**

```bash
git add src/api/proxies.py
git commit -m "feat: update proxies API to use provider text field"
```

---

### Task 5: Remove Provider API and Update main.py

**Files:**
- Delete: `src/api/providers.py`
- Modify: `src/main.py`
- Modify: `src/api/stats.py`

**Step 1: Delete providers API**

Delete `src/api/providers.py` entirely.

**Step 2: Update main.py**

Remove these lines from `src/main.py`:
- Line 63: `from src.api.providers import router as providers_router`
- Line 70: Remove `providers_stats_router` from the stats import
- Line 74: `app.include_router(providers_router, prefix="/api/v1")`
- Line 84: `app.include_router(providers_stats_router, prefix="/api/v1")`

**Step 3: Update stats API**

In `src/api/stats.py`:
- Remove `from src.models.provider import Provider` import (line 13)
- Remove `total_providers` count query (line 42)
- Remove `total_providers=total_providers` from overview response (line 70)
- Remove `providers_stats_router` definition (line 171)
- Remove the entire `get_provider_stats` endpoint (lines 213-223)

Also update `src/schemas/stats.py` to remove `total_providers` field (line 14).

**Step 4: Commit**

```bash
git rm src/api/providers.py
git add src/main.py src/api/stats.py src/schemas/stats.py
git commit -m "feat: remove provider API, stats router, and main.py registration"
```

---

### Task 6: Update Web Routes — Rename Stats to Dashboard, Remove Provider/Blacklist Routes

**Files:**
- Modify: `src/web/routes.py`

**Step 1: Update web routes**

```python
import pathlib

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))


def _ctx(request: Request) -> dict:
    return {"request": request, "admin_token": settings.pm_admin_password}


@router.get("/", response_class=RedirectResponse)
async def index():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", _ctx(request))


@router.get("/stats", response_class=RedirectResponse)
async def stats_redirect():
    return RedirectResponse(url="/dashboard")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", _ctx(request))


@router.get("/proxies", response_class=HTMLResponse)
async def proxies_page(request: Request):
    return templates.TemplateResponse("proxies.html", _ctx(request))


@router.get("/pools", response_class=HTMLResponse)
async def pools_page(request: Request):
    return templates.TemplateResponse("pools.html", _ctx(request))


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse("projects.html", _ctx(request))


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", _ctx(request))


@router.get("/blacklist", response_class=RedirectResponse)
async def blacklist_redirect():
    return RedirectResponse(url="/projects")


@router.get("/providers", response_class=RedirectResponse)
async def providers_redirect():
    return RedirectResponse(url="/proxies")


def not_found_handler(request: Request, exc: Exception):
    """Custom 404 handler returning styled page."""
    return templates.TemplateResponse("404.html", _ctx(request), status_code=404)
```

**Step 2: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: rename stats to dashboard, redirect old routes"
```

---

### Task 7: Update Navbar in base.html

**Files:**
- Modify: `src/web/templates/base.html`

**Step 1: Update navbar links**

In `src/web/templates/base.html`, replace the navbar links section (lines 798-808):

Change:
```html
<a href="/stats" class="navbar-brand">ProxyManager</a>
<a href="/setup" class="nav-setup-btn" title="Quick Setup">
```

To:
```html
<a href="/dashboard" class="navbar-brand">ProxyManager</a>
```

Remove the `nav-setup-btn` entirely (lines 799-801).

Replace the navbar-links div contents (lines 802-808):
```html
<div class="navbar-links" id="navLinks">
    <a href="/dashboard" id="nav-dashboard">Dashboard</a>
    <a href="/proxies" id="nav-proxies">Proxies</a>
    <a href="/pools" id="nav-pools">Pools</a>
    <a href="/projects" id="nav-projects">Projects</a>
</div>
```

**Step 2: Commit**

```bash
git add src/web/templates/base.html
git commit -m "feat: consolidate navbar to Dashboard | Proxies | Pools | Projects"
```

---

### Task 8: Rename stats.html to dashboard.html and Update Title

**Files:**
- Rename: `src/web/templates/stats.html` -> `src/web/templates/dashboard.html`

**Step 1: Rename file and update content**

Rename the file, then update:
- Line 2: `{% block title %}Dashboard - ProxyManager{% endblock %}`
- Line 149: Change `<h1>Stats</h1>` to `<h1>Dashboard</h1>`
- Line 154: Remove the `<a href="/setup" class="btn btn-primary">Quick Setup</a>` link (setup is first-run only now)
- Line 456: Change `<a href="/stats"` to `<a href="/dashboard"` in the success page Done link

**Step 2: Commit**

```bash
git mv src/web/templates/stats.html src/web/templates/dashboard.html
git add src/web/templates/dashboard.html
git commit -m "feat: rename stats page to dashboard"
```

---

### Task 9: Update Proxies Template — Remove Provider Entity References

**Files:**
- Modify: `src/web/templates/proxies.html`

**Step 1: Simplify import modal provider field**

Replace the combobox provider field (lines 79-85) with a simple text input:

```html
<div class="form-group">
    <label for="importProvider">Provider <span style="color:var(--text-muted);font-weight:400;text-transform:none">(optional label)</span></label>
    <input type="text" id="importProvider" placeholder="e.g. BrightData, IPRoyal...">
</div>
```

Remove the hidden `importProviderId` input and the `providerSuggestions` dropdown div.

**Step 2: Simplify the JavaScript**

Remove `loadProviders()`, `filterProviderSuggestions()`, `showProviderDropdown()`, `selectProvider()`, `selectNewProvider()` functions entirely.

Update `renderProxies` to show `p.provider` directly instead of looking up `providerMap[p.provider_id]`:
```javascript
const provName = p.provider || '-';
```

Remove `let providerMap = {};` and `let allProviders = [];`.

Update `doImport()`:
- Remove the provider creation logic (lines 262-268 that call `POST /api/v1/providers`)
- Simply pass the text value: `provider: document.getElementById('importProvider').value.trim() || null`
- Remove `providerId` variable, use provider string directly
- For pool creation, filter by provider string: `/api/v1/ips?provider=${encodeURIComponent(providerName)}&per_page=100`

Replace the `doImport` function:
```javascript
async function doImport() {
    const provider = document.getElementById('importProvider').value.trim() || null;
    const importBtn = document.querySelector('#importModal .btn-primary');
    btnLoading(importBtn);

    let text = document.getElementById('importText').value.trim();
    const fileInput = document.getElementById('importFile');
    if (!text && fileInput.files.length > 0) {
        text = await fileInput.files[0].text();
    }
    if (!text) { btnReset(importBtn); showToast('Please paste proxies or upload a file', 'error'); return; }

    try {
        const result = await apiCall('POST', '/api/v1/ips/bulk', {
            provider: provider,
            proxies: text,
        });

        let poolMsg = '';

        if (document.getElementById('importCreatePool').checked) {
            const poolName = document.getElementById('importPoolName').value.trim();
            const strategy = document.getElementById('importPoolStrategy').value;
            if (!poolName) { btnReset(importBtn); showToast('Please enter a pool name', 'error'); return; }

            const pool = await apiCall('POST', '/api/v1/pools', {
                name: poolName,
                rotation_strategy: strategy,
            });

            const filterParam = provider ? `&provider=${encodeURIComponent(provider)}` : '';
            const proxyData = await apiCall('GET', `/api/v1/ips?per_page=100${filterParam}`);
            const proxyIds = (proxyData.data || []).map(p => p.id);
            if (proxyIds.length > 0) {
                await apiCall('POST', `/api/v1/pools/${pool.id}/ips`, { proxy_ids: proxyIds });
            }
            poolMsg = `, pool "${poolName}" created with ${proxyIds.length} proxies`;
        }

        btnReset(importBtn);
        showToast(`Imported ${result.created} proxies` + (result.skipped ? `, ${result.skipped} skipped` : '') + poolMsg, 'success');
        closeModal('importModal');

        document.getElementById('importText').value = '';
        document.getElementById('importProvider').value = '';
        fileInput.value = '';
        document.getElementById('fileName').textContent = 'No file selected';
        document.getElementById('importCreatePool').checked = false;
        document.getElementById('importPoolFields').style.display = 'none';
        document.getElementById('importPoolName').value = '';

        loadProxies();
    } catch (e) {
        btnReset(importBtn);
        showToast('Import failed: ' + e.message, 'error');
    }
}
```

Update page init: replace `loadProviders().then(() => loadProxies());` with just `loadProxies();`

Remove the provider dropdown close handler and the combobox CSS styles.

**Step 3: Commit**

```bash
git add src/web/templates/proxies.html
git commit -m "feat: simplify proxies page — provider is now a text input"
```

---

### Task 10: Update Pools Template — Remove Provider API Dependency

**Files:**
- Modify: `src/web/templates/pools.html`

**Step 1: Update manageProxies function**

In `src/web/templates/pools.html`, the `manageProxies` function (line 127) currently fetches providers to group proxies by provider. Update it to:
- Remove the `apiCall('GET', '/api/v1/providers')` call from the `Promise.all` (line 135)
- Group proxies by `p.provider` text field instead of `p.provider_id`
- Remove `providerMap` lookup

Replace the grouping logic:
```javascript
const byProvider = {};
allProxies.forEach(p => {
    const prov = p.provider || 'No Provider';
    if (!byProvider[prov]) byProvider[prov] = [];
    byProvider[prov].push(p);
});
```

And update the rendering loop to use the provider string as the key directly instead of looking up `providerMap[providerId]`:
```javascript
for (const [provName, proxies] of Object.entries(byProvider)) {
    const provKey = provName.replace(/[^a-zA-Z0-9]/g, '_');
    // ... use provKey for data-provider attributes, provName for display
```

**Step 2: Commit**

```bash
git add src/web/templates/pools.html
git commit -m "feat: update pools page — group proxies by provider text label"
```

---

### Task 11: Update Setup Wizard — Remove Provider API Calls

**Files:**
- Modify: `src/web/templates/setup.html`

**Step 1: Replace provider combobox with text input**

In `src/web/templates/setup.html`:

Replace the provider combobox section (lines 349-357) with a simple text input:
```html
<div class="form-group">
    <label for="setupProvider">Provider <span style="color:var(--text-muted);font-weight:400;text-transform:none;font-size:11px">(optional label)</span></label>
    <input type="text" id="setupProvider" placeholder="e.g. BrightData, IPRoyal..." />
</div>
```

Remove the hidden `setupProviderId` input.

**Step 2: Simplify JavaScript**

- Remove `loadProviders()`, `showProviderDropdown()`, `filterProviders()`, `selectProvider()`, `selectNewProvider()` functions
- Remove `let providers = [];`, `let selectedProviderId = null;`, `let selectedProviderName = '';`
- Update `hasProvider()` to check the text input: `return document.getElementById('setupProvider').value.trim().length > 0;`
- Update `validateStep1` trigger — add `oninput="validateStep1()"` to the provider input
- Update `goToStep2()`: get provider from text input directly
- Update `finishSetup()`:
  - Remove provider creation API call (lines 705-708)
  - Use `const provider = document.getElementById('setupProvider').value.trim() || null;`
  - Pass `provider: provider` to bulk import instead of `provider_id: providerId`
- Remove combobox CSS and dropdown close handler
- Remove `loadProviders()` call at init

**Step 3: Commit**

```bash
git add src/web/templates/setup.html
git commit -m "feat: simplify setup wizard — provider is now a text input"
```

---

### Task 12: Delete providers.html Template

**Files:**
- Delete: `src/web/templates/providers.html`

**Step 1: Delete file**

```bash
git rm src/web/templates/providers.html
git commit -m "chore: remove providers template (provider is now a text label)"
```

---

### Task 13: Update Health Checker — Remove Provider Import If Present

**Files:**
- Check/Modify: `src/health/checker.py` (if it references Provider model)
- Check/Modify: `src/models/__init__.py` (ensure no Provider references remain)

**Step 1: Grep for remaining provider references**

Run: `grep -rn "provider" src/ --include="*.py" | grep -v "__pycache__" | grep -v "provider:" | grep -vi "# provider"`

Fix any remaining references to `Provider` model, `provider_id`, or `src.models.provider` throughout the codebase. Key files to check:
- `src/health/checker.py`
- `src/models/__init__.py`
- `src/services/bandwidth.py` (line 60 — check if "provider" entity_type needs updating in metrics)

For `src/models/__init__.py`, ensure Provider is fully removed from imports and `__all__`.

For `src/models/metrics.py` (line 19), the check constraint allows `entity_type IN ('proxy', 'pool', 'project', 'provider')` — leave this for now as it's in the metrics_rollup table and removing it would require another migration.

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: clean up remaining provider references"
```

---

### Task 14: Delete blacklist.html Template (Moved to Projects)

**Files:**
- Delete: `src/web/templates/blacklist.html`

**Note:** The blacklist API endpoints (`/api/v1/projects/{id}/blacklist`) remain unchanged. Only the standalone Blacklist page is removed — the UI will be embedded into the Projects page in the next task.

**Step 1: Delete file**

```bash
git rm src/web/templates/blacklist.html
git commit -m "chore: remove standalone blacklist page (moved to project detail)"
```

---

### Task 15: Embed Blacklist UI into Projects Page

**Files:**
- Modify: `src/web/templates/projects.html`

**Step 1: Add blacklist section to project rows**

In `src/web/templates/projects.html`, extend the usage expandable row to also include a blacklist section. After the existing usage `code-block` divs in the row template, add a blacklist section:

```html
<p style="color:var(--text-muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.3px;margin:12px 0 8px 0">Blacklist</p>
<div id="bl-${p.id}" style="font-size:13px;color:var(--text-muted)">Loading...</div>
```

Add a `loadBlacklist(projectId)` function that fetches `/api/v1/projects/${projectId}/blacklist` and renders a compact table inside the `bl-${projectId}` div, with remove buttons.

Add a "Block Proxy" button per project that opens a modal (reuse the blacklist modal pattern from the old `blacklist.html`).

Update `toggleUsage` to also trigger `loadBlacklist(id)` on first expand.

**Step 2: Commit**

```bash
git add src/web/templates/projects.html
git commit -m "feat: embed blacklist management into project detail view"
```

---

### Task 16: Final Cleanup and Verification

**Files:**
- Various — verification pass

**Step 1: Search for any broken references**

Run: `grep -rn "provider_id\|from src.models.provider\|from src.schemas.provider\|/api/v1/providers\|providers_router\|providers_stats" src/ --include="*.py" | grep -v __pycache__`

Fix any remaining references found.

**Step 2: Search templates for broken references**

Run: `grep -rn "provider_id\|/api/v1/providers\|providerMap\|loadProviders\|nav-blacklist\|nav-stats\|/stats\b" src/web/templates/ --include="*.html" | grep -v "redirect"`

Fix any remaining references found.

**Step 3: Verify Python imports work**

Run: `cd /Users/admin/Repositories/proxymanager && python -c "from src.models.proxy import Proxy; from src.schemas.proxy import ProxyBulkImport; print('OK')"`

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup — verify no broken provider references remain"
```

---

## Summary of Deleted Files

| File | Reason |
|------|--------|
| `src/models/provider.py` | Provider entity removed |
| `src/schemas/provider.py` | Provider schemas removed |
| `src/api/providers.py` | Provider API removed |
| `src/web/templates/providers.html` | Provider page removed |
| `src/web/templates/blacklist.html` | Moved into projects page |

## Summary of Changes

| Area | Change |
|------|--------|
| Data model | `provider_id` FK -> `provider` text on proxies |
| API | Remove `/api/v1/providers/*`, update `/api/v1/ips` to use `provider` string |
| Navigation | 7 items -> 4: Dashboard, Proxies, Pools, Projects + Settings cog |
| Stats page | Renamed to Dashboard |
| Blacklist page | Removed (embedded in Projects) |
| Setup wizard | Provider combobox -> simple text input |
| Import flow | No more provider creation step, just type a label |
