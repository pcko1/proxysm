# Dashboard Revamp Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Revamp the dashboard into three sections (Proxies, Pools, Projects) with per-entity metrics and status code breakdowns.

**Architecture:** Add two new API endpoints (status codes from `request_log`, pool aggregate stats from `metrics_rollup`), then rewrite `dashboard.html` into 3 clearly labeled sections reusing existing chart components. No migrations needed.

**Tech Stack:** FastAPI, SQLAlchemy (raw SQL for aggregation), Jinja2 templates, vanilla JS/CSS

---

### Task 1: Add Status Code Breakdown API Endpoint

**Files:**
- Modify: `src/schemas/stats.py`
- Modify: `src/api/stats.py`

**Step 1: Add Pydantic schema for status code response**

Add to `src/schemas/stats.py`:

```python
class StatusCodeBreakdown(BaseModel):
    project_id: str
    project_name: str
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    total: int = 0

    model_config = ConfigDict(from_attributes=True)
```

**Step 2: Add the endpoint to `src/api/stats.py`**

Add this endpoint to the existing `router`:

```python
from src.schemas.stats import StatusCodeBreakdown

@router.get("/stats/status-codes")
async def get_status_codes(
    project_id: uuid.UUID | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Status code breakdown per project from request_log."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    filters = "WHERE rl.created_at >= :cutoff"
    params: dict = {"cutoff": cutoff}
    if project_id:
        filters += " AND rl.project_id = :project_id"
        params["project_id"] = project_id

    sql = text(f"""
        SELECT
            rl.project_id,
            p.name AS project_name,
            COUNT(*) FILTER (WHERE rl.status_code >= 200 AND rl.status_code < 300) AS status_2xx,
            COUNT(*) FILTER (WHERE rl.status_code >= 300 AND rl.status_code < 400) AS status_3xx,
            COUNT(*) FILTER (WHERE rl.status_code >= 400 AND rl.status_code < 500) AS status_4xx,
            COUNT(*) FILTER (WHERE rl.status_code >= 500 OR rl.status_code IS NULL) AS status_5xx,
            COUNT(*) AS total
        FROM request_log rl
        JOIN projects p ON p.id = rl.project_id
        {filters}
        GROUP BY rl.project_id, p.name
        ORDER BY total DESC
    """)

    rows = await db.execute(sql, params)
    return {
        "data": [
            StatusCodeBreakdown(
                project_id=str(row.project_id),
                project_name=row.project_name,
                status_2xx=row.status_2xx,
                status_3xx=row.status_3xx,
                status_4xx=row.status_4xx,
                status_5xx=row.status_5xx,
                total=row.total,
            )
            for row in rows
        ]
    }
```

Add `from sqlalchemy import text` to imports if not already present.

**Step 3: Test manually**

```bash
curl -H "X-Admin-Token: changeme" "http://localhost:8080/api/v1/stats/status-codes"
```

Expected: `{"data": [...]}` — empty array if no request_log data yet, otherwise rows with status code counts.

**Step 4: Commit**

```bash
git add src/schemas/stats.py src/api/stats.py
git commit -m "feat: add status code breakdown API endpoint"
```

---

### Task 2: Add Pool Aggregate Stats API Endpoint

**Files:**
- Modify: `src/api/stats.py`

**Step 1: Add pool stats endpoint**

Add to `src/api/stats.py` on the existing `router`:

```python
@router.get("/stats/pool-metrics")
async def get_pool_metrics(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(admin_auth),
):
    """Aggregate metrics per pool from metrics_rollup (24h window)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    sql = text("""
        SELECT
            m.entity_id AS pool_id,
            p.name AS pool_name,
            COALESCE(SUM(m.total_requests), 0) AS total_requests,
            COALESCE(SUM(m.successful_requests), 0) AS successful_requests,
            COALESCE(SUM(m.failed_requests), 0) AS failed_requests,
            AVG(m.avg_response_time_ms) AS avg_response_time_ms
        FROM metrics_rollup m
        JOIN pools p ON p.id = m.entity_id
        WHERE m.entity_type = 'pool'
          AND m.period_granularity = '5min'
          AND m.period_start >= :cutoff
        GROUP BY m.entity_id, p.name
        ORDER BY total_requests DESC
    """)

    rows = await db.execute(sql, {"cutoff": cutoff})
    data = []
    for row in rows:
        total = row.total_requests
        failed = row.failed_requests
        error_rate = round((failed / total * 100), 1) if total > 0 else 0.0
        data.append({
            "pool_id": str(row.pool_id),
            "pool_name": row.pool_name,
            "total_requests": total,
            "error_rate": error_rate,
            "avg_latency_ms": round(row.avg_response_time_ms, 1) if row.avg_response_time_ms else None,
        })
    return {"data": data}
```

**Step 2: Test manually**

```bash
curl -H "X-Admin-Token: changeme" "http://localhost:8080/api/v1/stats/pool-metrics"
```

**Step 3: Commit**

```bash
git add src/api/stats.py
git commit -m "feat: add pool aggregate metrics API endpoint"
```

---

### Task 3: Rewrite Dashboard Template

**Files:**
- Modify: `src/web/templates/dashboard.html`

This is the main task. Rewrite the template to have 3 sections. Keep all existing CSS classes and chart-drawing JS functions — just reorganize the HTML structure and add new data-loading functions.

**Step 1: Restructure HTML into 3 sections**

The new HTML structure (inside `{% block content %}`):

```
<style>
    /* Keep ALL existing CSS */
    /* Add section header styles: */
    .section-header { ... }
    /* Add status code bar styles: */
    .status-bar-track { ... }
    .status-bar-2xx { background: var(--green); }
    .status-bar-3xx { background: var(--accent); }
    .status-bar-4xx { background: var(--yellow); }
    .status-bar-5xx { background: var(--red); }
</style>

<!-- Page Header (keep existing) -->
<div class="page-header">...</div>

<!-- SECTION 1: PROXIES -->
<h2 class="section-header">Proxies</h2>
<div class="stat-cards"> 4 cards: Total | Healthy | Degraded | Dead </div>
<div class="dashboard-grid">
    <!-- Left: Health Ring (existing) -->
    <!-- Right: Request Volume chart (existing) -->
</div>
<div class="dash-card"> Top Failing Proxies table (existing) </div>

<!-- SECTION 2: POOLS -->
<h2 class="section-header">Pools</h2>
<div class="dashboard-grid">
    <!-- Left: Pool Utilization bars (existing) -->
    <!-- Right: Pool Metrics table (NEW — loads from /stats/pool-metrics) -->
</div>

<!-- SECTION 3: PROJECTS -->
<h2 class="section-header">Projects</h2>
<div class="dash-card"> Per-project stats table (NEW — loads from /stats/overview + entity stats) </div>
<div class="dash-card"> Status Code Breakdown bars (NEW — loads from /stats/status-codes) </div>
```

**Step 2: Add new JS functions**

Keep existing functions: `drawHealthRing()`, `drawTimeseries()`, `fillTimeslots()`, `loadOverview()`, `loadTimeseries()`, `loadPoolUtilization()`, `loadFailingProxies()`.

Add new functions:

```javascript
async function loadPoolMetrics() {
    // Fetch from /api/v1/stats/pool-metrics
    // Render table: pool name | requests | error rate | avg latency
}

async function loadProjectStats() {
    // Fetch from /api/v1/projects (for list) + /api/v1/stats/status-codes
    // Render per-project table: name | requests | bandwidth | latency | error rate
    // Render status code stacked bars per project
}
```

Update `loadStats()` to call all loaders:

```javascript
async function loadStats() {
    await Promise.all([
        loadOverview(),
        loadTimeseries(),
        loadPoolUtilization(),
        loadFailingProxies(),
        loadPoolMetrics(),
        loadProjectStats(),
    ]);
}
```

**Step 3: Remove "Recent Activity" table**

Delete the `<div class="dash-card activity-card">` block and the `populateActivityTable()` function — it's redundant with the request volume chart.

**Step 4: Add status code bar component**

For each project, render a horizontal stacked bar like:

```html
<div class="pool-bar-row">
    <span class="pool-bar-name">project-name</span>
    <div class="status-bar-track">
        <div class="status-bar-2xx" style="width: 80%"></div>
        <div class="status-bar-3xx" style="width: 5%"></div>
        <div class="status-bar-4xx" style="width: 10%"></div>
        <div class="status-bar-5xx" style="width: 5%"></div>
    </div>
    <span class="pool-bar-pct">1,575</span>
</div>
```

Reuse existing `.pool-bar-row`, `.pool-bar-name`, `.pool-bar-track`, `.pool-bar-pct` CSS classes. Override `.pool-bar-track` height to `12px` for stacked bars. The `.status-bar-*` segments are absolutely positioned children with width percentages.

**Step 5: Test in browser**

Visit `http://localhost:8080/dashboard` and verify:
1. Three sections visible with headers
2. Proxies section: stat cards, health ring, request chart, failing table
3. Pools section: utilization bars, metrics table
4. Projects section: stats table, status code bars
5. Auto-refresh works (15s)
6. Responsive layout on mobile

**Step 6: Commit**

```bash
git add src/web/templates/dashboard.html
git commit -m "feat: revamp dashboard with 3 sections and status code breakdowns"
```

---

### Task 4: Deploy and Verify

**Step 1: Build and deploy**

```bash
docker compose up -d --build
```

**Step 2: Verify all endpoints return data**

```bash
curl -H "X-Admin-Token: changeme" "http://localhost:8080/api/v1/stats/overview"
curl -H "X-Admin-Token: changeme" "http://localhost:8080/api/v1/stats/status-codes"
curl -H "X-Admin-Token: changeme" "http://localhost:8080/api/v1/stats/pool-metrics"
```

**Step 3: Visual check**

Open `http://localhost:8080/dashboard` and verify all 3 sections render correctly.

**Step 4: Commit if any fixes needed**

```bash
git add -A
git commit -m "fix: dashboard deployment fixes"
```
