"""
TAB 3 — "Trend Template (Minervini)": the long-term trend filter.

Runs every watchlist stock through Mark Minervini's 7-rule Trend Template
(see minervini.py for the rules in plain English) and shows only the stocks
in a confirmed, established uptrend.
"""

import pandas as pd
import streamlit as st

from data_fetcher import fetch_watchlist_history, clear_all_caches, UK
from minervini import (evaluate_trend_template, relative_strength_ranks,
                       CRITERIA_LABELS)
from ui_helpers import PAGE_TREND, go_to_analysis, freshness_banner, glossary_expander
from watchlist import all_tickers, company_name


def render():
    st.header("📈 Trend Template (Minervini)")
    st.markdown(
        "This is a **long-term trend filter** (Mark Minervini's Trend "
        "Template). Unlike the breakout scanner, it only shows stocks already "
        "in a **confirmed, established uptrend** — fewer results, but "
        "higher-quality trends. Use it to find **WHAT** to watch; then use "
        "the breakout scanner to time **WHEN** to consider entering."
    )
    with st.expander("📜 The 7 rules a stock must pass (plain English)"):
        st.markdown("""
1. **Price above both the 150-day and 200-day moving averages** — trading above its long-term trend lines.
2. **150-day average above the 200-day average** — the medium-term trend is stronger than the long-term one.
3. **200-day average rising for at least a month** — the long-term trend itself points up.
4. **50-day average above the 150-day and 200-day** — the short-term trend is the strongest of all.
5. **Price above the 50-day average** — strength right now, not just historically.
6. **Price at least 30% above its 52-week low** — it has already proven it can rally.
7. **Price within 25% of its 52-week high** — near the top of its range, not buried in a crater.
""")
    glossary_expander()

    with st.spinner("Checking the watchlist against the Trend Template…"):
        histories, fetched_at = fetch_watchlist_history(tuple(all_tickers()))

    if not histories:
        st.error("😕 Couldn't download market data right now (no connection "
                 "or Yahoo is rate-limiting). Wait a minute and refresh.")
        if st.button("🔄 Refresh data"):
            clear_all_caches()
            st.rerun()
        return

    last_bar = max(df.index[-1] for df in histories.values())
    freshness_banner(fetched_at, last_bar)

    # ---------------- Relative Strength (Minervini's 8th rule) ----------------
    rs_ranks = relative_strength_ranks(histories)
    st.info(
        "ℹ️ **Relative Strength rank (vs watchlist):** this ranks each "
        "stock's 6- and 12-month price performance against the others in "
        "this watchlist on a 1-100 scale — an approximation of IBD's RS "
        "Rating, **not** the RSI momentum gauge used elsewhere in this app. "
        "Minervini's original 8th rule requires a high RS Rating.")

    # ---------------- Options ----------------
    c1, c2 = st.columns(2)
    with c1:
        loosen = st.toggle(
            "Loosen to 6 of 7 rules", value=False,
            help="The strict template requires ALL 7. Loosening shows "
                 "near-misses too — useful in choppy markets when almost "
                 "nothing passes 7/7.")
    with c2:
        require_rs = st.toggle(
            "Also require Relative Strength rank above 70 (8th rule)",
            value=False,
            help="Minervini's full checklist also demands the stock be a "
                 "top performer vs its peers.")

    # ---------------- Evaluate every stock ----------------
    rows, details = [], {}
    for ticker, df in histories.items():
        result = evaluate_trend_template(df)
        if result is None:
            continue  # too little history for 200-day rules — skipped fairly
        details[ticker] = result
        rows.append({
            "Ticker": ticker,
            "Company": company_name(ticker),
            "Price": result["price"],
            "% above 52-wk low": result["pct_above_low"],
            "% below 52-wk high": result["pct_below_high"],
            "RS rank (vs watchlist)": rs_ranks.get(ticker),
            "Rules passed": f"{result['passed']}/7 " +
                            ("✅" if result["passed"] == 7 else
                             "🟡" if result["passed"] == 6 else "❌"),
            "_passed": result["passed"],
        })

    table = pd.DataFrame(rows)
    need = 6 if loosen else 7
    passing = table[table["_passed"] >= need]
    if require_rs:
        passing = passing[passing["RS rank (vs watchlist)"].fillna(0) > 70]
    passing = passing.sort_values(
        ["_passed", "RS rank (vs watchlist)"], ascending=False
    ).drop(columns="_passed").reset_index(drop=True)

    scan_time = (fetched_at.astimezone(UK).strftime("%a %d %b %Y, %I:%M %p UK time")
                 if fetched_at else "unknown")
    st.markdown(f"**{len(passing)} of {len(table)} stocks pass** "
                f"({need} of 7 rules{' + RS rank > 70' if require_rs else ''}). "
                f"&nbsp; Last scan: {scan_time}.")

    if passing.empty:
        st.info("No stocks pass right now. That's normal in weak or choppy "
                "markets — the template is deliberately strict. Try the "
                "'6 of 7' toggle, or simply check back another day: when "
                "little passes, cash is also a position.")
        return

    st.markdown("**Tap the circle at the left of any row** to open that "
                "stock's full analysis instantly.")
    # Versioned key: bumping it after navigation clears the old selection.
    ver = st.session_state.setdefault("minervini_table_ver", 0)
    event = st.dataframe(
        passing,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"minervini_table_{ver}",
        column_config={
            "Ticker": st.column_config.TextColumn(
                pinned=True,
                help="Stays visible while you scroll the table sideways "
                     "on a phone."),
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "% above 52-wk low": st.column_config.NumberColumn(
                format="%+.0f%%",
                help="Rule 6 needs at least +30%: the stock must have "
                     "already proven it can rally."),
            "% below 52-wk high": st.column_config.NumberColumn(
                format="%.0f%%",
                help="Rule 7 needs 25% or less: the stock must be near the "
                     "top of its yearly range."),
            "RS rank (vs watchlist)": st.column_config.NumberColumn(
                format="%d",
                help="1-100 performance rank vs this watchlist (approximation "
                     "of IBD's RS Rating — NOT the RSI gauge)."),
            "Rules passed": st.column_config.TextColumn(
                help="How many of the 7 Trend Template rules this stock "
                     "passes. Expand the checklist below for the detail."),
        },
    )

    selected = event.selection.rows if event and event.selection else []
    if selected:
        ticker = passing.iloc[selected[0]]["Ticker"]
        st.session_state["minervini_table_ver"] = ver + 1  # forget selection
        go_to_analysis(ticker, PAGE_TREND)
        st.rerun()

    # ---------------- Per-rule checklist for the passing stocks ----------------
    with st.expander("🔬 Full rule-by-rule checklist for these stocks"):
        check_rows = []
        for ticker in passing["Ticker"]:
            result = details[ticker]
            row = {"Ticker": ticker}
            for label, ok in zip(CRITERIA_LABELS, result["checks"]):
                row[label] = "✅" if ok else "❌"
            check_rows.append(row)
        st.dataframe(pd.DataFrame(check_rows), hide_index=True,
                     width="stretch")

    st.caption("Stocks with under ~11 months of trading history are skipped — "
               "the 200-day-average rules can't be computed for recent IPOs.")
