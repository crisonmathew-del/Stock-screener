# 📈 Plain-English Stock Screener

A free, browser-based tool that scans US stocks (NYSE/Nasdaq) for potential
**breakout setups** and explains everything it finds in plain English —
built for people with **no trading experience**.

> ⚠️ **Educational and research purposes only. Not financial advice.**
> A high score is a reason to research further, never a signal to buy.
> Always verify live data against a second source and manage your risk.

---

## What can it do?

The app has three tabs:

| Tab | What it does | When to use it |
|---|---|---|
| 🔍 **Find Breakout Stocks (Scanner)** | Scans 170+ US stocks and scores each 0–100 on how closely it matches a classic short-term *breakout setup* (price pushing through a ceiling on heavy volume). | "Show me what's moving **today**." |
| 📊 **Analyse a Specific Stock** | A full deep-dive on any ticker: plain-English summary, earnings warning, interactive chart, score breakdown, key price levels, a stop-loss & position-size calculator, chart-pattern detection and a market-context check. | "Tell me everything about **this** stock." |
| 📈 **Trend Template (Minervini)** | A strict 7-rule **long-term trend filter** (Mark Minervini's Trend Template). Shows only stocks already in confirmed, established uptrends. | "What's worth watching over **months**, not days?" |

A good workflow: use the **Trend Template** to find *what* to watch, then the
**Scanner** to time *when* a setup is forming, then **Analyse** before doing
anything — and read the risk section last, always.

---

## Getting started (10 minutes, no experience needed)

### 1. Install Python
You need Python **3.10 or newer**. Check with:

```bash
python3 --version
```

If you don't have it, download it from [python.org/downloads](https://www.python.org/downloads/).

### 2. Download this project

```bash
git clone https://github.com/crisonmathew-del/stock-screener.git
cd stock-screener
```

(Or click the green **Code → Download ZIP** button on GitHub and unzip it.)

### 3. Install the libraries

```bash
python3 -m venv venv                 # create an isolated environment (recommended)
source venv/bin/activate             # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

Your browser opens automatically at `http://localhost:8501`. That's it —
no API keys, no accounts, no payment. Data comes free from Yahoo Finance.

> 🕐 **The very first scan takes about a minute** — it downloads ~2 years of
> price history for every stock on the watchlist. After that, everything is
> cached and instant. Data refreshes automatically every 5–10 minutes, or
> press a **🔄 Refresh data** button any time.

---

## Understanding the breakout score (Tab 1)

Each stock gets 0–100 points across five categories:

| Category | Points | What it measures |
|---|---|---|
| **Volume surge** | 30 | Is today's trading volume unusually heavy (1.2×–3×+ the 20-day average)? Heavy volume = real buying interest. |
| **Price momentum** | 25 | Is price breaking above its 20-day high? Is today a healthy up-day (the sweet spot is +2–5%, *not* a huge spike)? |
| **Trend confirmation** | 20 | Is price above its 20-day and 50-day averages? Is the 50-day above the 200-day? |
| **Consolidation → expansion** | 15 | Did the stock trade quietly (a tight range) and is it now expanding *upward*? This is the classic breakout signature. |
| **RSI & MACD** | 10 | Is momentum strong but not overheated (RSI 55–70)? Did MACD just cross upward? |

Plus three honesty mechanisms that protect you from **chasing**:

* **Chase guard** — a stock up more than 8% today, +20% in 5 days, or +35%
  in 10 days is flagged **Extended** and scored down. The best entries happen
  *early*, not after the elevator already left.
* **Overbought penalty** — RSI above 78 subtracts points.
* **52-week-high bonus** — a stock within 3% of its yearly high gets a small
  bonus, because breakouts to new highs have no "ceiling" of trapped sellers.

**Verdicts:** 🟢 70–100 = strong setup · 🟡 45–69 = building · 🔴 below 45 = not a candidate.
The **Entry quality** column tells you whether *now* is a sensible moment even
for a strong setup.

## The Trend Template rules (Tab 3)

A stock passes only if **all 7** are true: price above the 150- and 200-day
averages · 150-day above 200-day · 200-day rising for a month · 50-day above
both · price above the 50-day · price ≥30% above its 52-week low · price
within 25% of its 52-week high. A toggle loosens this to 6-of-7.

The **Relative Strength rank** column ranks each stock's 6–12 month
performance against the rest of the watchlist (1–100). It approximates IBD's
RS Rating — and it is **not** the RSI momentum gauge, despite the similar name.

---

## Frequently asked questions

**Is the data truly live?**
Yahoo Finance data is free and may be delayed up to ~15 minutes. The app
tells you when markets are closed, when data is stale, and flags any price
that looks like a glitch. Always confirm against your broker before acting.

**Why does a stock score 75 in the morning and 60 in the afternoon?**
Scores are computed from live volume and price, which change all day. That's
a feature: a fading breakout *should* lose points.

**Why doesn't the Trend Template show some famous stock?**
The template is deliberately strict — most stocks fail it most of the time.
Also, stocks with under ~11 months of trading history (recent IPOs) are
skipped because the 200-day rules can't be computed.

**Can I change which stocks are scanned?**
Yes — open `watchlist.py` and add/remove lines. Everything updates automatically.

**It says "Couldn't download market data".**
Usually a brief Yahoo rate-limit or no internet. Wait a minute and press
**🔄 Refresh data**. If it persists, check that `finance.yahoo.com` loads in
your browser.

**Holidays?** Market-hours detection covers weekdays 9:30am–4pm US Eastern.
On a market holiday the app simply shows the last session's prices.

---

## Project layout (for the curious / tinkerers)

```
app.py             ← start here: page setup + the three tabs
watchlist.py       ← the 170+ stocks scanned (edit me!)
data_fetcher.py    ← all Yahoo Finance downloads, caching, market hours
indicators.py      ← the maths: RSI, MACD, moving averages, Fibonacci…
breakout_score.py  ← the 0–100 scoring rules (every threshold documented)
price_chart.py     ← the interactive chart + neutral technical-event markers
patterns.py        ← chart-pattern detection (cup & handle, flags, candles…)
minervini.py       ← the 7-rule Trend Template + relative-strength ranking
tab_scanner.py     ← Tab 1 UI
tab_analysis.py    ← Tab 2 UI (summary, chart, risk calculator…)
tab_minervini.py   ← Tab 3 UI
ui_helpers.py      ← badges, glossary, disclaimers, freshness banners
smoke_test.py      ← offline sanity checks: python smoke_test.py
```

Every file is heavily commented in plain English so you can tweak thresholds,
add indicators or extend the watchlist without being a programmer.

---

## One last reminder

This tool finds *candidates* and teaches *vocabulary*. It cannot see news,
earnings quality, lawsuits, or tomorrow. **Never risk money you can't afford
to lose, decide your exit before you enter, and risk only 1–2% of your
account per trade** — the built-in calculator does that maths for you.
