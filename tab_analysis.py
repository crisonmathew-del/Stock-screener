"""
TAB 2 — "Analyse a Specific Stock": the full deep-dive on one ticker.

Reading order (top to bottom):
  A) Quick Summary — the whole story in plain English
  A2) Verdict — ONE clear, colour-coded read on the setup right now
  B) Earnings warning — if results are due soon, you need to know FIRST
  C) Price block — live price, today's move, 52-week range
  D) Interactive chart — candles, moving averages, support/resistance, Fibonacci
  E) Breakout score breakdown — exactly where every point came from
  F) Fibonacci & support/resistance tables
  G) Risk management — stop-loss suggestion + position-size calculator
  H) Chart pattern analysis (informational)
  I) Market context — are the market and the sector helping or hurting today?

Every number in the summary (A) is read from the SAME calculations as the
detailed sections below it, so the summary can never contradict the details.
"""

import math

import numpy as np
import pandas as pd
import streamlit as st


from breakout_score import compute_breakout
from data_fetcher import (fetch_stock, fetch_quotes,
                          clear_all_caches, EASTERN, UK)
from minervini import evaluate_trend_template
from indicators import (fibonacci_levels, support_resistance, swing_low,
                        range_position, range_position_label)
from patterns import detect_patterns
from price_chart import detect_chart_events, build_price_chart
from ui_helpers import (money, pct, card, badge, freshness_banner,
                        sanity_check_price_move, glossary_expander)
from watchlist import (SECTOR_ETFS, DEFAULT_MARKET_ETF, sector_of,
                       ticker_options, option_label, ticker_from_option)


def render():
    st.header("📊 Analyse a Specific Stock")

    # "← Back" appears when the user arrived here by clicking a scan result.
    came_from = st.session_state.get("came_from")
    if came_from:
        def _go_back():
            st.session_state["nav_target"] = came_from
            st.session_state["came_from"] = None
        st.button("← Back to scan results", on_click=_go_back)

    # A clicked scan row requests a ticker via "analyse_target" — load it
    # into the search box BEFORE the widget is created (Streamlit's rule).
    if "analyse_target" in st.session_state:
        st.session_state["stock_search"] = option_label(
            st.session_state.pop("analyse_target"))
    st.session_state.setdefault("stock_search", option_label("AAPL"))

    # Type-ahead search: suggestions appear as you type (matching ticker OR
    # company name), and any other US ticker can be typed in free-form.
    choice = st.selectbox(
        "Search for a stock — type a ticker (AAPL) or a company name (Apple):",
        options=ticker_options(),
        key="stock_search",
        accept_new_options=True,
        placeholder="Start typing… e.g. NVDA or Nvidia",
        help="Suggestions cover the scanner's watchlist. For any other US "
             "stock, just type its ticker (find tickers on finance.yahoo.com) "
             "and press Enter.",
    )
    ticker = ticker_from_option(choice)

    glossary_expander()
    if not ticker:
        st.info("Start typing above to find a stock — for example **AAPL** "
                "(Apple).")
        return

    with st.spinner(f"Downloading data for {ticker}…"):
        data = fetch_stock(ticker)

    if data is None:
        st.error(f"😕 Couldn't find data for **{ticker}**. Double-check the "
                 "spelling (e.g. GOOGL, not GOOGLE) — you can look tickers up "
                 "on finance.yahoo.com. If the ticker is definitely right, "
                 "Yahoo may be rate-limiting; wait a minute and try again.")
        return

    hist, info = data["hist"], data["info"]
    breakout = compute_breakout(hist)
    if breakout is None:
        st.warning(f"**{ticker}** doesn't have enough trading history yet "
                   "(at least ~3 months is needed) to analyse properly.")
        return

    # ------------------------------------------------------------------
    # ONE set of numbers for the whole page (summary + details share these)
    # ------------------------------------------------------------------
    price = float(info["current_price"] or breakout["price"])
    prev_close = info["previous_close"] or breakout["prev_close"]
    # Yahoo's live quote is a SEPARATE feed from the price history and can be
    # on a different split-adjustment basis (the source of impossible numbers
    # like +1009%). If the quote disagrees wildly with the cleaned history,
    # trust the history — it has been sanity-checked, the quote hasn't.
    if not (1 / 3 < price / breakout["price"] < 3):
        price = breakout["price"]
    if (not prev_close or not (1 / 3 < prev_close / breakout["prev_close"] < 3)
            or not (1 / 3 < price / prev_close < 3)):
        prev_close = breakout["prev_close"]
    pct_today = ((price - prev_close) / prev_close * 100) if prev_close else None
    # Prefer Yahoo's own intraday 52-week extremes (matches Yahoo/CNBC);
    # fall back to ones computed from the downloaded history.
    low52 = float(info["low52"] or breakout["low52"])
    high52 = float(info["high52"] or breakout["high52"])
    pos = range_position(price, low52, high52)
    pos_label = range_position_label(pos)
    fib = fibonacci_levels(hist)          # same numbers feed chart AND table
    levels = support_resistance(hist)     # same numbers feed chart AND table
    pattern_report = detect_patterns(hist)
    earnings_date = data["next_earnings"]
    days_to_earnings = ((earnings_date - pd.Timestamp.now(tz=EASTERN).date()).days
                        if earnings_date else None)
    company = info["name"]

    # ------------------------------------------------------------------
    # A) QUICK SUMMARY — plain English, all from the numbers above
    # ------------------------------------------------------------------
    _render_summary(ticker, company, breakout, price, pct_today, pos, pos_label,
                    levels, days_to_earnings)

    # ------------------------------------------------------------------
    # A2) VERDICT — one clear, colour-coded read on the setup right now
    # ------------------------------------------------------------------
    _render_verdict(ticker, info, hist, breakout, pct_today, days_to_earnings)

    # ------------------------------------------------------------------
    # B) EARNINGS WARNING — prominent, near the top
    # ------------------------------------------------------------------
    if days_to_earnings is not None and 0 <= days_to_earnings <= 7:
        card(f"⚠️ <b>Earnings due {earnings_date.strftime('%A %d %B %Y')}</b> "
             f"({days_to_earnings} day{'s' if days_to_earnings != 1 else ''} away). "
             "This stock can move sharply up or down overnight regardless of "
             "the chart, and a stop-loss won't protect against an overnight "
             "gap. Many traders avoid opening new positions right before "
             "earnings.", kind="bad")
    elif days_to_earnings is not None and 8 <= days_to_earnings <= 21:
        st.caption(f"🗓 Note: earnings are scheduled for "
                   f"{earnings_date.strftime('%d %B %Y')} "
                   f"(about {days_to_earnings} days away).")

    # ------------------------------------------------------------------
    # C) PRICE BLOCK
    # ------------------------------------------------------------------
    freshness_banner(data["fetched_at"], hist.index[-1])
    sanity_check_price_move(pct_today)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{ticker} price", f"${price:,.2f}",
              f"{pct_today:+.2f}% today" if pct_today is not None else "N/A",
              help="The latest price Yahoo Finance has, and today's change "
                   "vs yesterday's closing price.")
    c2.metric("Previous close", f"${prev_close:,.2f}" if prev_close else "N/A",
              help="Where the stock finished the previous trading day — "
                   "the reference for 'today's change'.")
    extra_label, extra_val = "After-hours / Pre-market", "—"
    if info["post_market"]:
        extra_label, extra_val = "After-hours price", f"${info['post_market']:,.2f}"
    elif info["pre_market"]:
        extra_label, extra_val = "Pre-market price", f"${info['pre_market']:,.2f}"
    c3.metric(extra_label, extra_val,
              help="Trading that happens outside regular 9:30am-4pm ET hours. "
                   "Thinner and jumpier than regular trading.")
    c4.metric("Data as of",
              data["fetched_at"].astimezone(UK).strftime("%I:%M %p UK"),
              help="When this page's data was downloaded from Yahoo Finance "
                   "(shown in UK time).")

    st.markdown(f"**52-week range:** &nbsp; 52-week low: {money(low52)} — "
                f"52-week high: {money(high52)}")
    if pos is not None and not np.isnan(pos):
        st.markdown(f"Right now the price sits **{pos * 100:.0f}% of the way up** "
                    f"that range — in plain terms, it is **{pos_label}**.")

    # ------------------------------------------------------------------
    # D) CHART (interactive: zoom, pan, range buttons, event markers)
    # ------------------------------------------------------------------
    st.subheader("📉 Interactive price chart")
    chart_events = detect_chart_events(hist)
    st.plotly_chart(
        build_price_chart(ticker, hist, fib, levels, chart_events),
        width="stretch",
        config={"scrollZoom": True, "displaylogo": False},
    )
    st.caption("Drag to pan, scroll to zoom, or use the 1M/3M/6M/YTD/1Y "
               "buttons and the slider underneath. Click a legend entry to "
               "hide or show a line or a marker group. Hover any candle or "
               "marker for the detail.")

    # Plain-English recap of the markers, most recent first
    if chart_events:
        recent = list(reversed(chart_events[-4:]))
        st.markdown("**Most recent events on this chart:** "
                    + "; ".join(f"{e['date'].strftime('%d %b %Y')} — {e['label']}"
                                for e in recent) + ".")
    else:
        st.markdown("**Most recent events on this chart:** none detected in "
                    "the charted period — a quiet chart is normal.")
    card("🏷 The markers show technical events that have <b>already "
         "happened</b> — they are <b>NOT</b> buy or sell signals. Indicators "
         "describe the past and often get the future wrong. Use them to "
         "understand what the chart is doing, then decide for yourself.",
         kind="neutral")
    st.markdown("*Use this chart to visually confirm the patterns described "
                "below before acting. Solid lines are support/resistance; "
                "dashed lines are Fibonacci levels.*")

    # ------------------------------------------------------------------
    # E) BREAKOUT SCORE BREAKDOWN
    # ------------------------------------------------------------------
    st.subheader(f"🧮 Breakout score: {breakout['score']} / 100")
    badge(breakout["verdict"],
          "good" if breakout["score"] >= 70 else
          "warn" if breakout["score"] >= 45 else "bad")
    st.markdown(f"**Entry quality:** {breakout['entry_note']}")

    cols = st.columns(len(breakout["components"]))
    for col, (name, comp) in zip(cols, breakout["components"].items()):
        with col:
            earned_most = comp["points"] >= comp["max"] * 0.6
            icon = "✅" if earned_most else ("➖" if comp["points"] > 0 else "❌")
            card(f"<b>{icon} {name}</b><br>"
                 f"<span style='font-size:1.3rem;font-weight:700;'>"
                 f"{comp['points']} / {comp['max']}</span><br>"
                 f"<small>{comp['detail']}</small>",
                 kind="good" if earned_most else
                      ("warn" if comp["points"] > 0 else "neutral"))

    adjustments = []
    if breakout["bonus"]:
        adjustments.append(f"➕ {breakout['bonus']} bonus (within 3% of the "
                           "52-week high — no overhead resistance)")
    if breakout["penalty"]:
        adjustments.append(f"➖ {breakout['penalty']} penalty (extended move "
                           "and/or overbought RSI)")
    if adjustments:
        st.markdown("**Adjustments:** " + " · ".join(adjustments))
    for flag in breakout["flags"]:
        st.markdown(f"- ⚠️ {flag}")

    # ------------------------------------------------------------------
    # F) FIBONACCI & SUPPORT/RESISTANCE
    # ------------------------------------------------------------------
    st.subheader("📐 Key price levels")
    st.markdown("These are the exact levels drawn on the chart above — the "
                "table and the chart always use the same lookback windows, so "
                "they can never disagree.")
    fcol, scol = st.columns(2)
    with fcol:
        st.markdown(f"**Fibonacci retracements** *(from the "
                    f"{fib['lookback']}-day swing: high {money(fib['swing_high'])}, "
                    f"low {money(fib['swing_low'])})*")
        for name, lvl in fib["levels"].items():
            near = abs(price - lvl) / price <= 0.02
            note = " ← **price is within 2% of this level now**" if near else ""
            st.markdown(f"- {name}: {money(lvl)}{note}")
        st.caption("Traders watch these as natural 'pause points' when a "
                   "stock pulls back after a run.")
    with scol:
        st.markdown("**Support (floors) & resistance (ceilings)**")
        st.markdown(f"- Support, 30-day lookback: {money(levels[30]['support'])}")
        st.markdown(f"- Support, 90-day lookback: {money(levels[90]['support'])}")
        st.markdown(f"- Resistance, 30-day lookback: {money(levels[30]['resistance'])}")
        st.markdown(f"- Resistance, 90-day lookback: {money(levels[90]['resistance'])}")
        st.caption("Support = where buyers stepped in before. Resistance = "
                   "where sellers showed up before. A 'breakout' clears "
                   "resistance; after that, the old ceiling often becomes the "
                   "new floor.")

    # ------------------------------------------------------------------
    # G) RISK MANAGEMENT
    # ------------------------------------------------------------------
    st.subheader("🛡️ Risk management")
    stop = min(swing_low(hist, 10), price * 0.93)
    stop_dist = (price - stop) / price * 100
    st.markdown(
        f"**Suggested stop-loss: {money(stop)}** ({stop_dist:.1f}% below the "
        "current price) — the lower of the last 10 days' lowest price and 7% "
        "below the current price. A stop-loss is a pre-decided 'I was wrong' "
        "exit: if the stock falls there, you sell and take a small loss "
        "instead of riding it down.")

    st.markdown("**Position-size calculator** — how many shares can you buy "
                "while keeping the worst-case loss small?")
    r1, r2 = st.columns(2)
    with r1:
        account = st.number_input(
            "Your account size ($)", min_value=100.0, value=10_000.0,
            step=500.0,
            help="The total money in your trading account.")
    with r2:
        risk_pct = st.number_input(
            "Max risk per trade (%)", min_value=0.1, max_value=10.0,
            value=1.0, step=0.5,
            help="The slice of your account you're willing to LOSE if the "
                 "stop-loss is hit. Professionals typically risk 1-2%.")

    risk_dollars = account * risk_pct / 100
    per_share_risk = price - stop
    if per_share_risk <= 0:
        st.info("The stop-loss is at or above the current price (this can "
                "happen after a sharp drop) — the calculator needs a stop "
                "below the price to size a position.")
    else:
        shares = math.floor(risk_dollars / per_share_risk)
        position_value = shares * price
        if shares == 0:
            st.info("At this account size and risk %, even 1 share risks more "
                    "than your limit. That's the calculator protecting you — "
                    "this stock is too expensive/volatile for this account "
                    "size, not a number to override.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Shares to buy", f"{shares:,}")
            k2.metric("Dollars at risk if stopped out", f"${risk_dollars:,.0f}")
            k3.metric("Position as % of account",
                      f"{position_value / account * 100:.1f}%")
            st.markdown(f"That's a position of about {money(position_value)}. "
                        f"If the stop at {money(stop)} is hit, you lose roughly "
                        f"{money(risk_dollars, 0)} — and live to trade another day.")
    card("💡 Risking only 1-2% per trade is how traders survive losing "
         "streaks. Even a great strategy loses 4-5 times in a row sometimes; "
         "at 1% risk that's a scratch, at 20% risk it's game over.",
         kind="neutral")

    # ------------------------------------------------------------------
    # H) TECHNICAL CHART ANALYSIS (informational — not part of the score)
    # ------------------------------------------------------------------
    st.subheader("📊 Technical chart analysis")
    st.markdown("*Informational only — these pattern checks do not change the "
                "breakout score.*")
    kind = {"good": "good", "bad": "bad", "neutral": "neutral"}[
        pattern_report["verdict_kind"]]
    card(f"<b>{pattern_report['verdict']}</b>", kind=kind)

    if pattern_report["shown"]:
        for p in pattern_report["shown"]:
            arrow = {"bullish": "📈", "bearish": "📉", "neutral": "⚖️"}[p["direction"]]
            st.markdown(f"**{arrow} {p['name']} — detected.** {p['sentence']}")
    else:
        st.markdown("No classic chart pattern is clearly present right now — "
                    "which is the normal state of most charts most of the time.")
    with st.expander("Patterns checked but not detected"):
        st.markdown(", ".join(pattern_report["not_detected"]) or "—")
    st.caption("Pattern detection is automated and approximate. Always "
               "visually confirm on the chart. This is not financial advice.")

    # ------------------------------------------------------------------
    # I) MARKET CONTEXT (informational — not part of the score)
    # ------------------------------------------------------------------
    st.subheader("🌍 Market context check")
    st.markdown("*Even a great stock struggles to rise on a day the whole "
                "market is falling — always glance at the weather before "
                "setting sail. Informational only; not part of the score.*")
    _render_market_context(ticker, info)

    if st.button("🔄 Refresh this stock's data"):
        clear_all_caches()
        st.rerun()


# ==========================================================================
# Helper renderers
# ==========================================================================

def _trend_phrase(breakout):
    """A trend description GUARANTEED to agree with the moving-average facts
    (the summary must never say 'uptrend' while the 50-day is below the
    200-day)."""
    price, ma50, ma200 = breakout["price"], breakout["ma50"], breakout["ma200"]
    if np.isnan(ma200):
        return ("too new to judge the long-term trend (less than a year of "
                "trading history)")
    if ma50 > ma200:
        if price > ma50:
            return "in a confirmed uptrend (price above the 50-day average, which is above the 200-day)"
        return ("in a longer-term uptrend but currently pulling back below "
                "its 50-day average")
    if price > ma50:
        return ("bouncing short-term, but still in a longer-term downtrend "
                "(the 50-day average remains below the 200-day)")
    return "in a downtrend (price below its 50-day average, which is below the 200-day)"


def _render_summary(ticker, company, b, price, pct_today, pos, pos_label,
                    levels, days_to_earnings):
    """Section A: the beginner-first summary. Reads ONLY values computed by
    the detailed sections, so it can never contradict them."""
    score, verdict = b["score"], b["verdict"]
    trend = _trend_phrase(b)

    # The one-line bottom line
    if score >= 70:
        bottom = (f"{company} ({ticker}) scores <b>{score}/100</b> — a strong "
                  f"breakout setup, and the stock is {trend}.")
    elif score >= 45:
        bottom = (f"{company} ({ticker}) scores <b>{score}/100</b> — momentum "
                  f"is building but the setup isn't complete; the stock is {trend}.")
    else:
        bottom = (f"{company} ({ticker}) scores <b>{score}/100</b> — not a "
                  f"breakout candidate right now; the stock is {trend}.")

    # The 3 most important findings, picked by priority
    candidates = []
    if days_to_earnings is not None and 0 <= days_to_earnings <= 7:
        candidates.append("🗓 <b>Earnings are due within a week</b> — expect "
                          "possible sharp overnight moves (see the warning below).")
    if b["extended"]:
        candidates.append("⚠️ The stock has <b>already run hard recently</b> — "
                          "buying after a big spike is where beginners get hurt.")
    if b["vol_ratio"] >= 1.5:
        candidates.append(f"📦 Trading volume is <b>{b['vol_ratio']:.1f}x its "
                          "normal level</b> — real buying interest, not noise.")
    if b["broke_20d_high"]:
        candidates.append("🚀 Price has <b>broken above its 20-day ceiling</b> — "
                          "the core breakout ingredient.")
    if b["near_52wk_high"]:
        candidates.append("🏔 Price is <b>within 3% of its 52-week high</b> — "
                          "no old 'ceiling' of trapped sellers overhead.")
    if b["macd_crossed_up"]:
        candidates.append("📈 MACD just <b>crossed upward</b> — short-term "
                          "momentum is turning positive.")
    candidates.append(f"📊 RSI is <b>{b['rsi']:.0f}</b> — "
                      + ("in the healthy 55-70 zone." if 55 <= b["rsi"] <= 70
                         else "outside the ideal 55-70 zone."))
    candidates.append(f"📏 The long-term picture: the stock is {trend}.")
    findings = candidates[:3]

    # "What to watch" from the SAME support/resistance numbers as section F
    resist = levels[30]["resistance"] if price < levels[30]["resistance"] \
        else levels[90]["resistance"]
    support = levels[30]["support"] if price > levels[30]["support"] \
        else levels[90]["support"]
    watch = (f"👀 <b>What to watch:</b> a clean push above {money(resist)} "
             f"(recent ceiling) would strengthen the case; a drop below "
             f"{money(support)} (recent floor) would weaken it.")

    move_txt = pct(pct_today) if pct_today is not None else "N/A"
    pos_txt = (f"{pos * 100:.0f}% of the way up its 52-week range — {pos_label}"
               if pos is not None and not np.isnan(pos) else "position unknown")

    body = (
        f"<b style='font-size:1.1rem;'>{bottom}</b><br><br>"
        f"<b>Right now:</b> the stock trades at {money(price)} ({move_txt} "
        f"today) and sits {pos_txt}.<br>"
        f"<b>Verdict in one sentence:</b> {verdict.split(' ', 1)[1]} — "
        + ("worth deeper research, but check the entry-quality note before "
           "doing anything." if b['score'] >= 70 else
           "keep it on a watchlist and wait for the setup to complete."
           if b['score'] >= 45 else
           "the ingredients of a breakout simply aren't here today.")
        + "<br><br><b>The 3 most important things:</b><br>"
        + "<br>".join(f"&nbsp;&nbsp;{f}" for f in findings)
        + f"<br><br>{watch}<br><br>"
        "🛡 <b>Remember:</b> any stock can drop 10%+ on one headline. Never "
        "risk money you can't afford to lose, and decide your exit before "
        "you enter — the risk section below does the maths for you.<br><br>"
        "<i>↓ Scroll down for the full breakdown.</i>"
    )
    kind = "good" if score >= 70 else "warn" if score >= 45 else "neutral"
    card(body, kind=kind, title=f"📋 Quick summary — {company} ({ticker})")


def _render_market_context(ticker, info):
    """Section I: index futures + the stock's sector ETF."""
    sector = info.get("sector") or sector_of(ticker)
    # Yahoo calls Consumer Cyclical "Consumer Cyclical"; map either wording
    etf = SECTOR_ETFS.get(sector, DEFAULT_MARKET_ETF)
    symbols = ("ES=F", "NQ=F", etf)
    quotes, fetched = fetch_quotes(symbols)

    if not quotes:
        st.info("Couldn't fetch market-context data right now — try the "
                "Refresh button in a minute.")
        return

    labels = {
        "ES=F": "S&P 500 futures",
        "NQ=F": "Nasdaq futures",
        etf: f"{sector or 'Market'} sector ETF ({etf})",
    }
    cols = st.columns(3)
    for col, sym in zip(cols, symbols):
        q = quotes.get(sym)
        with col:
            if q is None:
                st.metric(labels[sym], "N/A")
            else:
                st.metric(labels[sym], f"{q['price']:,.2f}",
                          pct(q["pct_change"]),
                          help=f"As of {q['as_of'].strftime('%d %b %Y')} "
                               "(daily data, may lag a few minutes).")

    es = quotes.get("ES=F", {}).get("pct_change")
    nq = quotes.get("NQ=F", {}).get("pct_change")
    if es is not None and nq is not None:
        if es >= 0.5 and nq >= 0.5:
            card("✅ <b>Market tailwind:</b> both S&P and Nasdaq futures are up "
                 "more than 0.5% — a rising tide that helps individual "
                 "breakouts succeed.", kind="good")
        elif es <= -0.5 or nq <= -0.5:
            card("❌ <b>Market headwind:</b> index futures are down more than "
                 "0.5% — even strong setups often fail on red market days. "
                 "Extra caution warranted.", kind="bad")
        else:
            card("⚠️ <b>Neutral market:</b> futures are roughly flat (within "
                 "±0.5%) — the market is neither helping nor hurting today.",
                 kind="warn")

    sec_q = quotes.get(etf)
    if sec_q and sec_q.get("pct_change") is not None:
        direction = ("rising" if sec_q["pct_change"] > 0.2 else
                     "falling" if sec_q["pct_change"] < -0.2 else "flat")
        st.markdown(f"**Sector check:** {labels[etf]} is {direction} "
                    f"({pct(sec_q['pct_change'])}) — stocks tend to move with "
                    "their sector 'neighbourhood'.")

    with st.expander("❓ What are futures, and why do they matter?"):
        st.markdown(
            "**Futures** are contracts that track where traders think an index "
            "(like the S&P 500) is heading. They trade almost around the "
            "clock, so before and during the market day they act as a live "
            "mood ring for the whole market. If futures are deeply red, most "
            "stocks — including great breakout setups — will struggle that "
            "day. Checking them takes five seconds and saves a lot of pain.")




# ==========================================================================
# The Verdict section: one clear, colour-coded read on the current setup
# ==========================================================================

def compute_verdict(minervini_passed, score, vol_ratio, pct_today, rsi,
                    extended, backdrop, days_to_earnings):
    """Combine the six checks into ONE verdict. Pure logic, no UI, so it's
    easy to test. Returns {"level": green/amber/red, "drivers", "risks"}.

    The factors and their weights (positives push up, negatives pull down):
      * Long-term trend passes the Minervini Trend Template -> strong positive
      * Breakout score >=70 positive / 45-69 mild positive / <45 negative
      * Volume today >=1.5x average -> positive
      * Not over-extended (not up >8% today, RSI <78) -> positive, else a
        STRONG negative
      * Market backdrop positive/neutral/negative
      * Earnings more than 7 days away -> positive; within 7 days -> a
        STRONG negative
    A strong negative always forces the verdict down to amber or red —
    never green with a major risk on the table.
    """
    drivers, risks = [], []
    total, negatives, strong_neg = 0, 0, False

    # 1. Long-term trend (Minervini Trend Template)
    if minervini_passed == 7:
        total += 2
        drivers.append("in a confirmed long-term uptrend — it passes all 7 "
                       "Minervini trend rules")
    elif minervini_passed == 6:
        total += 1
        drivers.append("close to a confirmed long-term uptrend (6 of 7 "
                       "trend rules)")
    else:
        risks.append("the long-term trend isn't confirmed")

    # 2. Breakout score
    if score >= 70:
        total += 2
        drivers.append(f"showing a strong breakout setup (score {score}/100)")
    elif score >= 45:
        total += 1
        drivers.append(f"building momentum (score {score}/100)")
    else:
        total -= 2
        negatives += 1
        risks.append(f"the breakout ingredients just aren't there today "
                     f"(score {score}/100)")

    # 3. Volume
    if vol_ratio >= 1.5:
        total += 1
        drivers.append(f"trading on heavy volume ({vol_ratio:.1f}x normal)")

    # 4. Over-extension (chase guard)
    over_today = pct_today is not None and pct_today > 8
    if not over_today and rsi < 78 and not extended:
        total += 1
        drivers.append("not over-extended — it hasn't already run away")
    else:
        total -= 2
        negatives += 1
        strong_neg = True
        if over_today:
            risks.append(f"it's already up {pct_today:.0f}% today — buying "
                         "after a spike is where beginners get hurt")
        elif rsi >= 78:
            risks.append(f"RSI is {rsi:.0f} (overheated) — late entries "
                         "usually meet a pullback")
        else:
            risks.append("it has already run hard over the past two weeks")

    # 5. Market backdrop (futures + sector)
    if backdrop == "positive":
        total += 1
        drivers.append("the broader market is rising today")
    elif backdrop == "negative":
        total -= 1
        negatives += 1
        risks.append("the broader market is falling today — even good "
                     "setups struggle on red days")

    # 6. Earnings timing
    if days_to_earnings is not None and 0 <= days_to_earnings <= 7:
        total -= 2
        negatives += 1
        strong_neg = True
        risks.insert(0, f"earnings are due in {days_to_earnings} "
                        f"day{'s' if days_to_earnings != 1 else ''} — "
                        "overnight gaps jump straight past stop-losses")
    else:
        total += 1  # clear of the earnings minefield (or no date known)

    if total >= 5 and negatives == 0 and not strong_neg:
        level = "green"
    elif total <= 0 or (strong_neg and total <= 2):
        level = "red"
    else:
        level = "amber"
    return {"level": level, "drivers": drivers, "risks": risks, "total": total}


def _market_backdrop(ticker, info):
    """positive / neutral / negative — same data the Market Context section
    shows (cached, so this costs nothing extra). Unknown -> neutral."""
    sector = info.get("sector") or sector_of(ticker)
    etf = SECTOR_ETFS.get(sector, DEFAULT_MARKET_ETF)
    quotes, _ = fetch_quotes(("ES=F", "NQ=F", etf))
    es = quotes.get("ES=F", {}).get("pct_change")
    nq = quotes.get("NQ=F", {}).get("pct_change")
    sec = quotes.get(etf, {}).get("pct_change")
    if es is None or nq is None:
        return "neutral"
    if es >= 0.5 and nq >= 0.5:
        # strong futures, but a falling sector makes it mixed, not positive
        return "neutral" if (sec is not None and sec <= -0.3) else "positive"
    if es <= -0.5 or nq <= -0.5 or (sec is not None and sec <= -0.5):
        return "negative"
    return "neutral"


def _render_verdict(ticker, info, hist, breakout, pct_today, days_to_earnings):
    """Section A2: the big colour-coded banner + why + main risk."""
    st.subheader("🎯 Verdict")
    trend = evaluate_trend_template(hist)
    v = compute_verdict(
        minervini_passed=trend["passed"] if trend else None,
        score=breakout["score"],
        vol_ratio=breakout["vol_ratio"],
        pct_today=pct_today,
        rsi=breakout["rsi"],
        extended=breakout["extended"],
        backdrop=_market_backdrop(ticker, info),
        days_to_earnings=days_to_earnings,
    )

    banner = {
        "green": ("🟢 Strong setup — worth a closer look", "good"),
        "amber": ("🟡 Mixed — proceed with caution", "warn"),
        "red":   ("🔴 Weak setup — not favourable right now", "bad"),
    }[v["level"]]
    card(f"<span style='font-size:1.35rem;font-weight:800;'>{banner[0]}</span>",
         kind=banner[1])

    # 2-3 plain sentences: the WHY (drivers) and the MAIN RISK
    def join3(items):
        items = items[:3]
        return (items[0] if len(items) == 1
                else ", ".join(items[:-1]) + " and " + items[-1])

    if v["level"] == "green":
        why = (f"This stock is {join3(v['drivers'])} — that's why this "
               "looks favourable.")
    elif v["drivers"]:
        why = (f"In its favour, the stock is {join3(v['drivers'])}. But the "
               "picture is not one-sided.")
    else:
        why = "Very little is working in this stock's favour right now."
    risk = (f"**Main risk:** {v['risks'][0]}." if v["risks"] else
            "**Main risk:** none specific today beyond the usual — any "
            "stock can drop 10%+ on a single headline.")
    st.markdown(f"{why} {risk}")

    st.markdown("*This is the tool's read on the current setup — not a "
                "promise the stock will rise, and not financial advice. A 🟢 "
                "setup can still lose; a 🔴 can still rise. It describes "
                "conditions now, not the future. Verify, and use the risk "
                "section to size your trade.*")
