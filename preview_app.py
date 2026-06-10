"""
DEMO PREVIEW entry point — runs the real app with SYNTHETIC offline data.

Use this only to preview the user interface in environments where Yahoo
Finance is unreachable (e.g. sandboxes/CI):    streamlit run preview_app.py

All prices, scores and company moves shown are randomly generated — they are
NOT real market data. For the real app, run:   streamlit run app.py
"""

from datetime import datetime, timezone, timedelta, date

import numpy as np
import pandas as pd

from watchlist import all_tickers


def make_history(days=520, drift=0.0005, vol=0.015, seed=1,
                 last_day_jump=0.0, last_day_volume_mult=1.0):
    """A random-walk OHLCV history that looks like a real stock."""
    rng = np.random.default_rng(seed)
    close = 50 * np.exp(np.cumsum(rng.normal(drift, vol, days)))
    if last_day_jump:
        close[-1] = close[-2] * (1 + last_day_jump)
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.003, days))
    high = np.maximum(open_, close) * (1 + abs(rng.normal(0, 0.006, days)))
    low = np.minimum(open_, close) * (1 - abs(rng.normal(0, 0.006, days)))
    volume = rng.integers(1_000_000, 2_000_000, days).astype(float)
    volume[-1] *= last_day_volume_mult
    idx = pd.bdate_range(end=pd.Timestamp.today(), periods=days)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low,
                         "Close": close, "Volume": volume}, index=idx)


# A varied universe: uptrends, downtrends, and a handful of "breakout days"
HISTORIES = {}
for i, t in enumerate(all_tickers()):
    rng = np.random.default_rng(i)
    drift = float(rng.uniform(-0.001, 0.002))
    jump, vol_mult = 0.0, 1.0
    if i % 12 == 0:                      # sprinkle in strong breakout setups
        jump, vol_mult, drift = 0.035, 3.2, 0.0012
    elif i % 7 == 0:                     # and some building/extended ones
        jump, vol_mult = 0.02, 1.7
    HISTORIES[t] = make_history(seed=i, drift=drift, last_day_jump=jump,
                                last_day_volume_mult=vol_mult)

FETCHED = datetime.now(timezone.utc)


def fake_watchlist_history(tickers):
    return HISTORIES, FETCHED


def fake_stock(ticker):
    h = HISTORIES.get(ticker.strip().upper())
    if h is None:
        return None
    price = float(h["Close"].iloc[-1])
    return {
        "ticker": ticker, "hist": h,
        "info": {"name": f"{ticker} (demo data)", "sector": "Technology",
                 "current_price": price,
                 "previous_close": float(h["Close"].iloc[-2]),
                 "low52": float(h["Low"].iloc[-252:].min()),
                 "high52": float(h["High"].iloc[-252:].max()),
                 "pre_market": None, "post_market": None},
        "next_earnings": date.today() + timedelta(days=5),
        "fetched_at": FETCHED,
    }


def fake_quotes(symbols):
    return ({s: {"price": 5234.5, "pct_change": 0.85,
                 "as_of": datetime.now()} for s in symbols}, FETCHED)


# Swap the network layer out from under the tab modules, then run the app.
import tab_analysis, tab_minervini, tab_scanner  # noqa: E402

tab_scanner.fetch_watchlist_history = fake_watchlist_history
tab_minervini.fetch_watchlist_history = fake_watchlist_history
tab_analysis.fetch_stock = fake_stock
tab_analysis.fetch_quotes = fake_quotes

import runpy  # noqa: E402

runpy.run_path("app.py", run_name="__main__")
