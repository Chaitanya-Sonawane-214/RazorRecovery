const API_BASE = "/api";

async function loadSummary() {
    try {
        const res = await fetch(`${API_BASE}/summary`);
        const data = await res.json();
        renderSummary(data);
        renderBreakdown(data);
    } catch (err) {
        console.error("Failed to load summary:", err);
    }
}

function renderSummary(data) {
    document.getElementById("total-transactions").textContent = data.total_transactions;
    document.getElementById("recovery-rate").textContent = `${data.recovery_rate_percent}%`;
    document.getElementById("amount-recovered").textContent = formatCurrency(data.recovered.amount);
    document.getElementById("amount-at-risk").textContent = formatCurrency(data.total_amount_at_risk);
}

function renderBreakdown(data) {
    const container = document.getElementById("breakdown-bars");
    const total = data.total_transactions;

    const rows = [
        { label: "Recovered", count: data.recovered.count, amount: data.recovered.amount, color: "#22c55e" },
        { label: "Escalated (max attempts)", count: data.escalated_max_attempts.count, amount: data.escalated_max_attempts.amount, color: "#fbbf24" },
        { label: "Escalated (low probability)", count: data.escalated_low_probability.count, amount: data.escalated_low_probability.amount, color: "#fb923c" },
        { label: "Retry failed", count: data.retry_failed.count, amount: data.retry_failed.amount, color: "#f87171" },
    ];

    container.innerHTML = rows.map(row => {
        const pct = total ? (row.count / total * 100).toFixed(1) : 0;
        return `
            <div class="breakdown-row">
                <span class="label">${row.label}</span>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${pct}%; background:${row.color}"></div>
                </div>
                <span class="value">${row.count} (${formatCurrency(row.amount)})</span>
            </div>
        `;
    }).join("");
}

async function loadTransactions(status = "") {
    const tbody = document.getElementById("transactions-body");
    tbody.innerHTML = `<tr><td colspan="6" class="loading">Loading...</td></tr>`;

    try {
        const url = status
            ? `${API_BASE}/transactions?status=${status}&limit=50`
            : `${API_BASE}/transactions?limit=50`;
        const res = await fetch(url);
        const transactions = await res.json();
        renderTransactions(transactions);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="loading">Failed to load transactions.</td></tr>`;
        console.error("Failed to load transactions:", err);
    }
}

function renderTransactions(transactions) {
    const tbody = document.getElementById("transactions-body");

    if (!transactions.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="loading">No transactions found.</td></tr>`;
        return;
    }

    tbody.innerHTML = transactions.map(tx => `
        <tr>
            <td>${tx.transaction_id}</td>
            <td>${formatCurrency(tx.amount)}</td>
            <td>${tx.root_cause}</td>
            <td>${tx.recommended_action}</td>
            <td>${(tx.recovery_probability * 100).toFixed(1)}%</td>
            <td><span class="status-badge status-${tx.final_status}">${formatStatus(tx.final_status)}</span></td>
        </tr>
    `).join("");
}

function formatCurrency(amount) {
    return `₹${Number(amount).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatStatus(status) {
    return status.replace(/_/g, " ");
}

document.getElementById("status-filter").addEventListener("change", (e) => {
    loadTransactions(e.target.value);
});

// Initial load
loadSummary();
loadTransactions();