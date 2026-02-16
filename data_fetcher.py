"""
Quant Swing Trade Scanner — Data Fetcher
Fetches NSE/BSE stock data via yfinance and filters the universe.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import config
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CURATED STOCK UNIVERSE — Major NSE liquid stocks
# Format: (Symbol, Name, Sector, Exchange)
# ═══════════════════════════════════════════════════════════════

NSE_STOCKS = [
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
    ("UNIONBANK.NS", "Union Bank of India", "Banking", "NSE"),
    ("IOB.NS", "Indian Overseas Bank", "Banking", "NSE"),
    ("BAJFINANCE.NS", "Bajaj Finance", "Financial Services", "NSE"),
    ("BAJAJFINSV.NS", "Bajaj Finserv", "Financial Services", "NSE"),
    ("CHOLAFIN.NS", "Cholamandalam Inv & Fin", "Financial Services", "NSE"),
    ("SHRIRAMFIN.NS", "Shriram Finance", "Financial Services", "NSE"),
    ("MUTHOOTFIN.NS", "Muthoot Finance", "Financial Services", "NSE"),
    ("M&MFIN.NS", "Mahindra & Mahindra Financial", "Financial Services", "NSE"),
    ("MANAPPURAM.NS", "Manappuram Finance", "Financial Services", "NSE"),
    ("LICHSGFIN.NS", "LIC Housing Finance", "Financial Services", "NSE"),
    ("PEL.NS", "Piramal Enterprises", "Financial Services", "NSE"),
    ("SBICARD.NS", "SBI Cards", "Financial Services", "NSE"),
    ("HDFCLIFE.NS", "HDFC Life Insurance", "Insurance", "NSE"),
    ("SBILIFE.NS", "SBI Life Insurance", "Insurance", "NSE"),
    ("ICICIPRULI.NS", "ICICI Prudential Life", "Insurance", "NSE"),
    ("ICICIGI.NS", "ICICI Lombard GI", "Insurance", "NSE"),

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
    ("LTTS.NS", "L&T Technology Services", "IT", "NSE"),

    # ── AUTOMOBILE ──
    ("TATAMOTORS.NS", "Tata Motors", "Automobile", "NSE"),
    ("M&M.NS", "Mahindra & Mahindra", "Automobile", "NSE"),
    ("MARUTI.NS", "Maruti Suzuki", "Automobile", "NSE"),
    ("BAJAJ-AUTO.NS", "Bajaj Auto", "Automobile", "NSE"),
    ("HEROMOTOCO.NS", "Hero MotoCorp", "Automobile", "NSE"),
    ("EICHERMOT.NS", "Eicher Motors", "Automobile", "NSE"),
    ("TVSMOTOR.NS", "TVS Motor", "Automobile", "NSE"),
    ("ASHOKLEY.NS", "Ashok Leyland", "Automobile", "NSE"),
    ("MOTHERSON.NS", "Motherson Sumi", "Auto Ancillary", "NSE"),
    ("BALKRISIND.NS", "Balkrishna Industries", "Auto Ancillary", "NSE"),
    ("MRF.NS", "MRF", "Auto Ancillary", "NSE"),
    ("APOLLOTYRE.NS", "Apollo Tyres", "Auto Ancillary", "NSE"),
    ("EXIDEIND.NS", "Exide Industries", "Auto Ancillary", "NSE"),

    # ── PHARMA & HEALTHCARE ──
    ("SUNPHARMA.NS", "Sun Pharma", "Pharma", "NSE"),
    ("DRREDDY.NS", "Dr Reddy's Labs", "Pharma", "NSE"),
    ("CIPLA.NS", "Cipla", "Pharma", "NSE"),
    ("DIVISLAB.NS", "Divi's Laboratories", "Pharma", "NSE"),
    ("LUPIN.NS", "Lupin", "Pharma", "NSE"),
    ("AUROPHARMA.NS", "Aurobindo Pharma", "Pharma", "NSE"),
    ("BIOCON.NS", "Biocon", "Pharma", "NSE"),
    ("TORNTPHARM.NS", "Torrent Pharma", "Pharma", "NSE"),
    ("ALKEM.NS", "Alkem Labs", "Pharma", "NSE"),
    ("APOLLOHOSP.NS", "Apollo Hospitals", "Healthcare", "NSE"),
    ("MAXHEALTH.NS", "Max Healthcare", "Healthcare", "NSE"),
    ("FORTIS.NS", "Fortis Healthcare", "Healthcare", "NSE"),

    # ── OIL & GAS / ENERGY ──
    ("RELIANCE.NS", "Reliance Industries", "Oil & Gas", "NSE"),
    ("ONGC.NS", "ONGC", "Oil & Gas", "NSE"),
    ("IOC.NS", "Indian Oil Corporation", "Oil & Gas", "NSE"),
    ("BPCL.NS", "Bharat Petroleum", "Oil & Gas", "NSE"),
    ("GAIL.NS", "GAIL India", "Oil & Gas", "NSE"),
    ("HINDPETRO.NS", "Hindustan Petroleum", "Oil & Gas", "NSE"),
    ("PETRONET.NS", "Petronet LNG", "Oil & Gas", "NSE"),
    ("ADANIENT.NS", "Adani Enterprises", "Conglomerate", "NSE"),
    ("ADANIPORTS.NS", "Adani Ports", "Infrastructure", "NSE"),
    ("ADANIGREEN.NS", "Adani Green Energy", "Energy", "NSE"),
    ("ADANIPOWER.NS", "Adani Power", "Energy", "NSE"),
    ("NTPC.NS", "NTPC", "Power", "NSE"),
    ("POWERGRID.NS", "Power Grid Corp", "Power", "NSE"),
    ("TATAPOWER.NS", "Tata Power", "Power", "NSE"),
    ("NHPC.NS", "NHPC", "Power", "NSE"),
    ("SJVN.NS", "SJVN", "Power", "NSE"),
    ("COALINDIA.NS", "Coal India", "Mining", "NSE"),

    # ── METALS & MINING ──
    ("TATASTEEL.NS", "Tata Steel", "Metals", "NSE"),
    ("JSWSTEEL.NS", "JSW Steel", "Metals", "NSE"),
    ("HINDALCO.NS", "Hindalco", "Metals", "NSE"),
    ("VEDL.NS", "Vedanta", "Metals", "NSE"),
    ("SAIL.NS", "Steel Authority of India", "Metals", "NSE"),
    ("NMDC.NS", "NMDC", "Mining", "NSE"),
    ("NATIONALUM.NS", "National Aluminium", "Metals", "NSE"),
    ("JINDALSTEL.NS", "Jindal Steel & Power", "Metals", "NSE"),

    # ── CEMENT & CONSTRUCTION ──
    ("ULTRACEMCO.NS", "UltraTech Cement", "Cement", "NSE"),
    ("AMBUJACEM.NS", "Ambuja Cements", "Cement", "NSE"),
    ("SHREECEM.NS", "Shree Cement", "Cement", "NSE"),
    ("ACC.NS", "ACC", "Cement", "NSE"),
    ("DALMIACEM.NS", "Dalmia Bharat", "Cement", "NSE"),
    ("RAMCOCEM.NS", "Ramco Cements", "Cement", "NSE"),
    ("LT.NS", "Larsen & Toubro", "Construction", "NSE"),

    # ── FMCG & CONSUMER ──
    ("HINDUNILVR.NS", "Hindustan Unilever", "FMCG", "NSE"),
    ("ITC.NS", "ITC", "FMCG", "NSE"),
    ("NESTLEIND.NS", "Nestle India", "FMCG", "NSE"),
    ("BRITANNIA.NS", "Britannia Industries", "FMCG", "NSE"),
    ("DABUR.NS", "Dabur India", "FMCG", "NSE"),
    ("MARICO.NS", "Marico", "FMCG", "NSE"),
    ("GODREJCP.NS", "Godrej Consumer Products", "FMCG", "NSE"),
    ("COLPAL.NS", "Colgate Palmolive", "FMCG", "NSE"),
    ("TATACONSUM.NS", "Tata Consumer Products", "FMCG", "NSE"),
    ("VBL.NS", "Varun Beverages", "FMCG", "NSE"),
    ("UBL.NS", "United Breweries", "FMCG", "NSE"),
    ("TITAN.NS", "Titan Company", "Consumer Durables", "NSE"),
    ("HAVELLS.NS", "Havells India", "Consumer Durables", "NSE"),
    ("VOLTAS.NS", "Voltas", "Consumer Durables", "NSE"),
    ("CROMPTON.NS", "Crompton Greaves CE", "Consumer Durables", "NSE"),
    ("BATAINDIA.NS", "Bata India", "Consumer Durables", "NSE"),
    ("PAGEIND.NS", "Page Industries", "Textiles", "NSE"),
    ("TRENT.NS", "Trent", "Retail", "NSE"),
    ("DMART.NS", "Avenue Supermarts (DMart)", "Retail", "NSE"),

    # ── TELECOM & MEDIA ──
    ("BHARTIARTL.NS", "Bharti Airtel", "Telecom", "NSE"),
    ("IDEA.NS", "Vodafone Idea", "Telecom", "NSE"),
    ("ZEEL.NS", "Zee Entertainment", "Media", "NSE"),

    # ── CAPITAL GOODS / INDUSTRIALS ──
    ("SIEMENS.NS", "Siemens", "Capital Goods", "NSE"),
    ("ABB.NS", "ABB India", "Capital Goods", "NSE"),
    ("BHEL.NS", "BHEL", "Capital Goods", "NSE"),
    ("HAL.NS", "Hindustan Aeronautics", "Defence", "NSE"),
    ("BEL.NS", "Bharat Electronics", "Defence", "NSE"),
    ("BDL.NS", "Bharat Dynamics", "Defence", "NSE"),
    ("CUMMINSIND.NS", "Cummins India", "Capital Goods", "NSE"),
    ("THERMAX.NS", "Thermax", "Capital Goods", "NSE"),
    ("HONAUT.NS", "Honeywell Automation", "Capital Goods", "NSE"),
    ("CGPOWER.NS", "CG Power", "Capital Goods", "NSE"),

    # ── CHEMICALS ──
    ("PIDILITIND.NS", "Pidilite Industries", "Chemicals", "NSE"),
    ("SRF.NS", "SRF", "Chemicals", "NSE"),
    ("ATUL.NS", "Atul", "Chemicals", "NSE"),
    ("DEEPAKNTR.NS", "Deepak Nitrite", "Chemicals", "NSE"),
    ("NAVINFLUOR.NS", "Navin Fluorine", "Chemicals", "NSE"),
    ("CLEAN.NS", "Clean Science", "Chemicals", "NSE"),

    # ── REAL ESTATE ──
    ("DLF.NS", "DLF", "Real Estate", "NSE"),
    ("GODREJPROP.NS", "Godrej Properties", "Real Estate", "NSE"),
    ("OBEROIRLTY.NS", "Oberoi Realty", "Real Estate", "NSE"),
    ("PRESTIGE.NS", "Prestige Estates", "Real Estate", "NSE"),
    ("LODHA.NS", "Macrotech Developers", "Real Estate", "NSE"),
    ("PHOENIXLTD.NS", "Phoenix Mills", "Real Estate", "NSE"),

    # ── OTHERS ──
    ("ASIANPAINT.NS", "Asian Paints", "Paints", "NSE"),
    ("BERGEPAINT.NS", "Berger Paints", "Paints", "NSE"),
    ("INDIGO.NS", "InterGlobe Aviation", "Aviation", "NSE"),
    ("IRCTC.NS", "IRCTC", "Travel & Tourism", "NSE"),
    ("INDIANHOTELS.NS", "Indian Hotels", "Hotels", "NSE"),
    ("JUBLFOOD.NS", "Jubilant FoodWorks", "QSR", "NSE"),
    ("ZOMATO.NS", "Zomato", "Food Tech", "NSE"),
    ("PAYTM.NS", "One97 Communications", "Fintech", "NSE"),
    ("NYKAA.NS", "FSN E-Commerce (Nykaa)", "E-Commerce", "NSE"),
    ("POLICYBZR.NS", "PB Fintech", "Insurtech", "NSE"),
    ("LICI.NS", "LIC of India", "Insurance", "NSE"),
    ("PIIND.NS", "PI Industries", "Agro Chemicals", "NSE"),
    ("UPL.NS", "UPL", "Agro Chemicals", "NSE"),
    ("RECLTD.NS", "REC", "Financial Services", "NSE"),
    ("PFC.NS", "Power Finance Corp", "Financial Services", "NSE"),
    ("IRFC.NS", "Indian Railway Finance", "Financial Services", "NSE"),
    ("CONCOR.NS", "Container Corp", "Logistics", "NSE"),
    ("GRASIM.NS", "Grasim Industries", "Diversified", "NSE"),

    # ── BSE-LISTED (also available on NSE via .NS) ──
    ("TRIDENT.NS", "Trident", "Textiles", "BSE"),
    ("SUZLON.NS", "Suzlon Energy", "Energy", "BSE"),
    ("YESBANK.NS", "Yes Bank", "Banking", "BSE"),
    ("RBLBANK.NS", "RBL Bank", "Banking", "BSE"),
    ("GMRINFRA.NS", "GMR Airports Infra", "Infrastructure", "BSE"),
    ("IRCON.NS", "Ircon International", "Infrastructure", "BSE"),
    ("RVNL.NS", "RVNL", "Infrastructure", "BSE"),
    ("NBCC.NS", "NBCC India", "Construction", "BSE"),
    ("HUDCO.NS", "HUDCO", "Financial Services", "BSE"),
    ("IEX.NS", "Indian Energy Exchange", "Energy", "BSE"),
]


def get_stock_universe():
    """Return the curated stock universe as a list of dicts."""
    return [
        {
            "symbol": sym,
            "name": name,
            "sector": sector,
            "exchange": exchange,
        }
        for sym, name, sector, exchange in NSE_STOCKS
    ]


def fetch_daily_data(symbol: str) -> pd.DataFrame | None:
    """
    Fetch daily OHLCV data for a given symbol.
    Returns None if data is insufficient or fetch fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=config.DATA_PERIOD_DAILY, interval="1d")
        if df is None or len(df) < config.EMA_LONG + 20:
            logger.warning(f"Insufficient daily data for {symbol}: {len(df) if df is not None else 0} rows")
            return None
        # Standardize column names
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        logger.error(f"Error fetching daily data for {symbol}: {e}")
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
            logger.warning(f"Insufficient weekly data for {symbol}: {len(df) if df is not None else 0} rows")
            return None
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        logger.error(f"Error fetching weekly data for {symbol}: {e}")
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
