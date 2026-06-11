"""Quick offline sanity check (no internet needed): feeds synthetic price
data through every calculation module and checks the outputs make sense.
Run with:  python smoke_test.py
"""

import numpy as np
import pandas as pd

from breakout_score import compute_breakout, verdict_for, entry_note
from indicators import (rsi, macd, fibonacci_levels, support_resistance,
                        range_position, range_position_label)
from minervini import evaluate_trend_template, relative_strength_ranks
from patterns import detect_patterns


def make_history(days=500, drift=0.0005, vol=0.015, seed=1, last_day_jump=0.0,
                 last_day_volume_mult=1.0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, days)
    close = 50 * np.exp(np.cumsum(rets))
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


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    assert cond, name


print("indicators…")
df = make_history()
r = rsi(df["Close"]).iloc[-1]
check("RSI in 0-100", 0 <= r <= 100)
m, s = macd(df["Close"])
check("MACD computes", np.isfinite(m.iloc[-1]) and np.isfinite(s.iloc[-1]))
fib = fibonacci_levels(df)
check("fib levels ordered", fib["swing_low"] <= fib["levels"]["61.8%"]
      <= fib["levels"]["23.6%"] <= fib["swing_high"])
sr = support_resistance(df)
check("90d range contains 30d range",
      sr[90]["support"] <= sr[30]["support"] and
      sr[90]["resistance"] >= sr[30]["resistance"])
check("range position label", range_position_label(range_position(75, 50, 100))
      == "in the middle of its 52-week range")

print("breakout score…")
quiet = compute_breakout(make_history())
check("quiet stock scores", quiet is not None and 0 <= quiet["score"] <= 100)
breakout = compute_breakout(make_history(drift=0.001, last_day_jump=0.04,
                                         last_day_volume_mult=3.5))
check("breakout day scores higher", breakout["score"] > quiet["score"])
check("volume component maxed", breakout["components"]["Volume surge"]["points"] == 30)
spike = compute_breakout(make_history(drift=0.001, last_day_jump=0.12,
                                      last_day_volume_mult=3.5))
check("9%+ spike flagged extended", spike["extended"])
check(">8% day momentum cut", spike["components"]["Price momentum"]["points"]
      <= breakout["components"]["Price momentum"]["points"])
check("verdict bands", verdict_for(80).startswith("🟢")
      and verdict_for(50).startswith("🟡") and verdict_for(20).startswith("🔴"))
check("entry note extended", "Extended" in entry_note(60, 1.0, 80, True)
      or "Overbought" in entry_note(60, 1.0, 80, True))
short = compute_breakout(make_history(days=30))
check("too-short history returns None", short is None)

print("minervini…")
up = evaluate_trend_template(make_history(drift=0.002, vol=0.01))
down = evaluate_trend_template(make_history(drift=-0.002, vol=0.01))
check("uptrend passes 7/7", up is not None and up["passed"] == 7)
check("downtrend fails", down is not None and down["passed"] <= 3)
check("young stock skipped", evaluate_trend_template(make_history(days=100)) is None)
ranks = relative_strength_ranks({
    "UP": make_history(drift=0.003, vol=0.004, seed=2),
    "FLAT": make_history(drift=0.0, vol=0.004, seed=3),
    "DOWN": make_history(drift=-0.003, vol=0.004, seed=4),
})
check("RS ranks ordered", ranks["UP"] > ranks["FLAT"] > ranks["DOWN"])
check("RS ranks in 1-100", all(1 <= v <= 100 for v in ranks.values()))

print("price chart…")
from price_chart import detect_chart_events, build_price_chart, EVENT_TYPES
from indicators import fibonacci_levels as _fib, support_resistance as _sr

busy = make_history(drift=0.001, last_day_jump=0.04, last_day_volume_mult=3.5)
events = detect_chart_events(busy)
check("events detected on a busy chart", len(events) > 0)
check("event types are all known", all(e["type"] in EVENT_TYPES for e in events))
check("events sorted by date", all(a["date"] <= b["date"]
                                   for a, b in zip(events, events[1:])))
check("volume spike marked on jump day",
      any(e["type"] in ("volume_spike", "breakout")
          and e["date"] == busy.index[-1] for e in events))
import re
check("no buy/sell wording in labels/hovers",  # whole words only: "sellers" in prose is fine
      not any(re.search(r"\b(buy|sell)\b", (e["label"] + " " + e["hover"]).lower())
              for e in events))
fig = build_price_chart("TEST", busy, _fib(busy), _sr(busy), events)
check("figure builds with traces", len(fig.data) >= 5)
check("range buttons present",
      len(fig.layout.xaxis.rangeselector.buttons) == 5)
check("range slider present", fig.layout.xaxis2.rangeslider.visible is True)
check("no dollar signs in chart annotations (LaTeX guard)",
      all("$" not in (a.text or "") for a in fig.layout.annotations))
check("short history yields no events", detect_chart_events(make_history(days=30)) == [])

# Regression: a cross is a one-day event. Build a price path whose 50-day MA
# crosses the 200-day exactly once (long decline, then a strong rally) and
# make sure exactly ONE golden cross is reported — not one per day.
trend = np.r_[np.linspace(140, 80, 280), np.linspace(80, 150, 120)]
one_cross = pd.DataFrame({
    "Open": trend, "High": trend * 1.005, "Low": trend * 0.995,
    "Close": trend, "Volume": np.full(400, 1_500_000.0),
}, index=pd.bdate_range(end=pd.Timestamp.today(), periods=400))
golden = [e for e in detect_chart_events(one_cross) if e["type"] == "golden_cross"]
check("single MA cross -> exactly one golden-cross event", len(golden) == 1)
for t in ("golden_cross", "death_cross", "macd_up", "macd_down"):
    dts = sorted(e["date"] for e in events if e["type"] == t)
    adjacent = any((b - a).days <= 1 for a, b in zip(dts, dts[1:]))
    check(f"no {t} events on adjacent days", not adjacent)

print("patterns…")
rep = detect_patterns(make_history())
check("pattern report shape", {"shown", "not_detected", "verdict",
                               "verdict_kind"} <= set(rep))
dirs = {p["direction"] for p in rep["shown"]}
check("no bull+bear contradiction", not ({"bullish", "bearish"} <= dirs))
rep2 = detect_patterns(make_history(drift=0.001, last_day_jump=0.05,
                                    last_day_volume_mult=3.0))
check("verdict always present", bool(rep2["verdict"]))

print("\nAll checks passed ✔")
