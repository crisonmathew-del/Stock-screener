"""
Shared user-interface helpers: colours, badges, the disclaimer, the
plain-English glossary, data-freshness banners and tab navigation.

A note on colours: every badge uses dark text on a light background (or
white on a dark background) chosen to meet WCAG AA contrast, so the app is
readable for everyone.
"""

import streamlit as st

from data_fetcher import market_status, data_age_minutes

# --------------------------------------------------------------------------
# Navigation: the three "tabs".
#
# We use a radio styled as tabs instead of st.tabs() because the app needs to
# JUMP between tabs in code (e.g. "Analyse →" on a scan result must open the
# analysis tab) — st.tabs() can't be switched programmatically.
# --------------------------------------------------------------------------

PAGE_SCANNER = "🔍 Find Breakout Stocks (Scanner)"
PAGE_ANALYSE = "📊 Analyse a Specific Stock"
PAGE_TREND = "📈 Trend Template (Minervini)"
PAGES = [PAGE_SCANNER, PAGE_ANALYSE, PAGE_TREND]


def go_to_analysis(ticker: str, came_from: str):
    """Request a jump to the analysis tab with `ticker` pre-loaded.

    Works from anywhere (row clicks, buttons): it only records the request
    in session state — `handle_nav_target()` applies it at the very top of
    the NEXT rerun, before the navigation widget exists, which is the only
    moment Streamlit allows a widget's state to be changed in code."""
    st.session_state["analyse_target"] = ticker
    st.session_state["came_from"] = came_from
    st.session_state["nav_target"] = PAGE_ANALYSE


def handle_nav_target():
    """Apply any pending programmatic tab switch. Must be called in app.py
    BEFORE the navigation widget is created."""
    if "nav_target" in st.session_state:
        st.session_state["nav"] = st.session_state.pop("nav_target")


def apply_global_styles():
    """Small CSS layer for fluidity and mobile friendliness.

    * The tab navigation renders as tappable pill buttons that wrap neatly
      on narrow screens (instead of cramped radio dots).
    * On phones (<= 640px wide) page padding shrinks and headings scale
      down so content uses the full width.
    Uses only stable Streamlit/BaseWeb selectors; verified by the UI tests.
    """
    st.markdown("""<style>
    /* --- top navigation: radio styled as wrapping pill buttons --- */
    div[role="radiogroup"] {
        flex-direction: row; flex-wrap: wrap; gap: 0.45rem 0.55rem;
    }
    label[data-baseweb="radio"] {
        background: #f0f2f6; border: 1px solid #d5d9e0;
        border-radius: 999px; padding: 0.4rem 1rem; margin: 0;
        transition: background 0.15s ease, border-color 0.15s ease;
        cursor: pointer;
    }
    label[data-baseweb="radio"]:hover { background: #e6eaf1; }
    label[data-baseweb="radio"]:has(input:checked) {
        background: #e3ecf9; border-color: #1565c0; font-weight: 600;
    }
    label[data-baseweb="radio"] > div:first-child { display: none; } /* hide dot */

    /* --- phones: use the full width, scale type down a notch --- */
    @media (max-width: 640px) {
        .block-container { padding: 1.1rem 0.9rem 2rem; }
        h1 { font-size: 1.5rem; }
        h2 { font-size: 1.25rem; }
        h3 { font-size: 1.1rem; }
        [data-testid="stMetricValue"] { font-size: 1.35rem; }
    }
    </style>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Money / text formatting
# --------------------------------------------------------------------------

def money(x, decimals: int = 2) -> str:
    """Format a price for use inside st.markdown.

    The backslash before the dollar sign stops Streamlit's markdown from
    treating "$...$" as LaTeX maths and mangling the text.
    """
    if x is None:
        return "N/A"
    try:
        return f"\\${float(x):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def pct(x, decimals: int = 2) -> str:
    """Format a percentage change with its sign, e.g. '+2.31%'."""
    if x is None:
        return "N/A"
    try:
        return f"{float(x):+.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


# --------------------------------------------------------------------------
# Coloured badges / cards (WCAG-AA friendly colour pairs)
# --------------------------------------------------------------------------

_BADGE_STYLES = {
    # kind: (background, text colour, border)
    "good":    ("#e6f4ea", "#1e4620", "#7bc47f"),   # dark green on pale green
    "warn":    ("#fff4e0", "#7a4510", "#f0b454"),   # dark amber on pale amber
    "bad":     ("#fdecea", "#7a1c14", "#f1948a"),   # dark red on pale red
    "neutral": ("#e8eef7", "#1f3a5f", "#9bb4d4"),   # dark blue on pale blue
}


def badge(text: str, kind: str = "neutral"):
    """A small coloured pill, e.g. badge('Strong breakout setup', 'good')."""
    bg, fg, border = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])
    st.markdown(
        f"<span style='background:{bg};color:{fg};border:1px solid {border};"
        f"border-radius:6px;padding:2px 10px;font-weight:600;'>{text}</span>",
        unsafe_allow_html=True,
    )


def card(body_markdown: str, kind: str = "neutral", title: str = ""):
    """A coloured box with readable text, for summaries and warnings."""
    # Inside a raw-HTML block markdown does NOT process escapes (or LaTeX),
    # so money()'s protective backslash would show literally — drop it here.
    body_markdown = body_markdown.replace("\\$", "$")
    bg, fg, border = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])
    title_html = (f"<div style='font-weight:700;font-size:1.05rem;"
                  f"margin-bottom:6px;'>{title}</div>") if title else ""
    st.markdown(
        f"<div style='background:{bg};color:{fg};border:1px solid {border};"
        f"border-radius:10px;padding:14px 18px;margin:6px 0;line-height:1.55;'>"
        f"{title_html}{body_markdown}</div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# The disclaimer (shown prominently on every page)
# --------------------------------------------------------------------------

DISCLAIMER = ("**Educational and research purposes only. Not financial advice.** "
              "A high score is a reason to research further, never a signal to "
              "buy. Always verify live data against a second source and manage "
              "your risk.")


def show_disclaimer():
    st.warning(DISCLAIMER, icon="⚠️")


# --------------------------------------------------------------------------
# Data-freshness banner — used consistently wherever prices are shown
# --------------------------------------------------------------------------

def freshness_banner(fetched_at_utc, last_bar_time=None):
    """Tell the user how fresh the prices are, in a calm, plain way.

    * Market CLOSED  -> quiet blue note: prices are from the last session.
    * Market OPEN but the cached data is older than 15 minutes -> amber.
    * Otherwise -> nothing (no need to alarm anyone).
    """
    is_open, now_et = market_status()
    if not is_open:
        when = ""
        if last_bar_time is not None:
            try:
                when = f" ({last_bar_time.strftime('%a %d %b %Y')})"
            except Exception:
                when = ""
        st.info("ℹ️ US markets are currently closed. Prices are from the last "
                f"trading session{when}. They will update when the market "
                "reopens — 9:30am-4pm New York time (usually 2:30pm-9pm in "
                "the UK), Mon-Fri.")
        return

    age = data_age_minutes(fetched_at_utc)
    if age is not None and age > 15:
        st.warning(f"⚠️ This data is about {age:.0f} minutes old (delayed more "
                   "than 15 minutes). For up-to-the-second prices, check "
                   "finance.yahoo.com. Use the Refresh button to re-download.")


def sanity_check_price_move(pct_change):
    """Flag a daily move beyond ±30% — almost always a data glitch (or news so
    big you should verify it elsewhere before trusting any number here)."""
    if pct_change is not None and abs(pct_change) > 30:
        st.error("⚠️ This price looks unusual (a move of more than 30% vs the "
                 "previous close). It may be a data error — please verify on "
                 "finance.yahoo.com or your broker before acting on anything here.")


# --------------------------------------------------------------------------
# Plain-English glossary, shown as an expander on every tab
# --------------------------------------------------------------------------

GLOSSARY = {
    "Moving average (MA)": "The average closing price over the last N days "
        "(20, 50, 150 or 200 here). It smooths out daily noise; price above a "
        "rising average is the simplest definition of an uptrend.",
    "RSI (Relative Strength Index)": "A 0-100 'speedometer' of recent gains "
        "vs losses over 14 days. 55-70 = strong but healthy. Above ~70-78 = "
        "possibly overheated ('overbought'). Below 30 = beaten down ('oversold').",
    "MACD": "Compares a fast and a slow moving average of price. When the "
        "MACD line crosses above its 'signal' line, short-term momentum is "
        "turning upward.",
    "Volume vs 20-day average": "How heavy today's trading is compared with a "
        "normal day (last 20 days). '2.2x' means more than double the usual "
        "activity — big moves on heavy volume are more trustworthy.",
    "Breakout": "When price pushes above a level it repeatedly failed to pass "
        "(a 'ceiling' or resistance), ideally on heavy volume.",
    "Support and resistance": "Price floors and ceilings. Support = a level "
        "where buyers stepped in before; resistance = where sellers showed up "
        "before. Old ceilings often become new floors after a breakout.",
    "Golden cross / Death cross": "The 50-day average crossing above (golden) "
        "or below (death) the 200-day average — slow but well-watched signals "
        "that the long-term trend has changed.",
    "Fibonacci retracement": "Popular 'how far might a dip go?' levels (23.6%, "
        "38.2%, 50%, 61.8% of the recent swing). Many traders watch them, "
        "which is partly why they often matter.",
    "ATR / Bollinger Bands": "Two ways to measure how much a stock typically "
        "moves in a day. A narrow, 'quiet' band that suddenly expands is the "
        "signature of a breakout starting.",
    "52-week range": "The lowest and highest prices of the past year. Where "
        "today's price sits inside that range tells you a lot at a glance.",
    "Stop-loss": "A pre-decided exit price below your entry. If the stock "
        "falls there, you sell and take a SMALL loss instead of a big one.",
    "Relative Strength rank (Minervini tab)": "How a stock's 6-12 month price "
        "performance ranks against the other stocks in this watchlist "
        "(1-100). NOT the same as RSI, despite the similar name.",
    "Earnings": "The quarterly results announcement. Stocks routinely jump or "
        "drop 5-15% overnight on earnings, gapping straight past stop-losses — "
        "which is why the app warns you when earnings are close.",
}


def glossary_expander():
    with st.expander("📖 New to these words? Open the plain-English glossary"):
        for term, meaning in GLOSSARY.items():
            st.markdown(f"**{term}** — {meaning}")
