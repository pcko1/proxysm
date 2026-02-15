# UX Simplification Design

**Date:** 2026-02-15
**Problem:** Getting from "I have a proxy txt file" to "using proxies in a project" requires ~25 interactions across 4 pages. Too many clicks.

## User Research

- Provider is just a label (metadata), not a first-class entity
- Proxies are 1:1 with pools (one import = one pool)
- Multiple pools can be assigned to a project
- User wants a wizard for the common flow + simplified existing pages

## Changes

### 1. Quick Setup Wizard

A 3-step wizard accessible from the Stats page, empty states, and a `+` button in the navbar.

**Step 1 — Import Proxies**
- Textarea for paste + file upload
- Provider: combobox (type-to-search existing or create new inline)
- Auto-detects protocol from proxy format

**Step 2 — Create Pool**
- Pool name (auto-suggested from provider name, e.g. "papaproxy-01")
- Rotation strategy dropdown (round_robin default)
- Preview: "142 proxies will be added to this pool"

**Step 3 — Connect to Project**
- Toggle: "Create new project" or "Add to existing project"
- New: name input, creates project, shows API key + copy button
- Existing: dropdown of projects, pool auto-assigned
- Shows usage example with actual slug
- "Done" button closes wizard

**Result:** ~6 interactions instead of ~25.

### 2. Provider Demotion

- Remove Providers page from navbar
- Provider becomes a combobox field on import flows (wizard + standalone modal)
- Provider DB model stays — auto-created when new name is typed
- Provider label shown on Proxies page as a column
- "Manage Providers" moves to a section inside Settings (rename/delete)

### 3. Navigation Simplification

**Before:** Stats | Providers | Proxies | Pools | Projects | Blacklist | Settings (7 items)
**After:** Stats | Proxies | Pools | Projects | Blacklist | Settings (6 items + `+` button)

- Providers removed from nav
- `+` button in navbar (accent-colored) triggers Quick Setup wizard

### 4. Improved Standalone Import Modal

The existing import modal on the Proxies page:
- Provider field: combobox instead of select (type-to-search or create new)
- Optional "Create pool from import" checkbox with inline pool name + strategy fields
- Reduces clicks even outside the wizard

### 5. Data Model

No schema changes. The wizard chains existing API calls:
1. `POST /api/v1/providers` (if new provider name)
2. `POST /api/v1/ips/bulk` (import proxies)
3. `POST /api/v1/pools` (create pool)
4. `POST /api/v1/pools/:id/ips` (assign proxies to pool)
5. `POST /api/v1/projects` (create project, if new)
6. `POST /api/v1/projects/:id/pools` (assign pool to project)

### 6. New Files

- `src/web/templates/setup.html` — Quick Setup wizard page (or large modal in base.html)

### 7. Modified Files

- `src/web/templates/base.html` — Add `+` button to navbar, remove Providers link
- `src/web/templates/proxies.html` — Provider combobox + optional pool creation in import modal
- `src/web/templates/stats.html` — Add "Quick Setup" CTA button
- `src/web/templates/settings.html` — Add "Manage Providers" section
- `src/web/routes.py` — Add `/setup` route (if separate page), remove/redirect `/providers`
