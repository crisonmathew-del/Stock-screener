"""
The strategy backtester — "what WOULD have happened if you'd followed a
simple rule on this stock?"

A "backtest" replays history: it walks through the stock's past daily
prices, mechanically applies a buying-and-selling rule, and tracks what a
hypothetical pot of money would have done. It exists here for LEARNING —
to show how trading signals really behave — never as a strategy to follow.

How the simulation works (deliberately simple, like a beginner would trade):
  * Start with a pot of cash (default 10,000).
  * When the rule says "buy", spend ALL the cash at that day's closing price.
  * When the rule says "sell", sell ALL the shares at that day's closing price.
  * One position at a time: no buying while holding, no selling while not.
  * If still holding at the end, the last trade is marked "still open" and
    valued at the final price.
  * No fees, taxes, dividends or slippage — reality would be a bit worse.

Every result is compared against "buy and hold": just buying on day one and
doing nothing. That comparison is the whole lesson — simple rules often
lose to simply holding, and seeing that on a real stock teaches more than
any lecture.
"""

import numpy as np
import pandas as pd

from indicators import sma, macd

# ---------------------------------------------------------------------------
# The four rules a user can test. "warmup" = how many bars of history the
# rule's indicators need BEFORE the test period can start (a 200-day average
# needs 200 days of data before it says anything).
# ---------------------------------------------------------------------------
STRATEGIES = {
    "golden_cross": {
        "label": "Golden cross / death cross",
        "description": "Buy when the 50-day average crosses above the 200-day "
                       "average; sell when it crosses back below. A slow, "
                       "patient rule that trades rarely.",
        "warmup": 210,
    },
    "breakout_volume": {
        "label": "Breakout on volume",
        "description": "Buy when price closes above its highest level of the "
                       "last 20 days on at least 1.5x normal volume; sell on "
                       "a 7% stop-loss or a close below the 10-day low. The "
                       "scanner tab hunts for exactly this setup.",
        "warmup": 25,
    },
    "macd": {
        "label": "MACD momentum",
        "description": "Buy when the MACD line crosses above its signal line "
                       "(momentum turning up); sell when it crosses back "
                       "below. A faster rule that trades often.",
        "warmup": 40,
    },
    "ma_trend": {
        "label": "Moving-average trend",
        "description": "Buy when price closes above its 50-day average; sell "
                       "when it closes below. The simplest trend-following "
                       "rule there is.",
        "warmup": 55,
    },
}

MIN_TEST_BARS = 120  # ~6 months: any shorter and the "results" are noise


def _cross_signals(fast, slow):
    """(crossed_up, crossed_down) boolean series for fast vs slow lines.
    Uses shift(fill_value=...) to stay boolean — see price_chart.py for the
    pandas dtype trap this avoids."""
    above = fast > slow
    prev = above.shift(1, fill_value=False)
    return (above & ~prev), (~above & prev)


def _signals_for(df, strategy_key):
    """Build the rule's signals over the FULL history (so indicators are
    warmed up before the test window starts).

    Returns (buy_signal, sell_signal, state). `state` is a boolean series of
    "the rule says you should be holding right now" — used so a test window
    that starts mid-trend begins holding (the cross may have happened before
    the window; without this, trending stocks would show '0 trades' and sit
    in cash, which would mislead a learner). It is None for the breakout
    rule, which is event-based (its stop-loss needs a real entry price).
    """
    close, vol = df["Close"], df["Volume"]
    if strategy_key == "golden_cross":
        fast, slow = sma(close, 50), sma(close, 200)
        buy, sell = _cross_signals(fast, slow)
        return buy, sell, (fast > slow)
    if strategy_key == "macd":
        macd_line, signal_line = macd(close)
        buy, sell = _cross_signals(macd_line, signal_line)
        return buy, sell, (macd_line > signal_line)
    if strategy_key == "ma_trend":
        ma50 = sma(close, 50)
        buy, sell = _cross_signals(close, ma50)
        return buy, sell, (close > ma50)
    if strategy_key == "breakout_volume":
        high20 = df["High"].rolling(20).max().shift(1)   # prior 20-day ceiling
        avg_vol = vol.rolling(20).mean().shift(1)
        vol_ratio = vol / avg_vol
        buy = (close > high20) & (vol_ratio >= 1.5)
        low10 = df["Low"].rolling(10).min().shift(1)     # prior 10-day floor
        sell = close < low10   # the 7% stop-loss is checked in the loop,
        return buy, sell, None  # because it depends on each trade's buy price
    raise ValueError(f"unknown strategy: {strategy_key}")


def run_backtest(hist, strategy_key, years, starting_cash):
    """Replay the rule over the last `years` of `hist`.

    Returns a dict of results, or {"error": <friendly message>} when the
    stock doesn't have enough history. If there's enough data to test but
    less than requested (a recent IPO), the test runs on what exists and
    the result carries a "note" saying so.
    """
    meta = STRATEGIES[strategy_key]
    df = hist.dropna(subset=["Close", "High", "Low", "Volume"])

    available = len(df) - meta["warmup"]
    if available < MIN_TEST_BARS:
        return {"error": (
            "This stock doesn't have enough trading history to test this "
            "rule fairly — the rule needs time to 'warm up' its averages "
            "first. Recent IPOs usually can't be backtested. Try a stock "
            "with a few years of history.")}

    wanted = int(years * 252)            # ~252 trading days per year
    bars = min(wanted, available)
    note = None
    if bars < wanted:
        note = (f"You asked for {years} year{'s' if years > 1 else ''}, but "
                f"this stock only has enough history to test about "
                f"{bars / 252:.1f} years — the results below cover that "
                "shorter period.")

    buy_sig, sell_sig, state = _signals_for(df, strategy_key)
    test = df.iloc[-bars:]
    closes = test["Close"]

    # If the rule was already saying "hold" when the window opens (the buy
    # cross happened before the window), start the test holding from day one.
    started_in_market = bool(state is not None and state.loc[test.index[0]])

    # ------------------- walk forward, one day at a time -------------------
    cash = float(starting_cash)
    shares = 0.0
    entry_price, entry_date = None, None
    trades = []
    equity = []

    for date in test.index:
        price = float(closes.loc[date])
        if shares > 0:
            stop_hit = (strategy_key == "breakout_volume"
                        and price <= entry_price * 0.93)
            if bool(sell_sig.loc[date]) or stop_hit:
                cash = shares * price
                trades.append({
                    "buy_date": entry_date, "buy_price": entry_price,
                    "sell_date": date, "sell_price": price,
                    "pct": (price / entry_price - 1) * 100,
                    "open": False,
                })
                shares, entry_price, entry_date = 0.0, None, None
        elif bool(buy_sig.loc[date]) or (started_in_market
                                         and date == test.index[0]):
            shares = cash / price
            entry_price, entry_date = price, date
            cash = 0.0
        equity.append(cash + shares * price)

    last_price = float(closes.iloc[-1])
    if shares > 0:   # still holding at the end of the period
        trades.append({
            "buy_date": entry_date, "buy_price": entry_price,
            "sell_date": None, "sell_price": last_price,
            "pct": (last_price / entry_price - 1) * 100,
            "open": True,
        })

    # Dollar result of each trade (the pot compounds from trade to trade)
    pot = float(starting_cash)
    for t in trades:
        new_pot = pot * (1 + t["pct"] / 100)
        t["dollars"] = new_pot - pot
        pot = new_pot

    equity = pd.Series(equity, index=test.index)
    final_value = float(equity.iloc[-1])

    # ------------------- the benchmark: just buy and hold -------------------
    first_price = float(closes.iloc[0])
    bh_value = starting_cash / first_price * last_price
    bh_equity = closes / first_price * starting_cash

    closed = [t for t in trades if not t["open"]]
    wins = [t for t in closed if t["pct"] > 0]
    losses = [t for t in closed if t["pct"] <= 0]

    return {
        "error": None,
        "note": note,
        "started_in_market": started_in_market,
        "strategy": strategy_key,
        "label": meta["label"],
        "starting_cash": float(starting_cash),
        "final_value": final_value,
        "return_pct": (final_value / starting_cash - 1) * 100,
        "bh_value": float(bh_value),
        "bh_return_pct": (bh_value / starting_cash - 1) * 100,
        "beat_buy_hold": final_value > bh_value,
        "trades": trades,
        "n_closed": len(closed),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate": (len(wins) / len(closed) * 100) if closed else None,
        "avg_win_pct": float(np.mean([t["pct"] for t in wins])) if wins else None,
        "avg_loss_pct": float(np.mean([t["pct"] for t in losses])) if losses else None,
        "max_drawdown_pct": float((equity / equity.cummax() - 1).min() * 100),
        "bh_max_drawdown_pct": float((bh_equity / bh_equity.cummax() - 1).min() * 100),
        "test_closes": closes,
        "period_years": bars / 252,
    }


def interpret(result):
    """2-3 plain-English sentences explaining what the numbers mean —
    tailored to what actually happened, honest about the usual lessons."""
    if not result["trades"]:
        return ("The rule's conditions never lined up even once in this "
                "period, so the money just sat in cash while the stock did "
                "its thing. That's a result too: rules can keep you out of "
                "the market entirely — for better or worse.")

    sentences = []
    strat_pos = result["return_pct"] > 0

    if result["beat_buy_hold"]:
        sentences.append(
            "This rule actually beat simply holding the stock here — worth "
            "knowing that's the exception, not the rule, and one good "
            "backtest proves very little.")
    elif strat_pos:
        sentences.append(
            "This rule made money but less than simply holding — a very "
            "common result. Rules that cut losses also tend to sell winners "
            "too early and miss the recovery days that drive most gains.")
    else:
        sentences.append(
            "This rule lost money over the period — mechanical signals "
            "misfire often, and each misfire costs a slice of the pot.")

    # Only draw the "wins rarely but profits" lesson from a real sample size
    if (result["win_rate"] is not None and result["win_rate"] < 50
            and strat_pos and result["n_closed"] >= 4):
        sentences.append(
            "Notice it won less than half its trades yet still came out "
            "ahead — small losses and a few big winners. That's the classic "
            "trend-following pattern, and it's emotionally hard to follow "
            "in real life because you're 'wrong' most of the time.")
    elif result["n_closed"] >= 10:
        sentences.append(
            f"It also traded {result['n_closed']} times — in real life every "
            "trade adds fees, tax events and chances to second-guess "
            "yourself, none of which this test counts.")

    if (result["max_drawdown_pct"] > result["bh_max_drawdown_pct"] + 1):
        sentences.append(
            "And the ride was actually bumpier than just holding — the rule "
            "didn't even buy smoothness with the returns it gave up.")
    elif (result["max_drawdown_pct"] < result["bh_max_drawdown_pct"] - 10):
        sentences.append(
            "What the rule did buy was a smoother ride — its worst drop was "
            "much smaller than a holder's. Some people happily trade away "
            "returns for that.")

    return " ".join(sentences[:3])
