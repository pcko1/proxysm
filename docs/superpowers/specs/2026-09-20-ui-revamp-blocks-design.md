# Proxysm UI Revamp ("Blocks") — Design Spec

**Date:** 2026-09-20
**Status:** Draft for review
**Mockups:** `docs/design/ui-revamp-blocks/` (sources of the Claude Design canvas, page "Blocks (chosen)", https://claude.ai/artifact/Nq6UX9GRaPk5zPnfs9YADq). The mockups are the visual source of truth; where this spec and a mockup disagree on behaviour or data, this spec wins.
**Supersedes:** `2026-03-14-dashboard-proxies-tab-improvements-design.md` (never implemented). Its useful parts are absorbed here: 1h deltas, dead-proxy visibility (status filter), health transitions (proxy timeline).

## Goal

A minimal but powerful operator UI for three jobs, in this order: glance at fleet health, debug failing requests, manage inventory. Fewer screens and charts than today, but every engine capability that matters is reachable and editable from the UI.

## Decisions already made

- Look: "Blocks" — near-black ground, solid colour tiles, oversized numerals, pill controls — with the left icon sidebar from direction A.
- Same functions as the v1 mockups: one Overview page, "Needs attention", proxy detail panel, new Requests log, list + detail for Projects and Pools, Cmd+K palette.
- Dark only. No light theme.

## Non-goals

- No SPA, framework or build step. Server-rendered Jinja + vanilla JS stays.
- No geo/ASN lookup. `country_code`, `city`, `asn` are never populated today; the detail panel shows a Location row only when a value exists.
- No UI for `is_exclusive`, `sticky_session_ttl` or per-pool `health_check_interval`: the engine ignores them, so they would be dead knobs.
- No change to proxy protocols, rotation strategies or the health model.

## Visual system

| Token | Value | Use |
|---|---|---|
| `--ground` | `#0E0E10` | page, sidebar, inputs inside tiles |
| `--tile` | `#1C1C21` | neutral tiles, idle pills |
| `--tile-2` | `#2A2A31` | row dividers, chips, quiet badges, bar tracks |
| `--text` / `--text-2` / `--text-3` | `#FAFAF7` / `#E4E4E0` / `#B5B5BD` | primary / table body / labels (all >= 4.5:1 on `--tile`) |
| `--lime` / on-lime | `#D4F26A` / `#12160A` | healthy, primary action, selected palette row |
| `--amber` / on-amber | `#FFC95C` / `#1A1204` | degraded, 4xx, warning |
| `--coral` / on-coral | `#FF8A7A` / `#1F0A07` | dead, 5xx, no response, destructive |
| `--lavender` / on-lavender | `#C9B8FF` / `#17122B` | "Needs attention" tile only |
| `--paper` | `#FAFAF7` | active nav item, active filter pill, selected list tile (text `#0E0E10`) |

- Radii: tiles 28px, inner blocks 20px, selected table row 14px, every control 999px.
- Type: **Bricolage Grotesque** 700 for page titles (44px), tile numerals (60px), section titles (22px); **Figtree** 500/600/700 at 14px for everything else; **JetBrains Mono** 500/600 for host:port, keys and code. `font-variant-numeric: tabular-nums` globally.
- Colour carries status only. A coloured fill always has dark text on it; status text on dark tiles uses the same hue.
- Focus: 2px `--lime` outline, 2px offset, on every interactive element. `prefers-reduced-motion` disables transitions.

## Frontend architecture

- `src/web/static/css/app.css`: tokens + components (`.side-nav`, `.tile`, `.pill`, `.btn`, `.badge`, `.tbl`, `.seg`, `.field`, `.panel-detail`, `.toast`, `.modal`, `.palette`). Replaces the ~1,000 lines of CSS inlined in `base.html` and the legacy `.dash-card/.metrics-table` system. One style system.
- `src/web/static/js/app.js`: `apiCall`, toasts, modal/confirm, clipboard, selection, poller, relative time, palette. `src/web/static/js/pages/<page>.js`: one file per screen. Templates keep markup only; the two ports reach JS through `data-` attributes on `<body>`.
- Static URLs carry `?v=<app version>` for cache busting.
- **Zero external requests**: fonts self-hosted as woff2 in `static/fonts/` (all three are OFL); Geist files removed; highlight.js CDN removed (three short snippets do not need it).
- One poller in `app.js`: 10s on Overview, 3s on Requests while streaming, paused when the tab is hidden. The sidebar status reads "Updated Ns ago" from the last successful poll and switches to coral "Offline, retrying" on failure. This replaces the decorative Live pill and the sticky API banner. 401 still redirects to `/login`.
- Responsive: sidebar becomes a 72px icon rail below 1100px and a top bar with a menu button below 720px; tables scroll horizontally inside their tile; the detail panel becomes a full-width sheet below 1100px.
- Accessibility: real `<button>`/`<a>`/`<label>`; detail panel is an `<aside>` that closes on Esc and returns focus to the row; palette and modals trap focus; icon-only buttons have `aria-label`.

## Routes

| Route | Change |
|---|---|
| `/dashboard` | Rebuilt as **Overview** (nav label "Overview", URL unchanged) |
| `/proxies` | Rebuilt: filter pills, table, detail panel; Sources and Import in modals |
| `/pools` | Rebuilt as list + detail |
| `/projects` | Rebuilt as list + detail |
| `/requests` | **New** |
| `/settings` | Restyled; gains links to `/docs` and `/redoc` |
| `/login`, 404 | Restyled |
| `/api-docs` | Removed; 302 to `/docs` |
| `/setup` | Removed; 302 to `/dashboard`. The onboarding card stays and deep-links to `/proxies?import=1`, `/pools?new=1`, `/projects?new=1`, which open the matching modal |

Also removed: footer, nav Setup button, Live pill, dashboard tabs and the per-project chart drill-down (see Projects).

## Screens

### Sidebar (every page)
Logo, Search pill (opens palette, shows the platform shortcut), Overview / Proxies / Pools / Projects / Requests with icons, then status line, Settings, Sign out pinned to the bottom.

### Overview
- **Tiles:** Healthy (lime), Degraded (amber), Dead (coral), Requests/min (neutral, footer shows error rate and p50). Counts, 24h error rate and p50 come from the existing `/stats/overview`; requests/min from the existing global `/stats/throughput`. Each tile has a "vs 1h ago" chip (milestone 3); the chip is omitted while no history exists.
- **Traffic:** stacked bars (requests in paper, errors in coral, current bucket lime). Range switch 1h / 24h / 7d maps to `timeseries` granularity `5min` x12, `1hour` x24, `1day` x7 and is remembered in `localStorage`.
- **Needs attention** (lavender): at most 6 items from `GET /stats/attention`, each with one action that deep-links to the fix. Empty state: "Nothing needs attention."
- **Providers**, **Pools**, **Projects** tables. A pool whose healthy count is below its minimum gets a coral badge. The quota column appears in milestone 4.
- Onboarding card appears above the tiles while any of proxies / pools / projects is empty.

### Proxies
- Filter pills All / Healthy / Degraded / Dead / Unknown with live counts, plus search. Both are server-side (`/ips?status=&search=`), reflected in the URL.
- Table: select, host:port, protocol, provider, status badge, latency, success 24h, last check. Sortable as today. Bulk bar keeps recheck / move to pool / delete.
- Row click opens the **detail panel** (URL `?proxy=<id>`). Header tile takes the status colour and holds Recheck now, Disable/Enable, Delete. Body: 24h health timeline (48 half-hour blocks, worst status per block), hourly latency bars, protocol, provider, location (only if known), pools with an editable weight per pool (1-100; meaningful for `weighted_random` pools, labelled as such), last 5 failures with a link to Requests filtered by this proxy.
- "Sources" opens a modal with today's source table (add, poll now, delete). "Import" opens today's import modal.

### Requests (new)
- Live tail of `request_log`, newest first, 100 rows, "Load older" at the bottom. Streaming/Paused pill; Pause stops polling.
- Filters: text (domain substring), project, outcome pills All / Errors only / 4xx / 5xx / No response. Deep-linkable with `?proxy_id=`, `?project_id=`, `?domain=`.
- 2xx/3xx badges are quiet; 4xx amber; 5xx and no-response coral. Proxy cell links to that proxy's detail panel.

### Projects
- Left: project tiles (name, req/min, error rate; selected tile is paper). Right, for the selected project (`?project=<id>`):
  - **Connect:** HTTP / SOCKS5 switch, curl / Python / Node snippet using the viewing host, Copy, masked API key with Reveal and Rotate (rotate confirms first). Replaces the 8-language x 2 snippet matrix.
  - **Limits** (milestone 4): rate limit (req/min) and bandwidth quota (GB/month); 0 or empty means unlimited; Save enables only when dirty.
  - **Pools, tried in order:** numbered list, move up/down, remove, add. Order maps to `ProjectPool.priority`, which the proxy servers already honour.
  - **Last 24h** (milestone 3): status-code bar, top failing domains, errors by type, from the existing `status-codes`, `top-domains`, `error-breakdown` endpoints. The rest of the old drill-down (rotation distribution, pool latency histogram, per-project bandwidth chart) is dropped.
  - Rename inline; Delete confirms.

### Pools
Same list + detail pattern. Detail: rename, rotation strategy (round_robin / random / weighted_random), minimum healthy proxies, member table (host, status, latency, weight when weighted) with add/remove, and the projects using the pool.

### Command palette (Cmd/Ctrl+K, or `/`)
Groups: Proxies (server search by address, top 5), Actions (Import proxies, New pool, New project, Recheck all dead proxies, Pause/Resume requests), Go to (pages; also `g` then `o/p/l/j/r`). Arrow keys, Enter, Esc. Shortcuts are ignored while typing in a field.

## Backend changes

| # | Change | Milestone |
|---|---|---|
| B1 | `PoolUpdate`/`PoolResponse` gain `min_healthy_proxies` (>= 0) | 2 |
| B2 | `PATCH /pools/{pool_id}/ips/{proxy_id}` `{weight: 1..100}`; re-syncs the weighted ZSET via `sync_weighted_pool` | 2 |
| B3 | `PUT /projects/{id}/pools` `{pool_ids: [ordered]}` replaces assignments and sets `priority` by position (first = highest) | 2 |
| B4 | `GET /ips/{id}/detail`: proxy + `pools[{id,name,strategy,weight}]` + `health_24h[48]` + `uptime_pct` + `latency_24h[24]` (both from `health_check_log`) + `recent_failures[5]` (from `request_log`) | 3 |
| B5 | `GET /stats/requests`: params `project_id, pool_id, proxy_id, domain, outcome(all/errors/4xx/5xx/failed), limit<=200, before_id, after_id, hours<=168 (default 24)`; joins names; always bounded by `created_at` so partitions prune | 3 |
| B6 | `GET /stats/attention`: `pool_below_min` (healthy < `min_healthy_proxies`, pools with >= 1 proxy), `domain_error_spike` (last 60 min, >= 50 requests, error rate >= 25%), `dead_proxies` (count > 0), `quota_near` (>= 80%, milestone 4). Sorted by severity, max 6 | 3 |
| B7 | `GET /stats/overview` gains nullable `*_1h_ago` values: the four status counts (from `health_check_log`, 55-65 min window) and request rate, error rate and p50 (from `request_log`). Null on cold start | 3 |
| B8 | `GET /ips` rows gain `success_rate_24h` computed only for the returned page | 3 |
| B9 | `POST /ips/recheck` `{status: "dead"}` queues an immediate check of matching proxies in the health checker (bounded concurrency); returns the queued count | 5 |
| B10 | **Limit enforcement** (not enforced anywhere today, although the columns exist): `ProjectUpdate`/`ProjectResponse` gain `rate_limit_rpm`, `bandwidth_quota_bytes`; response adds `bandwidth_used_bytes_month`. Rate limit: Redis fixed-window counter per project per minute, checked after auth in both proxy servers. Quota: month-to-date byte counter per project in Redis, incremented where bytes are recorded today, rebuilt from stored metrics if missing. Over limit: HTTP `429` with `Retry-After` / SOCKS5 reply `0x02`. `0` = unlimited, which is every existing project's value, so behaviour is unchanged until someone sets a limit. Limit values ride in the auth cache, so edits apply within its TTL | 4 |

All new endpoints sit behind the existing admin auth and get Pydantic response models.

## States

Every table and panel defines loading (skeleton rows in `--tile-2`), empty (one sentence + the action that fixes it) and error (inline message with Retry; never a blank tile). Destructive actions confirm. Saves are optimistic only for weight and pool order; both roll back with a toast on failure.

## Testing

- pytest per new or changed endpoint: filters, pagination cursors, bounds validation, attention rules against fixtures, overview nulls on cold start.
- Limit enforcement: under/over limit on both protocols, window rollover, `0` = unlimited, quota rebuild.
- `tests/test_web_routes.py`: updated nav order, `/requests` returns HTML, `/api-docs` and `/setup` redirect, deep-link params render their modal hooks, rendered HTML contains no external `http(s)://` asset URLs, static css/js/fonts are served.
- No JS test toolchain is introduced; each milestone ends with a written browser smoke checklist run against the node2 instance.

## Milestones (one implementation plan each, shipped in order)

1. **Shell + restyle.** Static CSS/JS extraction, fonts, sidebar, all existing pages rebuilt in Blocks on existing endpoints, removals and redirects, poller and status line, sources/import modals, new Connect block. No backend change. Overview ships without deltas and "Needs attention"; project detail without Limits and Last 24h.
2. **Inventory editing.** B1-B3; Pools and Projects list + detail with rename, strategy, minimum healthy, weights, pool order.
3. **Debugging.** B4-B8; Requests page, full proxy detail panel, "Needs attention", 1h deltas, success column, project Last 24h.
4. **Limits.** B10; Limits block, quota bars on Overview and Projects, `quota_near` attention item.
5. **Palette.** Palette, keyboard shortcuts, B9.

## Risks

- B10 touches the proxy hot path. It is isolated in its own milestone, defaults to off, and adds one Redis call per connection.
- `request_log` volume: B5/B4/B8 must stay partition-pruned and index-backed; the plan verifies existing indexes and adds one if a filter needs it.
- Per-page JS moves out of templates in milestone 1; this is the largest diff and is pure refactor plus restyle, so it lands before any behaviour change.
