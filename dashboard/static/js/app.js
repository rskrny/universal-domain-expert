/* Neural Net Dashboard v2 - Command Station */

// ==================== COLOR UTILITIES ====================
const DOMAIN_COLOR_CACHE = {};
function domainColor(d) {
    if (!d || d === 'shared') return '#78909c';
    if (DOMAIN_COLOR_CACHE[d]) return DOMAIN_COLOR_CACHE[d];
    let hash = 0;
    for (let i = 0; i < d.length; i++) hash = d.charCodeAt(i) + ((hash << 5) - hash);
    const hue = Math.abs(hash) % 360;
    DOMAIN_COLOR_CACHE[d] = `hsl(${hue}, 65%, 65%)`;
    return DOMAIN_COLOR_CACHE[d];
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true, gfm: true });
        return marked.parse(text);
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

// ==================== STATE ====================
const state = {
    treemapData: null,
    refreshInterval: null,
    searchTimeout: null,
};

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', async () => {
    initTabs();
    initSearch();
    await Promise.all([
        loadStats(),
        loadCommandCenter(),
        loadGraph(),
        loadProjects(),
        loadFinances(),
        loadGoals(),
    ]);
    startAutoRefresh();
});

// ==================== TABS ====================
function initTabs() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });
}

// ==================== AUTO REFRESH ====================
function startAutoRefresh() {
    // Refresh command center every 60 seconds
    state.refreshInterval = setInterval(() => {
        const activeTab = document.querySelector('.nav-tab.active');
        if (activeTab && activeTab.dataset.tab === 'command') {
            loadCommandCenter();
        }
    }, 60000);

    // Manual refresh button
    document.getElementById('cmd-refresh-btn').addEventListener('click', () => {
        loadCommandCenter();
        loadStats();
    });
}

// ==================== GLOBAL SEARCH ====================
function initSearch() {
    const input = document.getElementById('global-search');
    const dropdown = document.getElementById('search-results');

    input.addEventListener('input', () => {
        clearTimeout(state.searchTimeout);
        const q = input.value.trim();
        if (q.length < 2) {
            dropdown.classList.remove('visible');
            return;
        }
        state.searchTimeout = setTimeout(async () => {
            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&top_k=8`);
                const data = await res.json();
                renderSearchResults(data.results || [], q);
            } catch (e) {
                dropdown.classList.remove('visible');
            }
        }, 300);
    });

    input.addEventListener('blur', () => {
        setTimeout(() => dropdown.classList.remove('visible'), 200);
    });

    input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2 && dropdown.children.length > 0) {
            dropdown.classList.add('visible');
        }
    });
}

function renderSearchResults(results, query) {
    const dropdown = document.getElementById('search-results');
    if (!results.length) {
        dropdown.innerHTML = '<div class="search-empty">No results</div>';
        dropdown.classList.add('visible');
        return;
    }
    dropdown.innerHTML = results.map(r => `
        <div class="search-item" data-domain="${r.domain || ''}">
            <div class="search-item-header">
                <span class="search-domain" style="color:${domainColor(r.domain)}">${escapeHtml(r.domain || 'general')}</span>
                <span class="search-score">${(r.score * 100).toFixed(0)}%</span>
            </div>
            <div class="search-item-text">${escapeHtml((r.text || '').slice(0, 120))}...</div>
            <div class="search-item-source">${escapeHtml(r.source_file || '')}</div>
        </div>
    `).join('');
    dropdown.classList.add('visible');

    // Click to show detail
    dropdown.querySelectorAll('.search-item').forEach((item, i) => {
        item.addEventListener('mousedown', (e) => {
            e.preventDefault();
            const r = results[i];
            showNodeDetail({
                label: r.source_file?.split('/').pop() || 'Result',
                domain: r.domain,
                source_file: r.source_file,
                chunk_count: 1,
                content_type: r.domain,
                tokens: r.text?.length / 4 || 0,
                preview: r.text,
            });
        });
    });
}

// ==================== STATS ====================
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('header-chunks').textContent = data.total_chunks || 0;
        document.getElementById('header-domains').textContent = data.domain_count || 0;

        // Update system status indicators
        updateSystemStatus(data);
    } catch (e) { console.warn('Stats load failed:', e); }
}

function updateSystemStatus(stats) {
    const setDot = (id, isActive) => {
        const el = document.getElementById(id);
        if (!el) return;
        const dot = el.querySelector('.status-dot');
        if (dot) {
            dot.className = 'status-dot ' + (isActive ? 'green' : 'gray');
        }
    };
    setDot('status-search', stats.total_chunks > 0);
    setDot('status-embeddings', stats.semantic_enabled === 'True' || stats.semantic_enabled === true);
    setDot('status-reranker', stats.reranker_ready || false);
    setDot('status-reddit', stats.reddit_configured || false);
    setDot('status-brainfeed', stats.brainfeed_configured || false);
}

// ==================== COMMAND CENTER ====================
async function loadCommandCenter() {
    try {
        const [projRes, healthRes] = await Promise.all([
            fetch('/api/projects/live'),
            fetch('/api/agents/health'),
        ]);
        const projects = await projRes.json();
        const health = await healthRes.json();
        renderCommandCenter(projects, health);
        renderAlerts(projects);
    } catch (e) { console.warn('Command center load failed:', e); }
}

function renderAlerts(projects) {
    const section = document.getElementById('alerts-section');
    const alerts = [];

    // Hardcoded critical deadlines (from compliance calendar)
    const today = new Date();
    const apr15 = new Date('2026-04-15');
    const daysTo5471 = Math.ceil((apr15 - today) / (1000 * 60 * 60 * 24));
    if (daysTo5471 > 0 && daysTo5471 <= 30) {
        alerts.push({
            text: `FORM 5471 DUE IN ${daysTo5471} DAYS. $10,000 penalty for non-filing.`,
            level: daysTo5471 <= 7 ? 'error' : 'warning'
        });
    }

    projects.forEach(p => {
        if (!p.latest_agent_run) return;
        const findings = p.latest_agent_run.findings || {};
        const actions = findings.action_items || [];
        actions.forEach(a => {
            if (a.startsWith('OVERDUE') || a.startsWith('URGENT') || a.startsWith('SITE DOWN') || a.startsWith('CRITICAL')) {
                const level = (a.startsWith('OVERDUE') || a.startsWith('SITE DOWN') || a.startsWith('CRITICAL')) ? 'error' : 'warning';
                alerts.push({ text: `${p.name}: ${a}`, level });
            }
        });
    });

    if (!alerts.length) {
        section.innerHTML = '';
        return;
    }

    section.innerHTML = alerts.map(a =>
        `<div class="alert-item ${a.level}">${escapeHtml(a.text)}</div>`
    ).join('');
}

function renderCommandCenter(projects, health) {
    health = health || {};
    const grid = document.getElementById('command-center-grid');
    if (!projects || !projects.length) {
        grid.innerHTML = '<div class="empty-state">No projects registered.</div>';
        return;
    }

    grid.innerHTML = projects.map(p => {
        let dotClass = 'gray';
        if (p.latest_agent_run) {
            const findings = p.latest_agent_run.findings || {};
            const healthInfo = findings.site_health;
            const actions = findings.action_items || [];
            if (p.latest_agent_run.status === 'error') dotClass = 'red';
            else if (healthInfo && !healthInfo.healthy) dotClass = 'red';
            else if (actions.some(a => a.startsWith('OVERDUE') || a.startsWith('SITE DOWN'))) dotClass = 'red';
            else if (actions.some(a => a.startsWith('URGENT'))) dotClass = 'yellow';
            else if (actions.length > 0) dotClass = 'yellow';
            else dotClass = 'green';
        } else if (p.has_agent) {
            dotClass = 'gray';
        }

        // Metrics row
        const metrics = [];
        if (p.revenue_monthly) metrics.push(`<span class="cmd-metric revenue">$${p.revenue_monthly}/mo</span>`);
        if (p.task_pending) {
            const cls = p.task_overdue > 0 ? 'overdue' : '';
            metrics.push(`<span class="cmd-metric ${cls}">${p.task_pending} tasks${p.task_overdue ? ` (${p.task_overdue} overdue)` : ''}</span>`);
        }
        if (p.indexed_chunks) metrics.push(`<span class="cmd-metric">${p.indexed_chunks} chunks</span>`);

        const stats = [];
        if (p.total_files) stats.push(`${p.total_files} files`);
        if (p.last_activity && p.last_activity !== 'folder not found') stats.push(p.last_activity);

        let agentHtml = '';
        if (p.has_agent) {
            if (p.latest_agent_run) {
                const findings = p.latest_agent_run.findings || {};
                const actions = findings.action_items || [];
                const healthInfo = findings.site_health;

                let findingsHtml = '';
                if (healthInfo) {
                    const statusText = healthInfo.healthy ? `OK (${healthInfo.response_ms}ms)` : `DOWN (${healthInfo.status_code})`;
                    findingsHtml += `<div class="cmd-finding">Site: ${statusText}</div>`;
                }
                if (actions.length > 0) {
                    findingsHtml += actions.slice(0, 3).map(a => {
                        const cls = a.startsWith('OVERDUE') || a.startsWith('SITE DOWN') ? 'error' : a.startsWith('URGENT') ? 'warning' : '';
                        return `<div class="cmd-finding ${cls}">${escapeHtml(a)}</div>`;
                    }).join('');
                    if (actions.length > 3) {
                        findingsHtml += `<div class="cmd-finding dim">+${actions.length - 3} more</div>`;
                    }
                } else {
                    findingsHtml += '<div class="cmd-finding ok">All clear</div>';
                }
                agentHtml = `<div class="cmd-agent">
                    <div class="cmd-agent-label">AGENT (${p.agent_schedule})</div>
                    ${findingsHtml}
                </div>`;
            } else {
                agentHtml = `<div class="cmd-agent">
                    <div class="cmd-agent-label">AGENT (${p.agent_schedule})</div>
                    <div class="cmd-finding dim">Not yet run</div>
                </div>`;
            }
        }

        const runBtn = p.has_agent ? `<button class="cmd-run-btn" onclick="runProjectAgent('${p.key}', this)">Run</button>` : '';

        return `<div class="cmd-card">
            ${runBtn}
            <div class="cmd-card-header">
                <span class="cmd-dot ${dotClass}"></span>
                <span class="cmd-name">${escapeHtml(p.name)}</span>
                <span class="cmd-category">${escapeHtml(p.category || '')}</span>
            </div>
            ${metrics.length ? `<div class="cmd-metrics">${metrics.join('')}</div>` : ''}
            <div class="cmd-desc">${escapeHtml(p.description || '')}</div>
            <div class="cmd-stats">${stats.join(' &middot; ')}</div>
            ${agentHtml}
        </div>`;
    }).join('');

    document.getElementById('cmd-last-refresh').textContent = new Date().toLocaleTimeString();
}

async function runProjectAgent(projectKey, btn) {
    btn.textContent = '...';
    btn.classList.add('running');
    try {
        await fetch(`/api/agents/run/${projectKey}`, { method: 'POST' });
        btn.textContent = 'Done';
        btn.classList.remove('running');
        setTimeout(() => { btn.textContent = 'Run'; loadCommandCenter(); }, 2000);
    } catch (e) {
        btn.textContent = 'Err';
        btn.classList.remove('running');
    }
}

// ==================== KNOWLEDGE TREEMAP ====================
async function loadGraph() {
    try {
        const res = await fetch('/api/treemap');
        state.treemapData = await res.json();
        requestAnimationFrame(() => renderTreemap(state.treemapData));
    } catch (e) { console.warn('Treemap load failed:', e); }
}

function renderTreemap(data) {
    const container = document.getElementById('graph-container');
    if (!data || !data.categories) {
        container.innerHTML = '<div class="empty-state">No knowledge indexed.</div>';
        return;
    }
    container.innerHTML = '';
    const treemap = document.createElement('div');
    treemap.className = 'treemap-root';
    container.appendChild(treemap);

    data.categories.forEach(cat => {
        if (!cat.w || !cat.h) return;
        const catEl = document.createElement('div');
        catEl.className = 'treemap-category';
        catEl.style.cssText = `left:${cat.x}%;top:${cat.y}%;width:${cat.w}%;height:${cat.h}%`;

        const labelEl = document.createElement('div');
        labelEl.className = 'treemap-cat-label';
        labelEl.style.color = cat.color;
        labelEl.textContent = cat.name;
        catEl.appendChild(labelEl);

        cat.domains.forEach(d => {
            if (!d.w || !d.h) return;
            const cell = document.createElement('div');
            cell.className = 'treemap-cell';
            cell.dataset.domain = d.domain;
            const relX = cat.w > 0 ? ((d.x - cat.x) / cat.w) * 100 : 0;
            const relY = cat.h > 0 ? ((d.y - cat.y) / cat.h) * 100 : 0;
            const relW = cat.w > 0 ? (d.w / cat.w) * 100 : 0;
            const relH = cat.h > 0 ? (d.h / cat.h) * 100 : 0;
            cell.style.cssText = `left:${relX}%;top:${relY}%;width:${relW}%;height:${relH}%;border-color:${cat.color}33;--glow-color:${cat.color}`;

            if (d.w > 4 && d.h > 3) {
                const nameEl = document.createElement('div');
                nameEl.className = 'treemap-cell-name';
                nameEl.textContent = d.label;
                cell.appendChild(nameEl);
                if (d.w > 6 && d.h > 5) {
                    const countEl = document.createElement('div');
                    countEl.className = 'treemap-cell-count';
                    countEl.textContent = d.chunks + ' chunks';
                    cell.appendChild(countEl);
                }
            }

            // Touch-friendly: use click for detail on mobile
            cell.addEventListener('click', () => {
                showNodeDetail({
                    label: d.label,
                    domain: d.domain,
                    source_file: `prompts/domains/${d.domain}.md`,
                    chunk_count: d.chunks,
                    content_type: cat.name,
                    tokens: 0,
                    preview: `${d.chunks} chunks in the ${d.label} domain (${cat.name} category)`,
                });
            });

            catEl.appendChild(cell);
        });
        treemap.appendChild(catEl);
    });

    // Legend
    const legend = document.getElementById('graph-legend');
    legend.innerHTML = '<div class="legend-title">Categories</div>' +
        data.categories.map(c =>
            `<div class="legend-item"><div class="legend-dot" style="background:${c.color}"></div><span>${c.name}</span><span class="legend-count">${c.domains.length}</span></div>`
        ).join('');

    // Search filter
    document.getElementById('graph-search').addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase();
        treemap.querySelectorAll('.treemap-cell').forEach(cell => {
            if (!q) {
                cell.classList.remove('tm-dimmed');
            } else {
                const match = cell.dataset.domain.includes(q) ||
                    (cell.querySelector('.treemap-cell-name')?.textContent || '').toLowerCase().includes(q);
                cell.classList.toggle('tm-dimmed', !match);
            }
        });
    });
}

function showNodeDetail(node) {
    const panel = document.getElementById('node-detail');
    document.getElementById('node-detail-title').textContent = node.label;
    document.getElementById('node-detail-file').textContent = node.source_file || '';

    let badges = '';
    if (node.domain) badges += `<span class="badge" style="color:${domainColor(node.domain)};border-color:${domainColor(node.domain)}">${node.domain}</span>`;
    if (node.chunk_count) badges += `<span class="badge" style="color:var(--green);border-color:rgba(102,187,106,0.3)">${node.chunk_count} chunks</span>`;
    if (node.content_type) badges += `<span class="badge" style="color:var(--text-dim);border-color:var(--border)">${node.content_type}</span>`;
    document.getElementById('node-detail-badges').innerHTML = badges;
    document.getElementById('node-detail-body').innerHTML = `<div class="detail-text">${escapeHtml(node.full_text || node.preview || '')}</div>`;
    panel.classList.add('open');
}

document.getElementById('node-detail-close').addEventListener('click', () => {
    document.getElementById('node-detail').classList.remove('open');
});

// ==================== PROJECTS ====================
async function loadProjects() {
    try {
        const res = await fetch('/api/projects');
        const projects = await res.json();
        renderProjects(projects);
    } catch (e) { console.warn('Projects load failed:', e); }
}

function renderProjects(projects) {
    const list = document.getElementById('projects-list');
    if (!projects.length) {
        list.innerHTML = '<div class="empty-state">No projects yet. Click + Add to create one.</div>';
        return;
    }
    list.innerHTML = projects.map(p => {
        const statusClass = p.status === 'active' ? 'status-active' : p.status === 'paused' ? 'status-paused' : 'status-completed';
        const tasks = p.tasks || [];
        const done = tasks.filter(t => t.status === 'done').length;
        return `<div class="project-card" data-id="${p.id}">
            <div class="project-name">${escapeHtml(p.name)}</div>
            <div class="project-meta">
                <span class="project-status ${statusClass}">${p.status}</span>
                <span>${tasks.length} tasks (${done} done)</span>
                ${p.revenue_monthly ? `<span>$${p.revenue_monthly}/mo</span>` : ''}
            </div>
            ${p.description ? `<div class="project-desc">${escapeHtml(p.description)}</div>` : ''}
            <div class="project-tasks">
                ${tasks.map(t => `<div class="task-item">
                    <div class="task-check ${t.status === 'done' ? 'done' : ''}"></div>
                    <span class="task-title ${t.status === 'done' ? 'done' : ''}">${escapeHtml(t.title)}</span>
                </div>`).join('')}
            </div>
        </div>`;
    }).join('');

    list.querySelectorAll('.project-card').forEach(card => {
        card.addEventListener('click', () => card.classList.toggle('expanded'));
    });
}

document.getElementById('add-project-btn').addEventListener('click', () => {
    showModal('New Project', [
        { name: 'name', label: 'Project Name', type: 'text', required: true },
        { name: 'description', label: 'Description', type: 'textarea' },
        { name: 'tech_stack', label: 'Tech Stack', type: 'text' },
        { name: 'revenue_monthly', label: 'Monthly Revenue ($)', type: 'number' },
    ], async (data) => {
        await fetch('/api/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        loadProjects();
    });
});

// ==================== FINANCES ====================
async function loadFinances() {
    try {
        const [summaryRes, entriesRes] = await Promise.all([
            fetch('/api/finances/summary'),
            fetch('/api/finances?limit=20'),
        ]);
        const summary = await summaryRes.json();
        const entries = await entriesRes.json();
        renderFinances(summary, entries);
    } catch (e) { console.warn('Finances load failed:', e); }
}

function renderFinances(summary, entries) {
    document.getElementById('finance-summary').innerHTML = `
        <div class="finance-card"><div class="label">MRR</div><div class="value ${summary.mrr >= 0 ? 'positive' : 'negative'}">$${summary.mrr.toFixed(0)}</div></div>
        <div class="finance-card"><div class="label">Revenue (30d)</div><div class="value positive">$${summary.revenue_this_month.toFixed(0)}</div></div>
        <div class="finance-card"><div class="label">Expenses (30d)</div><div class="value negative">$${summary.expenses_this_month.toFixed(0)}</div></div>
        <div class="finance-card"><div class="label">Net Profit</div><div class="value ${summary.net_profit >= 0 ? 'positive' : 'negative'}">$${summary.net_profit.toFixed(0)}</div></div>
    `;

    const listEl = document.getElementById('finance-list');
    if (!entries.length) {
        listEl.innerHTML = '<div class="empty-state">No entries yet.</div>';
        return;
    }
    listEl.innerHTML = entries.map(e => `
        <div class="finance-entry">
            <div>
                <div>${escapeHtml(e.description || e.category || 'Entry')}</div>
                <div class="finance-date">${e.date} ${e.category ? '| ' + e.category : ''}</div>
            </div>
            <div class="finance-amount ${e.type}">${e.type === 'revenue' ? '+' : '-'}$${Math.abs(e.amount).toFixed(2)}</div>
        </div>
    `).join('');
}

document.getElementById('add-finance-btn').addEventListener('click', () => {
    showModal('Add Entry', [
        { name: 'description', label: 'Description', type: 'text', required: true },
        { name: 'amount', label: 'Amount ($)', type: 'number', required: true },
        { name: 'type', label: 'Type', type: 'select', options: ['expense', 'revenue'] },
        { name: 'category', label: 'Category', type: 'text' },
        { name: 'date', label: 'Date', type: 'date', default: new Date().toISOString().split('T')[0] },
    ], async (data) => {
        data.amount = parseFloat(data.amount);
        await fetch('/api/finances', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        loadFinances();
    });
});

// ==================== GOALS ====================
async function loadGoals() {
    try {
        const res = await fetch('/api/goals');
        const goals = await res.json();
        renderGoals(goals);
    } catch (e) { console.warn('Goals load failed:', e); }
}

function renderGoals(goals) {
    const list = document.getElementById('goals-list');
    if (!goals.length) {
        list.innerHTML = '<div class="empty-state">No goals yet. Click + Add to set one.</div>';
        return;
    }
    list.innerHTML = goals.map(g => `
        <div class="goal-card">
            <div class="goal-title">${escapeHtml(g.title)}</div>
            <div class="goal-progress-bar"><div class="goal-progress-fill" style="width:${g.progress}%"></div></div>
            <div class="goal-meta">
                <span>${g.progress}%</span>
                <span>${g.target_date || 'No deadline'}</span>
            </div>
        </div>
    `).join('');
}

document.getElementById('add-goal-btn').addEventListener('click', () => {
    showModal('New Goal', [
        { name: 'title', label: 'Goal', type: 'text', required: true },
        { name: 'target_date', label: 'Target Date', type: 'date' },
        { name: 'category', label: 'Category', type: 'text' },
    ], async (data) => {
        await fetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        loadGoals();
    });
});

// ==================== MODAL ====================
function showModal(title, fields, onSubmit) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    let fieldsHtml = fields.map(f => {
        let input = '';
        if (f.type === 'textarea') {
            input = `<textarea name="${f.name}" rows="3"></textarea>`;
        } else if (f.type === 'select') {
            input = `<select name="${f.name}">${f.options.map(o => `<option value="${o}">${o}</option>`).join('')}</select>`;
        } else {
            input = `<input type="${f.type || 'text'}" name="${f.name}" ${f.required ? 'required' : ''} ${f.default ? `value="${f.default}"` : ''}>`;
        }
        return `<div class="modal-field"><label>${f.label}</label>${input}</div>`;
    }).join('');

    overlay.innerHTML = `<div class="modal">
        <h3>${title}</h3>
        <form id="modal-form">${fieldsHtml}
            <div class="modal-actions">
                <button type="button" class="btn-cancel" id="modal-cancel">Cancel</button>
                <button type="submit" class="btn-primary">Save</button>
            </div>
        </form>
    </div>`;

    document.body.appendChild(overlay);
    overlay.querySelector('#modal-cancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#modal-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        await onSubmit(Object.fromEntries(formData));
        overlay.remove();
    });
    setTimeout(() => overlay.querySelector('input, textarea')?.focus(), 50);
}
