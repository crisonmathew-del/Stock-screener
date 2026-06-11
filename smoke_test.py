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

print("data sanity (the KLAC +1009% class of bug)…")
from data_fetcher import sanitize_history

normal = make_history()
check("normal history untouched", len(sanitize_history(normal)) == len(normal))
big_real_day = make_history(last_day_jump=0.45)  # +45%: rare but possible
check("a real +45% day is kept", len(sanitize_history(big_real_day)) == len(big_real_day))
corrupt = make_history(last_day_jump=10.0)  # +1000%: adjustment glitch
check("an 11x corrupt last bar is dropped",
      len(sanitize_history(corrupt)) == len(corrupt) - 1)
split_like = make_history()
split_like.iloc[-1, split_like.columns.get_loc("Close")] /= 10  # 0.1x glitch
check("a 0.1x corrupt last bar is dropped",
      len(sanitize_history(split_like)) == len(split_like) - 1)
flagged = compute_breakout(big_real_day)
check("±30%+ move sets the verify flag", flagged["suspect_move"] is True)
check("normal move not flagged", compute_breakout(normal)["suspect_move"] is False)

# Hardened cases the first fix missed: a corrupt bar in the MIDDLE (which
# made "% today" insane via a bad PREVIOUS close), and a RUN of bad bars.
mid_spike = make_history()
mid_spike.iloc[-2, mid_spike.columns.get_loc("Close")] *= 11  # bad yesterday
check("corrupt middle bar removed",
      len(sanitize_history(mid_spike)) == len(mid_spike) - 1)
cleaned = sanitize_history(mid_spike)
r_last = cleaned["Close"].iloc[-1] / cleaned["Close"].iloc[-2]
check("pct today sane after middle-bar cleanup", 0.5 < r_last < 2)
run_bad = make_history()
for k in (1, 2, 3):
    run_bad.iloc[-k, run_bad.columns.get_loc("Close")] *= 12
check("a run of 3 corrupt trailing bars all dropped",
      len(sanitize_history(run_bad)) == len(run_bad) - 3)

print("verdict…")
from tab_analysis import compute_verdict

green = compute_verdict(minervini_passed=7, score=80, vol_ratio=2.0,
                        pct_today=3.0, rsi=62, extended=False,
                        backdrop="positive", days_to_earnings=30)
check("all-positive case is green", green["level"] == "green")
check("green names its drivers", len(green["drivers"]) >= 3)

earn = compute_verdict(minervini_passed=7, score=80, vol_ratio=2.0,
                       pct_today=3.0, rsi=62, extended=False,
                       backdrop="positive", days_to_earnings=3)
check("imminent earnings forces verdict below green", earn["level"] != "green")
check("earnings is the lead risk", "earnings" in earn["risks"][0])

spike_v = compute_verdict(minervini_passed=7, score=75, vol_ratio=3.0,
                          pct_today=12.0, rsi=85, extended=True,
                          backdrop="positive", days_to_earnings=30)
check("heavy overextension forces verdict below green",
      spike_v["level"] != "green")

weak = compute_verdict(minervini_passed=2, score=20, vol_ratio=0.8,
                       pct_today=-9.0, rsi=80, extended=True,
                       backdrop="negative", days_to_earnings=4)
check("mostly-negative case is red", weak["level"] == "red")
mixed = compute_verdict(minervini_passed=None, score=55, vol_ratio=1.0,
                        pct_today=1.0, rsi=60, extended=False,
                        backdrop="neutral", days_to_earnings=None)
check("middling case is amber", mixed["level"] == "amber")
for v in (green, earn, spike_v, weak, mixed):
    check("verdict always has a risk or driver",
          v["drivers"] or v["risks"])

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
