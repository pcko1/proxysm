/* Projects page: project tiles on the left; the selected project's Connect
   snippet, API key and pools on the right. The selection lives in ?project=<id>. */
'use strict';

const POLL_MS = 30000;
// Project stats are built from 5-minute rollups, so refetching sooner is wasted work.
const STATS_TTL_MS = 5 * 60 * 1000;
const PROTOS = ['http', 'socks5'];
const LANGS = ['curl', 'python', 'node'];
const STATS_HINT = 'Since the oldest 5-minute metrics still kept (7 days by default)';

let projects = [];
let allPools = [];
let stats = {};
let statsLoadedAt = 0;
let selectedProjectId = new URLSearchParams(window.location.search).get('project');
let loadedOnce = false;
let loadSeq = 0;
let keyRevealed = false;
let connectProto = readPref('proxysm.connect.proto', PROTOS);
let connectLang = readPref('proxysm.connect.lang', LANGS);
let modalProjectId = null;
let modalAssigned = new Set();
const lastHtml = {};

/* ---------- small helpers ---------- */
function readPref(key, allowed) {
    try {
        const value = window.localStorage.getItem(key);
        if (allowed.includes(value)) return value;
    } catch (e) { /* storage blocked */ }
    return allowed[0];
}

function writePref(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* storage blocked */ }
}

function setVisible(el, on) {
    el.style.display = on ? '' : 'none';
}

// Skip identical re-renders so a background poll never steals focus from a button.
function setHtml(el, html) {
    if (lastHtml[el.id] === html) return;
    lastHtml[el.id] = html;
    el.innerHTML = html;
}

function selectedProject() {
    return projects.find((p) => p.id === selectedProjectId) || null;
}

function writeSelectionToUrl() {
    const params = new URLSearchParams(window.location.search);
    if (selectedProjectId) params.set('project', selectedProjectId);
    else params.delete('project');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
}

function maskKey(key) {
    return '••••••••••••' + String(key).slice(-4);
}

function copyWithFeedback(text, btn, message) {
    copyToClipboard(text).then((ok) => {
        if (!ok) { showToast('Copy failed, select the text manually', 'error'); return; }
        btn.textContent = 'Copied';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
        showToast(message);
    });
}

/* ---------- loading ---------- */
// Run by the Poller: never toasts. A failed first load shows the error tile;
// a failed later poll keeps the last good data on screen.
async function loadProjects() {
    const seq = ++loadSeq;
    const [projRes, poolRes] = await Promise.allSettled([
        apiCall('GET', '/api/v1/projects?per_page=100'),
        apiCall('GET', '/api/v1/pools?per_page=100'),
    ]);
    if (seq !== loadSeq) return;
    if (projRes.status !== 'fulfilled') {
        if (!loadedOnce) renderLoadError();
        throw projRes.reason;
    }
    projects = projRes.value.data || [];
    if (poolRes.status === 'fulfilled') allPools = poolRes.value.data || [];
    loadedOnce = true;
    if (!selectedProject()) {
        selectedProjectId = projects.length > 0 ? projects[0].id : null;
        keyRevealed = false;
        writeSelectionToUrl();
    }
    renderPage();
    await loadStats();
}

async function loadStats() {
    const stale = Date.now() - statsLoadedAt > STATS_TTL_MS;
    const ids = projects.map((p) => p.id).filter((id) => stale || !stats[id]);
    if (ids.length === 0) return;
    const results = await Promise.allSettled(
        ids.map((id) => apiCall('GET', `/api/v1/projects/${id}/stats`))
    );
    ids.forEach((id, i) => {
        if (results[i].status === 'fulfilled') stats[id] = results[i].value;
        else if (!stats[id]) stats[id] = null;
    });
    if (stale) statsLoadedAt = Date.now();
    paintStats();
}

function reloadProjects() {
    return loadProjects().catch(() => { /* the status line reports outages */ });
}

async function retryLoad(btn) {
    btnLoading(btn);
    try {
        await loadProjects();
    } catch (e) {
        showToast('Still not reachable: ' + e.message, 'error');
    }
    btnReset(btn);
}

/* ---------- rendering ---------- */
function clearListTiles() {
    document.getElementById('projectList')
        .querySelectorAll('.list-tile, .skeleton')
        .forEach((el) => el.remove());
}

function renderLoadError() {
    clearListTiles();
    delete lastHtml.projectList;
    setVisible(document.getElementById('projectsError'), true);
}

function renderPage() {
    const has = projects.length > 0;
    setVisible(document.getElementById('projectsError'), false);
    setVisible(document.getElementById('projectsEmpty'), !has);
    setVisible(document.getElementById('projectDetail'), has);
    renderList();
    if (has) renderDetail();
}

function statsLine(id) {
    const s = stats[id];
    if (s === undefined) return 'Loading…';
    if (s === null) return '—';
    if (!s.total_requests) return 'No traffic yet';
    return fmtNum(s.total_requests) + ' requests · ' + fmtPct(s.failed_requests, s.total_requests) + ' errors';
}

function renderList() {
    const html = projects.map((p) => `
        <button type="button" class="list-tile" data-project-id="${esc(p.id)}">
            <h3 class="truncate" title="${esc(p.name)}">${esc(p.name)}</h3>
            <span class="muted" title="${STATS_HINT}"></span>
        </button>`).join('');
    // The tiles are siblings of the page head inside #projectList, so replace only them.
    if (lastHtml.projectList !== html) {
        lastHtml.projectList = html;
        clearListTiles();
        document.getElementById('projectList').insertAdjacentHTML('beforeend', html);
    }
    markActiveTile();
    paintStats();
}

function markActiveTile() {
    document.querySelectorAll('#projectList .list-tile').forEach((tile) => {
        const on = tile.dataset.projectId === selectedProjectId;
        tile.classList.toggle('active', on);
        if (on) tile.setAttribute('aria-current', 'true');
        else tile.removeAttribute('aria-current');
    });
}

function paintStats() {
    document.querySelectorAll('#projectList .list-tile').forEach((tile) => {
        const line = tile.querySelector('.muted');
        if (line) line.textContent = statsLine(tile.dataset.projectId);
    });
}

function renderDetail() {
    const p = selectedProject();
    if (!p) return;
    const name = document.getElementById('detailName');
    name.textContent = p.name;
    name.title = p.name;
    document.getElementById('detailCreated').textContent = 'created ' + fmtDate(p.created_at);
    const user = document.getElementById('connectUser');
    user.textContent = p.slug;
    user.title = p.slug;
    renderSnippet();
    renderKey();
    renderPools();
}

/* ---------- Connect ---------- */
// The snippet never contains the real key: it reads PROXYSM_KEY from the
// environment, so it can be pasted into a ticket or a repo as it is.
function buildSnippet(slug, proto, lang) {
    const socks = proto === 'socks5';
    const base = (socks ? 'socks5' : 'http') + '://' + slug + ':';
    const at = '@' + APP.host + ':' + (socks ? APP.socks5Port : APP.httpPort);
    if (lang === 'python') {
        return [
            'import os, requests',
            '',
            'key = os.environ["PROXYSM_KEY"]',
            'proxy = f"' + base + '{key}' + at + '"',
            'r = requests.get("https://httpbin.org/ip", proxies={"all": proxy})',
        ].join('\n');
    }
    if (lang === 'node') {
        return (socks ? [
            'import { SocksProxyAgent } from "socks-proxy-agent";',
            '',
            'const key = process.env.PROXYSM_KEY;',
            'const url = `' + base + '${key}' + at + '`;',
            'const agent = new SocksProxyAgent(url);',
            'const res = await fetch("https://httpbin.org/ip", { agent });',
        ] : [
            'import { ProxyAgent, fetch } from "undici";',
            '',
            'const key = process.env.PROXYSM_KEY;',
            'const url = `' + base + '${key}' + at + '`;',
            'const dispatcher = new ProxyAgent(url);',
            'const res = await fetch("https://httpbin.org/ip", { dispatcher });',
        ]).join('\n');
    }
    return [
        'curl --proxy ' + base + '$PROXYSM_KEY' + at + ' \\',
        '     https://httpbin.org/ip',
    ].join('\n');
}

function syncSeg(rootId, attr, current) {
    document.querySelectorAll('#' + rootId + ' button').forEach((btn) => {
        const on = btn.dataset[attr] === current;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-pressed', String(on));
    });
}

function renderSnippet() {
    const p = selectedProject();
    syncSeg('protoSeg', 'proto', connectProto);
    syncSeg('langSeg', 'lang', connectLang);
    // Only the <code> child is rewritten, and only with textContent: the Copy button
    // that addCopyButtons() appended to the .code-block stays in place.
    document.getElementById('connectCode').textContent = p ? buildSnippet(p.slug, connectProto, connectLang) : '';
}

function renderKey() {
    const p = selectedProject();
    const hasKey = Boolean(p && p.api_key);
    if (!hasKey) keyRevealed = false;
    const value = document.getElementById('keyValue');
    value.classList.toggle('mono', hasKey);
    value.classList.toggle('muted', !hasKey);
    if (hasKey) value.textContent = keyRevealed ? p.api_key : maskKey(p.api_key);
    else value.textContent = 'Not available. Rotate to get a new key.';
    const reveal = document.getElementById('keyRevealBtn');
    setVisible(reveal, hasKey);
    reveal.textContent = keyRevealed ? 'Hide' : 'Reveal';
    reveal.setAttribute('aria-pressed', String(keyRevealed));
    setVisible(document.getElementById('keyCopyBtn'), hasKey && keyRevealed);
}

function toggleKeyReveal() {
    keyRevealed = !keyRevealed;
    renderKey();
}

function copyKey(btn) {
    const p = selectedProject();
    if (!p || !p.api_key) return;
    copyWithFeedback(p.api_key, btn, 'API key copied');
}

async function rotateKey() {
    const p = selectedProject();
    if (!p) return;
    const question = `Generate a new API key for "${p.name}"? The current key stops working immediately.`;
    if (!(await confirmAction(question, 'Rotate API key?', 'Rotate'))) return;
    const btn = document.getElementById('keyRotateBtn');
    btnLoading(btn);
    try {
        const result = await apiCall('POST', `/api/v1/projects/${p.id}/rotate-key`);
        if (result && result.api_key) {
            p.api_key = result.api_key;
            showApiKey(p.name, result.api_key);
        }
        keyRevealed = false;
        renderKey();
        showToast('API key rotated');
    } catch (e) {
        showToast('Failed to rotate key: ' + e.message, 'error');
    }
    btnReset(btn);
}

/* ---------- new-key banner ---------- */
function showApiKey(projectName, key) {
    document.getElementById('apiKeyProject').textContent = projectName;
    document.getElementById('apiKeyValue').textContent = key;
    const alertBox = document.getElementById('apiKeyAlert');
    setVisible(alertBox, true);
    alertBox.scrollIntoView({ block: 'nearest' });
}

function copyApiKey(btn) {
    copyWithFeedback(document.getElementById('apiKeyValue').textContent, btn, 'API key copied');
}

function dismissApiKeyAlert() {
    setVisible(document.getElementById('apiKeyAlert'), false);
    document.getElementById('apiKeyValue').textContent = '';
}

/* ---------- Pools ---------- */
// Pools nested in a project carry no counts (the API leaves them null), so join
// them with the full pool list, which has proxy_count and healthy_count.
function poolsOf(project) {
    const byId = {};
    allPools.forEach((pool) => { byId[pool.id] = pool; });
    return (project.pools || []).map((pool) => byId[pool.id] || pool);
}

function healthBadge(pool) {
    const total = pool.proxy_count;
    const healthy = pool.healthy_count;
    if (total === null || total === undefined || healthy === null || healthy === undefined) {
        return '<span class="muted">—</span>';
    }
    const cls = total > 0 && healthy === 0 ? 'badge-bad' : 'badge-quiet';
    return `<span class="badge ${cls}">${esc(fmtNum(healthy))} / ${esc(fmtNum(total))} healthy</span>`;
}

function renderPools() {
    const p = selectedProject();
    const pools = p ? poolsOf(p) : [];
    setVisible(document.getElementById('projectPoolsTable'), pools.length > 0);
    setVisible(document.getElementById('projectPoolsEmpty'), pools.length === 0);
    setHtml(document.getElementById('projectPoolsBody'), pools.map((pool) => `
        <tr>
            <td class="strong"><div class="truncate" style="max-width:340px" title="${esc(pool.name)}">${esc(pool.name)}</div></td>
            <td><span class="muted">${esc(pool.rotation_strategy)}</span></td>
            <td>${healthBadge(pool)}</td>
            <td class="actions"><button class="btn btn-ghost btn-sm" type="button" data-remove-pool="${esc(pool.id)}" aria-label="Remove ${esc(pool.name)} from this project">Remove</button></td>
        </tr>`).join(''));
}

async function removePool(poolId, btn) {
    const p = selectedProject();
    if (!p) return;
    const pool = poolsOf(p).find((x) => x.id === poolId);
    const question = `Remove "${pool ? pool.name : 'this pool'}" from "${p.name}"? Requests will stop using it.`;
    if (!(await confirmAction(question, 'Remove pool?', 'Remove'))) return;
    btnLoading(btn);
    try {
        await apiCall('DELETE', `/api/v1/projects/${p.id}/pools/${poolId}`);
        showToast('Pool removed');
    } catch (e) {
        showToast('Remove failed: ' + e.message, 'error');
    }
    btnReset(btn);
    reloadProjects();
}

async function openManagePools() {
    const p = selectedProject();
    if (!p) return;
    try {
        const [poolsData, fresh] = await Promise.all([
            apiCall('GET', '/api/v1/pools?per_page=100'),
            apiCall('GET', `/api/v1/projects/${p.id}`),
        ]);
        allPools = poolsData.data || [];
        modalProjectId = p.id;
        modalAssigned = new Set((fresh.pools || []).map((pool) => pool.id));
        document.getElementById('managePoolsInfo').textContent = 'Tick the pools that "' + p.name + '" may use.';
        const box = document.getElementById('poolCheckboxes');
        if (allPools.length === 0) {
            box.innerHTML = '<p class="muted">No pools exist yet. <a href="/pools?new=1">Create a pool</a> first.</p>';
        } else {
            box.innerHTML = allPools.map((pool) => `
                <label for="poolcb-${esc(pool.id)}">
                    <input type="checkbox" id="poolcb-${esc(pool.id)}" value="${esc(pool.id)}"${modalAssigned.has(pool.id) ? ' checked' : ''}>
                    <span class="strong truncate spacer" title="${esc(pool.name)}">${esc(pool.name)}</span>
                    <span class="muted">${esc(fmtNum(pool.proxy_count || 0))} proxies · ${esc(pool.rotation_strategy)}</span>
                </label>`).join('');
        }
        document.getElementById('savePoolsBtn').disabled = allPools.length === 0;
        openModal('managePoolsModal');
    } catch (e) {
        showToast('Failed to load pools: ' + e.message, 'error');
    }
}

// POST /pools only ever adds, so removals go through DELETE one by one.
async function savePoolAssignments() {
    if (!modalProjectId) return;
    const checked = new Set(
        Array.from(document.querySelectorAll('#poolCheckboxes input[type="checkbox"]'))
            .filter((box) => box.checked)
            .map((box) => box.value)
    );
    const adds = Array.from(checked).filter((id) => !modalAssigned.has(id));
    const removes = Array.from(modalAssigned).filter((id) => !checked.has(id));
    if (adds.length === 0 && removes.length === 0) {
        closeModal('managePoolsModal');
        return;
    }
    const btn = document.getElementById('savePoolsBtn');
    btnLoading(btn);
    try {
        if (adds.length > 0) {
            await apiCall('POST', `/api/v1/projects/${modalProjectId}/pools`, { pool_ids: adds });
        }
        for (const poolId of removes) {
            await apiCall('DELETE', `/api/v1/projects/${modalProjectId}/pools/${poolId}`);
        }
        showToast('Pools updated');
        closeModal('managePoolsModal');
    } catch (e) {
        showToast('Update failed: ' + e.message, 'error');
    }
    btnReset(btn);
    reloadProjects();
}

/* ---------- create, select, delete ---------- */
async function createProject() {
    const input = document.getElementById('projectName');
    const name = input.value.trim();
    if (!name) { showToast('Project name is required', 'error'); return; }
    const btn = document.getElementById('createProjectBtn');
    btnLoading(btn);
    try {
        const result = await apiCall('POST', '/api/v1/projects', { name: name });
        closeModal('createProjectModal');
        input.value = '';
        if (result.api_key) showApiKey(result.name, result.api_key);
        // Show it at once (the list is newest first); the reload below confirms it.
        projects = [result].concat(projects.filter((x) => x.id !== result.id));
        selectedProjectId = result.id;
        keyRevealed = false;
        writeSelectionToUrl();
        renderPage();
        showToast('Project created');
        reloadProjects();
    } catch (e) {
        showToast('Create failed: ' + e.message, 'error');
    }
    btnReset(btn);
}

function selectProject(id) {
    if (id === selectedProjectId) return;
    selectedProjectId = id;
    keyRevealed = false;
    writeSelectionToUrl();
    markActiveTile();
    renderDetail();
}

async function deleteProject() {
    const p = selectedProject();
    if (!p) return;
    const question = `Delete "${p.name}"? Its API key stops working immediately.`;
    if (!(await confirmAction(question, 'Delete project?', 'Delete'))) return;
    const btn = document.getElementById('deleteProjectBtn');
    btnLoading(btn);
    try {
        await apiCall('DELETE', `/api/v1/projects/${p.id}`);
        const idx = projects.findIndex((x) => x.id === p.id);
        const next = projects[idx + 1] || projects[idx - 1] || null;
        projects = projects.filter((x) => x.id !== p.id);
        delete stats[p.id];
        selectedProjectId = next ? next.id : null;
        keyRevealed = false;
        writeSelectionToUrl();
        renderPage();
        showToast('Project deleted');
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
    btnReset(btn);
    reloadProjects();
}

/* ---------- wiring ---------- */
document.getElementById('projectList').addEventListener('click', (e) => {
    const tile = e.target.closest('.list-tile');
    if (tile) selectProject(tile.dataset.projectId);
});

document.getElementById('projectPoolsBody').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-remove-pool]');
    if (btn) removePool(btn.dataset.removePool, btn);
});

document.getElementById('protoSeg').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-proto]');
    if (!btn || !PROTOS.includes(btn.dataset.proto)) return;
    connectProto = btn.dataset.proto;
    writePref('proxysm.connect.proto', connectProto);
    renderSnippet();
});

document.getElementById('langSeg').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-lang]');
    if (!btn || !LANGS.includes(btn.dataset.lang)) return;
    connectLang = btn.dataset.lang;
    writePref('proxysm.connect.lang', connectLang);
    renderSnippet();
});

openModalFromQuery({ new: 'createProjectModal' });
renderSnippet();
Poller.start(loadProjects, POLL_MS);
