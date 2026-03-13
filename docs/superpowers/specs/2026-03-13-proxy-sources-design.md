# Proxy Sources Design

## Overview

Every proxy in the system belongs to a **source** — the mechanism through which it was imported. Sources come in three types:

- **URL** — a remote feed that is polled hourly to sync the proxy list
- **File** — a one-time import from a file upload (static, not polled)
- **Manual** — a one-time import from pasted text (static, not polled)

Only URL sources are polled. File and manual sources are static records of how proxies entered the system.

## Data Model

### New table: `proxy_sources`

| Column                 | Type           | Notes                                                        |
|------------------------|----------------|--------------------------------------------------------------|
| `id`                   | UUID           | PK (UUIDMixin)                                               |
| `name`                 | VARCHAR(255)   | Display name, unique. See naming conventions below            |
| `type`                 | VARCHAR(10)    | `url`, `file`, `manual` — check constraint                   |
| `url`                  | TEXT           | Nullable — only set for `url` type                           |
| `provider`             | VARCHAR(255)   | Required — propagated to `Proxy.provider`                    |
| `is_active`            | BOOLEAN        | Default true — controls whether URL sources get polled       |
| `last_polled_at`       | DATETIME(tz)   | Nullable — last poll attempt timestamp                       |
| `last_status_code`     | INTEGER        | Nullable — HTTP status from last poll                        |
| `consecutive_failures` | INTEGER        | Default 0 — reset on successful poll                         |
| `created_at`           | DATETIME(tz)   | TimestampMixin                                               |
| `updated_at`           | DATETIME(tz)   | TimestampMixin                                               |

### Modified table: `proxies`

| Column      | Change                                                             |
|-------------|--------------------------------------------------------------------|
| `source_id` | New **non-nullable** UUID FK → `proxy_sources.id`, `ON DELETE CASCADE` |

`ON DELETE CASCADE` ensures deleting a source hard-deletes all its proxies.

### Source naming conventions

- **URL sources**: user-defined name
- **File sources**: `{filename}-{YYYY-MM-DD-HH:mm}` (e.g. `proxies.txt-2026-03-13-14:30`)
- **Manual sources**: `manual-{YYYY-MM-DD-HH:mm}`

Each import creates a distinct source so individual batches can be traced and deleted.

## Source Poller Service

**New file:** `src/services/source_poller.py`

Follows the existing service pattern (metrics, bandwidth, partitions) — a `start_source_poller(scheduler)` function that registers a job on the shared APScheduler.

### Configuration

New setting in `src/config.py`:

- `source_poll_interval: int = 3600` — global polling interval in seconds (default 1 hour)

### Job registration

- Registered in `start_health_checker()` alongside other background services
- `max_instances=1` to prevent overlapping polls

### Poll logic (`poll_all_sources`)

1. Query all `ProxySource` where `type = 'url'` and `is_active = True`
2. For each source, fetch the URL via `httpx.AsyncClient(timeout=30)`
3. **On HTTP error / timeout:**
   - Increment `consecutive_failures`
   - Update `last_polled_at`, `last_status_code`
   - Skip sync, move to next source
4. **On 200 OK:**
   - Reset `consecutive_failures` to 0
   - Update `last_polled_at`, `last_status_code`
   - Parse response with `parse_proxy_list()`
   - Run sync logic

Sources are polled sequentially (low source count expected).

## Sync Logic

When a URL source returns 200, we compare the parsed list against existing proxies for that source.

### Step 1 — Build lookup sets

- `feed_set`: set of `(host, port, protocol)` tuples from the parsed response
- `db_proxies`: all proxies where `source_id = this source`

### Step 2 — Add new proxies

For each entry in `feed_set` not in DB: create a new `Proxy` with `source_id` and `provider` from the source.

### Step 3 — Handle disappeared proxies

For each DB proxy whose `(host, port, protocol)` is NOT in `feed_set`:
- If `last_health_status` is `dead` or `degraded` → set `is_active = False`
- If `last_health_status` is `healthy` or `unknown` → leave it alone

### Step 4 — Re-activate returning proxies

For each entry in `feed_set` that IS in DB but has `is_active = False`:
- Set `is_active = True`
- Reset `last_health_status` to `unknown` (health checker re-evaluates fresh)

### Step 5 — Update credentials

If a proxy exists in both feed and DB but username/password changed, update them.

## API

### New router: `src/api/sources.py`

Prefix: `/sources`, tags: `["sources"]`. All endpoints require `admin_auth`.

| Endpoint               | Method | Description                                          |
|------------------------|--------|------------------------------------------------------|
| `/sources`             | GET    | List all sources (paginated)                         |
| `/sources`             | POST   | Create a new source (type, name, url, provider)      |
| `/sources/{id}`        | GET    | Get single source                                    |
| `/sources/{id}`        | PATCH  | Update source (name, url, provider, is_active)       |
| `/sources/{id}`        | DELETE | Delete source + cascade-deletes all its proxies      |
| `/sources/{id}/poll`   | POST   | Trigger an immediate poll for a URL source           |

### Modifications to existing bulk import (`POST /ips/bulk`)

- When `url` is provided: create a `ProxySource(type="url")`, assign `source_id` to imported proxies
- When `proxies` (raw text) is provided: create a `ProxySource(type="manual", name="manual-TIMESTAMP")`
- When `proxy_list` (structured JSON) is provided: also `type="manual", name="manual-TIMESTAMP"`
- File upload: `ProxySource(type="file", name="filename-TIMESTAMP")`

## UI — Sources Panel on Proxies Page

Located at the top of `src/web/templates/proxies.html`, above the existing proxy table.

### Collapsible panel

**Collapsed state:** `"Sources (4)"` — summary count with expand button.

**Expanded state:**
- Table with columns: Name, Type, Provider, URL (truncated), Last Polled, Status, Actions
- Status indicators:
  - Green dot: last poll succeeded
  - Red dot: `consecutive_failures > 0`
  - Grey dot: static source (file/manual — never polled)
- Actions per row:
  - Edit (pencil icon)
  - Delete (trash icon → confirmation modal)
  - Poll Now (refresh icon, URL type only)
- "Add Source" button → form modal (fields: name, type, URL, provider)

### Delete confirmation modal

> "This will permanently delete this source and all X proxies imported from it. Are you sure?"

## Migration

Alembic migration:

1. Create `proxy_sources` table
2. Add `source_id` as a non-nullable UUID FK on `proxies` with `ON DELETE CASCADE`

Fresh project — no backwards compatibility concerns. All proxies will always have a source.
