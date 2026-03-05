"""
Quant Swing Trade Scanner — Core Scanner Engine
Applies all mandatory criteria and alpha boosters to identify setups.
"""

import pandas as pd
import numpy as np
import config
import indicators
import logging

logger = logging.getLogger(__name__)


class ScanResult:
    """Holds the result of scanning a single stock."""

    def __init__(self, symbol: str, name: str, sector: str, exchange: str):
        self.symbol = symbol
        self.name = name
        self.sector = sector
        self.exchange = exchange
        self.passed = False
        self.reasons = []
        self.pattern = ""
        self.alpha_boosters = []
        self.alpha_score = 0
        self.daily_df = None
        self.weekly_df = None
        self.failed_at = ""

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "exchange": self.exchange,
            "passed": self.passed,
            "pattern": self.pattern,
            "reasons": self.reasons,
            "alpha_boosters": self.alpha_boosters,
            "alpha_score": self.alpha_score,
            "failed_at": self.failed_at,
        }


def check_trend_filter(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Check EMA alignment: 20 EMA > 50 EMA > 200 EMA
    and price above 200 EMA.
    """
    reasons = []

    ema_20 = df["ema_20"].iloc[-1]
    ema_50 = df["ema_50"].iloc[-1]
    ema_200 = df["ema_200"].iloc[-1]
    close = df["close"].iloc[-1]

    if not (ema_20 > ema_50 > ema_200):
        return False, ["EMA alignment failed (20>50>200 not met)"]

    if close < ema_200:
        return False, ["Price below 200 EMA"]

    reasons.append(f"EMAs aligned bullish (20>{ema_20:.1f} > 50>{ema_50:.1f} > 200>{ema_200:.1f})")
    reasons.append(f"Price ₹{close:.2f} above 200 EMA")
    return True, reasons


def check_momentum(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Check RSI criteria:
    - RSI between 55 and 70
    - RSI rising for last 3-5 candles
    - No bearish divergence in last 15 candles
    """
    reasons = []

    rsi = df["rsi"].iloc[-1]

    if rsi < config.RSI_LOWER or rsi > config.RSI_UPPER:
        return False, [f"RSI {rsi:.1f} outside range [{config.RSI_LOWER}-{config.RSI_UPPER}]"]

    if not indicators.is_rsi_rising(df, config.RSI_RISING_CANDLES):
        return False, [f"RSI not rising for last {config.RSI_RISING_CANDLES} candles"]

    if indicators.has_rsi_divergence(df, config.RSI_DIVERGENCE_LOOKBACK):
        return False, ["Bearish RSI divergence detected"]

    reasons.append(f"RSI {rsi:.1f} in sweet spot [{config.RSI_LOWER}-{config.RSI_UPPER}]")
    reasons.append(f"RSI rising for {config.RSI_RISING_CANDLES}+ candles")
    reasons.append("No bearish RSI divergence")
    return True, reasons


def check_volatility_structure(df: pd.DataFrame) -> tuple[bool, list[str], str]:
    """
    Check volatility & breakout criteria:
    - BB squeeze or volatility contraction (preferred but optional if breakout exists)
    - Breakout above swing high or consolidation range
    """
    reasons = []
    pattern = ""

    # Check breakout FIRST — this is the most important criterion
    is_breakout, breakout_pattern = indicators.is_breakout_above_resistance(df)
    if not is_breakout:
        return False, ["No breakout above resistance level"], ""

    pattern = breakout_pattern
    reasons.append(f"Pattern: {breakout_pattern}")

    # Check BB squeeze (adds to quality but not required when breakout exists)
    bb_squeeze = indicators.is_bb_squeeze(df)
    if bb_squeeze:
        reasons.append("Bollinger Band squeeze detected (volatility contraction)")
    else:
        # Check for general volatility contraction
        bb_width = df["bb_width"].iloc[-1]
        bb_width_avg = df["bb_width"].iloc[-20:].mean()
        if bb_width < bb_width_avg:
            reasons.append("Volatility contracting (BB width below average)")
        else:
            reasons.append("Breakout detected despite expanded volatility")

    return True, reasons, pattern


def check_volume(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Check volume criteria:
    - Volume ≥ 1.8x 20-day average
    - Volume sustained for 2+ days
    """
    reasons = []

    if not indicators.has_volume_breakout(df):
        vol_ratio = df["vol_ratio"].iloc[-1]
        return False, [f"Volume ratio {vol_ratio:.1f}x insufficient (need ≥{config.BREAKOUT_VOLUME_MULTIPLIER}x)"]

    vol_ratio = df["vol_ratio"].iloc[-1]
    reasons.append(f"Volume {vol_ratio:.1f}x average (≥{config.BREAKOUT_VOLUME_MULTIPLIER}x required)")
    reasons.append(f"Volume expansion sustained for {config.VOLUME_SUSTAIN_DAYS}+ days")
    return True, reasons


def check_alpha_boosters(df: pd.DataFrame, weekly_df: pd.DataFrame,
                          nifty_df: pd.DataFrame) -> tuple[bool, list[str], int]:
    """
    Check optional alpha boosters — need at least 2 of 6.
    """
    boosters = []

    # 1. MACD bullish crossover above zero
    if indicators.has_macd_bullish_crossover(df):
        boosters.append("MACD bullish crossover above zero line")

    # 2. ADX > 25 and rising
    if indicators.is_adx_strong_and_rising(df):
        boosters.append(f"ADX {df['adx'].iloc[-1]:.1f} > {config.ADX_THRESHOLD} and rising")

    # 3. VWAP reclaim and hold
    if indicators.is_above_vwap(df, config.VWAP_HOLD_CANDLES):
        boosters.append(f"Price above VWAP for {config.VWAP_HOLD_CANDLES}+ candles")

    # 4. Relative strength vs NIFTY > 1
    rs = indicators.compute_relative_strength(df, nifty_df)
    if rs is not None and rs > 1:
        boosters.append(f"Relative Strength vs NIFTY: {rs:.2f}")

    # 5. Inside bar / Flag pattern breakout
    if indicators.detect_inside_bar(df):
        boosters.append("Inside Bar breakout pattern")
    elif indicators.detect_flag_pattern(df):
        boosters.append("Bullish Flag pattern breakout")

    # 6. Strong sector momentum (simplified: stock's own weekly momentum)
    if weekly_df is not None and len(weekly_df) >= 4:
        weekly_pct = (weekly_df["close"].iloc[-1] / weekly_df["close"].iloc[-4] - 1) * 100
        if weekly_pct > 5:
            boosters.append(f"Strong weekly momentum: +{weekly_pct:.1f}% in 4 weeks")

    count = len(boosters)
    passed = count >= config.MIN_ALPHA_BOOSTERS

    return passed, boosters, count


def scan_stock(symbol: str, name: str, sector: str, exchange: str,
               daily_df: pd.DataFrame, weekly_df: pd.DataFrame,
               nifty_df: pd.DataFrame) -> ScanResult:
    """
    Run the full scan on a single stock.
    Returns a ScanResult with pass/fail and all details.
    """
    result = ScanResult(symbol, name, sector, exchange)

    # Compute all indicators
    try:
        daily_df = indicators.compute_all_indicators(daily_df)
    except Exception as e:
        result.failed_at = f"Indicator computation: {e}"
        return result

    result.daily_df = daily_df
    result.weekly_df = weekly_df

    # ── MANDATORY CRITERION 1: TREND FILTER ──
    passed, reasons = check_trend_filter(daily_df)
    if not passed:
        result.failed_at = "Trend Filter"
        result.reasons = reasons
        return result
    result.reasons.extend(reasons)

    # ── MANDATORY CRITERION 2: WEEKLY CONFIRMATION ──
    if not indicators.is_weekly_bullish(weekly_df):
        result.failed_at = "Weekly Trend"
        result.reasons.append("Weekly trend not bullish")
        return result
    result.reasons.append("Weekly trend confirmed bullish")

    # ── MANDATORY CRITERION 3: MOMENTUM ──
    passed, reasons = check_momentum(daily_df)
    if not passed:
        result.failed_at = "Momentum"
        result.reasons = reasons
        return result
    result.reasons.extend(reasons)

    # ── MANDATORY CRITERION 4: VOLATILITY & STRUCTURE ──
    passed, reasons, pattern = check_volatility_structure(daily_df)
    if not passed:
        result.failed_at = "Volatility/Structure"
        result.reasons = reasons
        return result
    result.reasons.extend(reasons)
    result.pattern = pattern

    # ── MANDATORY CRITERION 5: VOLUME CONFIRMATION ──
    passed, reasons = check_volume(daily_df)
    if not passed:
        result.failed_at = "Volume"
        result.reasons = reasons
        return result
    result.reasons.extend(reasons)

    # ── ALPHA BOOSTERS (≥2 required) ──
    passed, boosters, count = check_alpha_boosters(daily_df, weekly_df, nifty_df)
    if not passed:
        result.failed_at = f"Alpha Boosters ({count}/{config.MIN_ALPHA_BOOSTERS})"
        result.reasons.append(f"Only {count} alpha boosters met (need ≥{config.MIN_ALPHA_BOOSTERS})")
        return result
    result.alpha_boosters = boosters
    result.alpha_score = count
    result.reasons.extend([f"✅ {b}" for b in boosters])

    # ── ALL CRITERIA PASSED ──
    result.passed = True
    return result
