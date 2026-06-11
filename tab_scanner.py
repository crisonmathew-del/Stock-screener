"""
TAB 1 — "Find Breakout Stocks (Scanner)".

Scans every stock in the watchlist, scores each 0-100 for breakout
potential, and shows the results as a sortable table you can filter by
score, price and sector. Click a row to open the full analysis in Tab 2.
"""

from datetime import timezone

import pandas as pd
import streamlit as st

from breakout_score import compute_breakout
from data_fetcher import fetch_watchlist_history, UK, clear_all_caches
from ui_helpers import (PAGE_SCANNER, go_to_analysis, freshness_banner,
                        glossary_expander)
from watchlist import all_tickers, all_sectors, company_name, sector_of


@st.cache_data(ttl=600, show_spinner=False)
def _score_watchlist(_histories, cache_key):
    """Score every stock. `cache_key` is the download timestamp, so scores are
    recomputed only when fresh data arrives (the underscore on `_histories`
    tells Streamlit not to hash the big DataFrames themselves)."""
    rows = []
    for ticker, df in _histories.items():
        result = compute_breakout(df)
        if result is None:
            continue  # not enough history to score fairly — skip quietly
        rows.append({
            "Ticker": ticker,
            "Company": company_name(ticker),
            "Sector": sector_of(ticker),
            "Price": result["price"],
            "% today": result["pct_today"],
            "Volume vs avg": result["vol_ratio"],
            "RSI": result["rsi"],
            "Score": result["score"],
            "Verdict": result["verdict"],
            "Entry quality": result["entry_note"],
        })
    return pd.DataFrame(rows)


def render():
    st.header("🔍 Find Breakout Stocks")
    st.markdown(
        "This scanner looks at **{n} US stocks** (large, mid and small caps "
        "across six sectors) and scores each one **0-100** on how closely it "
        "matches a classic *breakout setup* — a stock pushing above a price "
        "ceiling on unusually heavy volume. **A high score means \"worth "
        "researching\", never \"buy now\".**".format(n=len(all_tickers()))
    )
    glossary_expander()

    # ---------------- Download + score (cached for 10 minutes) ----------------
    with st.spinner("Scanning the watchlist… first scan downloads ~2 years of "
                    "data for every stock and can take a minute. After that "
                    "it's cached and instant."):
        histories, fetched_at = fetch_watchlist_history(tuple(all_tickers()))

    if not histories:
        st.error("😕 Couldn't download market data right now. This usually "
                 "means no internet connection or Yahoo Finance is rate-"
                 "limiting. Wait a minute and press **Refresh data** below.")
        if st.button("🔄 Refresh data"):
            clear_all_caches()
            st.rerun()
        return

    table = _score_watchlist(histories, fetched_at)
    last_bar = max(df.index[-1] for df in histories.values())
    freshness_banner(fetched_at, last_bar)

    # ---------------- Filters ----------------
    st.subheader("Filters")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        min_score = st.slider(
            "Minimum breakout score", 0, 100, 0,
            help="Slide right to only see the strongest setups. 70+ is "
                 "'strong', 45-69 is 'building', below 45 is 'not a candidate'.")
    with col2:
        min_price = st.number_input(
            "Minimum price ($)", min_value=0.0, value=5.0, step=1.0,
            help="Stocks under $5 ('penny stocks') are often manipulated and "
                 "extra risky, so they're hidden by default.")
    with col3:
        # Default is "Any" on purpose: a low default cap would silently hide
        # most of the market from beginners.
        max_choice = st.selectbox(
            "Maximum price ($)", ["Any", 25, 50, 100, 250, 500, 1000],
            index=0,
            help="Cap the share price if you have a small account. 'Any' "
                 "shows everything.")
    with col4:
        sector = st.selectbox(
            "Sector", ["All sectors"] + all_sectors(),
            help="Only show stocks from one industry group.")

    filtered = table[(table["Score"] >= min_score) & (table["Price"] >= min_price)]
    if max_choice != "Any":
        filtered = filtered[filtered["Price"] <= float(max_choice)]
    if sector != "All sectors":
        filtered = filtered[filtered["Sector"] == sector]
    filtered = filtered.sort_values("Score", ascending=False).reset_index(drop=True)

    # ---------------- Match count + last-scan time (shown in UK time) ----------------
    scan_time = (fetched_at.astimezone(UK).strftime("%a %d %b %Y, %I:%M %p UK time")
                 if fetched_at else "unknown")
    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"**{len(filtered)} of {len(table)} stocks match your "
                    f"filters.** &nbsp; Last scan: {scan_time}.")
    with right:
        if st.button("🔄 Refresh data", help="Re-download fresh prices "
                     "(otherwise data refreshes every 10 minutes)."):
            clear_all_caches()
            _score_watchlist.clear()
            st.rerun()

    if filtered.empty:
        st.info("No stocks match these filters. Try lowering the minimum "
                "score — on quiet market days even the best setups may only "
                "score 40-60.")
        return

    # ---------------- Results table (tap a row to analyse) ----------------
    st.markdown("**Tap the circle at the left of any row** to open that "
                "stock's full analysis instantly. Click a column header "
                "to re-sort.")
    # The key is versioned: after navigating away we bump it, so returning
    # to this tab shows a fresh table instead of re-firing the old selection.
    ver = st.session_state.setdefault("scanner_table_ver", 0)
    event = st.dataframe(
        filtered,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"scanner_table_{ver}",
        column_config={
            "Ticker": st.column_config.TextColumn(
                pinned=True,
                help="The stock's trading symbol. Stays visible while you "
                     "scroll the table sideways on a phone."),
            "Price": st.column_config.NumberColumn(
                format="$%.2f", help="Latest price from Yahoo Finance."),
            "% today": st.column_config.NumberColumn(
                format="%+.2f%%",
                help="Change vs yesterday's closing price."),
            "Volume vs avg": st.column_config.NumberColumn(
                format="%.1f×",
                help="Today's trading volume vs the 20-day average. "
                     "2.0x = double the usual activity."),
            "RSI": st.column_config.NumberColumn(
                format="%.0f",
                help="0-100 momentum gauge. 55-70 = strong but healthy; "
                     "above ~78 = overheated."),
            "Score": st.column_config.ProgressColumn(
                format="%d", min_value=0, max_value=100,
                help="The 0-100 breakout score. See the score breakdown in "
                     "the analysis tab for exactly where points came from."),
            "Verdict": st.column_config.TextColumn(
                help="🟢 70-100 strong setup · 🟡 45-69 building · 🔴 below 45."),
            "Entry quality": st.column_config.TextColumn(
                help="Even a strong setup can be a BAD entry if the stock "
                     "already jumped — this column flags that."),
        },
    )

    # A tapped row opens the analysis tab immediately — no extra click.
    selected_rows = event.selection.rows if event and event.selection else []
    if selected_rows:
        ticker = filtered.iloc[selected_rows[0]]["Ticker"]
        st.session_state["scanner_table_ver"] = ver + 1  # forget the selection
        go_to_analysis(ticker, PAGE_SCANNER)
        st.rerun()

    st.caption("Verdicts: 🟢 70-100 = Strong breakout setup · 🟡 45-69 = "
               "Watch — building momentum · 🔴 below 45 = Not a breakout "
               "candidate. Scores update as new data arrives; a stock's score "
               "this morning can be different by this afternoon.")
