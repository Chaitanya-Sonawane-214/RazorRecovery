/* ─────────────────────────────────────────────────────────
   RazorRecovery Dashboard — script.js
   Sidebar nav · minimal B&W theme · gold only on active nav
   ───────────────────────────────────────────────────────── */

const API = '';

let summaryData = null;
let simSource = null;
let simPaused = false;
let simBuffer = [];
let simTotal = 0;
let simDone = 0;
let simCounts = { recovered: 0, escalated: 0, retry_failed: 0 };

const PANEL_TITLES = {
    overview: 'Overview',
    ab: 'A/B Comparison',
    roi: 'Cost / ROI',
    transactions: 'Transactions',
    directions: 'Directions',
};

// ── Init ─────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    checkRazorpayStatus();
    loadSummary();
    loadABComparison();
    loadTransactions();
});

// ── Sidebar navigation ────────────────────────────────────
function switchPanel(name) {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById('nav-' + name).classList.add('active');
    document.getElementById('panel-' + name).classList.add('active');
    document.getElementById('topbar-title').textContent = PANEL_TITLES[name] || name;
}

// ── Formatters ────────────────────────────────────────────
function fmt(n) { return n == null ? '—' : '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 }); }
function fmtPct(n) { return n != null ? n + '%' : '—'; }
function fmtPP(n) { return n != null ? (n >= 0 ? '+' : '') + n + ' pp' : '—'; }

// ── Razorpay status ───────────────────────────────────────
async function checkRazorpayStatus() {
    try {
        const res = await fetch(`${API}/api/razorpay/status`);
        const d = await res.json();
        const dot = document.getElementById('rzp-dot');
        const text = document.getElementById('razorpay-mode-text');
        if (d.connected) {
            dot.classList.add('live');
            text.textContent = `Live · ${d.key_id_prefix}`;
        } else {
            dot.classList.add('sandbox');
            text.textContent = 'Sandbox mode';
        }
    } catch { document.getElementById('razorpay-mode-text').textContent = 'Offline'; }
}

// ── Summary ───────────────────────────────────────────────
async function loadSummary() {
    try {
        const res = await fetch(`${API}/api/summary`);
        summaryData = await res.json();
        populateKPIs(summaryData);
        populateOutcomeBars(summaryData);
        populateCauseBars(summaryData);
        populateROITab(summaryData);
        populateDirections(summaryData);
    } catch (e) { console.error('Summary failed', e); }
}

function populateKPIs(s) {
    document.getElementById('kpi-val-total').textContent = (s.total_transactions || 0).toLocaleString();
    document.getElementById('kpi-val-rate').textContent = fmtPct(s.recovery_rate_percent);
    document.getElementById('kpi-val-recovered').textContent = fmt(s.recovered?.amount);
    document.getElementById('kpi-sub-recovered').textContent = `${s.recovered?.count || 0} transactions`;
    const roi = s.roi?.roi;
    // if (roi) document.getElementById('kpi-val-roi').textContent = fmtPct(roi.roi_percent);
    if (roi) document.getElementById('kpi-val-roi').textContent = fmt(roi.net_roi);
    const ab = s.ab_comparison_summary;
    if (ab) document.getElementById('kpi-val-uplift').textContent = fmtPP(ab.rate_delta_pp);
}

function populateOutcomeBars(s) {
    const total = s.total_transactions || 1;
    const items = [
        { label: 'Recovered', count: s.recovered?.count || 0, amount: s.recovered?.amount, cls: 'fill-green' },
        { label: 'Escalated — max attempts', count: s.escalated_max_attempts?.count || 0, amount: s.escalated_max_attempts?.amount, cls: 'fill-orange' },
        { label: 'Escalated — low prob', count: s.escalated_low_probability?.count || 0, amount: s.escalated_low_probability?.amount, cls: 'fill-mid' },
        { label: 'Retry Failed', count: s.retry_failed?.count || 0, amount: s.retry_failed?.amount, cls: 'fill-lo' },
    ];
    document.getElementById('outcome-bars').innerHTML = items.map(i => `
        <div class="bar-row">
            <span class="bar-label">${i.label}</span>
            <div class="bar-track">
                <div class="bar-fill ${i.cls}" style="width:${(i.count / total * 100).toFixed(1)}%"></div>
            </div>
            <span class="bar-val">${i.count} · ${fmt(i.amount)}</span>
        </div>`).join('');
}

function populateCauseBars(s) {
    const bd = s.root_cause_breakdown || {};
    const total = Object.values(bd).reduce((a, b) => a + b, 0) || 1;
    const fills = ['fill-hi', 'fill-mid', 'fill-lo', 'fill-hi', 'fill-mid', 'fill-lo', 'fill-hi', 'fill-mid'];
    document.getElementById('cause-bars').innerHTML = Object.entries(bd)
        .sort((a, b) => b[1] - a[1])
        .map(([cause, cnt], i) => `
        <div class="bar-row">
            <span class="bar-label">${cause.replace(/_/g, ' ')}</span>
            <div class="bar-track">
                <div class="bar-fill ${fills[i % fills.length]}" style="width:${(cnt / total * 100).toFixed(1)}%"></div>
            </div>
            <span class="bar-val">${cnt}</span>
        </div>`).join('');
}

// ── A/B Comparison ────────────────────────────────────────
async function loadABComparison() {
    try {
        const res = await fetch(`${API}/api/ab-comparison`);
        const d = await res.json();
        populateABTab(d);
    } catch (e) { console.error('A/B failed', e); }
}

function populateABTab(d) {
    if (!d) return;
    const rb = d.rule_based;
    const ml = d.ml_augmented;
    const adv = d.ml_advantage;

    const metrics = [
        { lbl: 'Recovery Rate', ctrl: rb.recovery_rate_percent + '%', ml: ml.recovery_rate_percent + '%', delta: adv.recovery_rate_delta_pp, suf: ' pp' },
        { lbl: 'Recovered Amount', ctrl: fmt(rb.recovered_amount), ml: fmt(ml.recovered_amount), delta: ml.recovered_amount - rb.recovered_amount, isAmt: true },
        { lbl: 'Operational Cost', ctrl: fmt(rb.total_operational_cost), ml: fmt(ml.total_operational_cost), delta: rb.total_operational_cost - ml.total_operational_cost, isAmt: true, inv: true },
        { lbl: 'Net Value', ctrl: fmt(rb.net_value), ml: fmt(ml.net_value), delta: ml.net_value - rb.net_value, isAmt: true },
        { lbl: 'Recovered Count', ctrl: rb.recovered_count, ml: ml.recovered_count, delta: ml.recovered_count - rb.recovered_count },
        { lbl: 'Escalated Count', ctrl: rb.escalated_count, ml: ml.escalated_count, delta: rb.escalated_count - ml.escalated_count, inv: true },
    ];

    document.getElementById('ab-metrics').innerHTML = metrics.map(m => {
        const raw = m.inv ? -m.delta : m.delta;
        const cls = raw > 0.01 ? 'pos' : raw < -0.01 ? 'neg' : 'neu';
        const dLabel = m.isAmt
            ? (m.delta >= 0 ? '+' : '') + fmt(Math.abs(m.delta))
            : (m.delta >= 0 ? '+' : '') + m.delta + (m.suf || '');
        return `
            <div class="ab-metric">
                <div class="ab-metric-lbl">${m.lbl}</div>
                <div class="ab-metric-row">
                    <span class="ab-ctrl">${m.ctrl}</span>
                    <span class="ab-delta ${cls}">${dLabel}</span>
                    <span class="ab-ml">${m.ml}</span>
                </div>
            </div>`;
    }).join('');

    document.getElementById('ab-verdict').innerHTML = `
        <div class="ab-verdict-title">ML Advantage Summary</div>
        <div class="verdict-grid">
            <div>
                <div class="verdict-item-lbl">Unnecessary retries avoided</div>
                <div class="verdict-item-val">${adv.unnecessary_retries_ml_avoided}</div>
            </div>
            <div>
                <div class="verdict-item-lbl">Extra recoveries ML caught</div>
                <div class="verdict-item-val">${adv.recoveries_ml_caught_rules_missed}</div>
            </div>
            <div>
                <div class="verdict-item-lbl">Operational cost savings</div>
                <div class="verdict-item-val">${fmt(adv.operational_cost_savings)}</div>
            </div>
            <div>
                <div class="verdict-item-lbl">Net value uplift</div>
                <div class="verdict-item-val">${fmt(adv.net_value_uplift)}</div>
            </div>
        </div>
        <p style="margin-top:14px;font-size:0.72rem;color:var(--text-muted)">${adv.verdict}</p>`;
}

// ── ROI ───────────────────────────────────────────────────
function populateROITab(s) {
    const roi = s.roi; if (!roi) return;
    const rev = roi.revenue, costs = roi.costs, kpis = roi.roi, be = roi.break_even;

    document.getElementById('roi-grid').innerHTML = `
        <div class="roi-section">
            <div class="roi-sec-title">Revenue</div>
            <div class="roi-row"><span class="roi-row-lbl">Gross Recovered</span><span class="roi-row-val">${fmt(rev.gross_recovered)}</span></div>
            <div class="roi-row"><span class="roi-row-lbl">Gateway Fees (2%)</span><span class="roi-row-val lo">−${fmt(rev.gateway_fees)}</span></div>
            <hr class="roi-divider">
            <div class="roi-row"><span class="roi-row-lbl">Net Revenue</span><span class="roi-row-val">${fmt(rev.net_recovered)}</span></div>
        </div>
        <div class="roi-section">
            <div class="roi-sec-title">Operational Costs</div>
            <div class="roi-row"><span class="roi-row-lbl">Retry Cost (₹0.50/attempt)</span><span class="roi-row-val dim">−${fmt(costs.retry_cost)}</span></div>
            <div class="roi-row"><span class="roi-row-lbl">Escalation Cost (₹5/case)</span><span class="roi-row-val dim">−${fmt(costs.escalation_cost)}</span></div>
            <hr class="roi-divider">
            <div class="roi-row"><span class="roi-row-lbl">Total Cost</span><span class="roi-row-val dim">−${fmt(costs.total_operational_cost)}</span></div>
        </div>
        <div class="roi-section">
            <div class="roi-sec-title">Return on Investment</div>
            <div class="roi-row"><span class="roi-row-lbl">Net ROI</span><span class="roi-row-val">${fmt(kpis.net_roi)}</span></div>
            <div class="roi-row"><span class="roi-row-lbl">Cost Efficiency</span><span class="roi-row-val">${fmtPct(kpis.cost_efficiency_percent)}</span></div>
            <div class="roi-row"><span class="roi-row-lbl">Cost per ₹1 recovered</span><span class="roi-row-val lo">₹${kpis.cost_per_recovered_rupee?.toFixed(4) || '—'}</span></div>
        </div>`;

    const surplus = (be.actual_recovery_rate_percent - be.break_even_recovery_rate_percent).toFixed(1);
    document.getElementById('break-even-card').innerHTML = `
        <div>
            <div class="be-item-lbl">Break-Even Rate</div>
            <div class="be-item-val">${fmtPct(be.break_even_recovery_rate_percent)}</div>
        </div>
        <div>
            <div class="be-item-lbl">Actual Rate</div>
            <div class="be-item-val accent">${fmtPct(be.actual_recovery_rate_percent)}</div>
        </div>
        <div>
            <div class="be-item-lbl">Surplus</div>
            <div class="be-item-val">+${surplus} pp</div>
        </div>
        <div>
            <div class="be-item-lbl">Min. Recoveries Needed</div>
            <div class="be-item-val">${be.min_recoveries_needed}</div>
        </div>`;
}

// ── Directions ────────────────────────────────────────────
function populateDirections(s) {
    const pd = s.per_direction || {};
    const meta = {
        payment_failure: { icon: '💳', name: 'Payment Failure', sub: 'UPI · Card · Bank' },
        checkout_abandonment: { icon: '🛒', name: 'Checkout Abandonment', sub: 'Cart · Friction · Promo' },
        subscription_lapsed: { icon: '↻', name: 'Subscription Lapsed', sub: 'Mandate · Pause · Renewal' },
        b2b_receivable: { icon: '◻', name: 'B2B Receivable', sub: 'Invoice · Credit · Dispute' },
    };
    document.getElementById('directions-grid').innerHTML = Object.entries(meta).map(([key, m]) => {
        const d = pd[key] || { total: 0, recovered_count: 0, recovered_amount: 0, recovery_rate_percent: 0 };
        return `
            <div class="dir-card">
                <div class="dir-icon">${m.icon}</div>
                <div class="dir-name">${m.name}</div>
                <div class="dir-sub">${m.sub}</div>
                <div class="dir-bar-wrap">
                    <div class="dir-bar-header">
                        <span>Recovery Rate</span>
                        <span>${d.recovery_rate_percent}%</span>
                    </div>
                    <div class="dir-bar-track">
                        <div class="dir-bar-fill" style="width:${d.recovery_rate_percent}%"></div>
                    </div>
                </div>
                <div class="dir-stats">
                    <div><div class="dir-stat-val">${d.total}</div><div class="dir-stat-lbl">Total</div></div>
                    <div><div class="dir-stat-val">${d.recovered_count || 0}</div><div class="dir-stat-lbl">Recovered</div></div>
                    <div><div class="dir-stat-val">${fmt(d.recovered_amount)}</div><div class="dir-stat-lbl">Amount</div></div>
                </div>
            </div>`;
    }).join('');
}

// ── Transactions ──────────────────────────────────────────
async function loadTransactions() {
    const status = document.getElementById('status-filter').value;
    const direction = document.getElementById('direction-filter').value;
    const search = document.getElementById('search-filter').value.trim();
    let url = `${API}/api/transactions?limit=1000`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (direction) url += `&direction=${encodeURIComponent(direction)}`;
    const tbody = document.getElementById('txn-body');
    tbody.innerHTML = '<tr><td colspan="9" class="loading">Loading...</td></tr>';
    try {
        const res = await fetch(url);
        let data = await res.json();
        if (search) data = data.filter(r => r.transaction_id?.toLowerCase().includes(search.toLowerCase()));
        if (!data.length) { tbody.innerHTML = '<tr><td colspan="9" class="loading">No results.</td></tr>'; return; }
        tbody.innerHTML = data.map(buildRow).join('');
    } catch (e) { tbody.innerHTML = `<tr><td colspan="9" class="loading">Error: ${e.message}</td></tr>`; }
}

function statusPill(s) {
    const map = {
        recovered: { cls: 'pill-green', lbl: 'Recovered' },
        escalated_max_attempts: { cls: 'pill-orange', lbl: 'Escalated · cap' },
        escalated_low_probability: { cls: 'pill-gray', lbl: 'Escalated · prob' },
        retry_failed: { cls: 'pill-gray', lbl: 'Retry Failed' },
    };
    const p = map[s] || { cls: 'pill-gray', lbl: s };
    return `<span class="pill ${p.cls}">${p.lbl}</span>`;
}

function dirLabel(d) {
    const m = { payment_failure: 'Payment', checkout_abandonment: 'Checkout', subscription_lapsed: 'Subscription', b2b_receivable: 'B2B' };
    return m[d] || d || '—';
}

function buildRow(row) {
    const prob = row.recovery_probability || 0;
    const probPct = (prob * 100).toFixed(0);
    const probClr = prob >= 0.5 ? 'var(--s-green)' : prob >= 0.2 ? 'var(--text-muted)' : 'var(--s-red)';
    const rzpMode = row.razorpay_mode || 'sandbox';
    const rzpCls = rzpMode.startsWith('live') ? '' : 'sandbox';
    return `<tr>
        <td class="mono" style="font-size:0.67rem;color:var(--text-faint)">${row.transaction_id || '—'}</td>
        <td style="font-size:0.7rem;color:var(--text-muted)">${dirLabel(row.direction)}</td>
        <td style="font-weight:600;color:var(--text-hi)">${fmt(row.amount)}</td>
        <td style="font-size:0.7rem">${(row.root_cause || '—').replace(/_/g, ' ')}</td>
        <td style="font-size:0.68rem;color:var(--text-faint)">${(row.recommended_action || '—').replace(/_/g, ' ')}</td>
        <td>
            <div class="prob-wrap">
                <div class="prob-track"><div class="prob-fill" style="width:${probPct}%;background:${probClr}"></div></div>
                <span class="mono" style="font-size:0.67rem;color:var(--text-faint)">${probPct}%</span>
            </div>
        </td>
        <td>${statusPill(row.final_status)}</td>
        <td><span class="pill ${rzpCls ? 'pill-gray' : 'pill-gold'}" style="font-size:0.6rem">${rzpMode.replace('_', ' ')}</span></td>
        <td><button class="btn-explain" onclick='openExplain("${row.transaction_id}")'>Explain</button></td>
    </tr>`;
}

// ── Explain modal ─────────────────────────────────────────
async function openExplain(txnId) {
    document.getElementById('modal-backdrop').style.display = 'flex';
    document.getElementById('modal-title').textContent = txnId;
    document.getElementById('modal-body').innerHTML = '<p style="color:var(--text-muted);font-size:0.75rem">Loading...</p>';
    try {
        const res = await fetch(`${API}/api/transactions/${txnId}/explain`);
        const d = await res.json();
        renderModal(d);
    } catch (e) { document.getElementById('modal-body').innerHTML = `<p style="color:var(--s-red)">Error: ${e.message}</p>`; }
}

function renderModal(d) {
    const ex     = d.explainability || {};
    const path   = ex.decision_path || [];
    const fac    = ex.factors || {};
    const conf   = ex.confidence || 'medium';
    const rzp    = d.razorpay_response;
    const status = d.final_status;

    // ── Outcome banner — shows FINAL result, not just decision point ──
    const outcomeMeta = {
        recovered:                  { cls: 'pill-green',  icon: '✓', lbl: 'Recovered',                  note: 'Payment was successfully captured.' },
        retry_failed:               { cls: 'pill-gray',   icon: '✗', lbl: 'Retry Failed',                note: 'Agent decided to retry (see decision path below), but the retry attempt itself failed — Razorpay returned a payment failure even after the retry.' },
        escalated_max_attempts:     { cls: 'pill-orange', icon: '↑', lbl: 'Escalated — Max Attempts',    note: 'All 3 retry attempts were exhausted without recovery. Handed off to manual review.' },
        escalated_low_probability:  { cls: 'pill-gray',   icon: '↑', lbl: 'Escalated — Low Probability', note: 'ML model predicted recovery probability fell below 20%. Agent stopped retrying early to save cost.' },
    };
    const om = outcomeMeta[status] || { cls: 'pill-gray', icon: '?', lbl: status, note: '' };

    const outcomeBanner = `
        <div style="display:flex;align-items:flex-start;gap:10px;background:var(--bg-row);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px 14px;margin-bottom:18px">
            <span class="pill ${om.cls}" style="flex-shrink:0;margin-top:1px">${om.icon} ${om.lbl}</span>
            <span style="font-size:0.72rem;color:var(--text-muted);line-height:1.6">${om.note}</span>
        </div>`;

    const pathHtml = path.map((step, i) => {
        const last = i === path.length - 1;
        return `<span class="path-step ${last ? 'end' : ''}">${step}</span>${!last ? '<span class="path-arrow">→</span>' : ''}`;
    }).join('');

    const factorRows = [
        ['Attempt Number',     fac.attempt_number],
        ['Max Attempts Cap',   fac.max_attempts_cap],
        ['Recovery Prob.',     fac.recovery_probability != null ? (fac.recovery_probability * 100).toFixed(1) + '%' : '—'],
        ['Stopping Threshold', fac.stopping_threshold != null ? (fac.stopping_threshold * 100).toFixed(0) + '%' : '—'],
        ['Rule Triggered',     (fac.stopping_rule_triggered || 'none').replace(/_/g, ' ')],
        ['Root Cause',         (fac.root_cause || '—').replace(/_/g, ' ')],
        ['Direction',          (fac.direction || '—').replace(/_/g, ' ')],
    ].map(([k, v]) => `<tr><td>${k}</td><td>${v ?? '—'}</td></tr>`).join('');

    const rzpHtml = rzp ? `
        <div class="explain-sec-title">Razorpay Response</div>
        <div class="rzp-box">${JSON.stringify(rzp, null, 2)}</div>` : '';

    // Customer message — add a note if status is retry_failed that the "retrying" message was sent BEFORE the retry failed
    const msgNote = status === 'retry_failed'
        ? `<div style="font-size:0.65rem;color:var(--text-faint);margin-bottom:6px">Message sent to customer at decision time (before retry outcome was known):</div>`
        : '';

    document.getElementById('modal-body').innerHTML = `
        ${outcomeBanner}

        <div class="explain-sec-title">Decision Path</div>
        <div class="path-row">${pathHtml}</div>

        <div class="explain-sec-title" style="margin-top:16px">Decision Summary</div>
        <div class="explain-summary">${ex.human_readable || d.reasoning || '—'}</div>

        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
            <div class="explain-sec-title" style="margin:0">Confidence</div>
            <span class="conf-pill ${conf}">${conf.replace(/_/g, ' ')}</span>
        </div>

        <div class="explain-sec-title">Decision Factors</div>
        <table class="factor-table"><tbody>${factorRows}</tbody></table>

        ${rzpHtml}

        <div class="explain-sec-title" style="margin-top:16px">Customer Message</div>
        ${msgNote}
        <div class="msg-box">${d.customer_message || '—'}</div>`;
}

function closeModal() { document.getElementById('modal-backdrop').style.display = 'none'; }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── Live Simulation ───────────────────────────────────────
function startSimulation() {
    if (simSource) { simSource.close(); simSource = null; }
    const speed = parseFloat(document.getElementById('sim-speed').value || '1');
    document.getElementById('sim-overlay').style.display = 'block';
    document.getElementById('feed-card').style.display = 'block';
    document.getElementById('live-feed').innerHTML = '';
    switchPanel('overview');
    simTotal = 0; simDone = 0; simPaused = false; simBuffer = [];
    simCounts = { recovered: 0, escalated: 0, retry_failed: 0 };
    document.getElementById('sim-status-text').textContent = 'Connecting...';
    document.getElementById('sim-progress-bar').style.width = '0%';
    document.getElementById('sim-count-text').textContent = '0 / 0';
    document.getElementById('btn-simulate').disabled = true;

    simSource = new EventSource(`${API}/api/simulate/stream?speed=${speed}`);
    simSource.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (simPaused) { simBuffer.push(msg); return; }
        handleSimMsg(msg);
    };
    simSource.onerror = () => {
        document.getElementById('sim-status-text').textContent = 'Stream error';
        document.getElementById('btn-simulate').disabled = false;
    };
}

function handleSimMsg(msg) {
    if (msg.type === 'meta') {
        simTotal = msg.total;
        document.getElementById('sim-status-text').textContent = `Simulating ${simTotal} transactions...`;
        document.getElementById('sim-count-text').textContent = `0 / ${simTotal}`;
    } else if (msg.type === 'transaction') {
        simDone++;
        const pct = simTotal ? ((simDone / simTotal) * 100).toFixed(1) : 0;
        document.getElementById('sim-progress-bar').style.width = pct + '%';
        document.getElementById('sim-count-text').textContent = `${simDone} / ${simTotal}`;
        const row = msg.data;
        const s = row.final_status;
        if (s === 'recovered') simCounts.recovered++;
        else if (s?.startsWith('escalated')) simCounts.escalated++;
        else simCounts.retry_failed++;
        document.getElementById('kpi-val-rate').textContent = ((simCounts.recovered / simDone) * 100).toFixed(1) + '%';

        const cls = s === 'recovered' ? 'recovered' : s === 'escalated_max_attempts' ? 'escalated_max' : s === 'escalated_low_probability' ? 'escalated_low' : 'retry_failed';
        const entry = document.createElement('div');
        entry.className = 'feed-entry';
        entry.innerHTML = `
            <span class="feed-badge ${cls}">${s?.replace(/_/g, ' ')}</span>
            <span class="feed-txn">${row.transaction_id}</span>
            <span class="feed-dir">${dirLabel(row.direction)}</span>
            <span class="feed-amount">${fmt(row.amount)}</span>`;
        const feed = document.getElementById('live-feed');
        feed.insertBefore(entry, feed.firstChild);
        if (feed.children.length > 40) feed.removeChild(feed.lastChild);
    } else if (msg.type === 'summary') {
        document.getElementById('sim-status-text').textContent = 'Simulation complete';
        if (msg.data) { summaryData = msg.data; populateKPIs(summaryData); populateOutcomeBars(summaryData); }
        document.getElementById('btn-simulate').disabled = false;
    } else if (msg.type === 'done') { simSource?.close(); simSource = null; }
}

function pauseSimulation() {
    simPaused = !simPaused;
    document.getElementById('btn-pause').textContent = simPaused ? '▶ Resume' : '⏸ Pause';
    if (!simPaused) { simBuffer.forEach(handleSimMsg); simBuffer = []; }
}

function stopSimulation() {
    simSource?.close(); simSource = null;
    document.getElementById('sim-overlay').style.display = 'none';
    document.getElementById('btn-simulate').disabled = false;
    simPaused = false;
}

function changeSimSpeed() { if (simSource) { stopSimulation(); setTimeout(startSimulation, 150); } }