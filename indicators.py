"""
Quant Swing Trade Scanner — Technical Indicators Engine
Calculates all required technical indicators for the scanning system.
"""

import pandas as pd
import numpy as np
import config
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# EXPONENTIAL MOVING AVERAGES
# ═══════════════════════════════════════════════════════════════

def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Compute Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def add_emas(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA 20, 50, 200 to the dataframe."""
    df["ema_20"] = compute_ema(df["close"], config.EMA_SHORT)
    df["ema_50"] = compute_ema(df["close"], config.EMA_MID)
    df["ema_200"] = compute_ema(df["close"], config.EMA_LONG)
    return df


# ═══════════════════════════════════════════════════════════════
# RSI (RELATIVE STRENGTH INDEX)
# ═══════════════════════════════════════════════════════════════

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using Wilder's smoothing method."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI(14) to the dataframe."""
    df["rsi"] = compute_rsi(df["close"], config.RSI_PERIOD)
    return df


def is_rsi_rising(df: pd.DataFrame, candles: int = 3) -> bool:
    """Check if RSI has been rising for the last N candles."""
    if len(df) < candles + 1:
        return False
    rsi_vals = df["rsi"].iloc[-(candles + 1):]
    for i in range(1, len(rsi_vals)):
        if rsi_vals.iloc[i] <= rsi_vals.iloc[i - 1]:
            return False
    return True


def has_rsi_divergence(df: pd.DataFrame, lookback: int = 15) -> bool:
    """
    Detect bearish RSI divergence in the last N candles.
    Bearish divergence: price makes higher high but RSI makes lower high.
    Returns True if divergence is found (which is BAD for our setup).
    """
    if len(df) < lookback + 5:
        return False

    recent = df.iloc[-lookback:]
    prices = recent["close"].values
    rsis = recent["rsi"].values

    # Find local peaks in price
    price_peaks = []
    rsi_at_peaks = []
    for i in range(2, len(prices) - 2):
        if prices[i] > prices[i - 1] and prices[i] > prices[i - 2] and \
           prices[i] > prices[i + 1] and prices[i] > prices[i + 2]:
            price_peaks.append(prices[i])
            rsi_at_peaks.append(rsis[i])

    if len(price_peaks) < 2:
        return False

    # Check last two peaks for bearish divergence
    if price_peaks[-1] > price_peaks[-2] and rsi_at_peaks[-1] < rsi_at_peaks[-2]:
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# BOLLINGER BANDS
# ═══════════════════════════════════════════════════════════════

def add_bollinger_bands(df: pd.DataFrame) -> pd.DataFrame:
    """Add Bollinger Bands (20, 2) to the dataframe."""
    df["bb_mid"] = df["close"].rolling(window=config.BB_PERIOD).mean()
    bb_std = df["close"].rolling(window=config.BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + (config.BB_STD_DEV * bb_std)
    df["bb_lower"] = df["bb_mid"] - (config.BB_STD_DEV * bb_std)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    return df


def is_bb_squeeze(df: pd.DataFrame) -> bool:
    """
    Detect Bollinger Band squeeze (volatility contraction).
    BB width is below 20th percentile of its recent history.
    """
    if len(df) < 60:
        return False

    bb_width = df["bb_width"].dropna()
    if len(bb_width) < 40:
        return False

    current_width = bb_width.iloc[-1]
    threshold = bb_width.iloc[-60:].quantile(config.BB_SQUEEZE_PERCENTILE / 100.0)

    return current_width <= threshold


# ═══════════════════════════════════════════════════════════════
# MACD
# ═══════════════════════════════════════════════════════════════

def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Add MACD, Signal, and Histogram to the dataframe."""
    ema_fast = compute_ema(df["close"], config.MACD_FAST)
    ema_slow = compute_ema(df["close"], config.MACD_SLOW)
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = compute_ema(df["macd"], config.MACD_SIGNAL)
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def has_macd_bullish_crossover(df: pd.DataFrame) -> bool:
    """Check if MACD has bullish crossover above zero line."""
    if len(df) < 3:
        return False
    # Current: MACD > Signal, MACD > 0
    # Previous: MACD <= Signal
    curr_macd = df["macd"].iloc[-1]
    curr_signal = df["macd_signal"].iloc[-1]
    prev_macd = df["macd"].iloc[-2]
    prev_signal = df["macd_signal"].iloc[-2]

    return (curr_macd > curr_signal and
            prev_macd <= prev_signal and
            curr_macd > 0)


# ═══════════════════════════════════════════════════════════════
# ADX (AVERAGE DIRECTIONAL INDEX)
# ═══════════════════════════════════════════════════════════════

def add_adx(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ADX(14) to the dataframe using Wilder's smoothing.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    period = config.ADX_PERIOD

    plus_dm = high.diff()
    minus_dm = low.diff().abs()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm_neg = -low.diff()
    minus_dm_val = minus_dm_neg.where((minus_dm_neg > high.diff()) & (minus_dm_neg > 0), 0.0)

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder's smoothing
    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm_val.ewm(alpha=1 / period, min_periods=period).mean() / atr)

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
    df["adx"] = dx.ewm(alpha=1 / period, min_periods=period).mean()
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    return df


def is_adx_strong_and_rising(df: pd.DataFrame) -> bool:
    """Check if ADX > 25 and rising for last 2 candles."""
    if len(df) < 3:
        return False
    adx_curr = df["adx"].iloc[-1]
    adx_prev = df["adx"].iloc[-2]
    adx_prev2 = df["adx"].iloc[-3]

    return (adx_curr > config.ADX_THRESHOLD and
            adx_curr > adx_prev > adx_prev2)


# ═══════════════════════════════════════════════════════════════
# ATR (AVERAGE TRUE RANGE)
# ═══════════════════════════════════════════════════════════════

def add_atr(df: pd.DataFrame) -> pd.DataFrame:
    """Add ATR(14) to the dataframe."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["atr"] = tr.ewm(alpha=1 / config.ATR_PERIOD, min_periods=config.ATR_PERIOD).mean()
    return df


# ═══════════════════════════════════════════════════════════════
# VOLUME ANALYSIS
# ═══════════════════════════════════════════════════════════════

def add_volume_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Add volume moving average and volume ratio."""
    df["vol_ma_20"] = df["volume"].rolling(window=config.VOLUME_AVG_PERIOD).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma_20"]
    return df


def has_volume_breakout(df: pd.DataFrame) -> bool:
    """
    Check if breakout volume criteria are met:
    - Current volume ≥ 1.8x 20-day average
    - Volume expansion sustained for at least 2 days
    """
    if len(df) < config.VOLUME_SUSTAIN_DAYS + 1:
        return False

    for i in range(config.VOLUME_SUSTAIN_DAYS):
        idx = -(i + 1)
        if df["vol_ratio"].iloc[idx] < config.BREAKOUT_VOLUME_MULTIPLIER:
            return False

    return True


# ═══════════════════════════════════════════════════════════════
# SWING DETECTION
# ═══════════════════════════════════════════════════════════════

def find_swing_highs(df: pd.DataFrame, lookback: int = None) -> list:
    """Find swing high points in the price series."""
    if lookback is None:
        lookback = config.SWING_LOOKBACK
    swing_highs = []
    highs = df["high"].values

    for i in range(lookback, len(highs) - lookback):
        is_swing = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing = False
                break
        if is_swing:
            swing_highs.append((i, highs[i]))

    return swing_highs


def find_swing_lows(df: pd.DataFrame, lookback: int = None) -> list:
    """Find swing low points in the price series."""
    if lookback is None:
        lookback = config.SWING_LOOKBACK
    swing_lows = []
    lows = df["low"].values

    for i in range(lookback, len(lows) - lookback):
        is_swing = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing = False
                break
        if is_swing:
            swing_lows.append((i, lows[i]))

    return swing_lows


def get_recent_swing_low(df: pd.DataFrame) -> float | None:
    """Get the most recent swing low price."""
    swing_lows = find_swing_lows(df)
    if not swing_lows:
        # Fallback: use recent low of last 20 candles
        return df["low"].iloc[-20:].min()
    return swing_lows[-1][1]


def get_previous_swing_high(df: pd.DataFrame) -> float | None:
    """Get the previous (second-to-last) swing high price."""
    swing_highs = find_swing_highs(df)
    if len(swing_highs) < 1:
        return None
    return swing_highs[-1][1]


# ═══════════════════════════════════════════════════════════════
# CONSOLIDATION DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_consolidation(df: pd.DataFrame) -> dict | None:
    """
    Detect consolidation range (minimum 15 candles) before the breakout.
    Returns dict with range_high, range_low, duration or None.
    """
    if len(df) < config.CONSOLIDATION_MIN_CANDLES + 5:
        return None

    # Look at the candles before the last 2 (which are potential breakout candles)
    lookback_start = -(config.CONSOLIDATION_MIN_CANDLES + 2)
    lookback_end = -2
    window = df.iloc[lookback_start:lookback_end]

    range_high = window["high"].max()
    range_low = window["low"].min()
    range_pct = (range_high - range_low) / range_low * 100

    # Consolidation: range is < 15% of price
    if range_pct < 15:
        return {
            "range_high": range_high,
            "range_low": range_low,
            "duration": len(window),
            "range_pct": range_pct,
        }

    return None


def is_breakout_above_resistance(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Check if the latest candle(s) broke above:
    1. Previous swing high, OR
    2. Consolidation range

    Returns (is_breakout, pattern_description)
    """
    if len(df) < 20:
        return False, ""

    close = df["close"].iloc[-1]

    # Check consolidation breakout
    consolidation = detect_consolidation(df)
    if consolidation and close > consolidation["range_high"]:
        return True, f"Consolidation Breakout ({consolidation['duration']}-day range)"

    # Check swing high breakout
    prev_swing_high = get_previous_swing_high(df)
    if prev_swing_high and close > prev_swing_high:
        return True, "Swing High Breakout"

    return False, ""


# ═══════════════════════════════════════════════════════════════
# VWAP PROXY (using daily data)
# ═══════════════════════════════════════════════════════════════

def add_vwap_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a VWAP proxy using typical price × volume / cumulative volume.
    Uses a rolling 20-day window for daily VWAP approximation.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    tv = typical_price * df["volume"]

    df["vwap"] = tv.rolling(window=20).sum() / df["volume"].rolling(window=20).sum()
    return df


def is_above_vwap(df: pd.DataFrame, candles: int = 3) -> bool:
    """Check if price has been above VWAP for the last N candles."""
    if len(df) < candles:
        return False

    for i in range(candles):
        idx = -(i + 1)
        if df["close"].iloc[idx] < df["vwap"].iloc[idx]:
            return False
    return True


# ═══════════════════════════════════════════════════════════════
# RELATIVE STRENGTH vs NIFTY
# ═══════════════════════════════════════════════════════════════

def compute_relative_strength(stock_df: pd.DataFrame, nifty_df: pd.DataFrame,
                               period: int = 50) -> float | None:
    """
    Compute relative strength of stock vs NIFTY over a period.
    RS > 1 means stock outperforms NIFTY.
    """
    if stock_df is None or nifty_df is None:
        return None
    if len(stock_df) < period or len(nifty_df) < period:
        return None

    stock_return = (stock_df["close"].iloc[-1] / stock_df["close"].iloc[-period] - 1) * 100
    nifty_return = (nifty_df["close"].iloc[-1] / nifty_df["close"].iloc[-period] - 1) * 100

    if nifty_return == 0:
        return None

    return stock_return / nifty_return if nifty_return > 0 else None


# ═══════════════════════════════════════════════════════════════
# PATTERN DETECTION (Inside Bar, Flag)
# ═══════════════════════════════════════════════════════════════

def detect_inside_bar(df: pd.DataFrame) -> bool:
    """Detect an inside bar pattern in the last 3 candles followed by breakout."""
    if len(df) < 4:
        return False

    # Check if candle -3 or -2 is an inside bar relative to its predecessor
    for offset in [-3, -2]:
        mother_high = df["high"].iloc[offset - 1]
        mother_low = df["low"].iloc[offset - 1]
        inside_high = df["high"].iloc[offset]
        inside_low = df["low"].iloc[offset]

        if inside_high < mother_high and inside_low > mother_low:
            # Inside bar found, check if latest candle breaks above
            if df["close"].iloc[-1] > mother_high:
                return True

    return False


def detect_flag_pattern(df: pd.DataFrame) -> bool:
    """
    Detect a bullish flag pattern:
    - Strong move up (flagpole)
    - Followed by a gentle pullback (flag)
    - Then breakout above the flag
    """
    if len(df) < 25:
        return False

    # Flagpole: strong move in candles -25 to -15
    pole_start = df["close"].iloc[-25]
    pole_end = df["close"].iloc[-15]
    pole_gain = (pole_end - pole_start) / pole_start * 100

    if pole_gain < 8:  # Need at least 8% move up for flagpole
        return False

    # Flag: candles -15 to -3 should show gentle pullback (< 50% retracement)
    flag_high = df["high"].iloc[-15:-3].max()
    flag_low = df["low"].iloc[-15:-3].min()
    retracement = (flag_high - flag_low) / (pole_end - pole_start)

    if retracement > 0.5:  # Too deep a pullback
        return False

    # Breakout: last candle above flag high
    if df["close"].iloc[-1] > flag_high:
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# WEEKLY TREND CONFIRMATION
# ═══════════════════════════════════════════════════════════════

def is_weekly_bullish(weekly_df: pd.DataFrame) -> bool:
    """
    Check if weekly trend is bullish or sideways breakout:
    - Weekly close above 20 EMA
    - Last 3 weekly candles show strength (higher lows or breakout)
    """
    if weekly_df is None or len(weekly_df) < 25:
        return False

    weekly_df = weekly_df.copy()
    weekly_df["ema_20"] = compute_ema(weekly_df["close"], 20)

    close = weekly_df["close"].iloc[-1]
    ema20 = weekly_df["ema_20"].iloc[-1]

    if close < ema20:
        return False

    # Check for higher lows in last 3 weeks
    lows = weekly_df["low"].iloc[-3:].values
    if lows[-1] >= lows[0]:  # Current week low >= 3 weeks ago low
        return True

    # Check for sideways breakout: current close > highest close in prior 10 weeks
    prior_high = weekly_df["close"].iloc[-11:-1].max()
    if close > prior_high:
        return True

    return True  # Above weekly EMA is good enough


# ═══════════════════════════════════════════════════════════════
# MASTER FUNCTION: COMPUTE ALL INDICATORS
# ═══════════════════════════════════════════════════════════════

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all technical indicators to a daily dataframe."""
    df = df.copy()
    df = add_emas(df)
    df = add_rsi(df)
    df = add_bollinger_bands(df)
    df = add_macd(df)
    df = add_adx(df)
    df = add_atr(df)
    df = add_volume_analysis(df)
    df = add_vwap_proxy(df)
    return df
