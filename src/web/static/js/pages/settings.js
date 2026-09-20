/* Settings page: alert rules (table + typed create/edit modal) and the read-only
   system and retention values. Nothing polls: data loads once and again after
   each mutation. Uses the app.js globals (apiCall, esc, timeAgo, modals, toasts). */
'use strict';

const HINT_LIVE = 'Read-only. Configured through environment variables.';
const HINT_DEFAULTS = 'API unreachable. Showing the built-in defaults.';

/* ---------- system + retention values ---------- */
// Every field falls back to the shipped default, so an empty object renders the
// same values the old page showed when /system/info could not be reached.
function renderSystemInfo(data) {
    document.getElementById('setVersion').textContent = data.version || '0.1.0';
    document.getElementById('setHcInterval').textContent = (data.health_check_interval || 60) + 's';
    document.getElementById('setHcTimeout').textContent = (data.health_check_timeout || 10) + 's';
    document.getElementById('setHcConcurrency').textContent = data.health_check_concurrency || 200;
    document.getElementById('setHttpPort').textContent = data.proxy_http_port || APP.httpPort || 9080;
    document.getElementById('setSocksPort').textContent = data.proxy_socks5_port || APP.socks5Port || 9081;
    document.getElementById('setPrometheus').textContent = data.prometheus_enabled ? 'Enabled (/metrics)' : 'Disabled';
    document.getElementById('setLogRetention').textContent = (data.request_log_retention_days || 7) + ' days';
    document.getElementById('set5minRetention').textContent = (data.metrics_5min_retention_days || 7) + ' days';
    document.getElementById('set1hourRetention').textContent = (data.metrics_1hour_retention_days || 90) + ' days';
    document.getElementById('setRollupInterval').textContent = (data.metrics_rollup_interval || 300) + 's';
    document.getElementById('setBwFlush').textContent = (data.bandwidth_flush_interval || 30) + 's';
}

async function loadSystemInfo() {
    let data = {};
    let live = true;
    try {
        data = (await apiCall('GET', '/api/v1/system/info')) || {};
    } catch (e) {
        live = false; // no toast: the sidebar status line reports outages
    }
    renderSystemInfo(data);
    const hint = live ? HINT_LIVE : HINT_DEFAULTS;
    document.getElementById('systemHint').textContent = hint;
    document.getElementById('retentionHint').textContent = hint;
}

/* ---------- alert rules table ---------- */
let rules = [];

function formatCondType(t) {
    const map = {
        'error_rate_above': 'Error rate',
        'pool_below_min_healthy': 'Pool health',
        'bandwidth_exceeded': 'Bandwidth',
        'all_proxies_dead': 'All proxies dead',
    };
    return map[t] || t;
}

function formatActionType(t) {
    const map = {
        'webhook': 'Webhook',
    };
    return map[t] || t;
}

function ruleStatusBadge(enabled) {
    return enabled
        ? '<span class="badge badge-healthy">Enabled</span>'
        : '<span class="badge badge-quiet">Disabled</span>';
}

// state: 'loading' | 'table' | 'empty' | 'error'
function showRulesState(state) {
    document.getElementById('alertsLoading').hidden = state !== 'loading';
    document.getElementById('alertsTable').hidden = state !== 'table';
    document.getElementById('alertsEmpty').hidden = state !== 'empty';
    document.getElementById('alertsError').hidden = state !== 'error';
}

function ruleRow(a) {
    const id = esc(a.id);
    const last = a.last_triggered_at
        ? `<span title="${esc(fmtDate(a.last_triggered_at))}">${esc(timeAgo(a.last_triggered_at))} ago</span>`
        : '<span class="muted">never</span>';
    return `<tr>
        <td><div class="strong truncate" style="max-width:320px" title="${esc(a.name)}">${esc(a.name)}</div></td>
        <td>${esc(formatCondType(a.condition_type))}</td>
        <td><span class="tag">${esc(formatActionType(a.action_type))}</span></td>
        <td>${last}</td>
        <td>${ruleStatusBadge(a.is_enabled)}</td>
        <td class="actions">
            <button class="btn btn-ghost btn-sm" type="button" data-rule="${id}" onclick="toggleAlert('${id}', ${a.is_enabled ? 'false' : 'true'}, this)">${a.is_enabled ? 'Disable' : 'Enable'}</button>
            <button class="btn btn-sm" type="button" onclick="editAlert('${id}')">Edit</button>
            <button class="btn btn-danger btn-sm" type="button" onclick="deleteAlert('${id}')">Delete</button>
        </td>
    </tr>`;
}

function renderRules() {
    const tbody = document.getElementById('alertsList');
    if (rules.length === 0) {
        tbody.innerHTML = '';
        showRulesState('empty');
        return;
    }
    tbody.innerHTML = rules.map(ruleRow).join('');
    showRulesState('table');
}

// announce = true for user-initiated reloads (after a mutation, Retry): those toast
// their failure. The first load stays quiet; the sidebar status line reports outages.
async function loadAlerts(announce) {
    let data;
    try {
        data = await apiCall('GET', '/api/v1/alerts');
    } catch (e) {
        showRulesState('error');
        if (announce) showToast('Failed to load alerts: ' + e.message, 'error');
        return;
    }
    rules = Array.isArray(data) ? data : [];
    renderRules();
}

async function retryLoad(btn) {
    btnLoading(btn);
    await Promise.all([loadAlerts(true), loadSystemInfo()]);
    btnReset(btn);
}

/* ---------- typed condition fields ---------- */
const COND_FIELD_GROUPS = {
    'error_rate_above': ['grpErrThreshold', 'grpErrWindow'],
    'pool_below_min_healthy': ['grpPool', 'grpMinHealthy'],
    'bandwidth_exceeded': ['grpBwLimit'],
    'all_proxies_dead': ['grpAllDeadHint'],
};
const ALL_COND_GROUPS = [...new Set(Object.values(COND_FIELD_GROUPS).flat())];
const BYTES_PER_GB = 1e9;

// Originals of the rule being edited, so unknown config keys are preserved.
let origCondType = null;
let origCondConfig = {};
let origActionConfig = {};
let poolOptionsPromise = null;

function updateCondFields() {
    const type = document.getElementById('alertCondType').value;
    const visible = COND_FIELD_GROUPS[type] || [];
    ALL_COND_GROUPS.forEach((id) => {
        document.getElementById(id).hidden = !visible.includes(id);
    });
}

// Pools are fetched once per page view; a failed fetch is retried on the next open.
function loadPoolOptions() {
    if (!poolOptionsPromise) {
        poolOptionsPromise = apiCall('GET', '/api/v1/pools?per_page=100').then((resp) => {
            const pools = (resp && resp.data) || [];
            const sel = document.getElementById('alertPoolSelect');
            sel.innerHTML = '';
            if (pools.length === 0) sel.add(new Option('No pools available', ''));
            pools.forEach((p) => sel.add(new Option(p.name, p.id)));
            return pools;
        }).catch((e) => {
            poolOptionsPromise = null; // allow retry next time
            throw e;
        });
    }
    return poolOptionsPromise;
}

// The "(unknown pool)" option belongs to one edit session only.
function dropUnknownPoolOption() {
    document.querySelectorAll('#alertPoolSelect option[data-unknown]').forEach((o) => o.remove());
}

/* ---------- create / edit modal ---------- */
function openCreateAlert() {
    document.getElementById('alertModalTitle').textContent = 'Create alert rule';
    document.getElementById('alertEditId').value = '';
    document.getElementById('alertName').value = '';
    document.getElementById('alertCondType').value = 'error_rate_above';
    origCondType = null;
    origCondConfig = {};
    origActionConfig = {};
    document.getElementById('alertErrThreshold').value = '';
    document.getElementById('alertErrWindow').value = '300';
    document.getElementById('alertMinHealthy').value = '';
    document.getElementById('alertBwLimit').value = '';
    document.getElementById('alertWebhookUrl').value = '';
    document.getElementById('alertActionType').value = 'webhook';
    document.getElementById('alertEnabled').checked = true;
    dropUnknownPoolOption();
    loadPoolOptions().catch(() => {});
    updateCondFields();
    openModal('alertModal');
}

async function editAlert(id) {
    try {
        const rule = await apiCall('GET', `/api/v1/alerts/${id}`);
        document.getElementById('alertModalTitle').textContent = 'Edit alert rule';
        document.getElementById('alertEditId').value = id;
        document.getElementById('alertName').value = rule.name;
        document.getElementById('alertCondType').value = rule.condition_type;
        document.getElementById('alertActionType').value = rule.action_type;

        origCondType = rule.condition_type;
        origCondConfig = rule.condition_config || {};
        origActionConfig = rule.action_config || {};
        const cfg = origCondConfig;

        // Stored as a 0..1 fraction and as bytes; edited as a percentage and as GB.
        document.getElementById('alertErrThreshold').value =
            cfg.threshold != null ? parseFloat((cfg.threshold * 100).toFixed(4)) : '';
        document.getElementById('alertErrWindow').value =
            cfg.window_seconds != null ? cfg.window_seconds : '300';
        document.getElementById('alertMinHealthy').value =
            cfg.min_healthy != null ? cfg.min_healthy : '';
        document.getElementById('alertBwLimit').value =
            cfg.limit_bytes != null ? parseFloat((cfg.limit_bytes / BYTES_PER_GB).toFixed(4)) : '';

        try { await loadPoolOptions(); } catch (e) { /* pool list optional */ }
        dropUnknownPoolOption();
        const poolSel = document.getElementById('alertPoolSelect');
        if (cfg.pool_id) {
            if (![...poolSel.options].some((o) => o.value === String(cfg.pool_id))) {
                const opt = new Option(cfg.pool_id + ' (unknown pool)', cfg.pool_id);
                opt.dataset.unknown = '1';
                poolSel.add(opt);
            }
            poolSel.value = cfg.pool_id;
        }

        document.getElementById('alertWebhookUrl').value = origActionConfig.url != null ? origActionConfig.url : '';
        document.getElementById('alertEnabled').checked = rule.is_enabled;
        updateCondFields();
        openModal('alertModal');
    } catch (e) {
        showToast('Failed to load alert: ' + e.message, 'error');
    }
}

async function saveAlert() {
    const name = document.getElementById('alertName').value.trim();
    if (!name) { showToast('Please enter a name', 'error'); return; }

    const condType = document.getElementById('alertCondType').value;
    // Preserve unknown keys from the original config when the type is unchanged.
    const condConfig = condType === origCondType ? { ...origCondConfig } : {};

    if (condType === 'error_rate_above') {
        const pct = parseFloat(document.getElementById('alertErrThreshold').value);
        const win = parseInt(document.getElementById('alertErrWindow').value, 10);
        if (!isFinite(pct) || pct <= 0 || pct > 100) { showToast('Enter an error rate threshold between 0 and 100%', 'error'); return; }
        if (!isFinite(win) || win <= 0) { showToast('Enter a window in seconds (greater than 0)', 'error'); return; }
        condConfig.threshold = pct / 100;
        condConfig.window_seconds = win;
    } else if (condType === 'pool_below_min_healthy') {
        const poolId = document.getElementById('alertPoolSelect').value;
        const minHealthy = parseInt(document.getElementById('alertMinHealthy').value, 10);
        if (!poolId) { showToast('Select a pool', 'error'); return; }
        if (!isFinite(minHealthy) || minHealthy < 1) { showToast('Enter a min healthy count of at least 1', 'error'); return; }
        condConfig.pool_id = poolId;
        condConfig.min_healthy = minHealthy;
    } else if (condType === 'bandwidth_exceeded') {
        const gb = parseFloat(document.getElementById('alertBwLimit').value);
        if (!isFinite(gb) || gb <= 0) { showToast('Enter a bandwidth limit in GB (greater than 0)', 'error'); return; }
        condConfig.limit_bytes = Math.round(gb * BYTES_PER_GB);
    }
    // all_proxies_dead: no fields.

    const webhookUrl = document.getElementById('alertWebhookUrl').value.trim();
    if (!/^https?:\/\/\S+$/i.test(webhookUrl)) { showToast('Enter a valid webhook URL (http:// or https://)', 'error'); return; }
    const actionConfig = { ...origActionConfig, url: webhookUrl };

    const body = {
        name: name,
        condition_type: condType,
        condition_config: condConfig,
        action_type: document.getElementById('alertActionType').value,
        action_config: actionConfig,
        is_enabled: document.getElementById('alertEnabled').checked,
    };

    const editId = document.getElementById('alertEditId').value;
    const btn = document.getElementById('alertSaveBtn');
    btnLoading(btn);

    try {
        if (editId) {
            await apiCall('PATCH', `/api/v1/alerts/${editId}`, body);
            showToast('Alert updated', 'success');
        } else {
            await apiCall('POST', '/api/v1/alerts', body);
            showToast('Alert created', 'success');
        }
        btnReset(btn);
        closeModal('alertModal');
        loadAlerts(true);
    } catch (e) {
        btnReset(btn);
        showToast('Failed to save alert: ' + e.message, 'error');
    }
}

/* ---------- row actions ---------- */
async function toggleAlert(id, enabled, btn) {
    btnLoading(btn);
    try {
        await apiCall('PATCH', `/api/v1/alerts/${id}`, { is_enabled: enabled });
        const rule = rules.find((r) => r.id === id);
        if (rule) rule.is_enabled = enabled;
        renderRules();
        // The row was re-rendered: hand keyboard focus to the new toggle button.
        const again = document.querySelector('button[data-rule="' + id + '"]');
        if (again) again.focus();
        showToast(enabled ? 'Alert enabled' : 'Alert disabled', 'success');
    } catch (e) {
        btnReset(btn);
        showToast('Failed to toggle alert: ' + e.message, 'error');
        loadAlerts(); // re-sync the row with the server
    }
}

async function deleteAlert(id) {
    if (!(await confirmAction('Delete this alert rule? This cannot be undone.'))) return;
    try {
        await apiCall('DELETE', `/api/v1/alerts/${id}`);
        showToast('Alert deleted', 'success');
        loadAlerts(true);
    } catch (e) {
        showToast('Failed to delete alert: ' + e.message, 'error');
    }
}

loadSystemInfo();
loadAlerts();
