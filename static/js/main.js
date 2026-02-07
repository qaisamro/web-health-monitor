
// Error Handler
window.onerror = function (msg, url, line) {
    console.error("Critical JS Error:", msg, "at", url, ":", line);
    const app = document.body;
    if (app) app.insertAdjacentHTML('afterbegin', `<div style="position:fixed; top:0; left:0; width:100%; padding:1rem; background:red; color:white; z-index:9999; text-align:center;">⚠️ JavaScript Loading Error: ${msg} <button onclick="location.reload()" style="background:white; color:red; border:none; padding:0.2rem 0.5rem; margin-left:1rem; cursor:pointer;">Retry</button></div>`);
};

let token = localStorage.getItem('token');
let selectedId = null;
let chart = null;
let auditTimers = {};
let currentStrategy = 'mobile';

// --- Auth ---
function setupAuth() {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData();
            formData.append('username', e.target.username.value);
            formData.append('password', e.target.password.value);
            try {
                const res = await fetch('/api/v1/auth/login', { method: 'POST', body: formData });
                if (res.ok) {
                    const data = await res.json();
                    localStorage.setItem('token', data.access_token);
                    localStorage.setItem('user', e.target.username.value);
                    token = data.access_token;
                    init();
                } else {
                    document.getElementById('login-error').innerText = 'Invalid credentials';
                }
            } catch (err) {
                document.getElementById('login-error').innerText = 'Connection Error';
            }
        };
    }
}

function logout() {
    localStorage.clear();
    location.reload();
}

async function api(path, opts = {}) {
    opts.headers = { ...opts.headers, 'Authorization': `Bearer ${token}` };
    const res = await fetch(path, opts);
    if (res.status === 401) { logout(); return; }
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown API error" }));
        throw new Error(err.detail || "Request failed");
    }
    return res.json();
}

// --- UI State ---
window.setStrategy = function (mode) {
    currentStrategy = mode;
    const btnMobile = document.getElementById('btn-mobile');
    const btnDesktop = document.getElementById('btn-desktop');
    if (btnMobile) btnMobile.classList.toggle('active', mode === 'mobile');
    if (btnDesktop) btnDesktop.classList.toggle('active', mode === 'desktop');
}

window.showDashboard = function () {
    document.getElementById('hero-area').style.display = 'none';
    document.getElementById('report-view').style.display = 'none';
    const dashboardView = document.getElementById('dashboard-view');
    if (dashboardView) {
        dashboardView.style.display = 'block';
        // Add animation class if not present
        dashboardView.classList.add('fade-in-up');
    }
    loadMonitors();
}

window.showAnalysis = function () {
    document.getElementById('hero-area').style.display = 'none';
    document.getElementById('dashboard-view').style.display = 'none';
    const reportView = document.getElementById('report-view');
    if (reportView) {
        reportView.style.display = 'block';
        reportView.classList.add('fade-in-up');
    }
}

window.showHome = function () {
    document.getElementById('dashboard-view').style.display = 'none';
    document.getElementById('report-view').style.display = 'none';
    const hero = document.getElementById('hero-area');
    if (hero) {
        hero.style.display = 'block';
        hero.classList.add('fade-in-up');
    }
}

function getScoreColor(score) {
    if (!score && score !== 0) return '#94a3b8';
    if (score >= 90) return '#10b981';
    if (score >= 50) return '#fbbf24';
    return '#ef4444';
}

// --- Core Audit Logic ---
async function loadMonitors() {
    try {
        const monitors = await api('/api/v1/monitors');
        const list = document.getElementById('monitor-list');
        if (!list) return;

        if (monitors.length === 0) {
            list.innerHTML = `<div class="empty-state">No audits found. <br><small>Start a new analysis from the home page.</small></div>`;
            return;
        }

        list.innerHTML = monitors.reverse().map(m => `
        <div class="monitor-item" id="monitor-${m.id}" onclick="showDetail(${m.id})">
            <div class="monitor-info">
                <div class="monitor-name">
                    ${m.name}
                    <span class="badge badge-strategy">${m.strategy || 'mobile'}</span>
                </div>
                <div class="monitor-url">${m.url}</div>
            </div>
            <div class="monitor-stats">
                <div class="score-pill" style="color: ${getScoreColor(m.perf_score)}; border-color: ${getScoreColor(m.perf_score)}20; background: ${getScoreColor(m.perf_score)}10;">
                    <span class="score-label">Score</span>
                    <span class="score-val">${m.perf_score !== null ? Math.round(m.perf_score) : '--'}</span>
                </div>
                <button class="btn-icon btn-delete" onclick="event.stopPropagation(); deleteMonitor(${m.id})" title="Delete Trace">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            </div>
        </div>
      `).join('');
    } catch (err) {
        console.error("Failed to load monitors", err);
    }
}

window.deleteMonitor = async function (id) {
    if (!confirm('Delete this analysis trace?')) return;
    const item = document.getElementById(`monitor-${id}`);
    if (item) item.classList.add('deleting'); // Add CSS animation class
    setTimeout(async () => {
        await api(`/monitors/${id}`, { method: 'DELETE' });
        loadMonitors();
    }, 300);
}

function startCountdown(id) {
    if (auditTimers[id]) return;
    let val = 60;
    const statusMsgs = [
        { time: 55, en: "Connecting to Engine...", ar: "جاري الاتصال..." },
        { time: 40, en: "Running Lighthouse...", ar: "جاري تشغيل الفحص..." },
        { time: 25, en: "Processing Assets...", ar: "جاري تحليل الملفات..." },
        { time: 10, en: "Finalizing Report...", ar: "جاري إنهاء التقرير..." }
    ];

    auditTimers[id] = setInterval(() => {
        val--;
        if (selectedId === id) {
            const area = document.getElementById('audit-countdown');
            if (area) area.style.display = 'block';
            const pb = document.getElementById('audit-progress-bar');
            if (pb) pb.style.width = `${((60 - val) / 60) * 100}%`;
            const ts = document.getElementById('timer-val');
            if (ts) ts.innerText = val > 0 ? val : "Wait...";
            const msg = statusMsgs.find(m => val >= m.time) || statusMsgs[statusMsgs.length - 1];
            const st = document.getElementById('audit-status-msg');
            if (st) st.innerText = `🚀 ${msg.en} | ${msg.ar}`;
        }
        if (val <= -120) { clearInterval(auditTimers[id]); delete auditTimers[id]; }
    }, 1000);
}

function setupPSIForm() {
    const form = document.getElementById('psi-search-form');
    if (!form) return;

    form.onsubmit = async (e) => {
        e.preventDefault();
        let url = document.getElementById('psi-url-input').value;
        if (!url) return;
        if (!url.startsWith('http')) url = 'https://' + url;
        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.innerHTML = "<span class='spinner'></span> Analyzing..."; btn.disabled = true;

        try {
            const hostname = new URL(url).hostname;
            const res = await api('/api/v1/monitors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: hostname, url: url, interval_seconds: 60, strategy: currentStrategy })
            });
            if (res && res.id) {
                selectedId = res.id;
                startCountdown(res.id);
                showDetail(res.id);
                showAnalysis();
            }
        } catch (err) { alert("Error starting analysis: " + err.message); }
        finally { btn.innerHTML = originalText; btn.disabled = false; }
    };
}

window.showDetail = async function (id, retryCount = 0) {
    try {
        selectedId = id;
        showAnalysis();
        const ds = document.getElementById('detail-section');
        if (ds && retryCount === 0) ds.innerHTML = '<div class="loading-state"><div class="spinner-large"></div><h2>Generated Analysis Report...</h2></div>';

        // Set date for print footer
        if (ds) ds.setAttribute('data-date', new Date().toLocaleDateString() + ' ' + new Date().toLocaleTimeString());

        const monitors = await api('/api/v1/monitors');
        const m = monitors.find(x => x.id === id);
        if (!m) {
            console.error("Monitor not found for ID:", id);
            return;
        }

        // Auto-start countdown if audit is pending
        if (m.perf_score === null && !auditTimers[id]) {
            console.log("⏱️ Audit pending, starting countdown...");
            startCountdown(id);
        }

        if (!ds) return;

        // Determine status badge class
        const scoreClass = m.perf_score >= 90 ? 'text-success' : m.perf_score >= 50 ? 'text-warning' : 'text-danger';

        ds.innerHTML = `
    <div class="report-header glass-panel fade-in-up">
        <div class="header-content">
            <button onclick="showHome()" class="btn-back">&larr; Back</button>
            <div class="header-title-group">
                <h1>${m.url}</h1>
                <div class="strategy-badge ${m.strategy || 'mobile'}">
                    ${m.strategy === 'desktop' ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>' : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>'}
                    ${m.strategy || 'mobile'}
                </div>
            </div>
        </div>
        
        <div id="audit-countdown" class="audit-status-panel" style="display: ${(auditTimers[id] || m.perf_score === null) ? 'flex' : 'none'};">
            <div class="status-text-pulse" id="audit-status-msg">${m.perf_score === null && !auditTimers[id] ? '⌛ Analysis Pending...' : '🚀 Analyzing...'}</div>
            <div class="progress-wrapper">
                <div class="progress-fill" id="audit-progress-bar" style="width: ${m.perf_score === null ? '30%' : '0%'}; transition: width 1s;"></div>
            </div>
            <div class="time-est">Est. Time: <span id="timer-val">60</span>s</div>
        </div>
        
        <div class="header-actions">
            <button onclick="window.print()" class="btn btn-outline">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7"></path><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                Export PDF
            </button>
            <button onclick="triggerManualAudit()" id="refresh-btn" class="btn btn-primary" style="display: ${auditTimers[id] ? 'none' : 'flex'};">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                Re-Analyze
            </button>
        </div>
    </div>

    <div class="report-grid">
        <div class="metrics-overview glass-panel fade-in-up" style="animation-delay: 0.1s;">
            <div class="gauges-container">
                ${renderGauge('Performance', m.perf_score, 'الأداء')}
                ${renderGauge('Accessibility', m.perf_accessible, 'إمكانية الوصول')}
                ${renderGauge('Best Practices', m.perf_best_practices, 'أفضل الممارسات')}
                ${renderGauge('SEO', m.perf_seo, 'محركات البحث')}
            </div>
        </div>
        <div class="screenshot-panel glass-panel fade-in-up" style="animation-delay: 0.2s;">
            <div id="screenshot-container" class="screenshot-frame">
                ${m.perf_screenshot ? `<img src="${m.perf_screenshot}" alt="Page Screenshot">` : `<div class="placeholder-screenshot"><div class="spinner"></div><p>Generating Preview...</p></div>`}
            </div>
        </div>
    </div>

    <div class="glass-panel filmstrip-panel fade-in-up" style="animation-delay: 0.3s; margin-top: 2rem;">
        <h2>Loading Timeline (التسلسل الزمني)</h2>
        <div class="filmstrip-row">
            ${(m.perf_thumbnails || []).map(t => `<div class="filmstrip-item"><img src="${t.data}"><div class="filmstrip-time">${Math.round(t.timing)}ms</div></div>`).join('') || '<p class="empty-msg">Visual timeline will appear after audit completes.</p>'}
        </div>
    </div>

    <div class="key-metrics-grid fade-in-up" style="animation-delay: 0.4s;">
        ${renderMetric('First Contentful Paint', `${m.perf_fcp || '...'}s`, "FCP")}
        ${renderMetric('Largest Contentful Paint', `${m.perf_lcp || '...'}s`, "LCP")}
        ${renderMetric('Cumulative Layout Shift', m.perf_cls || '...', "CLS")}
        ${renderMetric('Total Blocking Time', `${m.perf_tbt || '...'}ms`, "TBT")}
    </div>

    <div id="error-section" class="opportunities-section fade-in-up" style="display: ${m.perf_details && m.perf_details.length > 0 ? 'block' : 'none'}; animation-delay: 0.5s;">
        <h2 style="margin-bottom: 2rem;">Opportunities (فرص التحسين)</h2>
        <div class="opportunities-list">
            ${(m.perf_details || []).map(e => `
                <div class="opportunity-card" style="border-left-color: ${getScoreColor(e.score * 100)};">
                    <div class="opp-header">
                        <div class="opp-title">${e.title}</div>
                        <div class="opp-score" style="color: ${getScoreColor(e.score * 100)}">Impact: ${Math.round((1 - e.score) * 100)}</div>
                    </div>
                    <div class="opp-desc">${e.description}</div>
                </div>
            `).join('')}
        </div>
    </div>

    <div class="glass-panel chart-panel fade-in-up" style="animation-delay: 0.6s;">
        <h2>Response Time History</h2>
        <div class="chart-container"><canvas id="responseChart"></canvas></div>
    </div>
    `;
        renderChart(id);
    } catch (err) {
        console.error("Dashboard error:", err);
        const ds = document.getElementById('detail-section');
        if (ds) ds.innerHTML = `<div class="error-state"><h2>⚠️ Error loading report</h2><p>${err.message}</p><button class="btn btn-primary" onclick="showDashboard()">Back to Dashboard</button></div>`;
    }
}

function renderGauge(label, score, ar) {
    const color = getScoreColor(score);
    return `
    <div class="gauge-wrapper">
        <div class="gauge-chart">
            <svg viewBox="0 0 36 36" class="circular-chart">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" class="circle-bg" />
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" class="circle" stroke="${color}" stroke-dasharray="${score || 0}, 100" />
            </svg>
            <div class="gauge-value" style="color: ${color}">${score !== null ? Math.round(score) : '--'}</div>
        </div>
        <div class="gauge-label">
            <span class="en">${label}</span>
            <span class="ar">${ar}</span>
        </div>
    </div>`;
}

function renderMetric(title, val, acronym) {
    return `
  <div class="metric-card glass-panel">
      <div class="metric-header">
          <span class="metric-acronym">${acronym}</span>
          <span class="metric-title">${title}</span>
      </div>
      <div class="metric-value">${val}</div>
  </div>`;
}

window.triggerManualAudit = async function () {
    if (!selectedId) return;
    await api(`/monitors/${selectedId}/audit?strategy=${currentStrategy}`, { method: 'POST' });
    startCountdown(selectedId);
    showDetail(selectedId);
}

async function renderChart(id) {
    if (typeof Chart === 'undefined') {
        return;
    }
    const checks = await api(`/monitors/${id}/checks?limit=20`);
    if (chart) chart.destroy();
    if (!checks || !checks.length) return;
    const ctx = document.getElementById('responseChart').getContext('2d');

    // Custom Chart Gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.5)'); // primary
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.0)');

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: checks.reverse().map(d => new Date(d.checked_at).toLocaleTimeString()),
            datasets: [{
                data: checks.map(d => d.response_ms),
                borderColor: '#8b5cf6',
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#8b5cf6',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#8b5cf6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#f1f5f9',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { display: false }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function setupWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event === 'monitor_created') startCountdown(data.monitor_id);
        if (data.event === 'audit_finished') {
            if (auditTimers[data.monitor_id]) { clearInterval(auditTimers[data.monitor_id]); delete auditTimers[data.monitor_id]; }
            if (selectedId === data.monitor_id) {
                const sm = document.getElementById('audit-status-msg');
                if (sm) { sm.innerText = "✅ Analysis Received! Syncing..."; sm.style.color = "var(--success)"; }
                const pb = document.getElementById('audit-progress-bar');
                if (pb) pb.style.width = '100%';
                setTimeout(() => showDetail(data.monitor_id), 2000);
            }
            loadMonitors();
        }
        if (data.event === 'audit_failed') {
            if (auditTimers[data.monitor_id]) { clearInterval(auditTimers[data.monitor_id]); delete auditTimers[data.monitor_id]; }
            if (selectedId === data.monitor_id) {
                const sm = document.getElementById('audit-status-msg');
                if (sm) { sm.innerText = `❌ Audit Failed: ${data.error || 'Blocked or Timeout'}`; sm.style.color = "var(--danger)"; }
                const pb = document.getElementById('audit-progress-bar');
                if (pb) pb.style.background = 'var(--danger)';
            }
        }
        if (data.event === 'check_finished') {
            loadMonitors();
            if (selectedId === data.monitor_id) renderChart(selectedId);
        }
    };
}

window.toggleChat = function () {
    const win = document.getElementById('chat-window');
    if (win) {
        const isFlex = getComputedStyle(win).display === 'flex';
        win.style.display = isFlex ? 'none' : 'flex';
    }
}

function setupChat() {
    const chatForm = document.getElementById('chat-form');
    if (!chatForm) return;

    chatForm.onsubmit = async (e) => {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if (!text) return;
        const msgArea = document.getElementById('chat-messages');
        msgArea.innerHTML += `<div class="msg msg-user">${text}</div>`;
        input.value = '';
        try {
            const res = await fetch('/api/v1/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ message: text }) });
            const data = await res.json();
            msgArea.innerHTML += `<div class="msg msg-bot">${data.reply || "Thinking..."}</div>`;
            msgArea.scrollTop = msgArea.scrollHeight;
        } catch { }
    };
}

function init() {
    console.log("🚀 Initializing App...");

    // Setup global event listeners
    setupAuth();
    setupChat();

    if (token) {
        console.log("🔑 Session found. Hiding overlay.");
        const overlay = document.getElementById('login-overlay');
        if (overlay) overlay.classList.add('hidden');

        try {
            const userDisplay = document.getElementById('user-display');
            if (userDisplay) userDisplay.innerText = `Signed in as ${localStorage.getItem('user') || 'Admin'}`;

            setupWS();
            setupPSIForm();
            const hero = document.getElementById('hero-area');
            if (hero) hero.style.display = 'block';
            console.log("✅ App Ready.");
        } catch (err) {
            console.error("Initialization failed:", err);
        }
    } else {
        console.log("🎟️ No session. Showing login.");
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);
