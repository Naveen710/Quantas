"""
Quant Swing Trade Scanner — Data Fetcher
Dynamically fetches ALL NSE stock symbols and their data via yfinance.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
from datetime import datetime, timedelta
import config
import logging
import os
import json

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# DYNAMIC NSE STOCK UNIVERSE
# ═══════════════════════════════════════════════════════════════

# Cache for stock universe
_universe_cache = None
_universe_cache_time = None
CACHE_DURATION_HOURS = 24

NSE_EQUITY_CSV_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.nseindia.com/",
}

# Fallback curated list if NSE CSV fails
FALLBACK_STOCKS = [
    # ── BANKING & FINANCIAL ──
    ("HDFCBANK.NS", "HDFC Bank", "Banking", "NSE"),
    ("ICICIBANK.NS", "ICICI Bank", "Banking", "NSE"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank", "Banking", "NSE"),
    ("SBIN.NS", "State Bank of India", "Banking", "NSE"),
    ("AXISBANK.NS", "Axis Bank", "Banking", "NSE"),
    ("INDUSINDBK.NS", "IndusInd Bank", "Banking", "NSE"),
    ("BANKBARODA.NS", "Bank of Baroda", "Banking", "NSE"),
    ("PNB.NS", "Punjab National Bank", "Banking", "NSE"),
    ("FEDERALBNK.NS", "Federal Bank", "Banking", "NSE"),
    ("IDFCFIRSTB.NS", "IDFC First Bank", "Banking", "NSE"),
    ("AUBANK.NS", "AU Small Finance Bank", "Banking", "NSE"),
    ("BANDHANBNK.NS", "Bandhan Bank", "Banking", "NSE"),
    ("CANBK.NS", "Canara Bank", "Banking", "NSE"),
    ("BAJFINANCE.NS", "Bajaj Finance", "Financial Services", "NSE"),
    ("BAJAJFINSV.NS", "Bajaj Finserv", "Financial Services", "NSE"),
    ("CHOLAFIN.NS", "Cholamandalam Inv & Fin", "Financial Services", "NSE"),
    ("SHRIRAMFIN.NS", "Shriram Finance", "Financial Services", "NSE"),
    ("MUTHOOTFIN.NS", "Muthoot Finance", "Financial Services", "NSE"),
    ("HDFCLIFE.NS", "HDFC Life Insurance", "Insurance", "NSE"),
    ("SBILIFE.NS", "SBI Life Insurance", "Insurance", "NSE"),

    # ── IT / TECH ──
    ("TCS.NS", "Tata Consultancy Services", "IT", "NSE"),
    ("INFY.NS", "Infosys", "IT", "NSE"),
    ("WIPRO.NS", "Wipro", "IT", "NSE"),
    ("HCLTECH.NS", "HCL Technologies", "IT", "NSE"),
    ("TECHM.NS", "Tech Mahindra", "IT", "NSE"),
    ("LTIM.NS", "LTIMindtree", "IT", "NSE"),
    ("MPHASIS.NS", "Mphasis", "IT", "NSE"),
    ("COFORGE.NS", "Coforge", "IT", "NSE"),
    ("PERSISTENT.NS", "Persistent Systems", "IT", "NSE"),

    # ── AUTOMOBILE ──
    ("TATAMOTORS.NS", "Tata Motors", "Automobile", "NSE"),
    ("M&M.NS", "Mahindra & Mahindra", "Automobile", "NSE"),
    ("MARUTI.NS", "Maruti Suzuki", "Automobile", "NSE"),
    ("BAJAJ-AUTO.NS", "Bajaj Auto", "Automobile", "NSE"),
    ("HEROMOTOCO.NS", "Hero MotoCorp", "Automobile", "NSE"),
    ("EICHERMOT.NS", "Eicher Motors", "Automobile", "NSE"),
    ("TVSMOTOR.NS", "TVS Motor", "Automobile", "NSE"),

    # ── PHARMA & HEALTHCARE ──
    ("SUNPHARMA.NS", "Sun Pharma", "Pharma", "NSE"),
    ("DRREDDY.NS", "Dr Reddy's Labs", "Pharma", "NSE"),
    ("CIPLA.NS", "Cipla", "Pharma", "NSE"),
    ("DIVISLAB.NS", "Divi's Laboratories", "Pharma", "NSE"),
    ("LUPIN.NS", "Lupin", "Pharma", "NSE"),
    ("APOLLOHOSP.NS", "Apollo Hospitals", "Healthcare", "NSE"),

    # ── OIL & GAS / ENERGY ──
    ("RELIANCE.NS", "Reliance Industries", "Oil & Gas", "NSE"),
    ("ONGC.NS", "ONGC", "Oil & Gas", "NSE"),
    ("IOC.NS", "Indian Oil Corporation", "Oil & Gas", "NSE"),
    ("BPCL.NS", "Bharat Petroleum", "Oil & Gas", "NSE"),
    ("NTPC.NS", "NTPC", "Power", "NSE"),
    ("POWERGRID.NS", "Power Grid Corp", "Power", "NSE"),
    ("TATAPOWER.NS", "Tata Power", "Power", "NSE"),
    ("COALINDIA.NS", "Coal India", "Mining", "NSE"),
    ("ADANIENT.NS", "Adani Enterprises", "Conglomerate", "NSE"),
    ("ADANIPORTS.NS", "Adani Ports", "Infrastructure", "NSE"),

    # ── METALS & MINING ──
    ("TATASTEEL.NS", "Tata Steel", "Metals", "NSE"),
    ("JSWSTEEL.NS", "JSW Steel", "Metals", "NSE"),
    ("HINDALCO.NS", "Hindalco", "Metals", "NSE"),
    ("VEDL.NS", "Vedanta", "Metals", "NSE"),

    # ── CEMENT & CONSTRUCTION ──
    ("ULTRACEMCO.NS", "UltraTech Cement", "Cement", "NSE"),
    ("AMBUJACEM.NS", "Ambuja Cements", "Cement", "NSE"),
    ("LT.NS", "Larsen & Toubro", "Construction", "NSE"),

    # ── FMCG & CONSUMER ──
    ("HINDUNILVR.NS", "Hindustan Unilever", "FMCG", "NSE"),
    ("ITC.NS", "ITC", "FMCG", "NSE"),
    ("NESTLEIND.NS", "Nestle India", "FMCG", "NSE"),
    ("BRITANNIA.NS", "Britannia Industries", "FMCG", "NSE"),
    ("TITAN.NS", "Titan Company", "Consumer Durables", "NSE"),
    ("TRENT.NS", "Trent", "Retail", "NSE"),
    ("DMART.NS", "Avenue Supermarts (DMart)", "Retail", "NSE"),

    # ── TELECOM ──
    ("BHARTIARTL.NS", "Bharti Airtel", "Telecom", "NSE"),

    # ── CAPITAL GOODS / DEFENCE ──
    ("SIEMENS.NS", "Siemens", "Capital Goods", "NSE"),
    ("ABB.NS", "ABB India", "Capital Goods", "NSE"),
    ("HAL.NS", "Hindustan Aeronautics", "Defence", "NSE"),
    ("BEL.NS", "Bharat Electronics", "Defence", "NSE"),

    # ── CHEMICALS ──
    ("PIDILITIND.NS", "Pidilite Industries", "Chemicals", "NSE"),
    ("SRF.NS", "SRF", "Chemicals", "NSE"),

    # ── REAL ESTATE ──
    ("DLF.NS", "DLF", "Real Estate", "NSE"),
    ("GODREJPROP.NS", "Godrej Properties", "Real Estate", "NSE"),

    # ── OTHERS ──
    ("ASIANPAINT.NS", "Asian Paints", "Paints", "NSE"),
    ("INDIGO.NS", "InterGlobe Aviation", "Aviation", "NSE"),
    ("IRCTC.NS", "IRCTC", "Travel & Tourism", "NSE"),
    ("ZOMATO.NS", "Zomato", "Food Tech", "NSE"),
    ("LICI.NS", "LIC of India", "Insurance", "NSE"),
    ("GRASIM.NS", "Grasim Industries", "Diversified", "NSE"),
    ("RECLTD.NS", "REC", "Financial Services", "NSE"),
    ("PFC.NS", "Power Finance Corp", "Financial Services", "NSE"),
    ("IRFC.NS", "Indian Railway Finance", "Financial Services", "NSE"),
]


def _fetch_nse_equity_list() -> list[dict]:
    """
    Download the official NSE equity list CSV containing ALL listed stocks.
    Returns a list of dicts with symbol, name, sector, exchange.
    """
    try:
        logger.info("Fetching all NSE-listed equities from NSE archives...")

        session = requests.Session()
        # First hit NSE homepage to get cookies
        session.get("https://www.nseindia.com/", headers=NSE_HEADERS, timeout=10)
        time.sleep(0.5)

        # Download CSV
        response = session.get(NSE_EQUITY_CSV_URL, headers=NSE_HEADERS, timeout=15)
        response.raise_for_status()

        # Parse CSV
        df = pd.read_csv(io.StringIO(response.text))

        # Clean column names
        df.columns = [c.strip().upper() for c in df.columns]

        stocks = []
        for _, row in df.iterrows():
            symbol = str(row.get("SYMBOL", "")).strip()
            name = str(row.get("NAME OF COMPANY", row.get("NAME", symbol))).strip()

            if not symbol or symbol == "nan":
                continue

            # Map industry/sector if available
            sector = "General"
            for col_name in ["INDUSTRY", "SECTOR", "SERIES"]:
                if col_name in df.columns:
                    val = str(row.get(col_name, "")).strip()
                    if val and val != "nan" and val != "":
                        sector = val
                        break

            stocks.append({
                "symbol": f"{symbol}.NS",
                "name": name[:50],  # Truncate long names
                "sector": sector,
                "exchange": "NSE",
            })

        logger.info(f"✅ Fetched {len(stocks)} NSE stocks from official list")
        return stocks

    except Exception as e:
        logger.error(f"Failed to fetch NSE equity list: {e}")
        return []


def get_stock_universe() -> list[dict]:
    """
    Return ALL NSE-listed stocks (dynamically fetched, cached for 24h).
    Falls back to curated list if dynamic fetch fails.
    """
    global _universe_cache, _universe_cache_time

    # Check cache
    if _universe_cache and _universe_cache_time:
        hours_elapsed = (datetime.now() - _universe_cache_time).total_seconds() / 3600
        if hours_elapsed < CACHE_DURATION_HOURS:
            return _universe_cache

    # Try dynamic fetch
    stocks = _fetch_nse_equity_list()

    if len(stocks) > 100:
        _universe_cache = stocks
        _universe_cache_time = datetime.now()
        logger.info(f"Stock universe: {len(stocks)} stocks (dynamic NSE)")
        return stocks

    # Fallback to curated list
    logger.warning("Using fallback curated stock list")
    fallback = [
        {"symbol": sym, "name": name, "sector": sector, "exchange": exchange}
        for sym, name, sector, exchange in FALLBACK_STOCKS
    ]
    _universe_cache = fallback
    _universe_cache_time = datetime.now()
    return fallback


def fetch_daily_data(symbol: str) -> pd.DataFrame | None:
    """
    Fetch daily OHLCV data for a given symbol.
    Returns None if data is insufficient or fetch fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=config.DATA_PERIOD_DAILY, interval="1d")
        if df is None or len(df) < config.EMA_LONG + 20:
            return None
        # Standardize column names
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        logger.debug(f"Error fetching daily data for {symbol}: {e}")
        return None


def fetch_weekly_data(symbol: str) -> pd.DataFrame | None:
    """
    Fetch weekly OHLCV data for a given symbol.
    Returns None if data is insufficient or fetch fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=config.DATA_PERIOD_WEEKLY, interval="1wk")
        if df is None or len(df) < 30:
            return None
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        logger.debug(f"Error fetching weekly data for {symbol}: {e}")
        return None


def fetch_nifty_data() -> pd.DataFrame | None:
    """Fetch NIFTY 50 daily data for relative strength calculations."""
    try:
        ticker = yf.Ticker(config.NIFTY_SYMBOL)
        df = ticker.history(period=config.DATA_PERIOD_DAILY, interval="1d")
        if df is None or len(df) < 60:
            return None
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        logger.error(f"Error fetching NIFTY data: {e}")
        return None


def passes_universe_filter(daily_df: pd.DataFrame) -> bool:
    """
    Check if stock passes basic universe filters:
    - Price ≥ MIN_PRICE
    - Average daily volume ≥ MIN_AVG_VOLUME
    """
    if daily_df is None or len(daily_df) < 20:
        return False

    current_price = daily_df["close"].iloc[-1]
    avg_volume = daily_df["volume"].iloc[-20:].mean()

    if current_price < config.MIN_PRICE:
        return False
    if avg_volume < config.MIN_AVG_VOLUME:
        return False

    return True
