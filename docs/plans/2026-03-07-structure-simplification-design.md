# Structure Simplification Design

**Date:** 2026-03-07
**Status:** Approved

---

## Problem

The current entity hierarchy (Provider -> Proxy -> Pool -> Project) and 7-item navigation create unnecessary cognitive overhead. Users struggle to understand when to use Pools vs Projects, and Providers feel like a mandatory detour that adds no value.

## Design

### 1. Demote Provider from Entity to Text Label

**Before:** `providers` table with full CRUD, own nav page, FK from proxies.
**After:** `provider` string column on `proxies` table. Just a label entered during import.

- Drop the `providers` table and all related API endpoints
- Drop `provider_id` FK from `proxies`, replace with `provider VARCHAR(255)` (nullable)
- Remove Providers page from web UI
- Import flow gets a text input for provider label (optional)
- Proxies table shows provider as a filterable text column

### 2. Consolidate Navigation (7 -> 4 items)

**Before:** `Proxies | Pools | Projects | Blacklist | Stats | Settings | Setup`
**After:** `Dashboard | Proxies | Pools | Projects` + Settings cog

| Removed item | Disposition |
|-------------|-------------|
| Providers | Removed entirely (provider = text label) |
| Blacklist | Moved into Project detail view |
| Stats | Renamed to Dashboard, becomes landing page |
| Setup (+) | First-run onboarding only, not permanent nav |

### 3. Streamlined Setup Flow

Single-page wizard shown on first run (or via "Quick Start" button on Dashboard):

1. Paste/upload proxies (with optional provider label)
2. Create a pool -> auto-assign imported proxies
3. Create a project -> auto-assign the pool
4. Show API key + usage examples

All in one page, linear flow. After completion, user lands on Dashboard.

### 4. Project as Primary View

Project detail page becomes the "home" for day-to-day usage:

- Assigned pools with proxy health summary (healthy/total counts)
- Usage examples (forward proxy, rotation API, SOCKS5)
- Blacklisted proxies (moved from separate page)
- API key management (rotate key)

### 5. Data Model Changes

```sql
-- Remove providers table entirely
DROP TABLE providers CASCADE;

-- Replace provider FK with text label
ALTER TABLE proxies DROP COLUMN provider_id;
ALTER TABLE proxies ADD COLUMN provider VARCHAR(255);
```

### 6. API Changes

**Removed endpoints:**
- `GET/POST/PATCH/DELETE /api/v1/providers`
- `GET /api/v1/providers/{id}`

**Modified endpoints:**
- `POST /api/v1/ips/bulk` — `provider_id` param replaced with `provider` (string, optional)
- `GET /api/v1/ips` — filter by `provider` string instead of `provider_id`

**Moved endpoints:**
- Blacklist endpoints remain at same paths, just UI access moves to project detail

### 7. Web UI Changes

- Remove `providers.html` template
- Remove Providers link from `base.html` navbar
- Rename Stats -> Dashboard in navbar
- Remove Blacklist from navbar
- Remove Setup (+) button from navbar (keep wizard accessible from Dashboard empty state)
- Update `proxies.html` — show provider as text column, update import modal
- Create project detail view with embedded blacklist section
- Update `base.html` navbar to: Dashboard | Proxies | Pools | Projects

## Migration Path

1. Alembic migration: add `provider VARCHAR(255)` to proxies, copy provider names from joined providers table, drop `provider_id` FK, drop `providers` table
2. Update models, schemas, API routes
3. Update web templates
4. Update import parser to accept `provider` string instead of `provider_id`
