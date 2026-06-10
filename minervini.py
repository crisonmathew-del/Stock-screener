"""
Mark Minervini's "Trend Template" — a long-term trend filter.

Minervini (a US Investing Champion) only considers buying stocks that are
already in a confirmed, established uptrend. His checklist has 7 price-based
rules; a stock must pass ALL of them. The idea: don't try to catch falling
knives — fish only in the pond of stocks already proven to be rising.

The 7 rules (translated to plain English):
  1. Price is above both its 150-day and 200-day moving averages
     ("trading above its long-term trend lines").
  2. The 150-day average is above the 200-day average
     ("the medium trend is stronger than the long trend").
  3. The 200-day average has been rising for at least a month
     ("the long-term trend itself points up").
  4. The 50-day average is above both the 150-day and the 200-day
     ("the short-term trend is the strongest of all").
  5. Price is above the 50-day average ("strength right now").
  6. Price is at least 30% above its 52-week low
     ("it has already proven it can rally").
  7. Price is within 25% of its 52-week high
     ("it's near the top of its range, not buried in a crater").

Rule 8 — RELATIVE STRENGTH: Minervini's original uses IBD's RS Rating, which
ranks a stock's price performance against EVERY other stock (1-99). That is
NOT the same thing as the RSI(14) momentum gauge used elsewhere in this app,
and we deliberately do not substitute it. Instead we approximate: each
stock's 6-month and 12-month returns are blended and ranked against the
other stocks in THIS watchlist, giving a 1-100 percentile.
"""

import numpy as np
import pandas as pd

from indicators import sma, fifty_two_week_range

# Short labels for the results table; full descriptions for tooltips/details.
CRITERIA_LABELS = [
    "1. Price > 150 & 200-day MA",
    "2. 150-day MA > 200-day MA",
    "3. 200-day MA rising (vs 1 month ago)",
    "4. 50-day MA > 150 & 200-day MA",
    "5. Price > 50-day MA",
    "6. Price ≥ 30% above 52-week low",
    "7. Price within 25% of 52-week high",
]

MIN_BARS = 230  # need ~230 trading days: 200 for the MA + ~22 to check its slope


def evaluate_trend_template(df):
    """Check one stock against the 7 rules.

    Returns a dict with each rule's pass/fail, the count passed, prices and
    distances from the 52-week extremes — or None if there's not enough
    history (young IPOs simply can't be judged on a 200-day average).
    """
    df = df.dropna(subset=["Close", "High", "Low"])
    if len(df) < MIN_BARS:
        return None

    close = df["Close"]
    price = float(close.iloc[-1])
    ma50 = float(sma(close, 50).iloc[-1])
    ma150 = float(sma(close, 150).iloc[-1])
    ma200_series = sma(close, 200)
    ma200 = float(ma200_series.iloc[-1])
    # "~22 trading days" is about one calendar month
    ma200_month_ago = float(ma200_series.iloc[-23])
    low52, high52 = fifty_two_week_range(df)

    checks = [
        price > ma150 and price > ma200,          # 1
        ma150 > ma200,                            # 2
        ma200 > ma200_month_ago,                  # 3
        ma50 > ma150 and ma50 > ma200,            # 4
        price > ma50,                             # 5
        price >= low52 * 1.30,                    # 6
        price <= high52 and price >= high52 * 0.75,  # 7
    ]

    return {
        "price": price,
        "checks": checks,
        "passed": int(sum(checks)),
        "pct_above_low": (price / low52 - 1) * 100 if low52 > 0 else np.nan,
        "pct_below_high": (1 - price / high52) * 100 if high52 > 0 else np.nan,
        "ma50": ma50, "ma150": ma150, "ma200": ma200,
        "low52": low52, "high52": high52,
    }


def relative_strength_ranks(histories):
    """Approximate IBD-style Relative Strength rank, 1-100, vs the watchlist.

    `histories` maps ticker -> price DataFrame. For each stock we blend its
    6-month return (60% weight — recent strength matters more) with its
    12-month return (40%), then convert to a percentile rank among peers.
    Returns {ticker: rank 1-100}. Stocks lacking a year of data are skipped.
    """
    composite = {}
    for ticker, df in histories.items():
        close = df["Close"].dropna()
        if len(close) < 253:
            continue
        price = float(close.iloc[-1])
        ret6 = price / float(close.iloc[-127]) - 1.0   # ~126 trading days = 6 months
        ret12 = price / float(close.iloc[-253]) - 1.0  # ~252 trading days = 12 months
        composite[ticker] = 0.6 * ret6 + 0.4 * ret12

    if not composite:
        return {}
    s = pd.Series(composite)
    # rank(pct=True) gives 0-1; scale to 1-100 so "99" means "beat ~99% of peers"
    ranks = (s.rank(pct=True) * 99 + 1).round().astype(int)
    return ranks.to_dict()
