"""
Chart-pattern detection (informational only — it does NOT affect the score).

Traders give names to shapes that price charts often make before big moves.
This module looks for the most famous ones automatically. Detection is
deliberately conservative: if a pattern isn't clearly there, we say
"Not detected" rather than force one.

The patterns, in plain English:
  * Cup & Handle (bullish): a long rounded dip and recovery (the cup), then a
    small final pullback (the handle) before pushing to new highs.
  * Bull Flag (bullish): a sharp run-up (the flagpole) followed by a few days
    of quiet drift — a "rest" before possibly continuing up.
  * Ascending Triangle (bullish): a flat ceiling that keeps getting tested,
    with higher and higher floors — pressure building under a lid.
  * Resistance breakout (bullish): closing above the recent ceiling on
    above-average volume.
  * Gap-up on volume (bullish): opening clearly above yesterday's entire
    range on heavy volume — usually big news.
  * Golden Cross (bullish) / Death Cross (bearish): the 50-day average
    crossing above / below the 200-day average — a long-term trend change.
  * Candlestick patterns (one- or two-day signals): bullish/bearish
    engulfing, hammer, doji.

Mutually contradictory patterns are never reported together: we total up the
evidence on each side and only show the strongest side's patterns.
"""

import numpy as np

from indicators import sma


def _detect_all(df):
    """Run every individual check. Returns a list of dicts:
    {"name", "direction" (bullish/bearish/neutral), "strength" 1-5, "sentence"}.
    """
    found = []
    close, high, low = df["Close"], df["High"], df["Low"]
    open_, vol = df["Open"], df["Volume"]
    price = float(close.iloc[-1])
    avg_vol_20 = float(vol.iloc[-21:-1].mean()) if len(vol) > 21 else np.nan
    vol_ratio = float(vol.iloc[-1]) / avg_vol_20 if avg_vol_20 and avg_vol_20 > 0 else 0.0

    # ---------- Golden / Death cross (needs ~200 days of history) ----------
    if len(close) >= 215:
        ma50 = sma(close, 50)
        ma200 = sma(close, 200)
        above = ma50 > ma200
        recent = above.iloc[-15:]
        if bool(above.iloc[-1]) and not bool(recent.iloc[0]):
            found.append({
                "name": "Golden Cross", "direction": "bullish", "strength": 4,
                "sentence": "The 50-day average just crossed above the 200-day "
                            "average — a classic sign the long-term trend is turning up.",
            })
        elif not bool(above.iloc[-1]) and bool(recent.iloc[0]):
            found.append({
                "name": "Death Cross", "direction": "bearish", "strength": 4,
                "sentence": "The 50-day average just crossed below the 200-day "
                            "average — a classic sign the long-term trend is turning down.",
            })

    # ---------- Gap-up on volume ----------
    if len(df) >= 22:
        gapped = float(open_.iloc[-1]) > float(high.iloc[-2]) * 1.005
        if gapped and vol_ratio >= 1.5:
            found.append({
                "name": "Gap-up on volume", "direction": "bullish", "strength": 3,
                "sentence": "The stock opened clearly above yesterday's entire range "
                            "on heavy volume — usually a reaction to big news.",
            })

    # ---------- Resistance breakout ----------
    if len(df) >= 32:
        ceiling = float(high.iloc[-31:-1].max())
        if price > ceiling and vol_ratio >= 1.2:
            found.append({
                "name": "Resistance breakout", "direction": "bullish", "strength": 4,
                "sentence": f"Price closed above its recent ceiling of {ceiling:.2f} "
                            "on above-average volume — old sellers are out of the way.",
            })

    # ---------- Bull flag ----------
    # Flagpole: a 12%+ run that ended 5-15 bars ago; flag: a quiet, slightly
    # drifting range since then on lighter volume.
    if len(df) >= 35:
        for pole_end in range(5, 16):  # bars ago the run-up ended
            pole_start = pole_end + 10
            if pole_start >= len(close):
                break
            pole_gain = (float(close.iloc[-pole_end]) /
                         float(close.iloc[-pole_start]) - 1) * 100
            if pole_gain < 12:
                continue
            flag = close.iloc[-pole_end:]
            drift = (price / float(flag.iloc[0]) - 1) * 100
            tight = (float(flag.max()) - float(flag.min())) / price < 0.08
            quieter = float(vol.iloc[-pole_end:].mean()) < float(
                vol.iloc[-pole_start:-pole_end].mean())
            if -6 <= drift <= 2 and tight and quieter:
                found.append({
                    "name": "Bull Flag", "direction": "bullish", "strength": 4,
                    "sentence": f"A sharp {pole_gain:.0f}% run-up followed by a few "
                                "quiet days of rest — flags often resolve in the "
                                "direction of the original run.",
                })
                break

    # ---------- Ascending triangle ----------
    if len(df) >= 25:
        win_h, win_l = high.iloc[-25:], low.iloc[-25:]
        ceiling = float(win_h.max())
        touches = int((win_h >= ceiling * 0.985).sum())
        lows_slope = np.polyfit(np.arange(len(win_l)), win_l.to_numpy(float), 1)[0]
        rising_floor = lows_slope > 0 and (float(win_l.iloc[-5:].mean()) >
                                           float(win_l.iloc[:5].mean()))
        if touches >= 3 and rising_floor and price >= ceiling * 0.95:
            found.append({
                "name": "Ascending Triangle", "direction": "bullish", "strength": 4,
                "sentence": f"A flat ceiling near {ceiling:.2f} has been tested "
                            f"{touches} times while the floors keep rising — "
                            "buying pressure is building under a lid.",
            })

    # ---------- Cup & Handle (very approximate) ----------
    if len(df) >= 80:
        win = close.iloc[-80:]
        left = win.iloc[:30]
        rim = float(left.max())
        bottom = float(win.iloc[30:65].min()) if len(win) >= 65 else np.nan
        if rim > 0 and not np.isnan(bottom):
            depth = (rim - bottom) / rim * 100
            recovered = price >= rim * 0.95
            handle = close.iloc[-10:]
            handle_dip = (float(handle.max()) - float(handle.min())) / float(handle.max()) * 100
            if 8 <= depth <= 35 and recovered and 1 <= handle_dip <= 10:
                found.append({
                    "name": "Cup & Handle", "direction": "bullish", "strength": 5,
                    "sentence": f"A rounded {depth:.0f}% dip-and-recovery (the cup) "
                                "followed by a small recent pullback (the handle) — "
                                "a setup famous for preceding moves to new highs.",
                })

    # ---------- Candlestick patterns (last 1-2 days) ----------
    if len(df) >= 7:
        o1, c1 = float(open_.iloc[-1]), float(close.iloc[-1])
        o2, c2 = float(open_.iloc[-2]), float(close.iloc[-2])
        h1, l1 = float(high.iloc[-1]), float(low.iloc[-1])
        day_range = max(h1 - l1, 1e-9)
        body = abs(c1 - o1)
        prior_falling = float(close.iloc[-7:-1].mean()) > c2  # was drifting down

        # Bullish engulfing: yesterday red, today green and bigger both ways
        if c2 < o2 and c1 > o1 and c1 >= o2 and o1 <= c2:
            found.append({
                "name": "Bullish Engulfing candle", "direction": "bullish", "strength": 2,
                "sentence": "Today's green candle completely swallowed yesterday's "
                            "red one — buyers overpowered sellers.",
            })
        # Bearish engulfing: the mirror image
        elif c2 > o2 and c1 < o1 and c1 <= o2 and o1 >= c2:
            found.append({
                "name": "Bearish Engulfing candle", "direction": "bearish", "strength": 2,
                "sentence": "Today's red candle completely swallowed yesterday's "
                            "green one — sellers overpowered buyers.",
            })

        # Hammer: tiny body at the top, long lower wick, after a dip
        lower_wick = min(o1, c1) - l1
        upper_wick = h1 - max(o1, c1)
        if (body <= 0.35 * day_range and lower_wick >= 2 * body
                and upper_wick <= 0.3 * day_range and prior_falling):
            found.append({
                "name": "Hammer candle", "direction": "bullish", "strength": 2,
                "sentence": "Price was pushed down hard during the day but buyers "
                            "fought back to close near the top — a possible bottom.",
            })

        # Doji: open and close almost equal — indecision
        if body <= 0.10 * day_range:
            found.append({
                "name": "Doji candle", "direction": "neutral", "strength": 1,
                "sentence": "The stock closed almost exactly where it opened — "
                            "buyers and sellers are evenly matched (indecision).",
            })

    return found


ALL_PATTERN_NAMES = [
    "Cup & Handle", "Bull Flag", "Ascending Triangle", "Resistance breakout",
    "Gap-up on volume", "Golden Cross", "Death Cross",
    "Bullish Engulfing candle", "Bearish Engulfing candle",
    "Hammer candle", "Doji candle",
]


def detect_patterns(df):
    """Detect patterns and resolve contradictions.

    Returns {"shown": [pattern dicts], "not_detected": [names],
             "verdict": str, "verdict_kind": "good"/"bad"/"neutral"}.
    Only the stronger side (bullish vs bearish) is reported, plus any
    neutral signals, so the card never claims 'bullish AND bearish at once'.
    """
    found = _detect_all(df)
    bull = [p for p in found if p["direction"] == "bullish"]
    bear = [p for p in found if p["direction"] == "bearish"]
    neutral = [p for p in found if p["direction"] == "neutral"]
    bull_score = sum(p["strength"] for p in bull)
    bear_score = sum(p["strength"] for p in bear)

    if bull_score > bear_score:
        shown = sorted(bull, key=lambda p: -p["strength"])[:3] + neutral
        verdict = ("📈 Overall chart verdict: leaning BULLISH — the strongest "
                   "shapes on this chart point upward.")
        kind = "good"
    elif bear_score > bull_score:
        shown = sorted(bear, key=lambda p: -p["strength"])[:3] + neutral
        verdict = ("📉 Overall chart verdict: leaning BEARISH — the strongest "
                   "shapes on this chart point downward.")
        kind = "bad"
    elif bull_score > 0:  # equal, non-zero: genuinely mixed — show neither side
        shown = neutral
        verdict = ("⚖️ Overall chart verdict: MIXED — bullish and bearish signals "
                   "cancel out. Best to wait for a clearer picture.")
        kind = "neutral"
    else:
        shown = neutral
        verdict = ("😐 Overall chart verdict: NEUTRAL — no classic pattern is "
                   "clearly present right now. That's normal most of the time.")
        kind = "neutral"

    shown_names = {p["name"] for p in shown}
    not_detected = [n for n in ALL_PATTERN_NAMES if n not in shown_names]
    return {"shown": shown, "not_detected": not_detected,
            "verdict": verdict, "verdict_kind": kind}
