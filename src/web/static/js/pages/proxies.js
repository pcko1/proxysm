/* Proxies page: status pills + search (both server-side, mirrored in the URL), sortable
   paginated table, bulk actions, and the Sources / Import / Move-to-pool modals.
   Classic script. Uses the globals from app.js; never redefines them. */
'use strict';

const PAGE_SIZE = 50;
const STATUSES = ['healthy', 'degraded', 'dead', 'unknown'];

let currentPage = 1;
let sortColumn = null;
let sortDir = 'asc';
let statusFilter = '';
let searchQuery = '';
let searchTimer = null;

let loadSeq = 0;           // responses that arrive out of order are dropped
let userLoads = 0;         // user-initiated table loads in flight
let loadedOnce = false;
let firstRefresh = true;

let overview = null;       // last good GET /stats/overview body
let sources = null;        // last good source list; null = never loaded
let sourcesTotal = null;

let deleteSourceId = null;
let moveIds = [];

/* ---------- small helpers ---------- */
function shorten(text, max) {
    const s = String(text);
    return s.length > max ? s.slice(0, max) + '…' : s;
}

function proxyWord(n) { return n === 1 ? 'proxy' : 'proxies'; }

// True while a background refresh would disturb the operator
function isBusy() {
    if (selectedIds.size > 0) return true;
    if (document.querySelector('.modal-overlay.active')) return true;
    return document.getElementById('proxyTableBody').contains(document.activeElement);
}

// Runs fn once, the next time the modal loses .active (button, Esc or a click outside)
function onceClosed(modalId, fn) {
    const modal = document.getElementById(modalId);
    const observer = new MutationObserver(() => {
        if (modal.classList.contains('active')) return;
        observer.disconnect();
        fn();
    });
    observer.observe(modal, { attributes: true, attributeFilter: ['class'] });
}

/* ---------- URL state: ?status=dead&search=foo ---------- */
function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    statusFilter = STATUSES.includes(status) ? status : '';
    searchQuery = (params.get('search') || '').trim();
    document.getElementById('proxySearch').value = searchQuery;
}

function syncUrl() {
    const params = new URLSearchParams(window.location.search);
    if (statusFilter) params.set('status', statusFilter); else params.delete('status');
    if (searchQuery) params.set('search', searchQuery); else params.delete('search');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
}

/* ---------- filters and sorting ---------- */
function renderPills() {
    document.querySelectorAll('#statusFilters .pill').forEach((pill) => {
        const on = pill.dataset.status === statusFilter;
        pill.classList.toggle('active', on);
        pill.setAttribute('aria-pressed', String(on));
    });
}

function setStatusFilter(status) {
    statusFilter = STATUSES.includes(status) ? status : '';
    renderPills();
    syncUrl();
    currentPage = 1;
    reloadTable();
}

function clearFilters() {
    clearTimeout(searchTimer);
    statusFilter = '';
    searchQuery = '';
    document.getElementById('proxySearch').value = '';
    renderPills();
    syncUrl();
    currentPage = 1;
    reloadTable();
}

function renderSortHeaders() {
    document.querySelectorAll('th.sortable').forEach((th) => {
        if (!th.dataset.label) th.dataset.label = th.textContent.trim();
        const on = th.dataset.sort === sortColumn;
        const arrow = sortDir === 'asc' ? ' ↑' : ' ↓';
        th.classList.toggle('sorted', on);
        th.setAttribute('aria-sort', on ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none');
        th.textContent = th.dataset.label + (on ? arrow : '');
    });
}

function toggleSort(col) {
    if (sortColumn === col) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = col;
        sortDir = 'asc';
    }
    renderSortHeaders();
    currentPage = 1;
    reloadTable();
}

function goPage(p) {
    currentPage = p;
    reloadTable();
}

/* ---------- page head and pill counts ---------- */
function renderHead() {
    const el = document.getElementById('proxyStats');
    if (!overview) { el.textContent = ''; return; }
    const total = fmtNum(overview.total_proxies);
    if (sourcesTotal === null) { el.textContent = total + ' total'; return; }
    el.textContent = total + ' from ' + fmtNum(sourcesTotal) + (sourcesTotal === 1 ? ' source' : ' sources');
}

function renderCounts() {
    if (!overview) return;
    document.getElementById('ctAll').textContent = fmtNum(overview.total_proxies);
    document.getElementById('ctHealthy').textContent = fmtNum(overview.healthy_proxies);
    document.getElementById('ctDegraded').textContent = fmtNum(overview.degraded_proxies);
    document.getElementById('ctDead').textContent = fmtNum(overview.dead_proxies);
    document.getElementById('ctUnknown').textContent = fmtNum(overview.unknown_proxies);
}

/* ---------- proxy table ---------- */
function showState(state) {
    document.getElementById('proxyTableWrap').hidden = state !== 'rows';
    document.getElementById('emptyState').hidden = state !== 'empty';
    document.getElementById('noMatchState').hidden = state !== 'nomatch';
    document.getElementById('loadError').hidden = state !== 'error';
    if (state !== 'rows') document.getElementById('pagination').innerHTML = '';
}

function latencyCell(p) {
    if (!p.avg_latency_ms) return '<span class="muted">—</span>';
    const text = fmtMs(p.avg_latency_ms);
    return p.avg_latency_ms > 500 ? `<span class="text-warn">${text}</span>` : text;
}

function proxyRow(p) {
    return `<tr>
        <td class="col-check"><input type="checkbox" class="row-checkbox" aria-label="Select proxy"></td>
        <td><div class="mono strong truncate" data-cell="host" style="max-width:300px">${esc(p.host)}<span class="muted">:${esc(p.port)}</span></div></td>
        <td>${protoTag(p.protocol)}</td>
        <td><div class="truncate" data-cell="provider" style="max-width:180px">${p.provider ? esc(p.provider) : '<span class="muted">—</span>'}</div></td>
        <td>${statusBadge(p.last_health_status)}</td>
        <td class="num nowrap">${latencyCell(p)}</td>
        <td class="num nowrap"><span class="muted" data-cell="checked">${esc(timeAgo(p.last_health_check))}</span></td>
        <td class="actions">
            <button class="btn btn-ghost btn-sm" type="button" data-action="recheck" aria-label="Recheck" title="Recheck"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>
            <button class="btn btn-danger btn-sm" type="button" data-action="delete">Delete</button>
        </td>
    </tr>`;
}

// Anything from the API that lands in an attribute is set as a DOM property, never interpolated
function hydrateProxyRow(tr, p) {
    const addr = p.host + ':' + p.port;
    const checkbox = tr.querySelector('.row-checkbox');
    tr.dataset.id = p.id;
    checkbox.dataset.id = p.id;
    checkbox.setAttribute('aria-label', 'Select ' + addr);
    tr.querySelector('[data-cell="host"]').title = addr;
    if (p.provider) tr.querySelector('[data-cell="provider"]').title = p.provider;
    if (p.last_health_check) {
        tr.querySelector('[data-cell="checked"]').title = new Date(p.last_health_check).toLocaleString();
    }
    tr.querySelector('[data-action="recheck"]').setAttribute('aria-label', 'Recheck ' + addr);
    tr.querySelector('[data-action="delete"]').setAttribute('aria-label', 'Delete ' + addr);
}

function renderProxies(proxies) {
    const tbody = document.getElementById('proxyTableBody');
    if (proxies.length === 0) {
        tbody.innerHTML = '';
        showState(statusFilter || searchQuery ? 'nomatch' : 'empty');
        clearSelection();
        return;
    }
    showState('rows');
    tbody.innerHTML = proxies.map(proxyRow).join('');
    Array.from(tbody.rows).forEach((tr, i) => hydrateProxyRow(tr, proxies[i]));
    clearSelection();
}

function renderPagination(total, shownCount) {
    const el = document.getElementById('pagination');
    if (total === 0) { el.innerHTML = ''; return; }
    const focused = el.contains(document.activeElement) ? document.activeElement.dataset.dir : null;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const from = (currentPage - 1) * PAGE_SIZE + 1;
    const to = (currentPage - 1) * PAGE_SIZE + shownCount;
    el.innerHTML = `
        <span>Showing <span class="strong">${from.toLocaleString('en-US')}–${to.toLocaleString('en-US')}</span> of <span class="strong">${total.toLocaleString('en-US')}</span></span>
        <div class="row">
            <button class="btn btn-sm" type="button" data-dir="prev" ${currentPage <= 1 ? 'disabled' : ''} onclick="goPage(${currentPage - 1})">Previous</button>
            <span class="pagination-info">Page ${currentPage} of ${totalPages}</span>
            <button class="btn btn-sm" type="button" data-dir="next" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goPage(${currentPage + 1})">Next</button>
        </div>`;
    if (focused) {
        const again = el.querySelector(`[data-dir="${focused}"]`);
        if (again && !again.disabled) again.focus();
    }
}

/* ---------- loaders (silent: they throw, the caller decides whether to toast) ---------- */
async function loadOverview() {
    overview = await apiCall('GET', '/api/v1/stats/overview');
    renderCounts();
    renderHead();
}

async function loadProxies(background, retried) {
    loadSeq += 1;
    const seq = loadSeq;
    let url = `/api/v1/ips?page=${currentPage}&per_page=${PAGE_SIZE}`;
    if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
    if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;
    if (sortColumn) url += `&sort_by=${sortColumn}&sort_dir=${sortDir}`;
    let data;
    try {
        data = await apiCall('GET', url);
    } catch (e) {
        if (seq === loadSeq && !loadedOnce) showState('error');
        throw e;
    }
    if (seq !== loadSeq) return;                          // a newer request is on its way
    if (background && loadedOnce && isBusy()) return;     // the operator started working meanwhile
    const proxies = data.data || [];
    const total = data.meta && typeof data.meta.total === 'number' ? data.meta.total : proxies.length;
    if (proxies.length === 0 && total > 0 && currentPage > 1 && !retried) {
        // The last page emptied (deletes): step back to the new last page
        currentPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
        await loadProxies(background, true);
        return;
    }
    loadedOnce = true;
    renderProxies(proxies);
    renderPagination(total, proxies.length);
}

// After a user action: reload the table and say so if that fails
function reloadTable() {
    userLoads += 1;
    return loadProxies(false)
        .catch((e) => showToast('Failed to load proxies: ' + e.message, 'error'))
        .finally(() => { userLoads -= 1; });
}

function reloadCounts() {
    loadOverview().catch(() => { /* the status line reports outages */ });
}

function retryLoad() {
    reloadTable();
    reloadCounts();
    loadSources().catch(() => { /* the status line reports outages */ });
}

// Poller target. Never toasts; skipped while a modal is open, a row is selected,
// focus is inside the table, or a user-initiated load is still in flight.
async function refresh() {
    if (!firstRefresh && (isBusy() || userLoads > 0)) return;
    firstRefresh = false;
    const jobs = [loadProxies(true), loadOverview()];
    if (sources === null) jobs.push(loadSources());   // first run, or still missing after an outage
    await Promise.all(jobs);
}

/* ---------- row actions ---------- */
async function deleteProxy(id) {
    if (!(await confirmAction('This proxy will be permanently removed.'))) return;
    try {
        await apiCall('DELETE', `/api/v1/ips/${id}`);
        showToast('Proxy deleted', 'success');
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

async function checkProxy(id, btn) {
    btnLoading(btn);
    try {
        const result = await apiCall('POST', `/api/v1/ips/${id}/check`);
        const latency = result.latency_ms ? ` (${fmtMs(result.latency_ms)})` : '';
        showToast(`Check complete: ${result.status}${latency}`, 'success');
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Check failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

/* ---------- bulk actions ---------- */
async function bulkDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!(await confirmAction(`Delete ${ids.length} ${proxyWord(ids.length)}? This cannot be undone.`))) return;
    let deleted = 0;
    for (const id of ids) {
        try {
            await apiCall('DELETE', `/api/v1/ips/${id}`);
            deleted += 1;
        } catch (e) { /* counted as not deleted */ }
    }
    showToast(`Deleted ${deleted} ${proxyWord(deleted)}`, 'success');
    clearSelection();
    reloadTable();
    reloadCounts();
}

async function bulkRecheck() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    showToast(`Rechecking ${ids.length} ${proxyWord(ids.length)}...`, 'success');
    let done = 0;
    for (let i = 0; i < ids.length; i += 10) {
        const chunk = ids.slice(i, i + 10);
        const results = await Promise.all(chunk.map((id) =>
            apiCall('POST', `/api/v1/ips/${id}/check`).then(() => true).catch(() => false)
        ));
        done += results.filter(Boolean).length;
    }
    showToast(`Rechecked ${done} of ${ids.length} ${proxyWord(ids.length)}`, 'success');
    clearSelection();
    reloadTable();
    reloadCounts();
}

async function openMoveToPool() {
    moveIds = Array.from(selectedIds);
    if (moveIds.length === 0) return;
    const select = document.getElementById('movePoolSelect');
    select.innerHTML = '<option value="">Loading pools...</option>';
    document.getElementById('movePoolMsg').textContent =
        `Add ${moveIds.length} selected ${proxyWord(moveIds.length)} to a pool.`;
    openModal('moveToPoolModal');
    try {
        const data = await apiCall('GET', '/api/v1/pools?per_page=100');
        const pools = data.data || [];
        if (pools.length === 0) {
            select.innerHTML = '<option value="">No pools available</option>';
            return;
        }
        select.innerHTML = pools.map((p) =>
            `<option>${esc(p.name)} (${fmtNum(p.proxy_count || 0)} proxies)</option>`
        ).join('');
        Array.from(select.options).forEach((option, i) => { option.value = pools[i].id; });
    } catch (e) {
        select.innerHTML = '<option value="">Failed to load pools</option>';
        showToast('Failed to load pools: ' + e.message, 'error');
    }
}

async function confirmMoveToPool() {
    const poolId = document.getElementById('movePoolSelect').value;
    if (!poolId) { showToast('Please select a pool', 'error'); return; }
    if (moveIds.length === 0) { closeModal('moveToPoolModal'); return; }
    const btn = document.getElementById('movePoolConfirmBtn');
    btnLoading(btn);
    try {
        const result = await apiCall('POST', `/api/v1/pools/${poolId}/ips`, { proxy_ids: moveIds });
        closeModal('moveToPoolModal');
        showToast(`Added ${result.added} ${proxyWord(result.added)} to pool`, 'success');
        clearSelection();
    } catch (e) {
        showToast('Move to pool failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

function injectBulkButtons() {
    const deleteBtn = document.getElementById('bulkDeleteBtn');
    const recheckBtn = document.createElement('button');
    recheckBtn.type = 'button';
    recheckBtn.id = 'bulkRecheckBtn';
    recheckBtn.className = 'btn btn-sm';
    recheckBtn.textContent = 'Recheck';
    recheckBtn.onclick = bulkRecheck;
    const moveBtn = document.createElement('button');
    moveBtn.type = 'button';
    moveBtn.id = 'bulkMoveBtn';
    moveBtn.className = 'btn btn-sm';
    moveBtn.textContent = 'Move to pool';
    moveBtn.onclick = openMoveToPool;
    deleteBtn.parentNode.insertBefore(recheckBtn, deleteBtn);
    deleteBtn.parentNode.insertBefore(moveBtn, deleteBtn);
    deleteBtn.onclick = bulkDelete;
}

/* ---------- sources (modal) ---------- */
function lastPolledCell(s) {
    if (s.type !== 'url') return '<span class="badge badge-quiet">static</span>';
    const when = s.last_polled_at ? esc(timeAgo(s.last_polled_at)) + ' ago' : 'never';
    if (s.consecutive_failures > 0) {
        return `${when} <span class="badge badge-bad" data-cell="failing">failing</span>`;
    }
    return when;
}

function sourceRow(s) {
    const pollBtn = s.type === 'url'
        ? '<button class="btn btn-ghost btn-sm" type="button" data-action="poll" aria-label="Poll now" title="Poll now"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>'
        : '';
    return `<tr>
        <td><button class="btn btn-ghost btn-sm" type="button" data-action="copy" style="max-width:220px"><span class="mono strong truncate" data-cell="name">${esc(s.name)}</span></button></td>
        <td data-cell="type">${esc(s.type)}</td>
        <td><div class="truncate" data-cell="provider" style="max-width:130px">${s.provider ? esc(s.provider) : '<span class="muted">—</span>'}</div></td>
        <td class="nowrap">${s.created_at ? esc(fmtDate(s.created_at)) : '<span class="muted">—</span>'}</td>
        <td class="nowrap">${lastPolledCell(s)}</td>
        <td class="num strong">${fmtNum(s.proxy_count)}</td>
        <td class="actions">${pollBtn}<button class="btn btn-danger btn-sm" type="button" data-action="delete">Delete</button></td>
    </tr>`;
}

function feedUrl(s) {
    if (s.type !== 'url' || !s.url) return null;
    try {
        const parsed = new URL(s.url);
        return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null;
    } catch (e) {
        return null;
    }
}

function hydrateSourceRow(tr, s) {
    tr.dataset.id = s.id;
    tr.querySelector('[data-action="copy"]').title = s.name + '\nClick to copy';
    if (s.provider) tr.querySelector('[data-cell="provider"]').title = s.provider;
    const failing = tr.querySelector('[data-cell="failing"]');
    if (failing) {
        failing.title = s.consecutive_failures + ' failed polls in a row'
            + (s.last_status_code ? ', last HTTP ' + s.last_status_code : '');
    }
    const href = feedUrl(s);
    if (href) {
        // The type doubles as a link to the feed, as before (there is no URL column)
        const link = document.createElement('a');
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.title = s.url;
        link.textContent = s.type + ' ↗';
        const cell = tr.querySelector('[data-cell="type"]');
        cell.textContent = '';
        cell.appendChild(link);
    }
}

function renderSources() {
    const wrap = document.getElementById('sourcesTableWrap');
    const empty = document.getElementById('sourcesEmpty');
    const tbody = document.getElementById('sourcesTableBody');
    if (sources === null) {
        wrap.hidden = false;
        empty.hidden = true;
        tbody.innerHTML = '<tr><td colspan="7"><span class="muted">Sources could not be loaded.</span></td></tr>';
        return;
    }
    wrap.hidden = sources.length === 0;
    empty.hidden = sources.length > 0;
    tbody.innerHTML = sources.map(sourceRow).join('');
    Array.from(tbody.rows).forEach((tr, i) => hydrateSourceRow(tr, sources[i]));
}

async function loadSources() {
    const data = await apiCall('GET', '/api/v1/sources?per_page=100');
    sources = data.data || [];
    sourcesTotal = data.meta && typeof data.meta.total === 'number' ? data.meta.total : sources.length;
    renderSources();
    renderHead();
}

function findSource(id) {
    return (sources || []).find((s) => s.id === id) || null;
}

function openSources() {
    openModal('sourcesModal');
    document.getElementById('sourcesCloseBtn').focus();
    loadSources().catch((e) => {
        renderSources();
        showToast('Failed to load sources: ' + e.message, 'error');
    });
}

// One modal at a time: hide the Sources list, show the child, come back when the child closes
function openFromSources(childId) {
    closeModal('sourcesModal');
    openModal(childId);
    onceClosed(childId, openSources);
}

function openAddSource() {
    openFromSources('addSourceModal');
}

function toggleSourceUrl() {
    document.getElementById('sourceUrlGroup').hidden = document.getElementById('sourceType').value !== 'url';
}

function copySourceName(id, btn) {
    const source = findSource(id);
    if (!source) return;
    copyToClipboard(source.name).then((ok) => {
        if (!ok) { showToast('Copy failed, select the text manually', 'error'); return; }
        const label = btn.querySelector('[data-cell="name"]');
        label.textContent = 'Copied!';
        setTimeout(() => { label.textContent = source.name; }, 1500);
        showToast('Source name copied', 'success');
    });
}

async function createSource() {
    const name = document.getElementById('sourceName').value.trim();
    const type = document.getElementById('sourceType').value;
    const url = document.getElementById('sourceUrl').value.trim() || null;
    const protocol = document.getElementById('sourceProtocol').value;
    const provider = document.getElementById('sourceProvider').value.trim() || null;
    if (!name) { showToast('Please enter a name', 'error'); return; }
    if (type === 'url' && !url) { showToast('Please enter a URL for URL sources', 'error'); return; }
    const btn = document.getElementById('createSourceBtn');
    btnLoading(btn);
    try {
        await apiCall('POST', '/api/v1/sources', {
            name: name, type: type, url: url, provider: provider, protocol: protocol,
        });
        showToast('Source created', 'success');
        document.getElementById('sourceName').value = '';
        document.getElementById('sourceUrl').value = '';
        document.getElementById('sourceProvider').value = '';
        closeModal('addSourceModal');     // the Sources list reopens and reloads (openFromSources)
        reloadCounts();
    } catch (e) {
        showToast('Failed to create source: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

function promptDeleteSource(id) {
    const source = findSource(id);
    if (!source) return;
    deleteSourceId = id;
    document.getElementById('deleteSourceMsg').textContent =
        `This will permanently delete source "${shorten(source.name, 60)}" and all ${fmtNum(source.proxy_count || 0)} proxies imported from it. Are you sure?`;
    openFromSources('deleteSourceModal');
}

async function confirmDeleteSource() {
    if (!deleteSourceId) return;
    const btn = document.getElementById('deleteSourceConfirmBtn');
    btnLoading(btn);
    try {
        await apiCall('DELETE', `/api/v1/sources/${deleteSourceId}`);
        deleteSourceId = null;
        showToast('Source and its proxies deleted', 'success');
        closeModal('deleteSourceModal');  // the Sources list reopens and reloads (openFromSources)
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

async function pollSource(id, btn) {
    btnLoading(btn);
    showToast('Polling source...', 'success');
    try {
        await apiCall('POST', `/api/v1/sources/${id}/poll`);
        showToast('Poll complete', 'success');
        loadSources().catch(() => { /* the status line reports outages */ });
        reloadTable();
        reloadCounts();
    } catch (e) {
        showToast('Poll failed: ' + e.message, 'error');
    } finally {
        btnReset(btn);
    }
}

/* ---------- import ---------- */
function updatePoolPlaceholder() {
    const provider = document.getElementById('importProvider').value.trim();
    document.getElementById('importPoolName').placeholder =
        provider ? provider.toLowerCase().replace(/\s+/g, '-') + '-001' : 'my-provider-001';
}

function togglePoolFields() {
    document.getElementById('importPoolFields').hidden = !document.getElementById('importCreatePool').checked;
}

// Resolves 'merge', 'overwrite' or 'cancel'. One modal at a time: the import modal is
// hidden while the question is open and comes back when it is answered.
function askPoolConflict(poolName, proxyCount) {
    return new Promise((resolve) => {
        let settled = false;
        function finish(action) {
            if (settled) return;
            settled = true;
            closeModal('poolConflictModal');
            openModal('importModal');
            resolve(action);
        }
        document.getElementById('poolConflictMsg').textContent =
            `A pool named "${shorten(poolName, 60)}" already exists with ${fmtNum(proxyCount)} proxies.`;
        document.getElementById('poolConflictMerge').onclick = () => finish('merge');
        document.getElementById('poolConflictOverwrite').onclick = () => finish('overwrite');
        document.getElementById('poolConflictCancel').onclick = () => finish('cancel');
        closeModal('importModal');
        openModal('poolConflictModal');
        document.getElementById('poolConflictCancel').focus();
        onceClosed('poolConflictModal', () => finish('cancel'));   // Esc or a click outside
    });
}

function resetImportForm() {
    document.getElementById('importText').value = '';
    document.getElementById('importProvider').value = '';
    document.getElementById('importUrl').value = '';
    document.getElementById('importFile').value = '';
    document.getElementById('fileName').textContent = 'No file selected';
    document.getElementById('importCreatePool').checked = false;
    document.getElementById('importPoolName').value = '';
    togglePoolFields();
    updatePoolPlaceholder();
}

async function doImport() {
    const importBtn = document.getElementById('importBtn');
    const fileInput = document.getElementById('importFile');
    const provider = document.getElementById('importProvider').value.trim() || null;
    const importUrl = document.getElementById('importUrl').value.trim() || null;
    const createPool = document.getElementById('importCreatePool').checked;
    const poolName = document.getElementById('importPoolName').value.trim();
    const strategy = document.getElementById('importPoolStrategy').value;
    let text = document.getElementById('importText').value.trim();

    btnLoading(importBtn);
    try {
        if (!text && fileInput.files.length > 0) text = (await fileInput.files[0].text()).trim();
        if (!text && !importUrl) {
            showToast('Please paste proxies, upload a file, or enter a URL', 'error');
            return;
        }
        if (createPool && !poolName) {
            showToast('Please enter a pool name', 'error');
            return;
        }

        // Settle the pool question before anything is written, so Cancel cancels everything
        let existingPool = null;
        let poolAction = 'created';
        if (createPool) {
            try {
                const poolsData = await apiCall('GET', '/api/v1/pools?per_page=100');
                existingPool = (poolsData.data || []).find((p) => p.name === poolName) || null;
            } catch (e) { /* treated as "no such pool"; creating it reports the real error */ }
            if (existingPool) {
                const action = await askPoolConflict(poolName, existingPool.proxy_count || 0);
                if (action === 'cancel') return;
                poolAction = action === 'overwrite' ? 'overwritten' : 'merged';
            }
        }

        const payload = { provider: provider, protocol: document.getElementById('importProtocol').value };
        if (text) payload.proxies = text;
        if (importUrl) payload.url = importUrl;
        if (fileInput.files.length > 0) payload.filename = fileInput.files[0].name;
        const result = await apiCall('POST', '/api/v1/ips/bulk', payload);

        let poolMsg = '';
        if (createPool) {
            let pool = existingPool;
            if (!pool) {
                pool = await apiCall('POST', '/api/v1/pools', { name: poolName, rotation_strategy: strategy });
            } else if (poolAction === 'overwritten') {
                // Remove the pool's current members first
                try {
                    const poolIps = await apiCall('GET', `/api/v1/ips?per_page=100&pool_id=${pool.id}`);
                    const existingIds = (poolIps.data || []).map((p) => p.id);
                    if (existingIds.length > 0) {
                        await apiCall('DELETE', `/api/v1/pools/${pool.id}/ips`, { proxy_ids: existingIds });
                    }
                } catch (e) { /* as before: a failed clean-up still adds the new proxies */ }
            }
            const filterParam = provider ? `&provider=${encodeURIComponent(provider)}` : '';
            const proxyData = await apiCall('GET', `/api/v1/ips?per_page=100${filterParam}`);
            const proxyIds = (proxyData.data || []).map((p) => p.id);
            if (proxyIds.length > 0) {
                await apiCall('POST', `/api/v1/pools/${pool.id}/ips`, { proxy_ids: proxyIds });
            }
            poolMsg = `, pool "${shorten(poolName, 40)}" ${poolAction} with ${proxyIds.length} proxies`;
        }

        showToast(`Imported ${result.created} proxies` + (result.skipped ? `, ${result.skipped} skipped` : '') + poolMsg, 'success');
        closeModal('importModal');
        resetImportForm();
        reloadTable();
        reloadCounts();
        loadSources().catch(() => { /* the status line reports outages */ });
    } catch (e) {
        showToast('Import failed: ' + e.message, 'error');
    } finally {
        btnReset(importBtn);
    }
}

/* ---------- wiring ---------- */
(function init() {
    injectBulkButtons();

    document.getElementById('proxySearch').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            searchQuery = e.target.value.trim();
            syncUrl();
            currentPage = 1;
            reloadTable();
        }, 300);
    });

    document.querySelectorAll('th.sortable').forEach((th) => {
        th.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            e.preventDefault();
            toggleSort(th.dataset.sort);
        });
    });

    const proxyBody = document.getElementById('proxyTableBody');
    proxyBody.addEventListener('change', (e) => {
        if (e.target.classList.contains('row-checkbox')) toggleRowSelection(e.target.dataset.id, e.target);
    });
    proxyBody.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const id = btn.closest('tr').dataset.id;
        if (btn.dataset.action === 'recheck') checkProxy(id, btn);
        if (btn.dataset.action === 'delete') deleteProxy(id);
    });

    document.getElementById('sourcesTableBody').addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const id = btn.closest('tr').dataset.id;
        if (btn.dataset.action === 'copy') copySourceName(id, btn);
        if (btn.dataset.action === 'poll') pollSource(id, btn);
        if (btn.dataset.action === 'delete') promptDeleteSource(id);
    });

    readUrlState();
    renderPills();
    renderSortHeaders();
    syncUrl();
    openModalFromQuery({ import: 'importModal' });

    Poller.start(refresh, 15000);
})();
