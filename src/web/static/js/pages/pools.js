/* Pools page: pools table, create modal, manage-proxies modal.
   Classic script. Functions are globals because pools.html uses inline handlers.
   Only a pool id (a UUID) is ever passed to an inline handler, never a name. */
'use strict';

const LIST_PAGE_SIZE = 100; // the API caps per_page at 100

let pools = null;         // last list that loaded; null until the first success
let currentPoolId = null; // pool open in the manage-proxies modal
let manageSeq = 0;        // drops a slow response that lands in a reopened modal

/* ---------- pools table ---------- */
function showPoolsState(state) {
    document.getElementById('poolsTableWrap').hidden = state !== 'table';
    document.getElementById('poolsEmpty').hidden = state !== 'empty';
    document.getElementById('poolsError').hidden = state !== 'error';
}

function metaTotal(data, fallback) {
    return data && data.meta && typeof data.meta.total === 'number' ? data.meta.total : fallback;
}

function strategyLabel(strategy) {
    return String(strategy || '').replace(/_/g, ' ');
}

// Badge and meter for one pool. The counts are nullable in the API schema, so
// "unknown" is a real state: a dash and an empty meter, never "null / null".
function poolHealth(p) {
    const n = p.proxy_count;
    const h = p.healthy_count;
    if (typeof n !== 'number' || typeof h !== 'number') {
        return { known: false, share: 0, badge: 'badge-quiet', meter: '', label: 'Health unknown' };
    }
    const share = n > 0 ? Math.max(0, Math.min(100, Math.round((h / n) * 100))) : 0;
    let badge = 'badge-quiet';
    let meter = 'meter--lime';
    if (n > 0 && h <= 0) { badge = 'badge-bad'; meter = 'meter--coral'; }
    else if (n > 0 && h / n < 0.5) { badge = 'badge-warn'; meter = 'meter--amber'; }
    const label = n > 0 ? fmtPct(h, n, 0) + ' healthy' : 'No proxies in this pool';
    return { known: true, share: share, badge: badge, meter: meter, label: label };
}

function poolRow(p) {
    const id = esc(p.id);
    const name = esc(p.name);
    const health = poolHealth(p);
    const healthy = health.known
        ? `<span class="badge ${health.badge}">${fmtNum(p.healthy_count)} / ${fmtNum(p.proxy_count)}</span>`
        : '<span class="muted">—</span>';
    return `<tr data-id="${id}">
        <td class="col-check"><input type="checkbox" class="row-checkbox" data-id="${id}" aria-label="Select pool ${name}" onchange="toggleRowSelection('${id}', this)"></td>
        <td><div class="strong truncate" style="max-width:320px" title="${name}">${name}</div><span class="sub">${esc(strategyLabel(p.rotation_strategy))}</span></td>
        <td class="num">${fmtNum(p.proxy_count)}</td>
        <td class="num">${healthy}</td>
        <td><div class="meter ${health.meter}" role="img" aria-label="${health.label}" title="${health.label}"><i style="width:${health.share}%"></i></div></td>
        <td class="muted">${esc(fmtDate(p.created_at))}</td>
        <td class="actions">
            <button class="btn btn-sm" type="button" aria-label="Manage proxies in ${name}" onclick="manageProxies('${id}')">Manage proxies</button>
            <button class="btn btn-sm btn-danger" type="button" aria-label="Delete pool ${name}" onclick="deletePool('${id}')">Delete</button>
        </td>
    </tr>`;
}

function renderPools(total) {
    const count = total === 1 ? '1 pool' : fmtNum(total) + ' pools';
    document.getElementById('poolsSub').textContent =
        total > pools.length ? count + ', showing the first ' + pools.length : count;
    document.getElementById('poolsBody').innerHTML = pools.map(poolRow).join('');
    showPoolsState(pools.length === 0 ? 'empty' : 'table');
    clearSelection();
}

// One-off load, re-run after every mutation. No toast on failure: the sidebar
// status line reports outages. A table that already loaded stays on screen.
async function loadPools() {
    let data;
    try {
        data = await apiCall('GET', '/api/v1/pools?per_page=' + LIST_PAGE_SIZE);
    } catch (e) {
        if (pools === null) {
            document.getElementById('poolsSub').textContent = 'Unavailable';
            showPoolsState('error');
        }
        return;
    }
    pools = (data && data.data) || [];
    renderPools(metaTotal(data, pools.length));
}

async function retryPools(btn) {
    btnLoading(btn);
    await loadPools();
    btnReset(btn);
}

/* ---------- create ---------- */
async function createPool() {
    const input = document.getElementById('poolName');
    const name = input.value.trim();
    if (!name) { showToast('Pool name is required', 'error'); input.focus(); return; }
    const strategy = document.getElementById('poolStrategy').value;
    const btn = document.getElementById('createPoolBtn');
    btnLoading(btn);
    try {
        await apiCall('POST', '/api/v1/pools', { name: name, rotation_strategy: strategy });
        btnReset(btn);
        showToast('Pool created', 'success');
        closeModal('createPoolModal');
        input.value = '';
        loadPools();
    } catch (e) {
        btnReset(btn);
        showToast('Create failed: ' + e.message, 'error');
    }
}

/* ---------- delete ---------- */
async function deletePool(id) {
    if (!(await confirmAction('This pool will be permanently deleted.'))) return;
    try {
        await apiCall('DELETE', '/api/v1/pools/' + encodeURIComponent(id));
        showToast('Pool deleted', 'success');
        loadPools();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

async function bulkDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const noun = ids.length === 1 ? 'pool' : 'pools';
    if (!(await confirmAction(`Delete ${ids.length} ${noun}? This cannot be undone.`))) return;
    let deleted = 0;
    for (const id of ids) {
        try {
            await apiCall('DELETE', '/api/v1/pools/' + encodeURIComponent(id));
            deleted += 1;
        } catch (e) { /* counted below */ }
    }
    if (deleted === ids.length) showToast(`Deleted ${deleted} ${noun}`, 'success');
    else showToast(`Deleted ${deleted} of ${ids.length} pools`, 'error');
    clearSelection();
    loadPools();
}

/* ---------- manage proxies ---------- */
function providerRow(name, group, count) {
    const label = esc(name);
    return `<label class="check-list__group">
        <input type="checkbox" data-kind="provider" data-group="${group}">
        <span class="truncate" title="${label}">${label}</span>
        <span class="muted">${count}</span>
    </label>`;
}

function proxyRow(p, group, checked) {
    const address = esc(p.host) + ':' + esc(p.port);
    return `<label>
        <input type="checkbox" data-kind="proxy" data-group="${group}" value="${esc(p.id)}"${checked ? ' checked' : ''}>
        <span class="mono truncate" title="${address}">${address}</span>
        ${protoTag(p.protocol)}
        <span class="spacer"></span>
        ${statusBadge(p.last_health_status)}
    </label>`;
}

function proxyBoxes(group) {
    const scope = group ? `[data-group="${group}"]` : '';
    return Array.from(document.querySelectorAll('#proxyCheckboxes input[data-kind="proxy"]' + scope));
}

function toggleProviderProxies(group, checked) {
    proxyBoxes(group).forEach((box) => { box.checked = checked; });
}

function updateProviderToggle(group) {
    const toggle = document.querySelector(`#proxyCheckboxes input[data-kind="provider"][data-group="${group}"]`);
    if (!toggle) return;
    const boxes = proxyBoxes(group);
    const all = boxes.length > 0 && boxes.every((box) => box.checked);
    toggle.checked = all;
    toggle.indeterminate = !all && boxes.some((box) => box.checked);
}

// Returns true when there is at least one proxy to tick.
function renderProxyChecklist(allData, memberData) {
    const list = document.getElementById('proxyCheckboxes');
    const note = document.getElementById('manageProxiesNote');
    const proxies = (allData && allData.data) || [];
    const assigned = new Set(((memberData && memberData.data) || []).map((p) => p.id));
    if (proxies.length === 0) {
        list.innerHTML = '<div class="empty-state"><h3>No proxies yet</h3>'
            + '<p>Import proxies first, then add them to this pool.</p>'
            + '<a class="btn btn-primary" href="/proxies?import=1">Import proxies</a></div>';
        return false;
    }
    // A Map, not a plain object: a provider may be called "constructor"
    const byProvider = new Map();
    proxies.forEach((p) => {
        const name = p.provider || 'No provider';
        if (!byProvider.has(name)) byProvider.set(name, []);
        byProvider.get(name).push(p);
    });
    const groups = [];
    let html = '';
    byProvider.forEach((members, name) => {
        const group = 'g' + groups.length;
        groups.push(group);
        html += providerRow(name, group, members.length);
        html += members.map((p) => proxyRow(p, group, assigned.has(p.id))).join('');
    });
    list.innerHTML = html;
    groups.forEach(updateProviderToggle);
    const total = metaTotal(allData, proxies.length);
    if (total > proxies.length) {
        note.textContent = `Showing the first ${proxies.length} of ${fmtNum(total)} proxies. `
            + 'For the rest, select them on the Proxies page and use Move to pool.';
        note.hidden = false;
    }
    return true;
}

async function manageProxies(poolId) {
    const pool = (pools || []).find((p) => p.id === poolId);
    if (!pool) return;
    currentPoolId = poolId;
    manageSeq += 1;
    const seq = manageSeq;
    const modal = document.getElementById('manageProxiesModal');
    const info = document.getElementById('manageProxiesInfo');
    const list = document.getElementById('proxyCheckboxes');
    const saveBtn = document.getElementById('saveProxiesBtn');
    info.textContent = 'Assign proxies to ' + pool.name;
    info.title = pool.name;
    document.getElementById('manageProxiesNote').hidden = true;
    list.innerHTML = '<div class="skeleton" style="height:40px"></div>'.repeat(5);
    btnReset(saveBtn);
    saveBtn.disabled = true;
    openModal('manageProxiesModal');
    try {
        const [allData, memberData] = await Promise.all([
            apiCall('GET', '/api/v1/ips?per_page=' + LIST_PAGE_SIZE),
            apiCall('GET', `/api/v1/ips?pool_id=${encodeURIComponent(poolId)}&per_page=${LIST_PAGE_SIZE}`),
        ]);
        // Closed or reopened for another pool while loading: drop this response
        if (seq !== manageSeq || !modal.classList.contains('active')) return;
        saveBtn.disabled = !renderProxyChecklist(allData, memberData);
        const first = list.querySelector('input');
        if (first) first.focus();
    } catch (e) {
        if (seq !== manageSeq || !modal.classList.contains('active')) return;
        closeModal('manageProxiesModal');
        showToast('Failed to load proxies: ' + e.message, 'error');
    }
}

async function saveProxyAssignments() {
    if (!currentPoolId) return;
    const poolId = currentPoolId;
    const boxes = proxyBoxes();
    const listed = new Set(boxes.map((box) => box.value));
    const wanted = new Set(boxes.filter((box) => box.checked).map((box) => box.value));
    const btn = document.getElementById('saveProxiesBtn');
    const membersUrl = '/api/v1/pools/' + encodeURIComponent(poolId) + '/ips';
    btnLoading(btn);
    try {
        // Diff against membership as it is now, not as it was when the modal opened
        const current = await apiCall(
            'GET', `/api/v1/ips?pool_id=${encodeURIComponent(poolId)}&per_page=${LIST_PAGE_SIZE}`
        );
        const currentIds = new Set(((current && current.data) || []).map((p) => p.id));
        const toAdd = [...wanted].filter((id) => !currentIds.has(id));
        // Only a proxy that had a checkbox can be removed. A member beyond the
        // first page was never shown, so it must not be dropped silently.
        const toRemove = [...currentIds].filter((id) => listed.has(id) && !wanted.has(id));
        if (toAdd.length > 0) await apiCall('POST', membersUrl, { proxy_ids: toAdd });
        if (toRemove.length > 0) await apiCall('DELETE', membersUrl, { proxy_ids: toRemove });
        btnReset(btn);
        if (toAdd.length + toRemove.length > 0) {
            showToast(`Updated pool: ${toAdd.length} added, ${toRemove.length} removed`, 'success');
        } else {
            showToast('No changes made', 'success');
        }
        closeModal('manageProxiesModal');
        loadPools();
    } catch (e) {
        btnReset(btn);
        showToast('Update failed: ' + e.message, 'error');
        loadPools(); // the add may have gone through before the remove failed
    }
}

/* ---------- init ---------- */
document.getElementById('proxyCheckboxes').addEventListener('change', (e) => {
    const box = e.target;
    if (!box.dataset || !box.dataset.group) return;
    if (box.dataset.kind === 'provider') toggleProviderProxies(box.dataset.group, box.checked);
    else updateProviderToggle(box.dataset.group);
});
document.getElementById('bulkDeleteBtn').addEventListener('click', bulkDelete);
openModalFromQuery({ new: 'createPoolModal' });
loadPools();
