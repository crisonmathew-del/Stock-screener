"""
All the internet-facing code: downloading data from Yahoo Finance (via the
free `yfinance` library) with caching, plus market-hours detection.

Why caching matters: Yahoo rate-limits heavy traffic. Without a cache, every
click would re-download 170 stocks and quickly get blocked. With
`@st.cache_data`, a download is reused for everyone for `ttl` seconds
(10 minutes for the big watchlist scan, 5 minutes for a single stock).
The "Refresh data" buttons in the app clear these caches on demand.

Every function here is defensive: network hiccups, invalid tickers and
missing fields return None / empty values instead of crashing the app.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

EASTERN = ZoneInfo("America/New_York")  # US stock exchanges run on Eastern Time


# --------------------------------------------------------------------------
# Market open/closed detection (used by the freshness banners everywhere)
# --------------------------------------------------------------------------

def market_status():
    """Is the US stock market open right now?

    Regular hours: 9:30am-4:00pm Eastern, Monday-Friday. (Public holidays are
    not checked — on a holiday the app will simply show the last session's
    prices with a 'markets closed' style timestamp from the data itself.)
    Returns (is_open: bool, now_in_eastern_time: datetime).
    """
    now_et = datetime.now(EASTERN)
    is_weekday = now_et.weekday() < 5  # Monday=0 ... Friday=4
    minutes = now_et.hour * 60 + now_et.minute
    is_open = is_weekday and (9 * 60 + 30) <= minutes < (16 * 60)
    return is_open, now_et


def data_age_minutes(fetched_at_utc):
    """How many minutes old is a cached download?"""
    if fetched_at_utc is None:
        return None
    return (datetime.now(timezone.utc) - fetched_at_utc).total_seconds() / 60.0


# --------------------------------------------------------------------------
# Bulk download: the whole watchlist in one request (for Tabs 1 and 3)
# --------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_watchlist_history(tickers: tuple):
    """Download ~2 years of daily prices for every watchlist ticker in ONE
    bulk request (much friendlier to Yahoo than 170 separate calls).

    Returns ({ticker: DataFrame}, fetched_at_utc). Tickers that fail simply
    don't appear in the dict. Returns ({}, None) if the whole download fails
    (e.g. no internet) so callers can show a friendly message.
    """
    try:
        raw = yf.download(
            list(tickers),
            period="2y",            # enough for 200-day MAs + a 12-month return
            interval="1d",
            group_by="ticker",
            auto_adjust=False,      # keep raw prices so they match Yahoo's site
            threads=True,
            progress=False,
        )
    except Exception:
        return {}, None

    if raw is None or raw.empty:
        return {}, None

    histories = {}
    for ticker in tickers:
        try:
            df = raw[ticker].dropna(subset=["Close"])
            if len(df) >= 2:
                histories[ticker] = df
        except (KeyError, TypeError):
            continue  # this ticker failed — skip it, don't crash the scan
    return histories, datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Single-stock deep dive (for Tab 2)
# --------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock(ticker: str):
    """Everything Tab 2 needs for one stock: 2 years of daily prices, the
    info block (company name, live price, 52-week range, pre/post-market
    prices...) and the next earnings date.

    Returns a dict, or None if the ticker is invalid / has no data.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return None
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y", interval="1d", auto_adjust=False)
    except Exception:
        return None
    if hist is None or hist.empty or len(hist) < 2:
        return None

    # .info is a big metadata dictionary. It's occasionally slow or missing
    # fields, so everything that reads it uses .get() with a fallback.
    try:
        info = t.info or {}
    except Exception:
        info = {}

    return {
        "ticker": ticker,
        "hist": hist,
        "info": {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": (info.get("regularMarketPreviousClose")
                               or info.get("previousClose")),
            # Use Yahoo's own INTRADAY 52-week extremes so the numbers match
            # what Yahoo Finance / CNBC display (not closing-price extremes).
            "low52": info.get("fiftyTwoWeekLow"),
            "high52": info.get("fiftyTwoWeekHigh"),
            "pre_market": info.get("preMarketPrice"),
            "post_market": info.get("postMarketPrice"),
        },
        "next_earnings": _next_earnings_date(t),
        "fetched_at": datetime.now(timezone.utc),
    }


def _next_earnings_date(t):
    """The next scheduled earnings date, or None if Yahoo doesn't have one.

    yfinance has changed how it exposes this over the years, so we try the
    modern `calendar` dict first, then the older `get_earnings_dates()` table.
    """
    today = datetime.now(EASTERN).date()

    try:
        cal = t.calendar
        dates = None
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date")
        elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
            dates = list(cal.loc["Earnings Date"])
        if dates:
            future = [d for d in pd.to_datetime(pd.Series(list(dates))).dt.date
                      if d >= today]
            if future:
                return min(future)
    except Exception:
        pass

    try:
        ed = t.get_earnings_dates(limit=12)
        if ed is not None and not ed.empty:
            future = [d.date() for d in ed.index.tz_localize(None) if d.date() >= today]
            if future:
                return min(future)
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# Market context: index futures + sector ETFs (for the Tab 2 context card)
# --------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_quotes(symbols: tuple):
    """Last price and % change for a few symbols (futures, ETFs).

    Returns ({symbol: {"price", "pct_change", "as_of"}}, fetched_at_utc).
    Symbols that fail are simply missing from the dict.
    """
    out = {}
    try:
        raw = yf.download(list(symbols), period="5d", interval="1d",
                          group_by="ticker", auto_adjust=False,
                          threads=True, progress=False)
    except Exception:
        return {}, None
    if raw is None or raw.empty:
        return {}, None

    for sym in symbols:
        try:
            df = raw[sym].dropna(subset=["Close"])
            if len(df) < 2:
                continue
            price = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            out[sym] = {
                "price": price,
                "pct_change": (price / prev - 1) * 100 if prev else None,
                "as_of": df.index[-1].to_pydatetime(),
            }
        except (KeyError, TypeError):
            continue
    return out, datetime.now(timezone.utc)


def clear_all_caches():
    """Wipe every cached download (wired to the 'Refresh data' buttons)."""
    fetch_watchlist_history.clear()
    fetch_stock.clear()
    fetch_quotes.clear()
