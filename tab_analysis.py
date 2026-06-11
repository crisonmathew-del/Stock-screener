"""
TAB 2 — "Analyse a Specific Stock": the full deep-dive on one ticker.

Reading order (top to bottom):
  A) Quick Summary — the whole story in plain English
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

import plotly.graph_objects as go

from backtest import STRATEGIES, run_backtest, interpret
from breakout_score import compute_breakout
from data_fetcher import (fetch_stock, fetch_quotes, fetch_backtest_history,
                          clear_all_caches, EASTERN, UK)
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

    # ------------------------------------------------------------------
    # J) STRATEGY BACKTEST (for learning — never advice)
    # ------------------------------------------------------------------
    _render_backtest(ticker)

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


def _render_backtest(ticker):
    """Section J: replay a simple trading rule on this stock's past prices.
    Pure learning tool — every output compares against buy-and-hold and ends
    with an honesty note. Uses its own 5-year data download so nothing else
    on the page changes."""
    st.subheader("📊 Strategy backtest (for learning)")
    st.markdown(
        "This shows you something powerful: **if you had followed a simple "
        "buying-and-selling rule on this stock over the past few years, "
        "would it actually have made money?** Pick a rule below and see the "
        "results. ⚠️ **Important:** this only shows what happened in the "
        "**PAST** on this **one stock**. It does **NOT** predict the future "
        "— a rule that worked before often stops working. This is here to "
        "help you understand how 'signals' really behave, not to give you a "
        "strategy to follow.")

    # ---------------- Controls ----------------
    c1, c2, c3 = st.columns(3)
    with c1:
        strategy_key = st.selectbox(
            "Trading rule to test",
            options=list(STRATEGIES.keys()),
            format_func=lambda k: STRATEGIES[k]["label"],
            key="bt_strategy",
            help="Each rule is a mechanical 'buy when X, sell when Y' "
                 "recipe — no judgement, no emotions, applied to every day "
                 "of past prices.")
    with c2:
        years = st.selectbox("Test period", [1, 2, 3], index=1,
                             format_func=lambda y: f"{y} year{'s' if y > 1 else ''}",
                             key="bt_years",
                             help="How far back to replay the rule.")
    with c3:
        start_cash = st.number_input(
            "Hypothetical starting money ($)", min_value=100.0,
            value=10_000.0, step=1_000.0, key="bt_cash",
            help="Pretend money. The simulation goes all-in on every buy "
                 "and fully out on every sell.")
    st.markdown(f"*{STRATEGIES[strategy_key]['description']}*")

    # ---------------- Data + run ----------------
    bt_hist, _bt_fetched = fetch_backtest_history(ticker)
    if bt_hist is None:
        st.info("😕 Couldn't download the longer price history needed for "
                "backtesting right now — Yahoo may be rate-limiting. Try "
                "again in a minute.")
        return
    result = run_backtest(bt_hist, strategy_key, years, start_cash)
    if result["error"]:
        st.info("ℹ️ " + result["error"])
        return
    if result["note"]:
        st.caption("ℹ️ " + result["note"])
    if result["started_in_market"]:
        st.caption("ℹ️ The rule was already saying 'hold' on the first day "
                   "of this period (its buy signal fired before the window "
                   "began), so the test starts with a buy on day one.")

    yrs_txt = (f"{result['period_years']:.1f} years"
               if result['period_years'] < years - 0.05
               else f"{years} year{'s' if years > 1 else ''}")

    # ---------------- Bottom line first ----------------
    if result["beat_buy_hold"]:
        verdict_txt = "In this case, the rule did <b>BETTER</b> than just holding."
        kind = "good"
    elif abs(result["return_pct"] - result["bh_return_pct"]) < 1:
        verdict_txt = ("In this case, the rule and just holding ended "
                       "<b>about the same</b>.")
        kind = "warn"
    else:
        verdict_txt = "In this case, the rule did <b>WORSE</b> than just holding."
        kind = "warn" if result["return_pct"] > 0 else "bad"
    card(f"Following this rule turned {money(result['starting_cash'], 0)} "
         f"into <b>{money(result['final_value'], 0)}</b> over {yrs_txt} "
         f"({result['return_pct']:+.1f}%). Simply buying and holding the "
         f"stock would have turned it into "
         f"<b>{money(result['bh_value'], 0)}</b> "
         f"({result['bh_return_pct']:+.1f}%). {verdict_txt}", kind=kind)

    # ---------------- Trade summary + drawdown, in plain words ----------------
    if result["n_closed"] == 0 and not result["trades"]:
        st.markdown("**The rule never triggered a single trade** in this "
                    "period — the money sat in cash the whole time.")
    else:
        bits = []
        if result["n_closed"]:
            bits.append(
                f"The rule made **{result['n_closed']} completed "
                f"trade{'s' if result['n_closed'] != 1 else ''}**: "
                f"{result['n_wins']} "
                f"winner{'s' if result['n_wins'] != 1 else ''} and "
                f"{result['n_losses']} "
                f"loser{'s' if result['n_losses'] != 1 else ''}"
                + (f" (a {result['win_rate']:.0f}% win rate)." if
                   result['win_rate'] is not None else "."))
            if result["avg_win_pct"] is not None:
                bits.append(f"The average winning trade made "
                            f"**{result['avg_win_pct']:+.1f}%**"
                            + (f"; the average losing trade lost "
                               f"**{result['avg_loss_pct']:+.1f}%**."
                               if result['avg_loss_pct'] is not None else "."))
        if any(t["open"] for t in result["trades"]):
            bits.append("One position is **still open** at the end of the "
                        "period, valued at the last price.")
        st.markdown(" ".join(bits))

    st.markdown(
        f"**Worst drop (drawdown):** at its lowest point, this strategy was "
        f"**down {abs(result['max_drawdown_pct']):.0f}% from its peak** — "
        f"that's how much patience it would have tested. (For comparison, a "
        f"buy-and-holder's worst drop was "
        f"{abs(result['bh_max_drawdown_pct']):.0f}%.) *Drawdown means how "
        "far your pot fell from its highest value before recovering — the "
        "scariest moment of the journey.*")

    # ---------------- Every trade, colour-coded ----------------
    if result["trades"]:
        rows = []
        for t in result["trades"]:
            icon = "🟢" if t["pct"] > 0 else "🔴"
            rows.append({
                "Bought": t["buy_date"].strftime("%d %b %Y"),
                "Buy price": t["buy_price"],
                "Sold": (t["sell_date"].strftime("%d %b %Y")
                         if not t["open"] else "Still open"),
                "Sell price": t["sell_price"],
                "Result": f"{icon} {t['pct']:+.1f}%",
                "Dollar result": t["dollars"],
            })
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, width="stretch",
            column_config={
                "Buy price": st.column_config.NumberColumn(format="$%.2f"),
                "Sell price": st.column_config.NumberColumn(
                    format="$%.2f",
                    help="For a 'still open' trade this is simply the "
                         "latest price."),
                "Dollar result": st.column_config.NumberColumn(
                    format="$%.0f",
                    help="How much this trade added to or took from the "
                         "pot (the pot compounds from trade to trade)."),
            })

        # ---------------- Where each buy/sell happened ----------------
        closes = result["test_closes"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=closes.index, y=closes, name="Price",
                                 line=dict(color="#455a64", width=1.5),
                                 hovertemplate="%{y:.2f}<extra></extra>"))
        buys = [(t["buy_date"], t["buy_price"]) for t in result["trades"]]
        sells = [(t["sell_date"], t["sell_price"]) for t in result["trades"]
                 if not t["open"]]
        fig.add_trace(go.Scatter(
            x=[d for d, _ in buys], y=[p for _, p in buys],
            mode="markers", name="Bought (in this backtest)",
            marker=dict(symbol="triangle-up", size=11, color="#1565c0",
                        line=dict(color="#ffffff", width=1.5)),
            hovertemplate="Bought at %{y:.2f}<extra></extra>"))
        if sells:
            fig.add_trace(go.Scatter(
                x=[d for d, _ in sells], y=[p for _, p in sells],
                mode="markers", name="Sold (in this backtest)",
                marker=dict(symbol="triangle-down", size=11, color="#6a1b9a",
                            line=dict(color="#ffffff", width=1.5)),
                hovertemplate="Sold at %{y:.2f}<extra></extra>"))
        fig.update_layout(
            title=dict(text=f"{ticker} — where this rule bought and sold "
                            "(historical replay, NOT live signals)",
                       font=dict(size=14)),
            height=340, margin=dict(l=10, r=10, t=60, b=10),
            legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)),
            plot_bgcolor="#fcfcfc",
        )
        fig.update_xaxes(gridcolor="#eceff1")
        fig.update_yaxes(gridcolor="#eceff1", tickformat=".2f")
        st.plotly_chart(fig, width="stretch",
                        config={"displaylogo": False})

    # ---------------- What it means + the honesty note ----------------
    st.markdown("**What this result is telling you:** " + interpret(result))
    card("🧠 <b>Remember: these are PAST results on ONE stock.</b> Past "
         "performance does not predict future results. A rule that worked "
         "here might fail on another stock or in the future. Real trading "
         "also involves fees, taxes, and the emotional difficulty of "
         "actually following a rule when money is on the line — none of "
         "which are shown here. This tool is for learning how strategies "
         "behave, not financial advice. Never trade real money based only "
         "on a backtest.", kind="warn")
    st.caption(f"Backtest uses split-adjusted daily closing prices up to "
               f"{bt_hist.index[-1].strftime('%d %b %Y')} (free Yahoo data, "
               "may be delayed ~15 min).")
