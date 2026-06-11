"""
The 0-100 breakout score — the heart of the scanner.

A "breakout" is when a stock pushes above a price ceiling it has struggled
with, on unusually heavy trading volume. The score rewards the ingredients
of a healthy breakout and PENALISES stocks that have already run too far
(so the tool never encourages chasing a spike).

How the 100 points are split:
  * VOLUME (30)         — is today's trading volume unusually heavy?
  * PRICE MOMENTUM (25) — is price pushing to new short-term highs today?
  * TREND (20)          — is the stock above its key moving averages?
  * CONSOLIDATION (15)  — was it quiet recently and now waking UP?
  * RSI & MACD (10)     — is momentum strong but not overheated?

Plus:
  * +5 bonus if price is within 3% of its 52-week high (no "ceiling" above).
  * Chase guard: a day up more than 8%, or +20% in 5 days / +35% in 10 days,
    is flagged "Extended" and scored down — late entries are risky entries.
  * RSI above 78 subtracts 4 points (overheated).
"""

import numpy as np

from indicators import (
    sma, rsi, macd_crossed_up_recently, bollinger_width,
    pct_return, fifty_two_week_range,
)

# Verdict bands (also used for the table colours)
STRONG_MIN = 70   # 70-100 -> "Strong breakout setup"
WATCH_MIN = 45    # 45-69  -> "Watch — building momentum"

MIN_BARS = 60  # need at least ~3 months of history to score sensibly


def compute_breakout(df):
    """Score one stock. `df` is its daily price history (needs Open/High/Low/
    Close/Volume columns, oldest row first). Returns a dict with the score,
    each category's points and a plain-English note for every part — or None
    if there isn't enough data to judge."""
    df = df.dropna(subset=["Close", "High", "Low", "Volume"])
    if len(df) < MIN_BARS:
        return None

    close, high, vol = df["Close"], df["High"], df["Volume"]
    price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    if prev_close <= 0 or price <= 0:
        return None
    pct_today = (price - prev_close) / prev_close * 100.0

    components = {}   # category name -> {"points", "max", "detail"}
    flags = []        # plain-English warnings shown to the user

    # ---------------- VOLUME (30 pts) ----------------
    # Compare today's volume with the average of the PREVIOUS 20 days
    # (today excluded, so a big day doesn't inflate its own benchmark).
    avg_vol_20 = float(vol.iloc[-21:-1].mean())
    vol_ratio = float(vol.iloc[-1]) / avg_vol_20 if avg_vol_20 > 0 else 0.0
    if vol_ratio >= 3.0:
        vol_pts = 30
    elif vol_ratio >= 2.0:
        vol_pts = 22
    elif vol_ratio >= 1.5:
        vol_pts = 14
    elif vol_ratio >= 1.2:
        vol_pts = 7
    else:
        vol_pts = 0
    components["Volume surge"] = {
        "points": vol_pts, "max": 30,
        "detail": (f"Today's volume is {vol_ratio:.1f}x its 20-day average. "
                   "Heavy volume means real buying interest, not a random wiggle."),
    }

    # ---------------- PRICE MOMENTUM (25 pts) ----------------
    high_20_prior = float(high.iloc[-21:-1].max())  # the recent "ceiling"
    broke_high = price > high_20_prior
    breakout_pts = 12 if broke_high else 0

    # Chase guard part 1: a one-day spike over +8% is usually too late to join.
    extended_today = pct_today > 8.0
    if extended_today:
        day_pts = 2  # sharply cut — we reward steady 2-5% days, not spikes
        flags.append(f"Up {pct_today:+.1f}% today — extended; chasing spikes is risky.")
    elif pct_today >= 5.0:
        day_pts = 13
    elif pct_today >= 3.0:
        day_pts = 9
    elif pct_today >= 1.5:
        day_pts = 5
    else:
        day_pts = 0
    momentum_pts = min(breakout_pts + day_pts, 25)
    components["Price momentum"] = {
        "points": momentum_pts, "max": 25,
        "detail": ((f"Price broke above its 20-day high of {high_20_prior:.2f}. "
                    if broke_high else
                    f"Price has not cleared its 20-day high of {high_20_prior:.2f}. ")
                   + f"Today's move: {pct_today:+.1f}%."
                   + (" (Points cut: the day's jump is too big to chase.)"
                      if extended_today else "")),
    }

    # ---------------- TREND CONFIRMATION (20 pts) ----------------
    ma20 = float(sma(close, 20).iloc[-1])
    ma50 = float(sma(close, 50).iloc[-1]) if len(close) >= 50 else np.nan
    ma200 = float(sma(close, 200).iloc[-1]) if len(close) >= 200 else np.nan
    above20 = price > ma20
    above50 = bool(not np.isnan(ma50) and price > ma50)
    golden = bool(not np.isnan(ma50) and not np.isnan(ma200) and ma50 > ma200)
    trend_pts = (7 if above20 else 0) + (7 if above50 else 0) + (6 if golden else 0)
    trend_bits = [
        ("above" if above20 else "below") + " its 20-day average",
        ("above" if above50 else "below") + " its 50-day average",
        ("50-day average is above the 200-day (long-term uptrend)" if golden
         else "50-day average is NOT above the 200-day"),
    ]
    components["Trend confirmation"] = {
        "points": trend_pts, "max": 20,
        "detail": "Price is " + trend_bits[0] + " and " + trend_bits[1]
                  + "; the " + trend_bits[2] + ".",
    }

    # ---------------- CONSOLIDATION → EXPANSION (15 pts) ----------------
    # The classic setup: the stock trades QUIETLY for a stretch (a tight,
    # narrow band) and then volatility expands UPWARD. We measure "quiet"
    # with Bollinger Band width: last 10 days vs the 20 days before that.
    bbw = bollinger_width(close)
    cons_pts, cons_detail = 0, "Not enough history to judge."
    if len(bbw.dropna()) >= 30:
        recent_width = float(bbw.iloc[-10:].mean())
        prior_width = float(bbw.iloc[-30:-10].mean())
        was_tight = prior_width > 0 and recent_width < 0.8 * prior_width
        expanding_up = float(bbw.iloc[-1]) > recent_width * 1.1 and pct_today > 0
        if was_tight and expanding_up:
            cons_pts = 15
            cons_detail = ("The stock traded in a tight, quiet range and is now "
                           "expanding upward — the classic breakout setup.")
        elif was_tight or expanding_up:
            cons_pts = 8
            cons_detail = ("Partial setup: " +
                           ("it was quiet recently but hasn't expanded upward yet."
                            if was_tight else
                            "volatility is expanding upward, but without a quiet "
                            "coiling phase first."))
        else:
            cons_detail = "No tight consolidation before this move — a weaker setup."
    components["Consolidation → expansion"] = {
        "points": cons_pts, "max": 15, "detail": cons_detail,
    }

    # ---------------- RSI & MACD (10 pts) ----------------
    rsi_now = float(rsi(close).iloc[-1])
    if 55 <= rsi_now <= 70:
        rsi_pts = 6
    elif 50 <= rsi_now < 55 or 70 < rsi_now <= 75:
        rsi_pts = 3
    else:
        rsi_pts = 0
    macd_up = macd_crossed_up_recently(close)
    macd_pts = 4 if macd_up else 0
    components["RSI & MACD momentum"] = {
        "points": rsi_pts + macd_pts, "max": 10,
        "detail": (f"RSI is {rsi_now:.0f} (the sweet spot is 55-70: strong but "
                   "not overheated). MACD "
                   + ("recently crossed upward — momentum is turning up."
                      if macd_up else "has not crossed upward recently.")),
    }

    score = sum(c["points"] for c in components.values())

    # ---------------- 52-week-high proximity bonus (+5) ----------------
    low52, high52 = fifty_two_week_range(df)
    near_52wk_high = high52 > 0 and price >= 0.97 * high52
    bonus = 5 if near_52wk_high else 0
    if near_52wk_high:
        flags.append("Within 3% of its 52-week high — breakouts to new highs "
                     "have no old 'ceiling' overhead (+5 bonus).")

    # ---------------- Chase guard part 2: multi-day extension ----------------
    ret5 = pct_return(close, 5)
    ret10 = pct_return(close, 10)
    extended_multi = ((not np.isnan(ret5) and ret5 > 20.0) or
                      (not np.isnan(ret10) and ret10 > 35.0))
    penalty = 0
    if extended_multi:
        penalty += 8
        flags.append(f"Already up {ret5:+.0f}% in 5 days / {ret10:+.0f}% in 10 days "
                     "— extended even if today looks quiet (-8 points).")

    # ---------------- RSI overheating penalty ----------------
    if rsi_now > 78:
        penalty += 4
        flags.append(f"RSI {rsi_now:.0f} is above 78 — overbought (-4 points).")

    extended = extended_today or extended_multi
    score = int(np.clip(score + bonus - penalty, 0, 100))

    # Data sanity (per the app-wide rule): a move beyond ±30% in one day is
    # rare enough that it deserves a "verify this elsewhere" flag — it can be
    # real (buyouts, biotech news) but is also how data glitches look.
    suspect_move = abs(pct_today) > 30
    if suspect_move:
        flags.append(f"Moved {pct_today:+.0f}% vs the previous close — moves "
                     "beyond ±30% are sometimes data errors. Verify on "
                     "finance.yahoo.com before trusting these numbers.")

    return {
        "price": price,
        "prev_close": prev_close,
        "pct_today": pct_today,
        "vol_ratio": vol_ratio,
        "rsi": rsi_now,
        "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "low52": low52, "high52": high52,
        "near_52wk_high": near_52wk_high,
        "broke_20d_high": broke_high,
        "macd_crossed_up": macd_up,
        "ret5": ret5, "ret10": ret10,
        "extended": extended,
        "suspect_move": suspect_move,
        "score": score,
        "bonus": bonus,
        "penalty": penalty,
        "components": components,
        "flags": flags,
        "verdict": verdict_for(score),
        "entry_note": entry_note(score, pct_today, rsi_now, extended),
    }


def verdict_for(score):
    """Translate the score into a plain-English verdict."""
    if score >= STRONG_MIN:
        return "🟢 Strong breakout setup"
    if score >= WATCH_MIN:
        return "🟡 Watch — building momentum"
    return "🔴 Not a breakout candidate"


def entry_note(score, pct_today, rsi_now, extended):
    """One-line note on whether NOW is a sensible moment, even for a good setup."""
    if score >= STRONG_MIN:
        if not extended and 2.0 <= pct_today <= 5.0 and 55 <= rsi_now <= 70:
            return "✅ Early — good entry zone"
        if not extended:
            return "✅ Strong setup — reasonable entry"
        return "⚡ Strong but extended — size carefully"
    if extended or rsi_now > 75:
        return "⚠️ Extended/Overbought — wait for pullback"
    if score >= WATCH_MIN:
        return "👀 Building — watch for entry trigger"
    return "— Not a setup right now"
