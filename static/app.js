/**
 * QUANTA — Swing Trade Scanner Dashboard
 * Frontend JavaScript: API calls, rendering, filtering, and interactions.
 */

// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════

let allAlerts = [];
let pollInterval = null;

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    updateClock();
    setInterval(updateClock, 1000);
    loadSectors();
    loadAlerts();
});

function updateClock() {
    const el = document.getElementById("currentTime");
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
        });
    }
}

async function loadSectors() {
    try {
        const res = await fetch("/api/sectors");
        const sectors = await res.json();
        const select = document.getElementById("filterSector");
        sectors.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s;
            opt.textContent = s;
            select.appendChild(opt);
        });
    } catch (e) {
        console.warn("Could not load sectors:", e);
    }
}

// ═══════════════════════════════════════════════════════════
// SCAN TRIGGER & POLLING
// ═══════════════════════════════════════════════════════════

async function triggerScan() {
    const btn = document.getElementById("btnScan");
    btn.classList.add("scanning");
    btn.querySelector("span").textContent = "Scanning...";

    const progress = document.getElementById("progressContainer");
    progress.classList.add("active");

    try {
        await fetch("/api/scan", { method: "POST" });
        startPolling();
    } catch (e) {
        console.error("Failed to start scan:", e);
        btn.classList.remove("scanning");
        btn.querySelector("span").textContent = "Run Scanner";
        progress.classList.remove("active");
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(pollStatus, 1500);
}

async function pollStatus() {
    try {
        const res = await fetch("/api/status");
        const status = await res.json();

        // Update progress bar
        const fill = document.getElementById("progressFill");
        const text = document.getElementById("progressText");
        const pct = document.getElementById("progressPct");

        fill.style.width = status.progress + "%";
        text.textContent = status.current_stock || "Processing...";
        pct.textContent = status.progress + "%";

        // Update stats
        document.getElementById("statScanned").textContent = status.total_scanned || "—";

        if (!status.running) {
            // Scan complete
            clearInterval(pollInterval);
            pollInterval = null;

            const btn = document.getElementById("btnScan");
            btn.classList.remove("scanning");
            btn.querySelector("span").textContent = "Run Scanner";

            setTimeout(() => {
                document.getElementById("progressContainer").classList.remove("active");
            }, 1000);

            loadAlerts();
        }
    } catch (e) {
        console.warn("Polling error:", e);
    }
}

// ═══════════════════════════════════════════════════════════
// LOAD & DISPLAY ALERTS
// ═══════════════════════════════════════════════════════════

async function loadAlerts() {
    try {
        const params = new URLSearchParams();
        const exchange = document.getElementById("filterExchange").value;
        const sector = document.getElementById("filterSector").value;
        const confidence = document.getElementById("filterConfidence").value;
        const sortBy = document.getElementById("filterSort").value;

        if (exchange) params.set("exchange", exchange);
        if (sector) params.set("sector", sector);
        if (confidence) params.set("min_confidence", confidence);
        if (sortBy) params.set("sort_by", sortBy);

        const res = await fetch("/api/alerts?" + params.toString());
        const data = await res.json();

        allAlerts = data.alerts || [];
        renderAlerts(allAlerts);

        // Update stats
        const status = data.scan_status || {};
        document.getElementById("statScanned").textContent = status.total_scanned || "—";
        document.getElementById("statAlerts").textContent = data.count || "0";
        document.getElementById("statLastScan").textContent = status.last_scan || "Never";

        if (allAlerts.length > 0) {
            const avgConf = Math.round(allAlerts.reduce((s, a) => s + a.confidence, 0) / allAlerts.length);
            document.getElementById("statConfidence").textContent = avgConf;
        } else {
            document.getElementById("statConfidence").textContent = "—";
        }

    } catch (e) {
        console.warn("Could not load alerts:", e);
    }
}

function applyFilters() {
    loadAlerts();
}

// ═══════════════════════════════════════════════════════════
// RENDER ALERT CARDS
// ═══════════════════════════════════════════════════════════

function renderAlerts(alerts) {
    const grid = document.getElementById("alertsGrid");
    const empty = document.getElementById("emptyState");

    if (alerts.length === 0) {
        // Check if we ever ran a scan
        const lastScan = document.getElementById("statLastScan").textContent;
        if (lastScan === "Never") {
            grid.innerHTML = "";
            grid.appendChild(empty);
        } else {
            grid.innerHTML = `
                <div class="no-results">
                    <h3>No Alerts Found</h3>
                    <p>No stocks currently meet all quantitative criteria. This is expected — the system is strict by design to ensure only high-probability setups are flagged.</p>
                </div>
            `;
        }
        return;
    }

    grid.innerHTML = alerts.map((alert, i) => renderCard(alert, i)).join("");
}

function renderCard(alert, index) {
    const confColor = getConfidenceColor(alert.confidence);
    const circumference = 2 * Math.PI * 20;
    const offset = circumference - (alert.confidence / 100) * circumference;

    return `
        <div class="alert-card" onclick="showDetail(${index})" style="animation-delay: ${index * 80}ms">
            <div class="card-header">
                <div class="card-stock-info">
                    <div class="card-stock-name">${escHtml(alert.stock_name)}</div>
                    <div class="card-symbol">${escHtml(alert.symbol)}</div>
                    <div class="card-badge-group">
                        <span class="card-sector">${escHtml(alert.sector)}</span>
                        <span class="card-exchange">${alert.exchange}</span>
                    </div>
                </div>
                <div class="card-confidence">
                    <div class="confidence-ring">
                        <svg viewBox="0 0 48 48" width="52" height="52">
                            <circle class="ring-bg" cx="24" cy="24" r="20"/>
                            <circle class="ring-fill" cx="24" cy="24" r="20"
                                stroke="${confColor}" stroke-dasharray="${circumference}"
                                stroke-dashoffset="${offset}"/>
                        </svg>
                        <span class="confidence-value" style="color:${confColor}">${alert.confidence}</span>
                    </div>
                    <span class="confidence-label">Confidence</span>
                </div>
            </div>

            <div class="card-price-row">
                <span class="card-price">₹${alert.current_price.toLocaleString("en-IN")}</span>
                <span class="card-price-label">CMP</span>
            </div>

            <div class="card-pattern">${escHtml(alert.pattern)}</div>

            <div class="card-metrics">
                <div class="metric">
                    <div class="metric-label">Entry</div>
                    <div class="metric-value cyan">₹${alert.entry_price}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Stop Loss</div>
                    <div class="metric-value red">₹${alert.stop_loss}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Target 1</div>
                    <div class="metric-value green">₹${alert.target_1}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Target 2</div>
                    <div class="metric-value green">₹${alert.target_2}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Max Target</div>
                    <div class="metric-value amber">₹${alert.max_target}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Vol Ratio</div>
                    <div class="metric-value cyan">${alert.volume_ratio}x</div>
                </div>
            </div>

            <div class="card-footer">
                <div class="card-rr">
                    <span class="rr-label">R:R</span>
                    <span class="rr-value">1:${alert.risk_reward}</span>
                </div>
                <span class="card-view-btn">View Details →</span>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════
// DETAIL MODAL
// ═══════════════════════════════════════════════════════════

function showDetail(index) {
    const alert = allAlerts[index];
    if (!alert) return;

    const confColor = getConfidenceColor(alert.confidence);
    const content = document.getElementById("modalContent");

    content.innerHTML = `
        <div class="modal-header">
            <div class="modal-stock-name">${escHtml(alert.stock_name)}</div>
            <div class="modal-stock-meta">
                <span class="card-symbol">${escHtml(alert.symbol)}</span>
                <span class="card-sector">${escHtml(alert.sector)}</span>
                <span class="card-exchange">${alert.exchange}</span>
                <span class="badge badge-time">${alert.scan_date}</span>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Price & Risk Management</div>
            <div class="modal-grid">
                <div class="modal-metric">
                    <div class="modal-metric-label">Current Price</div>
                    <div class="modal-metric-value" style="color:var(--text-primary)">₹${alert.current_price.toLocaleString("en-IN")}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Entry Price</div>
                    <div class="modal-metric-value" style="color:var(--accent-cyan)">₹${alert.entry_price}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Stop Loss</div>
                    <div class="modal-metric-value" style="color:var(--accent-red)">₹${alert.stop_loss}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Risk per Share</div>
                    <div class="modal-metric-value" style="color:var(--accent-amber)">₹${alert.risk_per_share}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Target 1 (1.5R)</div>
                    <div class="modal-metric-value" style="color:var(--accent-green)">₹${alert.target_1}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Target 2 (3R)</div>
                    <div class="modal-metric-value" style="color:var(--accent-green)">₹${alert.target_2}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Max Target</div>
                    <div class="modal-metric-value" style="color:var(--accent-amber)">₹${alert.max_target}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Risk : Reward</div>
                    <div class="modal-metric-value" style="color:var(--accent-green)">1:${alert.risk_reward}</div>
                </div>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Technical Indicators</div>
            <div class="modal-grid">
                <div class="modal-metric">
                    <div class="modal-metric-label">RSI (14)</div>
                    <div class="modal-metric-value">${alert.rsi}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">ADX (14)</div>
                    <div class="modal-metric-value">${alert.adx || '—'}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Volume Ratio</div>
                    <div class="modal-metric-value">${alert.volume_ratio}x</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">ATR (14)</div>
                    <div class="modal-metric-value">₹${alert.atr}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">EMA 20</div>
                    <div class="modal-metric-value">₹${alert.ema_20}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">EMA 50</div>
                    <div class="modal-metric-value">₹${alert.ema_50}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">EMA 200</div>
                    <div class="modal-metric-value">₹${alert.ema_200}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">BB Width</div>
                    <div class="modal-metric-value">${alert.bb_width}</div>
                </div>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Pattern & Confidence</div>
            <div class="modal-grid">
                <div class="modal-metric">
                    <div class="modal-metric-label">Pattern</div>
                    <div class="modal-metric-value" style="color:var(--accent-cyan); font-size: 0.9rem">${escHtml(alert.pattern)}</div>
                </div>
                <div class="modal-metric">
                    <div class="modal-metric-label">Confidence Score</div>
                    <div class="modal-metric-value" style="color:${confColor}">${alert.confidence}/100</div>
                </div>
            </div>
        </div>

        ${alert.alpha_boosters && alert.alpha_boosters.length > 0 ? `
        <div class="modal-section">
            <div class="modal-section-title">Alpha Boosters (${alert.alpha_count})</div>
            <ul class="modal-reasons">
                ${alert.alpha_boosters.map(b => `<li class="booster">⚡ ${escHtml(b)}</li>`).join("")}
            </ul>
        </div>
        ` : ""}

        <div class="modal-section">
            <div class="modal-section-title">Reasons for Selection</div>
            <ul class="modal-reasons">
                ${alert.reasons.map(r => `<li>${escHtml(r)}</li>`).join("")}
            </ul>
        </div>
    `;

    document.getElementById("modalOverlay").classList.add("active");
    document.body.style.overflow = "hidden";
}

function closeModal() {
    document.getElementById("modalOverlay").classList.remove("active");
    document.body.style.overflow = "";
}

// Close on Escape key
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
});

// ═══════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════

function getConfidenceColor(score) {
    if (score >= 75) return "#10b981";
    if (score >= 60) return "#00d4ff";
    if (score >= 45) return "#f59e0b";
    return "#ef4444";
}

function escHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}
