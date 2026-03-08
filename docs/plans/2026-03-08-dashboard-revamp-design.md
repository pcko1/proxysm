# Dashboard Revamp Design

## Goal

Revamp the dashboard into three sections (Proxies, Pools, Projects) that give a complete operational overview with meaningful stats, charts, and status code monitoring.

## Current State

The dashboard currently shows:
- 4 stat cards (total proxies, pools, projects, requests 24h)
- Health ring (proxy health distribution)
- Request volume stacked bar chart (success/fail over time, with granularity selector)
- Top failing proxies table
- Pool utilization bars
- Recent activity table

Data sources:
- `metrics_rollup` table: pre-aggregated stats per entity (proxy/pool/project) at 5min/1hour/1day granularity. Stores total_requests, successful_requests, failed_requests, bytes_sent, bytes_received, avg_response_time_ms, p95_response_time_ms.
- `request_log` table: raw per-request logs with status_code, response_time_ms, error_type. Partitioned by time.
- Proxy model: last_health_status, avg_latency_ms.

## New Layout

### Section 1: Proxies

**Stat cards row:** Total Proxies | Healthy | Degraded | Dead

**Two-column grid:**
- Left: Health ring donut chart (healthy/degraded/dead/unknown distribution with legend)
- Right: Request volume stacked bar chart (success/fail over time, with 5min/1hour/1day granularity selector)

**Below:** Top 5 failing proxies table (host:port, status, latency)

### Section 2: Pools

**Pool utilization bars:** horizontal bars showing % healthy proxies per pool (green/yellow/red based on threshold)

**Per-pool metrics table:** name, total requests (24h), error rate, avg latency

### Section 3: Projects

**Per-project stats table:** name, requests (24h), bandwidth consumed, avg latency, error rate

**Status code breakdown:** horizontal stacked bar per project showing 2xx/3xx/4xx/5xx distribution

## Backend Changes

### New API endpoint

`GET /api/v1/stats/status-codes`

Query params:
- `project_id` (optional) — filter to specific project
- `hours` (optional, default 24) — time window

Response:
```json
{
  "data": [
    {
      "project_id": "uuid",
      "project_name": "my-project",
      "status_2xx": 1500,
      "status_3xx": 20,
      "status_4xx": 45,
      "status_5xx": 10,
      "total": 1575
    }
  ]
}
```

Implementation: Query `request_log` table grouped by project_id and status code class (status_code / 100). Join with projects table for name. Filter by `created_at >= NOW() - interval`.

### Enhanced pool stats

Extend the existing pool utilization loading to also fetch per-pool metrics from `metrics_rollup` (entity_type='pool') for the 24h window — total requests, error rate, avg latency.

## Frontend Changes

- Remove the existing "Recent Activity" table (redundant with the request volume chart)
- Reorganize into 3 clearly labeled sections with section headers
- Add status code stacked bars (new component) using CSS bars (same pattern as existing bar charts)
- Color scheme: 2xx=green, 3xx=blue, 4xx=yellow, 5xx=red

## What stays the same

- Health ring component (reused in Proxies section)
- Request volume bar chart with granularity selector (reused in Proxies section)
- Pool utilization bars (reused in Pools section)
- 15-second auto-refresh
- Live indicator
- All existing CSS patterns and design language
