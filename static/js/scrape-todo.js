(function () {
    'use strict';

    const TYPE_COLORS = {
        coverage: { bg: '#fef9c3', color: '#854d0e' },
        rejection: { bg: '#fee2e2', color: '#991b1b' },
        both: { bg: '#f5f3ff', color: '#6d28d9' },
    };

    let allTargets = [];
    let currentFilter = 'all';

    const targetsBody = document.getElementById('targets-body');
    const targetCount = document.getElementById('target-count');
    const typeFilter = document.getElementById('type-filter');
    const copyCoverageBtn = document.getElementById('copy-coverage-btn');
    const copyAllBtn = document.getElementById('copy-all-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const emptyState = document.getElementById('empty-state');
    const errorState = document.getElementById('error-state');
    const tableContainer = document.getElementById('table-container');
    const toast = document.getElementById('toast');

    let toastTimer;
    function showToast(msg) {
        toast.textContent = msg;
        toast.style.transform = 'translateX(-50%) translateY(0)';
        toast.style.opacity = '1';
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toast.style.transform = 'translateX(-50%) translateY(100px)';
            toast.style.opacity = '0';
        }, 1500);
    }

    function copyToClipboard(text) {
        if (navigator.clipboard) {
            return navigator.clipboard.writeText(text);
        }
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        return Promise.resolve();
    }

    function showSkeleton() {
        targetsBody.innerHTML = '<tr><td colspan="5"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></td></tr>';
        tableContainer.style.display = 'block';
        emptyState.style.display = 'none';
        errorState.style.display = 'none';
    }

    function showEmpty() {
        targetsBody.innerHTML = '';
        tableContainer.style.display = 'none';
        emptyState.style.display = 'block';
        errorState.style.display = 'none';
    }

    function showError() {
        targetsBody.innerHTML = '';
        tableContainer.style.display = 'none';
        emptyState.style.display = 'none';
        errorState.style.display = 'block';
    }

    function priorityBar(score) {
        const pct = Math.min(100, Math.round(score * 100));
        let cls = 'progress-fill-low';
        if (pct >= 50) cls = 'progress-fill-mid';
        if (pct >= 80) cls = 'progress-fill-good';
        return '<div style="display:flex;align-items:center;gap:8px"><div class="progress-bar" style="flex:1;height:5px"><div class="progress-fill ' + cls + '" style="width:' + pct + '%"></div></div><span style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted);min-width:32px;text-align:right">' + pct + '</span></div>';
    }

    function typeBadge(type) {
        const c = TYPE_COLORS[type] || TYPE_COLORS.coverage;
        return '<span class="badge" style="background:' + c.bg + ';color:' + c.color + '">' + type + '</span>';
    }

    function escHtml(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function escAttr(s) {
        return String(s).replace(/"/g, '&quot;');
    }

    function renderRow(target) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td>' + typeBadge(target.type) + '</td>' +
            '<td><span class="query-text" style="cursor:pointer;font-family:var(--font-mono);font-size:13px;color:var(--text);padding:2px 6px;border-radius:4px;background:var(--bg);transition:background 0.15s" title="Click to copy">' + escHtml(target.query) + '</span></td>' +
            '<td>' + priorityBar(target.priority_score) + '</td>' +
            '<td style="font-size:13px;color:var(--text-muted)">' + escHtml(target.reason) + '</td>' +
            '<td><button class="btn btn-ghost btn-icon copy-btn" style="width:32px;height:32px;padding:6px" title="Copy query"><svg class="icon" aria-hidden="true" style="width:14px;height:14px"><use href="/static/svg/icons.svg#icon-external-link"/></svg></button></td>';
        tr.querySelector('.query-text').addEventListener('click', function () { copyToClipboard(target.query).then(function () { showToast('Query copied!'); }); });
        tr.querySelector('.copy-btn').addEventListener('click', function () { copyToClipboard(target.query).then(function () { showToast('Query copied!'); }); });
        return tr;
    }

    function render() {
        const filtered = allTargets.filter(function (t) { return currentFilter === 'all' || t.type === currentFilter; });
        if (filtered.length === 0) { showEmpty(); return; }
        targetsBody.innerHTML = '';
        filtered.forEach(function (t) { targetsBody.appendChild(renderRow(t)); });
        tableContainer.style.display = 'block';
        emptyState.style.display = 'none';
        errorState.style.display = 'none';
    }

    async function fetchTargets() {
        showSkeleton();
        try {
            const resp = await fetch('/api/scrape-todo');
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const data = await resp.json();
            allTargets = data.targets || [];
            targetCount.textContent = allTargets.length;
            render();
        } catch (e) {
            showError();
        }
    }

    function bulkCopy(type) {
        const filtered = allTargets.filter(function (t) { return type === 'all' || t.type === type; });
        if (filtered.length === 0) return;
        const text = filtered.map(function (t) { return t.query; }).join('\n');
        copyToClipboard(text).then(function () { showToast(filtered.length + ' queries copied!'); });
    }

    typeFilter.addEventListener('change', function () { currentFilter = typeFilter.value; render(); });
    copyCoverageBtn.addEventListener('click', function () { bulkCopy('coverage'); });
    copyAllBtn.addEventListener('click', function () { bulkCopy('all'); });
    refreshBtn.addEventListener('click', fetchTargets);

    fetchTargets();
})();
