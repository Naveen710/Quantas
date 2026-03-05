"""
Quant Swing Trade Scanner — Flask Application
Serves API endpoints and the web dashboard.
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

import config
import data_fetcher
import scanner
import risk_manager

# ── Logging Setup ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("QuantScanner")

# ── Flask App ──
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# ── Alert Cache & Dedup ──
alert_cache = []
alert_history = {}  # symbol -> last alert datetime
scan_failure_stats = {}  # criterion -> count of failures
scan_status = {
    "running": False,
    "last_scan": None,
    "total_scanned": 0,
    "alerts_found": 0,
    "progress": 0,
    "current_stock": "",
    "errors": 0,
}


def is_duplicate_alert(symbol: str) -> bool:
    """Check if symbol was alerted within the dedup window."""
    if symbol in alert_history:
        last_alert = alert_history[symbol]
        if datetime.now() - last_alert < timedelta(days=config.DEDUP_WINDOW_DAYS):
            return True
    return False


def run_scan():
    """Execute the full scan across all stocks in the universe."""
    global alert_cache, scan_status, scan_failure_stats

    scan_status["running"] = True
    scan_status["progress"] = 0
    scan_status["errors"] = 0
    alerts = []
    scan_failure_stats = {
        "data_fetch": 0,
        "universe_filter": 0,
        "Trend Filter": 0,
        "Weekly Trend": 0,
        "Momentum": 0,
        "Volatility/Structure": 0,
        "Volume": 0,
        "Alpha Boosters": 0,
        "risk_reward": 0,
    }

    # Get the stock universe
    universe = data_fetcher.get_stock_universe()
    total = len(universe)
    scan_status["total_scanned"] = total

    logger.info(f"═══ Starting scan of {total} stocks ═══")

    # Fetch NIFTY data once for relative strength calculations
    logger.info("Fetching NIFTY 50 benchmark data...")
    nifty_df = data_fetcher.fetch_nifty_data()

    scanned = 0
    passed_universe = 0
    passed_all = 0

    for i, stock in enumerate(universe):
        symbol = stock["symbol"]
        name = stock["name"]
        sector = stock["sector"]
        exchange = stock["exchange"]

        scan_status["current_stock"] = f"{name} ({symbol})"
        scan_status["progress"] = int((i + 1) / total * 100)

        # Skip duplicates
        if is_duplicate_alert(symbol):
            continue

        try:
            # Rate limit: small delay between API calls to avoid yfinance throttling
            if i > 0 and i % 5 == 0:
                time.sleep(0.3)

            # Fetch daily data
            daily_df = data_fetcher.fetch_daily_data(symbol)
            if daily_df is None:
                scan_failure_stats["data_fetch"] += 1
                continue

            # Universe filter
            if not data_fetcher.passes_universe_filter(daily_df):
                scan_failure_stats["universe_filter"] += 1
                continue
            passed_universe += 1

            # Fetch weekly data
            weekly_df = data_fetcher.fetch_weekly_data(symbol)

            # Run scanner
            result = scanner.scan_stock(
                symbol, name, sector, exchange,
                daily_df, weekly_df, nifty_df
            )
            scanned += 1

            if result.passed:
                # Generate alert with risk management
                alert = risk_manager.generate_alert(result)
                if alert:
                    alerts.append(alert)
                    alert_history[symbol] = datetime.now()
                    passed_all += 1
                    logger.info(f"✅ ALERT: {name} ({symbol}) — Confidence: {alert['confidence']}")
                else:
                    scan_failure_stats["risk_reward"] += 1
            else:
                # Track which criterion failed
                failed_at = result.failed_at
                for key in scan_failure_stats:
                    if key in failed_at:
                        scan_failure_stats[key] += 1
                        break

        except Exception as e:
            scan_status["errors"] += 1
            logger.error(f"Error scanning {symbol}: {e}")
            continue

    # Sort alerts by confidence (highest first)
    alerts.sort(key=lambda x: x["confidence"], reverse=True)

    alert_cache = alerts
    scan_status["running"] = False
    scan_status["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_status["alerts_found"] = len(alerts)
    scan_status["progress"] = 100

    logger.info(f"═══ Scan complete ═══")
    logger.info(f"    Universe: {total} | Passed filters: {passed_universe} | Scanned: {scanned}")
    logger.info(f"    Alerts generated: {len(alerts)} | Errors: {scan_status['errors']}")
    logger.info(f"    Failure breakdown: {json.dumps(scan_failure_stats, indent=2)}")

    return alerts


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Serve the main dashboard."""
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/scan", methods=["POST"])
def trigger_scan():
    """Trigger a new scan."""
    if scan_status["running"]:
        return jsonify({"error": "Scan already in progress"}), 409

    import threading
    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()

    return jsonify({"message": "Scan started", "total_stocks": len(data_fetcher.get_stock_universe())})


@app.route("/api/status")
def get_status():
    """Get current scan status."""
    return jsonify(scan_status)


@app.route("/api/alerts")
def get_alerts():
    """Get cached alerts."""
    # Optional filtering
    min_confidence = request.args.get("min_confidence", 0, type=int)
    sector = request.args.get("sector", "")
    exchange = request.args.get("exchange", "")
    sort_by = request.args.get("sort_by", "confidence")

    filtered = alert_cache

    if min_confidence > 0:
        filtered = [a for a in filtered if a["confidence"] >= min_confidence]
    if sector:
        filtered = [a for a in filtered if a["sector"].lower() == sector.lower()]
    if exchange:
        filtered = [a for a in filtered if a["exchange"].lower() == exchange.lower()]

    # Sort
    if sort_by == "risk_reward":
        filtered.sort(key=lambda x: x["risk_reward"], reverse=True)
    elif sort_by == "volume":
        filtered.sort(key=lambda x: x["volume_ratio"], reverse=True)
    elif sort_by == "price":
        filtered.sort(key=lambda x: x["current_price"])
    else:
        filtered.sort(key=lambda x: x["confidence"], reverse=True)

    return jsonify({
        "alerts": filtered,
        "count": len(filtered),
        "scan_status": scan_status,
    })


@app.route("/api/sectors")
def get_sectors():
    """Get all unique sectors in the universe."""
    universe = data_fetcher.get_stock_universe()
    sectors = sorted(set(s["sector"] for s in universe))
    return jsonify(sectors)


@app.route("/api/scan-stats")
def get_scan_stats():
    """Get scan failure statistics for debugging."""
    return jsonify({
        "failure_breakdown": scan_failure_stats,
        "scan_status": scan_status,
    })


# ═══════════════════════════════════════════════════════════════
# RUN SERVER
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║   Quant Swing Trade Scanner — NSE/BSE       ║")
    logger.info("║   Dashboard: http://127.0.0.1:5000          ║")
    logger.info("╚══════════════════════════════════════════════╝")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
