"""
📈 Plain-English Stock Screener — the main entry point.

Run it with:    streamlit run app.py

This file only does three jobs:
  1. Page setup (title, layout).
  2. The disclaimer that must appear on every page.
  3. Navigation between the three tabs (each tab lives in its own file:
     tab_scanner.py, tab_analysis.py, tab_minervini.py).

The "tabs" are a radio styled as tabs rather than st.tabs(), because the app
needs to jump between them in code — e.g. clicking "Analyse →" on a scan
result has to open the analysis tab with that stock pre-loaded, which
st.tabs() cannot do.
"""

import streamlit as st

import tab_analysis
import tab_minervini
import tab_scanner
from ui_helpers import (PAGES, PAGE_SCANNER, show_disclaimer,
                        apply_global_styles, handle_nav_target, render_hero)

st.set_page_config(
    page_title="Plain-English Stock Screener",
    page_icon="📈",
    layout="wide",
)
apply_global_styles()

render_hero(
    "📈 Plain-English Stock Screener",
    "Find potential breakout stocks, understand exactly <i>why</i> they "
    "scored what they scored, and learn the vocabulary as you go — no "
    "trading experience required.",
)

# The disclaimer appears prominently on EVERY page, above the content.
show_disclaimer()

# ---------------- Navigation ----------------
if "nav" not in st.session_state:
    st.session_state["nav"] = PAGE_SCANNER
handle_nav_target()  # apply any pending tab jump (e.g. a clicked scan row)

choice = st.radio("Choose a tab:", PAGES, key="nav", horizontal=True,
                  label_visibility="collapsed")

st.divider()

if choice == PAGES[0]:
    tab_scanner.render()
elif choice == PAGES[1]:
    tab_analysis.render()
else:
    tab_minervini.render()

st.divider()
show_disclaimer()
st.caption("Data: Yahoo Finance via the yfinance library (free, may be "
           "delayed ~15 minutes). Built for learning — see README.md for a "
           "beginner's guide to every feature.")
