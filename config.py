"""
Quant Swing Trade Scanner — Configuration
All thresholds, parameters, and constants for the scanning engine.
"""

# ═══════════════════════════════════════════
# MARKET UNIVERSE FILTERS
# ═══════════════════════════════════════════
MIN_PRICE = 50                    # Minimum stock price in ₹
MIN_AVG_VOLUME = 500_000          # 5 lakh shares minimum daily average
DATA_PERIOD_DAILY = "1y"          # 1 year of daily data
DATA_PERIOD_WEEKLY = "2y"         # 2 years of weekly data

# ═══════════════════════════════════════════
# EMA PERIODS
# ═══════════════════════════════════════════
EMA_SHORT = 20
EMA_MID = 50
EMA_LONG = 200

# ═══════════════════════════════════════════
# RSI PARAMETERS
# ═══════════════════════════════════════════
RSI_PERIOD = 14
RSI_LOWER = 55
RSI_UPPER = 70
RSI_RISING_CANDLES = 3            # Minimum candles RSI must be rising
RSI_DIVERGENCE_LOOKBACK = 15      # Candles to check for divergence

# ═══════════════════════════════════════════
# BOLLINGER BANDS
# ═══════════════════════════════════════════
BB_PERIOD = 20
BB_STD_DEV = 2
BB_SQUEEZE_PERCENTILE = 20        # Width below this percentile = squeeze

# ═══════════════════════════════════════════
# CONSOLIDATION / BREAKOUT
# ═══════════════════════════════════════════
CONSOLIDATION_MIN_CANDLES = 15    # Minimum candles for consolidation range
BREAKOUT_VOLUME_MULTIPLIER = 1.8  # Volume must be ≥ 1.8x 20-day avg
VOLUME_SUSTAIN_DAYS = 2           # Volume expansion must sustain this many days
VOLUME_AVG_PERIOD = 20            # Period for average volume calculation

# ═══════════════════════════════════════════
# MACD PARAMETERS
# ═══════════════════════════════════════════
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ═══════════════════════════════════════════
# ADX PARAMETERS
# ═══════════════════════════════════════════
ADX_PERIOD = 14
ADX_THRESHOLD = 25

# ═══════════════════════════════════════════
# ATR / RISK MANAGEMENT
# ═══════════════════════════════════════════
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 2             # Stop loss = 2 x ATR
TARGET_1_R = 1.5                  # Target 1 = 1.5R
TARGET_2_R = 3.0                  # Target 2 = 3R
STRETCH_TARGET_MIN_PCT = 10       # Stretch target minimum %
STRETCH_TARGET_MAX_PCT = 20       # Stretch target maximum %
MIN_RISK_REWARD = 2.0             # Minimum RR ratio

# ═══════════════════════════════════════════
# ALPHA BOOSTERS
# ═══════════════════════════════════════════
MIN_ALPHA_BOOSTERS = 2            # Minimum optional criteria to pass
VWAP_HOLD_CANDLES = 3             # VWAP must hold for 3 candles

# ═══════════════════════════════════════════
# ALERT DEDUPLICATION
# ═══════════════════════════════════════════
DEDUP_WINDOW_DAYS = 10            # Don't re-alert same stock within 10 days

# ═══════════════════════════════════════════
# NIFTY 50 BENCHMARK
# ═══════════════════════════════════════════
NIFTY_SYMBOL = "^NSEI"

# ═══════════════════════════════════════════
# SWING HIGH/LOW DETECTION
# ═══════════════════════════════════════════
SWING_LOOKBACK = 5                # Candles on each side to detect swing points

# ═══════════════════════════════════════════
# SERVER
# ═══════════════════════════════════════════
import os
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
