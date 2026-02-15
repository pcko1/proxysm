# UX Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce the proxy setup flow from ~25 interactions across 4 pages to ~6 interactions via a Quick Setup wizard, while simplifying existing pages by demoting Providers to a label.

**Architecture:** Pure frontend changes — no schema or API changes needed. The wizard chains existing API endpoints. Provider is demoted from a nav page to a combobox field. A new `/setup` page hosts the wizard.

**Tech Stack:** Jinja2 templates, vanilla JS, existing REST API endpoints.

**Design doc:** `docs/plans/2026-02-15-ux-simplification-design.md`

---

### Task 1: Update Navigation — Remove Providers, Add Quick Setup Button

**Files:**
- Modify: `src/web/templates/base.html:762-769` (navbar links)
- Modify: `src/web/routes.py` (add `/setup` route, redirect `/providers`)

**Step 1: Remove Providers link from navbar and add `+` button**

In `src/web/templates/base.html`, replace the navbar-links div (lines 762-769):

```html
<div class="navbar-links" id="navLinks">
    <a href="/proxies" id="nav-proxies">Proxies</a>
    <a href="/pools" id="nav-pools">Pools</a>
    <a href="/projects" id="nav-projects">Projects</a>
    <a href="/blacklist" id="nav-blacklist">Blacklist</a>
    <a href="/stats" id="nav-stats">Stats</a>
</div>
```

Add a `+` button right after the navbar-links div (before the settings cog):

```html
<a href="/setup" class="nav-setup-btn" title="Quick Setup">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
</a>
```

Add CSS for the `+` button (in the `<style>` block after `.nav-settings-cog` styles):

```css
.nav-setup-btn {
    margin-left: 8px;
    color: #fff;
    background: var(--accent);
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all var(--transition-fast);
    flex-shrink: 0;
}
.nav-setup-btn:hover {
    background: var(--accent-hover);
    color: #fff;
    box-shadow: 0 0 16px var(--accent-glow);
}
```

**Step 2: Add `/setup` route and redirect `/providers`**

In `src/web/routes.py`, add:

```python
@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", _ctx(request))
```

Change the existing `/providers` route to a redirect:

```python
@router.get("/providers", response_class=RedirectResponse)
async def providers_redirect():
    return RedirectResponse(url="/settings")
```

**Step 3: Verify**

Run: `docker compose up -d --build`
- Navigate to any page — Providers should be gone from nav, `+` button visible
- Clicking `+` goes to `/setup` (will 500 until setup.html exists — that's expected)
- `/providers` redirects to `/settings`

**Step 4: Commit**

```bash
git add src/web/templates/base.html src/web/routes.py
git commit -m "feat: update nav — remove Providers, add Quick Setup button"
```

---

### Task 2: Create Quick Setup Wizard Page

**Files:**
- Create: `src/web/templates/setup.html`

**Step 1: Create the wizard template**

Create `src/web/templates/setup.html` with a 3-step wizard. The wizard is a single page with step indicators and JS that shows/hides step content.

The page structure:

```
{% extends "base.html" %}
{% block title %}Quick Setup - ProxyManager{% endblock %}

{% block content %}
<!-- Step indicator bar: 1. Import  2. Pool  3. Project -->
<!-- Step 1: Import Proxies -->
<!--   - Textarea for paste + file upload -->
<!--   - Provider combobox (type to search/create) -->
<!--   - "Next" button that parses proxy count and advances -->
<!-- Step 2: Create Pool -->
<!--   - Pool name input (auto-suggested from provider) -->
<!--   - Rotation strategy dropdown -->
<!--   - Preview: "X proxies will be added" -->
<!--   - "Back" / "Next" buttons -->
<!-- Step 3: Connect to Project -->
<!--   - Radio toggle: "New project" / "Existing project" -->
<!--   - New: name input -->
<!--   - Existing: dropdown of projects -->
<!--   - "Back" / "Finish" buttons -->
<!-- Success state: shows API key, copy button, usage example, "Done" link -->
{% endblock %}

{% block scripts %}
<script>
// State management: currentStep, parsedProxies, selectedProvider, etc.
// Step navigation: showStep(n)
// Provider combobox: loadProviders(), filterProviders(), createProvider()
// Proxy parsing: parseProxyCount() — count lines to show preview
// Finish flow: chains API calls in sequence, handles errors, shows success
</script>
{% endblock %}
```

Key JS functions needed:

1. **`showStep(n)`** — hide all steps, show step `n`, update step indicator
2. **`loadProviders()`** — fetch existing providers for combobox autocomplete
3. **`parseProxyText()`** — count non-empty lines to show preview count
4. **`advanceToStep2()`** — validate step 1 (proxies present, provider set), show step 2
5. **`advanceToStep3()`** — validate step 2 (pool name set), show step 3
6. **`loadProjects()`** — fetch existing projects for the dropdown
7. **`finishSetup()`** — chains all API calls:
   - If provider is new: `POST /api/v1/providers` → get `provider_id`
   - `POST /api/v1/ips/bulk` with `provider_id` and proxy text
   - `POST /api/v1/pools` → get `pool_id`
   - Get all proxy IDs: `GET /api/v1/ips?provider_id=X&per_page=100` to get just-imported proxy IDs
   - `POST /api/v1/pools/{pool_id}/ips` with proxy IDs
   - If new project: `POST /api/v1/projects` → get `project_id` + `api_key`
   - `POST /api/v1/projects/{project_id}/pools` with `[pool_id]`
   - Show success state

**Step 2: Implement the full template**

Write the complete `setup.html` with all HTML, CSS (scoped in `{% block content %}`), and JS.

CSS should include:
- `.setup-container` — max-width 640px, centered
- `.step-indicator` — horizontal bar with circles for steps 1/2/3
- `.step-content` — each step section, hidden by default
- `.step-content.active` — displayed step
- `.provider-combobox` — input with dropdown suggestions
- `.success-state` — final success view with API key display

**Step 3: Verify**

Run: `docker compose up -d --build`
- Navigate to `/setup` via the `+` button
- Step 1 should render with textarea, file upload, provider combobox
- Step 2 should show pool name + strategy
- Step 3 should show project creation
- Full flow should chain APIs and show success with API key

**Step 4: Commit**

```bash
git add src/web/templates/setup.html
git commit -m "feat: add Quick Setup wizard page"
```

---

### Task 3: Improve Import Modal on Proxies Page

**Files:**
- Modify: `src/web/templates/proxies.html:45-70` (import modal)

**Step 1: Replace provider `<select>` with combobox**

Replace the provider form group in the import modal with a combobox that supports both selecting existing providers and typing a new name:

```html
<div class="form-group">
    <label for="importProvider">Provider</label>
    <div style="position:relative">
        <input type="text" id="importProviderInput" placeholder="Type to search or create new..."
               autocomplete="off" oninput="filterProviderSuggestions()" onfocus="showProviderDropdown()">
        <input type="hidden" id="importProviderId" value="">
        <div id="providerSuggestions" class="combobox-dropdown" style="display:none"></div>
    </div>
</div>
```

Add CSS for the combobox dropdown (in the `{% block content %}` style tag):

```css
.combobox-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    margin-top: 4px;
    max-height: 180px;
    overflow-y: auto;
    z-index: 10;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.combobox-dropdown .combobox-item {
    padding: 8px 12px;
    font-size: 13px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: background var(--transition-fast);
}
.combobox-dropdown .combobox-item:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}
.combobox-dropdown .combobox-create {
    color: var(--accent);
    font-weight: 600;
    border-top: 1px solid var(--border);
}
```

**Step 2: Add optional "Create pool from import" section**

After the file upload form group, add:

```html
<div class="form-group">
    <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-size:13px;color:var(--text-secondary);cursor:pointer">
        <input type="checkbox" id="importCreatePool" style="width:16px;height:16px;accent-color:var(--accent)"
               onchange="document.getElementById('poolFields').style.display = this.checked ? 'block' : 'none'">
        Also create a pool from this import
    </label>
</div>
<div id="poolFields" style="display:none">
    <div class="form-group">
        <label for="importPoolName">Pool Name</label>
        <input type="text" id="importPoolName" placeholder="e.g. papaproxy-us-01">
    </div>
    <div class="form-group">
        <label for="importPoolStrategy">Rotation Strategy</label>
        <select id="importPoolStrategy">
            <option value="round_robin" selected>Round Robin</option>
            <option value="random">Random</option>
        </select>
    </div>
</div>
```

**Step 3: Update JS functions**

Update `loadProviders()` to populate the combobox data instead of a `<select>`.

Add `filterProviderSuggestions()`, `showProviderDropdown()`, `selectProvider()`, `hideProviderDropdown()`.

Update `doImport()` to:
1. If provider is new name (no ID), call `POST /api/v1/providers` first
2. Import proxies with the provider ID
3. If "create pool" checkbox is checked:
   - `POST /api/v1/pools` to create pool
   - `GET /api/v1/ips?provider_id=X` to get proxy IDs
   - `POST /api/v1/pools/{pool_id}/ips` to assign proxies

**Step 4: Verify**

Run: `docker compose up -d --build`
- Go to Proxies page → click "Import Proxies"
- Provider field should be a combobox (type to filter, shows "Create 'xxx'" option)
- "Also create a pool" checkbox should reveal pool name + strategy fields
- Full import with pool creation should work end-to-end

**Step 5: Commit**

```bash
git add src/web/templates/proxies.html
git commit -m "feat: improve import modal — provider combobox + optional pool creation"
```

---

### Task 4: Add Manage Providers Section to Settings

**Files:**
- Modify: `src/web/templates/settings.html`

**Step 1: Add Providers management card**

After the "Data Retention" settings card and before the "Alert Rules" card, add:

```html
<!-- Manage Providers -->
<div class="settings-card alert-card-full">
    <h3>
        <span>Providers</span>
        <button class="btn btn-primary btn-sm" onclick="openCreateProviderModal()">Add Provider</button>
    </h3>
    <div id="providersList"></div>
    <div class="empty-state" id="providersEmpty" style="display:none;padding:30px 16px">
        <div class="empty-state-icon" style="font-size:28px">&#127968;</div>
        <h3>No Providers</h3>
        <p>Providers are auto-created when you import proxies.</p>
    </div>
</div>
```

**Step 2: Add provider management JS**

In the `{% block scripts %}`, add functions to load, create, rename, and delete providers.

Providers are shown as simple rows with name, proxy count, and rename/delete actions — reusing the `.alert-row` styling.

**Step 3: Verify**

Run: `docker compose up -d --build`
- Go to Settings page
- Providers section should appear with existing providers listed
- Can rename and delete providers
- `/providers` URL should redirect to Settings

**Step 4: Commit**

```bash
git add src/web/templates/settings.html
git commit -m "feat: add Manage Providers section to Settings page"
```

---

### Task 5: Add Quick Setup CTA to Stats Page

**Files:**
- Modify: `src/web/templates/stats.html`

**Step 1: Add a CTA button in the page header**

In the `page-header-actions` div on the stats page, add a Quick Setup button:

```html
<a href="/setup" class="btn btn-primary">Quick Setup</a>
```

This goes alongside the existing granularity toggle buttons.

**Step 2: Verify**

Run: `docker compose up -d --build`
- Stats page should show "Quick Setup" button in the header
- Clicking it navigates to `/setup`

**Step 3: Commit**

```bash
git add src/web/templates/stats.html
git commit -m "feat: add Quick Setup CTA to Stats page"
```

---

### Task 6: End-to-End Verification

**Step 1: Test the full happy path**

1. Start from Stats page, click "Quick Setup" (or `+` in navbar)
2. Paste proxies, type "PapaProxy" as provider (new)
3. Name pool "papaproxy-01", keep round_robin
4. Create new project "my-scraper"
5. See API key + usage example
6. Click "Done" → back to Stats

Verify:
- Provider "PapaProxy" exists (check Settings)
- Proxies imported (check Proxies page)
- Pool "papaproxy-01" has the proxies (check Pools page)
- Project "my-scraper" has the pool assigned (check Projects page)

**Step 2: Test the improved import modal**

1. Go to Proxies → Import Proxies
2. Type "PapaProxy" in combobox — existing provider should appear
3. Check "Also create a pool"
4. Import — pool should be created with proxies assigned

**Step 3: Test edge cases**

- Wizard with existing project (dropdown)
- Empty proxy paste (should show error)
- Duplicate provider name (should reuse existing)
- `/providers` URL redirects to Settings

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete UX simplification — wizard, nav, import improvements"
```
