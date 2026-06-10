"""
Technical indicator maths, all in one place.

Every function takes plain pandas data (the price history of one stock) and
returns numbers. No Streamlit, no internet — just maths. That makes these
easy to read, test and tweak.

Quick plain-English glossary of what's computed here:
  * Moving average (MA): the average closing price over the last N days.
    Smooths out the noise so you can see the underlying direction.
  * RSI: a 0-100 "speedometer" of recent gains vs losses. Above ~70 the stock
    may have risen too far too fast; below ~30 it may have fallen too far.
  * MACD: compares a fast and a slow moving average. When the MACD line
    crosses above its "signal" line, momentum is turning up.
  * ATR: the average size of a day's price swing — a volatility gauge.
  * Bollinger Bands: a band around the 20-day average, two standard
    deviations wide. A *narrow* band = the stock is coiling quietly;
    a *widening* band = a big move is starting.
  * Fibonacci retracements: popular "how far might a pullback go?" levels,
    measured between a recent swing high and swing low.
"""

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Moving averages
# --------------------------------------------------------------------------

def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average: the plain average of the last `window` values."""
    return series.rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average: like SMA but recent days count more."""
    return series.ewm(span=span, adjust=False).mean()


# --------------------------------------------------------------------------
# RSI (Relative Strength Index, Wilder's method, 14 days by default)
# --------------------------------------------------------------------------

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI: 0-100 momentum gauge. ~55-70 = healthy strength, >78 = overheated."""
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    # Wilder's smoothing is an EMA with alpha = 1/period
    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    # If there were literally no losses, RSI is 100 by definition
    return out.fillna(100.0).where(avg_loss.notna() | avg_gain.isna(), 100.0)


# --------------------------------------------------------------------------
# MACD
# --------------------------------------------------------------------------

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return (macd_line, signal_line). Cross above signal = momentum turning up."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line


def macd_crossed_up_recently(close: pd.Series, within_bars: int = 3) -> bool:
    """True if the MACD line crossed ABOVE its signal line in the last few days."""
    macd_line, signal_line = macd(close)
    above = macd_line > signal_line
    if len(above) < within_bars + 1:
        return False
    # A "cross" = below yesterday, above today, somewhere in the recent window
    crossed = above & ~above.shift(1, fill_value=False)
    return bool(crossed.iloc[-within_bars:].any())


# --------------------------------------------------------------------------
# Volatility: ATR and Bollinger Band width
# --------------------------------------------------------------------------

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range: typical size of one day's move, in dollars."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def bollinger_width(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """Width of the Bollinger Band as a fraction of price. Small = quiet/coiled."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return (2 * num_std * std) / mid


# --------------------------------------------------------------------------
# Returns / range helpers
# --------------------------------------------------------------------------

def pct_return(close: pd.Series, bars: int) -> float:
    """% change over the last `bars` trading days (e.g. bars=5 ≈ one week)."""
    if len(close) <= bars:
        return np.nan
    past = close.iloc[-(bars + 1)]
    if not past or np.isnan(past):
        return np.nan
    return (close.iloc[-1] / past - 1.0) * 100.0


def fifty_two_week_range(df: pd.DataFrame):
    """(low, high) over the last 252 trading days, using INTRADAY extremes
    (the daily High/Low columns), so it matches what Yahoo/CNBC show."""
    window = df.iloc[-252:]
    return float(window["Low"].min()), float(window["High"].max())


def range_position(price: float, low52: float, high52: float) -> float:
    """Where price sits in its 52-week range: 0.0 = at the low, 1.0 = at the high."""
    if high52 <= low52:
        return np.nan
    return (price - low52) / (high52 - low52)


def range_position_label(pos: float) -> str:
    """Translate the 0-1 range position into plain English."""
    if pos is None or np.isnan(pos):
        return "unknown"
    if pos >= 0.90:
        return "near its 52-week high"
    if pos >= 0.66:
        return "in the upper third of its 52-week range"
    if pos >= 0.33:
        return "in the middle of its 52-week range"
    if pos >= 0.10:
        return "in the lower third of its 52-week range"
    return "near its 52-week low"


# --------------------------------------------------------------------------
# Support / resistance and Fibonacci levels
#
# IMPORTANT: the chart overlay AND the tables both read from these two
# functions, with the SAME lookback windows, so the numbers never disagree.
# --------------------------------------------------------------------------

FIB_LOOKBACK_DAYS = 30  # swing window used for Fibonacci levels — everywhere


def fibonacci_levels(df: pd.DataFrame, lookback: int = FIB_LOOKBACK_DAYS):
    """Fibonacci retracement levels measured from the highest high and lowest
    low of the last `lookback` trading days. Returns a dict like
    {"swing_high": ..., "swing_low": ..., "levels": {"23.6%": price, ...}}."""
    window = df.iloc[-lookback:]
    swing_high = float(window["High"].max())
    swing_low = float(window["Low"].min())
    span = swing_high - swing_low
    ratios = {"23.6%": 0.236, "38.2%": 0.382, "50%": 0.50, "61.8%": 0.618}
    levels = {name: swing_high - span * r for name, r in ratios.items()}
    return {"swing_high": swing_high, "swing_low": swing_low,
            "levels": levels, "lookback": lookback}


def support_resistance(df: pd.DataFrame):
    """Simple support/resistance: the lowest low and highest high of the last
    30 and 90 trading days. Support = a floor where buyers stepped in before;
    resistance = a ceiling where sellers showed up before."""
    out = {}
    for days in (30, 90):
        window = df.iloc[-days:]
        out[days] = {"support": float(window["Low"].min()),
                     "resistance": float(window["High"].max())}
    return out


def swing_low(df: pd.DataFrame, lookback: int = 10) -> float:
    """Lowest intraday low of the last `lookback` days (used for stop-losses)."""
    return float(df["Low"].iloc[-lookback:].min())
