# UI revamp v1 (minimal)

Source files of the Claude Design canvas at
https://claude.ai/artifact/Nq6UX9GRaPk5zPnfs9YADq (private to the owner).
Each `.dc.html` is one artboard; `canvas.json` is the layout index. Sample data only.

| Board | Change |
|---|---|
| `Main` | One Overview page replaces the two dashboard tabs: KPI strip with 1h deltas, health bar, one traffic chart (1h/24h/7d), "Needs attention" list, provider / pool / project tables |
| `Proxies` | Status filter chips, row click opens a detail drawer (24h health timeline, latency, pools, weight, recent failures, recheck / disable / delete); sources behind a button |
| `Requests` | New live tail of `request_log` with project / status / error filters |
| `Projects` | List + detail: connect snippets (curl, Python, Node; HTTP or SOCKS5), editable rate limit, bandwidth quota and pool order |
| `Palette` | Cmd+K: jump to a page, find a proxy by address, run an action |
| `Nav` | Shared top bar; "Updated Ns ago" replaces the static Live pill |

Removed: Live pill, hand-written API Docs page, footer, nav Setup button, most dashboard charts.

Backend needed: expose `rate_limit_rpm`, `bandwidth_quota_bytes`, `min_healthy_proxies`,
`sticky_session_ttl`, pool-proxy `weight`, project-pool `priority` in the API schemas
(the models already have them), and add `GET /api/v1/stats/requests`.
