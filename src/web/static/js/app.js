/* Proxysm shared UI helpers. Loaded on every page before the page script.
   Everything here is a global on purpose: templates use inline handlers and
   page scripts are classic scripts, not modules. */
'use strict';

const APP = {
    httpPort: document.body.dataset.httpPort || '',
    socks5Port: document.body.dataset.socks5Port || '',
    host: window.location.hostname,
};

/* ---------- formatting ---------- */
// Safe for element content AND for quoted attribute values (title="...", data-x="...").
function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtNum(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    const v = Number(n);
    const a = Math.abs(v);
    const trim = (x) => x.toFixed(1).replace(/\.0$/, '');
    if (a >= 1e9) return trim(v / 1e9) + 'B';
    if (a >= 1e6) return trim(v / 1e6) + 'M';
    if (a >= 1e4) return Math.round(v / 1e3) + 'K';
    return Math.round(v).toLocaleString('en-US');
}

function fmtBytes(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let v = Number(n);
    let i = 0;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
    const text = i === 0 || v >= 100 ? String(Math.round(v)) : v.toFixed(1).replace(/\.0$/, '');
    return text + ' ' + units[i];
}

function fmtMs(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    return Math.round(Number(n)).toLocaleString('en-US') + ' ms';
}

function fmtPct(part, total, digits) {
    if (!total) return '—';
    return ((Number(part) / Number(total)) * 100).toFixed(digits === undefined ? 1 : digits) + '%';
}

function fmtDate(iso) {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function timeAgo(iso) {
    if (!iso) return 'never';
    const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    return Math.floor(s / 86400) + 'd';
}

function protoTag(protocol) {
    const p = esc(protocol);
    return `<span class="tag tag-${p}">${p}</span>`;
}

function statusBadge(status) {
    const known = ['healthy', 'degraded', 'dead', 'unknown'];
    const s = known.includes(status) ? status : 'unknown';
    return `<span class="badge badge-${s}">${s}</span>`;
}

/* ---------- connection status (sidebar) ---------- */
const Status = (() => {
    let lastOk = null;
    let down = false;
    function render() {
        const root = document.getElementById('navStatus');
        const text = document.getElementById('navStatusText');
        if (!root || !text) return;
        // Hidden until the page has made its first API call (the 404 page never does).
        root.hidden = !down && lastOk === null;
        root.classList.toggle('is-offline', down);
        if (down) { text.textContent = 'Offline, retrying'; return; }
        if (lastOk === null) return;
        const age = Math.round((Date.now() - lastOk) / 1000);
        text.textContent = age < 2 ? 'Updated just now' : 'Updated ' + timeAgo(new Date(lastOk).toISOString()) + ' ago';
    }
    setInterval(render, 1000);
    return {
        ok() { lastOk = Date.now(); down = false; render(); },
        offline() { down = true; render(); },
        isOffline() { return down; },
    };
})();

/* ---------- API ---------- */
let redirectingToLogin = false;

async function apiCall(method, url, body) {
    const opts = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined && body !== null) opts.body = JSON.stringify(body);
    let resp;
    try {
        resp = await fetch(url, opts);
    } catch (e) {
        Status.offline();
        throw e;
    }
    if (resp.status === 401) {
        if (!redirectingToLogin) {
            redirectingToLogin = true;
            window.location.href = '/login';
        }
        throw new Error('Session expired');
    }
    if (resp.status >= 500) {
        Status.offline();
    } else {
        Status.ok();
    }
    if (!resp.ok) {
        let msg = 'Error ' + resp.status;
        try {
            const data = await resp.json();
            msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data);
        } catch (e) { /* non-JSON error body */ }
        throw new Error(msg);
    }
    if (resp.status === 204) return null;
    return resp.json();
}

/* ---------- polling ---------- */
const Poller = (() => {
    let timer = null;
    let fn = null;
    let running = false;
    async function tick() {
        if (!fn || running || document.hidden) return;
        running = true;
        try { await fn(); } catch (e) { /* the status line reports outages */ } finally { running = false; }
    }
    function stop() {
        if (timer) clearInterval(timer);
        timer = null;
    }
    function start(f, ms) {
        stop();
        fn = f;
        tick();
        timer = setInterval(tick, ms);
    }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
    return { start: start, stop: stop, refresh: tick };
})();

/* ---------- toasts ---------- */
function showToast(message, type) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const kind = type === 'error' ? 'error' : 'success';
    const el = document.createElement('div');
    el.className = 'toast toast-' + kind;
    el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.style.transition = 'opacity 0.2s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 200);
    }, 3500);
}

/* ---------- modals ---------- */
let lastFocusBeforeModal = null;

function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    lastFocusBeforeModal = document.activeElement;
    modal.classList.add('active');
    setTimeout(() => {
        const field = modal.querySelector('input:not([type="hidden"]):not([type="file"]), textarea, select');
        if (field) field.focus();
    }, 60);
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('active');
    if (lastFocusBeforeModal && document.contains(lastFocusBeforeModal)) lastFocusBeforeModal.focus();
    lastFocusBeforeModal = null;
}

function openModalFromQuery(map) {
    const params = new URLSearchParams(window.location.search);
    let opened = false;
    Object.keys(map).forEach((param) => {
        if (!params.has(param)) return;
        if (!opened) { openModal(map[param]); opened = true; }
        params.delete(param);
    });
    if (opened) {
        const qs = params.toString();
        history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    }
}

function confirmAction(message, title, okLabel) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        const ok = document.getElementById('confirmOkBtn');
        const cancel = document.getElementById('confirmCancelBtn');
        document.getElementById('confirmMessage').textContent = message;
        document.getElementById('confirmTitle').textContent = title || 'Are you sure?';
        ok.textContent = okLabel || 'Delete';
        modal.classList.add('active');
        cancel.focus();
        function done(result) {
            modal.classList.remove('active');
            ok.removeEventListener('click', onOk);
            cancel.removeEventListener('click', onCancel);
            resolve(result);
        }
        function onOk() { done(true); }
        function onCancel() { done(false); }
        ok.addEventListener('click', onOk);
        cancel.addEventListener('click', onCancel);
    });
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),'
    + ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Keeps Tab inside the open dialog: without this, Tab walks on to the page behind the
// overlay and a keyboard user loses their place.
function trapFocus(e) {
    const modal = document.querySelector('.modal-overlay.active .modal');
    if (!modal) return;
    const items = Array.from(modal.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null);
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (!modal.contains(document.activeElement)) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus();
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
    } else if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
        trapFocus(e);
        return;
    }
    if (e.key === 'Escape') {
        const confirmModal = document.getElementById('confirmModal');
        if (confirmModal && confirmModal.classList.contains('active')) {
            document.getElementById('confirmCancelBtn').click();
            return;
        }
        const active = document.querySelector('.modal-overlay.active');
        if (active) closeModal(active.id);
        return;
    }
    // Enter submits the modal from a field; on a focused button or link it keeps its normal
    // meaning (otherwise Enter on Cancel would save).
    if (e.key === 'Enter' && !['TEXTAREA', 'BUTTON', 'A'].includes(e.target.tagName)) {
        const modal = e.target.closest ? e.target.closest('.modal-overlay.active') : null;
        if (!modal || modal.id === 'confirmModal') return;
        const primary = modal.querySelector('.modal-actions .btn-primary');
        if (primary && !primary.disabled) { e.preventDefault(); primary.click(); }
    }
});

document.addEventListener('click', (e) => {
    const t = e.target;
    if (!t.classList || !t.classList.contains('modal-overlay') || !t.classList.contains('active')) return;
    if (t.id === 'confirmModal') document.getElementById('confirmCancelBtn').click();
    else closeModal(t.id);
});

/* ---------- buttons ---------- */
function btnLoading(btn) { if (btn) { btn.disabled = true; btn.classList.add('btn-loading'); } }
function btnReset(btn) { if (btn) { btn.disabled = false; btn.classList.remove('btn-loading'); } }

/* ---------- clipboard ---------- */
// navigator.clipboard needs a secure context (HTTPS or localhost); on plain-HTTP
// origins fall back to a hidden textarea.
async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (e) { /* fall through */ }
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
}

function addCopyButtons() {
    document.querySelectorAll('.code-block').forEach((block) => {
        if (block.dataset.copyReady) return;
        block.dataset.copyReady = '1';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'copy-btn';
        btn.textContent = 'Copy';
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const clone = block.cloneNode(true);
            clone.querySelectorAll('.copy-btn').forEach((b) => b.remove());
            copyToClipboard(clone.textContent.trim()).then((ok) => {
                if (!ok) { showToast('Copy failed, select the text manually', 'error'); return; }
                btn.textContent = 'Copied';
                setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            });
        });
        block.appendChild(btn);
    });
}

/* ---------- table selection ---------- */
let selectedIds = new Set();

function updateBulkBar() {
    const bar = document.getElementById('bulkBar');
    if (!bar) return;
    const count = selectedIds.size;
    document.getElementById('bulkCount').textContent = count + ' selected';
    bar.classList.toggle('visible', count > 0);
    bar.setAttribute('aria-hidden', String(count === 0));
}

function toggleRowSelection(id, checkbox) {
    const row = checkbox.closest('tr');
    if (checkbox.checked) { selectedIds.add(id); row.classList.add('selected'); }
    else { selectedIds.delete(id); row.classList.remove('selected'); }
    updateSelectAll();
    updateBulkBar();
}

function toggleSelectAll(master) {
    document.querySelectorAll('tbody .row-checkbox').forEach((cb) => {
        cb.checked = master.checked;
        const row = cb.closest('tr');
        if (master.checked) { selectedIds.add(cb.dataset.id); row.classList.add('selected'); }
        else { selectedIds.delete(cb.dataset.id); row.classList.remove('selected'); }
    });
    updateBulkBar();
}

function updateSelectAll() {
    const master = document.getElementById('selectAll');
    if (!master) return;
    const boxes = Array.from(document.querySelectorAll('tbody .row-checkbox'));
    const all = boxes.length > 0 && boxes.every((cb) => cb.checked);
    master.checked = all;
    master.indeterminate = !all && boxes.some((cb) => cb.checked);
}

function clearSelection() {
    selectedIds.clear();
    document.querySelectorAll('.row-checkbox').forEach((cb) => {
        cb.checked = false;
        const row = cb.closest('tr');
        if (row) row.classList.remove('selected');
    });
    const master = document.getElementById('selectAll');
    if (master) { master.checked = false; master.indeterminate = false; }
    updateBulkBar();
}

/* ---------- misc ---------- */
function updateFileInput(input, nameSpan) {
    nameSpan.textContent = input.files.length > 0 ? input.files[0].name : 'No file selected';
}

(function initShell() {
    const toggle = document.getElementById('navToggle');
    const nav = document.getElementById('sideNav');
    if (toggle && nav) {
        toggle.addEventListener('click', () => {
            const open = nav.classList.toggle('open');
            toggle.setAttribute('aria-expanded', String(open));
        });
    }
    // Clicking the page you are already on is a no-op, not a reload
    document.querySelectorAll('.shell-nav a.nav-item').forEach((link) => {
        link.addEventListener('click', (e) => {
            if (window.location.pathname === link.getAttribute('href')) e.preventDefault();
        });
    });
    addCopyButtons();
    new MutationObserver(addCopyButtons).observe(document.body, { childList: true, subtree: true });
})();
