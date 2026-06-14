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
    """The app's visual theme — one CSS layer, applied once at startup.

    Pure styling: it changes how things LOOK (font, spacing, shadows,
    hover effects), never how they work. Targets only stable Streamlit /
    BaseWeb hooks, and is verified by the UI screenshot tests. Everything
    stays on the tested light, high-contrast palette (WCAG AA).

    Tweaking the look? The colour variables live in the :root block below.
    """
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --brand:        #1565c0;   /* primary blue (matches the 20-day MA) */
        --brand-dark:   #0d47a1;
        --ink:          #1b2430;   /* main text */
        --muted:        #5b6675;
        --surface:      #ffffff;
        --line:         #e6eaf0;   /* hairline borders */
        --shadow:       0 1px 2px rgba(16,32,56,.04), 0 6px 18px rgba(16,32,56,.06);
        --shadow-soft:  0 1px 3px rgba(16,32,56,.05);
        --radius:       14px;
    }

    /* ---------- typography + base ---------- */
    html, body, [class*="css"], .stMarkdown, button, input, textarea, select {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                     Roboto, sans-serif !important;
    }
    .stApp { background:
        radial-gradient(1200px 480px at 50% -120px, #eef4fc 0%, #ffffff 60%); }
    .block-container { padding-top: 1.4rem; max-width: 1180px; }
    h1, h2, h3 { color: var(--ink); letter-spacing: -0.01em; font-weight: 700; }
    a { color: var(--brand); }

    /* ---------- hero header ---------- */
    .hero {
        background: linear-gradient(135deg, #16307a 0%, #1565c0 55%, #1aa6e8 100%);
        color: #fff; border-radius: 20px; padding: 26px 30px;
        box-shadow: 0 10px 30px rgba(21,101,192,.28);
        margin: 0 0 1.1rem 0;
    }
    .hero h1 {
        color: #fff !important; margin: 0; font-size: 2.05rem; font-weight: 800;
        letter-spacing: -0.02em;
    }
    .hero p {
        margin: .5rem 0 0 0; color: rgba(255,255,255,.92); font-size: 1.03rem;
        line-height: 1.5; max-width: 760px;
    }

    /* ---------- top navigation: radio styled as pill buttons ---------- */
    div[role="radiogroup"] {
        flex-direction: row; flex-wrap: wrap; gap: 0.5rem 0.6rem;
    }
    label[data-baseweb="radio"] {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: 999px; padding: 0.5rem 1.15rem; margin: 0;
        box-shadow: var(--shadow-soft); cursor: pointer; font-weight: 500;
        transition: transform .15s ease, box-shadow .15s ease,
                    background .15s ease, border-color .15s ease;
    }
    label[data-baseweb="radio"]:hover {
        transform: translateY(-1px); border-color: #c2d4ee;
        box-shadow: 0 4px 14px rgba(21,101,192,.14);
    }
    label[data-baseweb="radio"]:has(input:checked) {
        background: linear-gradient(135deg, var(--brand) 0%, var(--brand-dark) 100%);
        border-color: transparent; color: #fff; font-weight: 600;
        box-shadow: 0 6px 16px rgba(21,101,192,.30);
    }
    label[data-baseweb="radio"]:has(input:checked) * { color: #fff !important; }
    label[data-baseweb="radio"] > div:first-child { display: none; } /* hide dot */

    /* ---------- buttons ---------- */
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px; border: 1px solid var(--line);
        font-weight: 600; padding: 0.5rem 1.1rem; box-shadow: var(--shadow-soft);
        transition: transform .14s ease, box-shadow .14s ease,
                    border-color .14s ease, background .14s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px); border-color: #c2d4ee;
        box-shadow: 0 6px 16px rgba(21,101,192,.16);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--brand) 0%, var(--brand-dark) 100%);
        border: none; color: #fff;
    }
    .stButton > button[kind="primary"]:hover { box-shadow: 0 8px 22px rgba(21,101,192,.34); }

    /* ---------- metric cards ---------- */
    [data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: var(--radius); padding: 14px 16px 12px;
        box-shadow: var(--shadow);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); font-weight: 600; }
    [data-testid="stMetricValue"] { font-weight: 700; letter-spacing: -0.01em; }

    /* ---------- inputs ---------- */
    [data-baseweb="select"] > div, .stNumberInput input, .stTextInput input {
        border-radius: 10px !important;
    }
    [data-baseweb="select"] > div:focus-within,
    .stNumberInput input:focus, .stTextInput input:focus {
        box-shadow: 0 0 0 3px rgba(21,101,192,.18) !important;
        border-color: var(--brand) !important;
    }

    /* ---------- expanders, tables, alerts ---------- */
    [data-testid="stExpander"] {
        border: 1px solid var(--line); border-radius: 12px;
        box-shadow: var(--shadow-soft); overflow: hidden;
    }
    [data-testid="stExpander"] summary:hover { color: var(--brand); }
    [data-testid="stDataFrame"] {
        border-radius: 12px; overflow: hidden; box-shadow: var(--shadow);
        border: 1px solid var(--line);
    }
    [data-testid="stAlert"] { border-radius: 12px; }
    [data-testid="stNotification"] { border-radius: 12px; }

    /* ---------- dividers + scrollbar ---------- */
    hr { border: none; height: 1px;
         background: linear-gradient(90deg, transparent, var(--line), transparent); }
    ::-webkit-scrollbar { width: 11px; height: 11px; }
    ::-webkit-scrollbar-thumb {
        background: #c7d2e0; border-radius: 8px; border: 3px solid #fff; }
    ::-webkit-scrollbar-thumb:hover { background: #aebccd; }

    /* ---------- phones: full width, scaled-down type ---------- */
    @media (max-width: 640px) {
        .block-container { padding: 1rem 0.85rem 2rem; }
        .hero { padding: 20px 20px; border-radius: 16px; }
        .hero h1 { font-size: 1.5rem; }
        .hero p { font-size: 0.95rem; }
        h1 { font-size: 1.5rem; }
        h2 { font-size: 1.25rem; }
        h3 { font-size: 1.1rem; }
        [data-testid="stMetricValue"] { font-size: 1.3rem; }
    }
    </style>""", unsafe_allow_html=True)


def render_hero(title: str, subtitle: str):
    """The gradient banner at the top of the page (styled by .hero CSS)."""
    st.markdown(
        f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


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
        f"border-radius:14px;padding:15px 19px;margin:8px 0;line-height:1.55;"
        f"box-shadow:0 1px 2px rgba(16,32,56,.04),0 6px 18px rgba(16,32,56,.06);'>"
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
