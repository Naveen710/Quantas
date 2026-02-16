"""
Quant Swing Trade Scanner — Risk Manager
Calculates entry, stop loss, targets, risk-reward, and confidence scores.
"""

import pandas as pd
import numpy as np
import config
import indicators
import logging

logger = logging.getLogger(__name__)


def calculate_entry_price(df: pd.DataFrame) -> float:
    """
    Entry price = breakout close price.
    In practice, this is the last close.
    """
    return round(df["close"].iloc[-1], 2)


def calculate_stop_loss(df: pd.DataFrame, entry_price: float) -> float:
    """
    Stop loss = tighter of:
    1. Below recent swing low
    2. Entry - 2 × ATR(14)
    """
    # Method 1: Recent swing low
    swing_low = indicators.get_recent_swing_low(df)
    sl_swing = swing_low * 0.99 if swing_low else entry_price * 0.95  # 1% buffer below swing low

    # Method 2: 2 × ATR
    atr = df["atr"].iloc[-1]
    sl_atr = entry_price - (config.ATR_SL_MULTIPLIER * atr)

    # Take the tighter (higher) stop loss for less risk
    stop_loss = max(sl_swing, sl_atr)

    # Ensure SL is below entry
    if stop_loss >= entry_price:
        stop_loss = entry_price * 0.97  # Fallback: 3% below entry

    return round(stop_loss, 2)


def calculate_targets(entry_price: float, stop_loss: float) -> dict:
    """
    Calculate target zones based on R multiples:
    - Target 1: 1.5R
    - Target 2: 3R
    - Stretch Target: 10-20% (if applicable)
    """
    risk = entry_price - stop_loss  # R value

    target_1 = round(entry_price + (config.TARGET_1_R * risk), 2)
    target_2 = round(entry_price + (config.TARGET_2_R * risk), 2)

    stretch_min = round(entry_price * (1 + config.STRETCH_TARGET_MIN_PCT / 100), 2)
    stretch_max = round(entry_price * (1 + config.STRETCH_TARGET_MAX_PCT / 100), 2)

    # Use the larger of target_2 and stretch_min for max target
    max_target = max(target_2, stretch_min)

    return {
        "target_1": target_1,
        "target_2": target_2,
        "stretch_min": stretch_min,
        "stretch_max": stretch_max,
        "max_target": max_target,
        "risk_per_share": round(risk, 2),
    }


def calculate_risk_reward(entry_price: float, stop_loss: float,
                            target_1: float) -> float:
    """Calculate risk-reward ratio using Target 1."""
    risk = entry_price - stop_loss
    if risk <= 0:
        return 0.0
    reward = target_1 - entry_price
    return round(reward / risk, 2)


def calculate_confidence_score(scan_result, rr_ratio: float) -> int:
    """
    Calculate confidence score (0-100) based on:
    - Number of alpha boosters met (25 pts)
    - Risk-reward ratio quality (25 pts)
    - Volume strength (20 pts)
    - Trend strength (15 pts)
    - Pattern quality (15 pts)
    """
    score = 0

    # Alpha boosters (25 pts): 2 boosters = 15, each additional = 5
    alpha_count = scan_result.alpha_score
    score += min(15 + (alpha_count - 2) * 5, 25)

    # Risk-reward (25 pts)
    if rr_ratio >= 4:
        score += 25
    elif rr_ratio >= 3:
        score += 20
    elif rr_ratio >= 2:
        score += 15
    elif rr_ratio >= 1.5:
        score += 10

    # Volume (20 pts)
    if scan_result.daily_df is not None:
        vol_ratio = scan_result.daily_df["vol_ratio"].iloc[-1]
        if vol_ratio >= 3:
            score += 20
        elif vol_ratio >= 2.5:
            score += 17
        elif vol_ratio >= 2:
            score += 14
        elif vol_ratio >= 1.8:
            score += 10

    # Trend strength (15 pts) — distance between EMAs
    if scan_result.daily_df is not None:
        df = scan_result.daily_df
        ema_spread = (df["ema_20"].iloc[-1] - df["ema_200"].iloc[-1]) / df["ema_200"].iloc[-1] * 100
        if ema_spread > 15:
            score += 15
        elif ema_spread > 10:
            score += 12
        elif ema_spread > 5:
            score += 9
        else:
            score += 6

    # Pattern quality (15 pts)
    pattern = scan_result.pattern.lower()
    if "consolidation" in pattern:
        score += 15  # Consolidation breakout is strongest
    elif "swing high" in pattern:
        score += 12
    elif "flag" in pattern:
        score += 14
    elif "inside bar" in pattern:
        score += 10
    else:
        score += 7

    return min(score, 100)


def generate_alert(scan_result) -> dict | None:
    """
    Generate a complete alert dict for a stock that passed all scans.
    Returns None if risk-reward doesn't meet minimum threshold.
    """
    if not scan_result.passed or scan_result.daily_df is None:
        return None

    df = scan_result.daily_df

    # Calculate risk management parameters
    entry = calculate_entry_price(df)
    stop_loss = calculate_stop_loss(df, entry)
    targets = calculate_targets(entry, stop_loss)
    rr_ratio = calculate_risk_reward(entry, stop_loss, targets["target_1"])

    # Validate minimum risk-reward
    if rr_ratio < config.MIN_RISK_REWARD:
        logger.info(f"{scan_result.symbol}: R:R {rr_ratio} below minimum {config.MIN_RISK_REWARD}")
        return None

    # Calculate confidence
    confidence = calculate_confidence_score(scan_result, rr_ratio)

    # Build alert
    alert = {
        "stock_name": scan_result.name,
        "symbol": scan_result.symbol,
        "exchange": scan_result.exchange,
        "sector": scan_result.sector,
        "current_price": round(df["close"].iloc[-1], 2),
        "pattern": scan_result.pattern,
        "entry_price": entry,
        "stop_loss": stop_loss,
        "target_1": targets["target_1"],
        "target_2": targets["target_2"],
        "max_target": targets["max_target"],
        "risk_per_share": targets["risk_per_share"],
        "risk_reward": rr_ratio,
        "confidence": confidence,
        "reasons": scan_result.reasons,
        "alpha_boosters": scan_result.alpha_boosters,
        "alpha_count": scan_result.alpha_score,
        "rsi": round(df["rsi"].iloc[-1], 1),
        "adx": round(df["adx"].iloc[-1], 1) if not pd.isna(df["adx"].iloc[-1]) else None,
        "volume_ratio": round(df["vol_ratio"].iloc[-1], 1),
        "atr": round(df["atr"].iloc[-1], 2),
        "ema_20": round(df["ema_20"].iloc[-1], 2),
        "ema_50": round(df["ema_50"].iloc[-1], 2),
        "ema_200": round(df["ema_200"].iloc[-1], 2),
        "bb_width": round(df["bb_width"].iloc[-1], 4),
        "scan_date": str(df.index[-1].date()) if hasattr(df.index[-1], 'date') else str(df.index[-1]),
    }

    return alert
