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

import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

EASTERN = ZoneInfo("America/New_York")  # US stock exchanges run on Eastern Time
UK = ZoneInfo("Europe/London")          # timestamps are DISPLAYED in UK time


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


def sanitize_history(df):
    """Remove corrupt price bars that Yahoo's free feed occasionally serves.

    The classic failure: around stock splits, some bars arrive on a different
    adjustment basis than the rest of the history, which shows up as an
    impossible jump like +1009% (or its mirror image, -91%). Real one-day
    moves never approach these sizes — even buyouts top out around 2x — so
    bars that far out of line are data errors, not market moves. Two checks:

    1. One-bar spikes ANYWHERE in the series: a close more than 3x (or less
       than a third of) BOTH of its neighbours is a glitch — remove the row.
       (A genuine huge move doesn't fully un-happen the very next day.)
    2. Corrupt trailing bars: walking back from the end, any last bar more
       than 4x (or under a quarter of) the stock's own 20-day median close
       is dropped — repeated up to 5 times in case several bad bars arrived.
    """
    if df is None or len(df) < 22:
        return df

    # 1) one-bar spikes anywhere
    close = df["Close"]
    ratio_prev = close / close.shift(1)
    ratio_next = close / close.shift(-1)
    spike = (((ratio_prev > 3) & (ratio_next > 3)) |
             ((ratio_prev < 1 / 3) & (ratio_next < 1 / 3))).fillna(False)
    if spike.any():
        df = df[~spike]

    # 2) corrupt trailing bars (the last bar has no "next neighbour" to
    #    compare against, so judge it against the recent median instead)
    for _ in range(5):
        if len(df) < 22:
            break
        close = df["Close"]
        last = float(close.iloc[-1])
        median20 = float(close.iloc[-21:-1].median())
        if median20 > 0 and (last > 4 * median20 or last < 0.25 * median20):
            df = df.iloc[:-1]
        else:
            break
    return df


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

    NOTE: we deliberately do NOT pass repair=True here. yfinance's repair
    fires several extra metadata requests PER ticker; across the ~170-stock
    watchlist that floods Yahoo and gets the whole batch rate-limited on a
    shared cloud IP. auto_adjust + sanitize_history already keep prices on
    one consistent basis and drop corrupt bars without that request storm.
    """
    raw = None
    for attempt in range(2):  # one retry: Yahoo throttling is often momentary
        try:
            raw = yf.download(
                list(tickers),
                period="2y",        # enough for 200-day MAs + a 12-month return
                interval="1d",
                group_by="ticker",
                auto_adjust=True,   # split/dividend-adjusted: keeps every bar on
                                    # ONE consistent basis, so a stock split can't
                                    # fake a +1000% day or corrupt moving averages
                threads=True,
                progress=False,
            )
        except Exception:
            raw = None
        if raw is not None and not raw.empty:
            break
        if attempt == 0:
            time.sleep(2)  # brief pause before the single retry

    if raw is None or raw.empty:
        return {}, None

    histories = {}
    for ticker in tickers:
        try:
            df = sanitize_history(raw[ticker].dropna(subset=["Close"]))
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
        # auto_adjust keeps every bar on one consistent split-adjusted basis;
        # sanitize_history (below) removes any corrupt bars. We don't use
        # repair=True — see fetch_watchlist_history for why it's avoided.
        hist = t.history(period="2y", interval="1d", auto_adjust=True)
    except Exception:
        return None
    if hist is None or hist.empty or len(hist) < 2:
        return None
    hist = sanitize_history(hist)

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
                          group_by="ticker", auto_adjust=True,
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
