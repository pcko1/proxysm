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
