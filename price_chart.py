"""
The upgraded interactive price chart for the single-stock analysis page,
plus detection of the technical EVENTS marked on it.

What the chart shows (last ~12 months of daily data, default view 6 months):
  * Candlesticks (green = closed up, red = closed down) with a hover tooltip
    showing date, open/high/low/close and the day's volume.
  * A volume subpanel, colour-matched to the candles.
  * 20/50/200-day moving-average overlays — click a legend entry to hide/show.
  * Solid support/resistance lines and dashed Fibonacci levels, each labelled
    with its price (the SAME values shown in the tables below the chart).
  * Range buttons (1M / 3M / 6M / YTD / 1Y) and a scrub slider underneath.
  * Neutral event markers (see below).

About the event markers: they flag things that ALREADY HAPPENED on the chart
(a moving-average cross, an RSI extreme, a volume spike…). They are
observations for learning to read the chart — deliberately drawn in neutral
colours and shapes, never as buy/sell arrows, because indicators describe
the past and often get the future wrong.
"""

import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from indicators import sma, rsi, macd

CHART_BARS = 252        # ~12 months charted, so the "1Y" button has data
DEFAULT_VIEW_BARS = 126  # ~6 months shown by default

# --------------------------------------------------------------------------
# Event catalogue: how each event type looks and what its tooltip says.
# "group" entries share one legend item, so the legend stays uncluttered.
# Colours are neutral (golds/blues/purples/teals/greys) and symbols are
# never arrows — these are observations, not buy/sell signals.
# --------------------------------------------------------------------------
EVENT_TYPES = {
    "golden_cross": dict(
        group="MA crosses", label="Golden cross — long-term bullish signal",
        color="#8d6e00", symbol="star", side="above",
        meaning="The 50-day average crossed above the 200-day average — "
                "a classic long-term bullish sign.",
        limitation="It is based on past prices and often lags the actual "
                   "move by weeks."),
    "death_cross": dict(
        group="MA crosses", label="Death cross — bearish",
        color="#37474f", symbol="star", side="below",
        meaning="The 50-day average crossed below the 200-day average — "
                "a classic long-term bearish sign.",
        limitation="It is based on past prices and often appears after most "
                   "of the fall has already happened."),
    "macd_up": dict(
        group="MACD crosses", label="MACD crossed up — momentum turning up",
        color="#1565c0", symbol="diamond", side="above",
        meaning="The MACD line crossed above its signal line — short-term "
                "momentum turning up.",
        limitation="MACD flips often in choppy markets and can whipsaw."),
    "macd_down": dict(
        group="MACD crosses", label="MACD crossed down — momentum fading",
        color="#5e35b1", symbol="diamond", side="below",
        meaning="The MACD line crossed below its signal line — short-term "
                "momentum fading.",
        limitation="MACD flips often in choppy markets and can whipsaw."),
    "rsi_overbought": dict(
        group="RSI 70/30", label="RSI overbought (above 70)",
        color="#b35300", symbol="circle-open", side="above",
        meaning="RSI rose above 70 — the stock climbed fast and may be "
                "overheated.",
        limitation="Strong stocks can stay overbought for weeks while "
                   "still rising."),
    "rsi_oversold": dict(
        group="RSI 70/30", label="RSI oversold (below 30)",
        color="#00695c", symbol="circle-open", side="below",
        meaning="RSI fell below 30 — the stock dropped fast and may be "
                "washed out.",
        limitation="Falling stocks can stay oversold a long time; cheap "
                   "can get cheaper."),
    "breakout": dict(
        group="Breakout on volume", label="Broke resistance on heavy volume",
        color="#283593", symbol="square", side="above",
        meaning="Price closed above its recent ceiling on well above-average "
                "volume — old sellers out of the way with real interest "
                "behind the move.",
        limitation="Some breakouts fail and slip back below the old ceiling "
                   "within days."),
    "volume_spike": dict(
        group="Unusual volume", label="Unusual volume",
        color="#5d4037", symbol="hexagon", side="below",
        meaning="Trading volume was more than 2 times its 20-day average — "
                "something drew a crowd that day.",
        limitation="Heavy volume shows interest, not direction — it "
                   "accompanies panics as well as rallies."),
}

MAX_PER_TYPE = 12  # cap markers per event type so busy charts stay readable


def _hover_text(meta, date, extra=""):
    """The plain-English tooltip for one marker: what it means AND its limits."""
    body = meta["meaning"] + (" " + extra if extra else "")
    return ("<b>" + date.strftime("%d %b %Y") + " — " + meta["label"] + "</b><br>"
            + "<br>".join(textwrap.wrap(body, 52)) + "<br><i>"
            + "<br>".join(textwrap.wrap("Limitation: " + meta["limitation"], 52))
            + "</i>")


def detect_chart_events(hist):
    """Find the technical events that occurred in the charted window.

    Returns a date-sorted list of dicts:
      {"date", "type", "group", "label", "y" (marker height), "hover"}.
    Everything is computed on the full history (so indicators are warmed up)
    and then filtered to the last CHART_BARS days the chart displays.
    """
    df = hist.dropna(subset=["Close", "High", "Low", "Volume"])
    if len(df) < 40:
        return []

    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]
    window = set(df.index[-min(CHART_BARS, len(df)):])
    events = []

    def add(mask, type_key, extra_fn=None):
        """Turn a boolean series of 'event happened this bar' into markers."""
        meta = EVENT_TYPES[type_key]
        dates = [ts for ts in df.index[mask.fillna(False)] if ts in window]
        for ts in dates[-MAX_PER_TYPE:]:
            y = (float(high.loc[ts]) * 1.03 if meta["side"] == "above"
                 else float(low.loc[ts]) * 0.97)
            extra = extra_fn(ts) if extra_fn else ""
            events.append({"date": ts, "type": type_key,
                           "group": meta["group"], "label": meta["label"],
                           "y": y, "hover": _hover_text(meta, ts, extra)})

    # NOTE on the .shift(1, fill_value=...) pattern used below: a plain
    # .shift(1) turns a True/False series into "object" dtype, where pandas'
    # & and ~ silently misbehave — fill_value keeps it boolean and correct.

    # --- Golden / death cross: the 50-day MA crossing the 200-day MA ---
    if len(close) >= 200:
        ma50, ma200 = sma(close, 50), sma(close, 200)
        # Only compare days where BOTH averages exist (and existed yesterday),
        # so the warm-up edge can't fake a cross.
        valid = ma50.notna() & ma200.notna()
        valid = valid & valid.shift(1, fill_value=False)
        above = (ma50 > ma200) & valid
        prev_above = above.shift(1, fill_value=False)
        add(valid & above & ~prev_above, "golden_cross")
        add(valid & ~above & prev_above, "death_cross")

    # --- MACD line crossing its signal line (both directions) ---
    macd_line, signal_line = macd(close)
    macd_above = macd_line > signal_line
    macd_prev = macd_above.shift(1, fill_value=False)
    add(macd_above & ~macd_prev, "macd_up")
    add(~macd_above & macd_prev, "macd_down")

    # --- RSI crossing into overbought (>70) / oversold (<30) territory ---
    r = rsi(close)
    add((r > 70) & (r.shift(1) <= 70), "rsi_overbought",
        lambda ts: f"RSI reached {r.loc[ts]:.0f}.")
    add((r < 30) & (r.shift(1) >= 30), "rsi_oversold",
        lambda ts: f"RSI fell to {r.loc[ts]:.0f}.")

    # --- Volume context used by the last two event types ---
    vol_avg20 = vol.rolling(20).mean().shift(1)  # avg of the PRIOR 20 days
    vol_ratio = vol / vol_avg20

    # --- Breaking above the prior 30-day high on heavy volume ---
    prior_high30 = high.rolling(30).max().shift(1)
    broke = (close > prior_high30) & (vol_ratio >= 1.5)
    add(broke & ~broke.shift(1, fill_value=False),  # first day of each break only
        "breakout", lambda ts: f"Volume was {vol_ratio.loc[ts]:.1f} times normal.")

    # --- Volume spikes above 2x the 20-day average ---
    spike = vol_ratio > 2.0
    add(spike & ~spike.shift(1, fill_value=False) & ~broke,
        "volume_spike", lambda ts: f"{vol_ratio.loc[ts]:.1f} times normal volume.")

    events.sort(key=lambda e: e["date"])
    return events


def _format_volume(v):
    """1234567 -> '1.2M' so hover tooltips stay short."""
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def build_price_chart(ticker, hist, fib, levels, events):
    """Build the interactive Plotly figure.

    `fib` and `levels` are the SAME dicts shown in the tables below the
    chart, so the drawn lines can never disagree with the printed numbers.
    Note: prices in on-chart labels are written without a currency symbol —
    a dollar sign would trigger Plotly's LaTeX maths rendering.
    """
    full_close = hist["Close"]
    df = hist.iloc[-CHART_BARS:]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.74, 0.26], vertical_spacing=0.02)

    # ---- Candlesticks, with volume folded into each candle's tooltip ----
    vol_avg20 = hist["Volume"].rolling(20).mean().shift(1).reindex(df.index)
    candle_text = [
        "Volume: " + _format_volume(v)
        + (f" ({v / a:.1f}x the 20-day average)" if a and a > 0 else "")
        for v, a in zip(df["Volume"], vol_avg20)
    ]
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name=ticker, showlegend=False,
        text=candle_text,  # appended to the standard date+OHLC hover
        increasing_line_color="#1a7f37", increasing_fillcolor="#1a7f37",
        decreasing_line_color="#c62828", decreasing_fillcolor="#c62828",
    ), row=1, col=1)

    # ---- Moving averages (computed on FULL history, accurate at the edges;
    #      click a legend entry to hide/show a line) ----
    for window, colour in ((20, "#1565c0"), (50, "#e65100"), (200, "#6a1b9a")):
        if len(full_close) >= window:
            ma = sma(full_close, window).reindex(df.index)
            fig.add_trace(go.Scatter(
                x=df.index, y=ma, name=f"{window}-day MA",
                line=dict(color=colour, width=1.6),
                hovertemplate=f"{window}-day MA: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # ---- Support / resistance (solid) and Fibonacci (dashed) levels,
    #      labelled with their price — same numbers as the tables ----
    for days, colour in ((30, "#2e7d32"), (90, "#33691e")):
        y = levels[days]["support"]
        fig.add_hline(y=y, line_color=colour, line_width=1.2, row=1, col=1,
                      annotation_text=f"Support {days}d · {y:.2f}",
                      annotation_position="bottom left",
                      annotation_font=dict(color=colour, size=11))
    for days, colour in ((30, "#b71c1c"), (90, "#880e4f")):
        y = levels[days]["resistance"]
        fig.add_hline(y=y, line_color=colour, line_width=1.2, row=1, col=1,
                      annotation_text=f"Resistance {days}d · {y:.2f}",
                      annotation_position="top left",
                      annotation_font=dict(color=colour, size=11))
    # Alternate the label side so closely spaced Fib levels don't overlap
    for i, (name, lvl) in enumerate(fib["levels"].items()):
        fig.add_hline(y=lvl, line_dash="dash", line_color="#546e7a",
                      line_width=1, row=1, col=1,
                      annotation_text=f"Fib {name} · {lvl:.2f}",
                      annotation_position=("top right" if i % 2 == 0
                                           else "bottom right"),
                      annotation_font=dict(color="#37474f", size=10))

    # ---- Event markers: one trace per event type, one legend entry per
    #      GROUP (clicking it toggles the whole group) ----
    seen_groups = set()
    for type_key, meta in EVENT_TYPES.items():
        evs = [e for e in events if e["type"] == type_key]
        if not evs:
            continue
        first_of_group = meta["group"] not in seen_groups
        seen_groups.add(meta["group"])
        fig.add_trace(go.Scatter(
            x=[e["date"] for e in evs], y=[e["y"] for e in evs],
            mode="markers", name=meta["group"],
            legendgroup=meta["group"], showlegend=first_of_group,
            marker=dict(symbol=meta["symbol"], size=11, color=meta["color"],
                        line=dict(color="#ffffff", width=1.5)),
            customdata=[e["hover"] for e in evs],
            hovertemplate="%{customdata}<extra></extra>",
        ), row=1, col=1)

    # ---- Volume subpanel, colour-matched to the candles ----
    bar_colours = ["#1a7f37" if c >= o else "#c62828"
                   for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], name="Volume", showlegend=False,
        marker_color=bar_colours, marker_line_width=0,
        hovertemplate="Volume: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ---- Layout: range buttons, scrub slider, default 6-month view ----
    view_start = df.index[max(0, len(df) - DEFAULT_VIEW_BARS)]
    view_end = df.index[-1] + pd.Timedelta(days=3)
    fig.update_layout(
        title=dict(text=f"{ticker} — daily candles (default view: 6 months)",
                   font=dict(size=16)),
        height=640,
        hovermode="x",
        dragmode="pan",
        legend=dict(orientation="h", y=1.07, x=0,
                    groupclick="togglegroup",
                    font=dict(size=11)),
        margin=dict(l=10, r=10, t=90, b=10),
        plot_bgcolor="#fcfcfc",
        bargap=0.15,
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                ],
                bgcolor="#eceff1", activecolor="#90a4ae",
                font=dict(color="#263238", size=12),
                x=0, y=1.16,
            ),
            range=[view_start, view_end],
            rangeslider=dict(visible=False),  # the slider lives on the bottom axis
        ),
        xaxis2=dict(
            rangeslider=dict(visible=True, thickness=0.07,
                             bgcolor="#f5f5f5", bordercolor="#cfd8dc",
                             borderwidth=1),
            range=[view_start, view_end],
        ),
    )

    # Hide weekend gaps; show a crosshair spike on hover for a fluid feel
    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])],
        showspikes=True, spikemode="across", spikethickness=1,
        spikedash="dot", spikecolor="#90a4ae",
        gridcolor="#eceff1",
    )
    fig.update_yaxes(title_text="Price", row=1, col=1, gridcolor="#eceff1",
                     tickformat=".2f")
    fig.update_yaxes(title_text="Volume", row=2, col=1, gridcolor="#eceff1",
                     tickformat="~s")
    return fig
