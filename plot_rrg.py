"""
plot_rrg.py — publication-quality interactive RRG chart (plotly).

Two entry points:
  make_rrg_figure(...)    static chart: trails + current heads
  make_rrg_animation(...) the same chart animated through time, with a
                          play button and a date slider (for video capture)

Design notes (deliberate, don't "fix" casually):
- Every head carries a persistent ticker label: with 11 series, color alone
  cannot safely carry identity (colorblind separation sits in the floor band),
  so identity = label + color, never color alone.
- Quadrant tints use reserved status hues at low alpha; series colors are a
  separate fixed categorical palette assigned in config.SECTORS order and
  never re-sorted or cycled.
- Axes are symmetric around 100 with equal x/y span so the four quadrants
  read as equal areas; one axis pair only.
- Heads get a 2px surface-colored ring so overlapping bubbles stay separable.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

import config
from rrg import latest_snapshot

HOVER = ("<b>%{customdata[0]} — %{customdata[1]}</b><br>"
         "%{customdata[2]}<br>"
         "RS-Ratio: %{x:.2f}<br>"
         "RS-Momentum: %{y:.2f}<br>"
         "Quadrant: %{customdata[3]}<br>"
         "Avg $ volume: %{customdata[4]}<br>"
         "Volume share: %{customdata[5]:.1%}<br>"
         "Realized vol (ann.): %{customdata[6]:.1%}"
         "<extra></extra>")


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _axis_range(snap: pd.DataFrame, min_pad: float = 2.5) -> float:
    """Half-span around 100 covering all plotted points, same for both axes."""
    dev = max((snap["rs_ratio"] - 100).abs().max(),
              (snap["rs_momentum"] - 100).abs().max())
    return max(min_pad, float(dev) * 1.18)


def _bubble_px(share: float, min_px: float = 14, max_px: float = 44) -> float:
    """Map a volume share (0..1) to a marker diameter. Sqrt so AREA tracks
    the value; floor keeps every mark comfortably clickable."""
    if pd.isna(share):
        return min_px
    return min_px + (max_px - min_px) * min(share / 0.25, 1.0) ** 0.5


def _fmt_dollar(v: float) -> str:
    if pd.isna(v):
        return "n/a"
    for unit, div in (("B", 1e9), ("M", 1e6)):
        if abs(v) >= div:
            return f"${v / div:,.1f}{unit}"
    return f"${v:,.0f}"


def _customdata(d: pd.DataFrame, name: str) -> list:
    return list(zip(
        d["ticker"], [name] * len(d), d["date"].dt.strftime("%d %b %Y"),
        d["quadrant"],
        [_fmt_dollar(v) for v in d["dollar_vol"]],
        d["vol_share"].fillna(0), d["volatility"].fillna(0),
    ))


def _label_positions(heads: list[tuple[float, float]],
                     pad: float) -> list[str]:
    """Pick a text position per head so labels of bunched sectors don't
    overlap: nearby heads cycle top → bottom → right → left."""
    cycle = ["top center", "bottom center", "middle right", "middle left"]
    placed: list[tuple[float, float, str]] = []
    out = []
    for x, y in heads:
        pos = cycle[0]
        near = [p for px, py, p in placed
                if abs(x - px) < pad * 0.16 and abs(y - py) < pad * 0.12]
        for cand in cycle:
            if cand not in near:
                pos = cand
                break
        placed.append((x, y, pos))
        out.append(pos)
    return out


def _sector_traces(d: pd.DataFrame, ticker: str, name: str, color: str,
                   th: dict, textposition: str = "top center",
                   ) -> tuple[go.Scatter, go.Scatter]:
    """(trail, head) traces for one sector from a date-sorted slice `d`."""
    n = len(d)
    custom = _customdata(d, name)

    trail = go.Scatter(
        x=d["rs_ratio"], y=d["rs_momentum"],
        mode="lines+markers", legendgroup=ticker, showlegend=False,
        line=dict(color=_rgba(color, 0.65), width=1.6,
                  shape="spline", smoothing=0.8),
        marker=dict(color=color, size=4,
                    opacity=[0.2 + 0.5 * k / max(n - 1, 1)
                             for k in range(n)]),
        customdata=custom, hovertemplate=HOVER, name=name,
    )

    h = d.iloc[-1]
    head = go.Scatter(
        x=[h["rs_ratio"]], y=[h["rs_momentum"]],
        mode="markers+text", legendgroup=ticker, name=name,
        marker=dict(color=color, size=_bubble_px(h["vol_share"]),
                    line=dict(color=th["surface"], width=1.5)),
        text=[f"<b>{config.display_ticker(ticker)}</b>"],
        textposition=textposition,
        textfont=dict(size=11, color=th["ink"]),
        customdata=[custom[-1]], hovertemplate=HOVER,
    )
    return trail, head


def _add_quadrants(fig: go.Figure, th: dict, lo: float, hi: float) -> None:
    """Tinted quadrant rectangles, corner labels, crosshair at 100/100."""
    qa = th["quadrant_alpha"]
    quads = [  # (name, x0, x1, y0, y1, label-x, label-y, anchor)
        ("Leading",   100, hi, 100, hi, hi, hi, "right"),
        ("Weakening", 100, hi, lo, 100, hi, lo, "right"),
        ("Lagging",   lo, 100, lo, 100, lo, lo, "left"),
        ("Improving", lo, 100, 100, hi, lo, hi, "left"),
    ]
    for name, x0, x1, y0, y1, lx, ly, anchor in quads:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=_rgba(config.QUADRANT_COLORS[name], qa),
                      line_width=0, layer="below")
        fig.add_annotation(x=lx, y=ly, text=f"<b>{name.upper()}</b>",
                           showarrow=False, xanchor=anchor,
                           yanchor="top" if ly == hi else "bottom",
                           xshift=-10 if anchor == "right" else 10,
                           yshift=-8 if ly == hi else 8, opacity=0.9,
                           font=dict(size=11, color=th["muted"]))
    fig.add_shape(type="line", x0=100, x1=100, y0=lo, y1=hi,
                  line=dict(color=th["axisline"], width=1), layer="below")
    fig.add_shape(type="line", x0=lo, x1=hi, y0=100, y1=100,
                  line=dict(color=th["axisline"], width=1), layer="below")


def _apply_layout(fig: go.Figure, th: dict, subtitle: str, lo: float,
                  hi: float, benchmark: str, bottom_margin: int = 115) -> None:
    fig.update_layout(
        title=dict(
            text=(f"<b>{config.LABEL} — RRG vs {benchmark}</b>"
                  f"<br><sup>{subtitle}</sup>"),
            font=dict(size=20, color=th["ink"]), x=0.02, xanchor="left"),
        paper_bgcolor=th["page"], plot_bgcolor=th["surface"],
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=th["ink2"], size=12),
        xaxis=dict(title=dict(text="JdK RS-Ratio  (relative strength →)",
                              font=dict(size=12, color=th["ink2"])),
                   range=[lo, hi], gridcolor=th["grid"], griddash="dot",
                   dtick=1, zeroline=False,
                   linecolor=th["axisline"], mirror=True, ticks="outside",
                   tickcolor=th["axisline"],
                   tickfont=dict(size=11, color=th["muted"]),
                   constrain="domain"),
        yaxis=dict(title=dict(text="JdK RS-Momentum  (improving →)",
                              font=dict(size=12, color=th["ink2"])),
                   range=[lo, hi], gridcolor=th["grid"], griddash="dot",
                   dtick=1, zeroline=False,
                   linecolor=th["axisline"], mirror=True, ticks="outside",
                   tickcolor=th["axisline"],
                   tickfont=dict(size=11, color=th["muted"]),
                   scaleanchor="x", scaleratio=1),
        legend=dict(orientation="v", x=1.02, y=1, xanchor="left",
                    font=dict(size=11, color=th["ink2"]),
                    bgcolor=_rgba(th["surface"], 0.0)),
        margin=dict(l=70, r=210, t=90, b=bottom_margin),
        width=980, height=880,
        hoverlabel=dict(bgcolor=th["surface"], bordercolor=th["axisline"],
                        font=dict(color=th["ink"], size=12)),
    )
    fig.add_annotation(
        text=("Bubble size = share of universe avg $ volume"
              " (20-period rolling) · Source: Yahoo Finance"
              " · Click legend to isolate sectors"),
        xref="paper", yref="paper", x=0, y=-0.135, showarrow=False,
        xanchor="left", font=dict(size=10, color=th["muted"]))


# ── static chart ─────────────────────────────────────────────────────────────

def make_rrg_figure(table: pd.DataFrame, *, timeframe_label: str = "Weekly",
                    tail: int = 12, theme: str | None = None,
                    benchmark: str = "SPY") -> go.Figure:
    """Build the static RRG figure from the tidy build_rrg_table output."""
    theme = theme or config.DEFAULT_THEME
    th = config.THEMES[theme]
    palette = config.PALETTE[theme]
    snap = latest_snapshot(table, tail)
    as_of = snap["date"].max()
    pad = _axis_range(snap)
    lo, hi = 100 - pad, 100 + pad

    fig = go.Figure()
    _add_quadrants(fig, th, lo, hi)
    slices = [(i, t, n, snap[snap["ticker"] == t].sort_values("date"))
              for i, (t, n) in enumerate(config.SECTORS.items())]
    slices = [s for s in slices if not s[3].empty]
    positions = _label_positions(
        [(d.iloc[-1]["rs_ratio"], d.iloc[-1]["rs_momentum"])
         for *_, d in slices], pad)
    for (i, ticker, name, d), pos in zip(slices, positions):
        trail, head = _sector_traces(d, ticker, name,
                                     palette[i % len(palette)], th,
                                     textposition=pos)
        fig.add_trace(trail)
        fig.add_trace(head)

    _apply_layout(fig, th,
                  f"{timeframe_label} · JdK RS-Ratio vs RS-Momentum"
                  f" · tail {tail} · as of {as_of:%d %b %Y}",
                  lo, hi, benchmark)
    return fig


# ── animated chart ───────────────────────────────────────────────────────────

def make_rrg_animation(table: pd.DataFrame, *, timeframe_label: str = "Weekly",
                       tail: int = 12, theme: str | None = None,
                       benchmark: str = "SPY", n_frames: int = 40,
                       frame_ms: int = 400) -> go.Figure:
    """RRG animated over the last `n_frames` periods: each frame shows every
    sector's trail up to that date. Play/pause buttons + a date slider.

    For video: press play and screen-record, or scrub the slider to a date
    while narrating. Axis range is fixed across ALL frames so the camera
    never jumps.
    """
    theme = theme or config.DEFAULT_THEME
    th = config.THEMES[theme]
    palette = config.PALETTE[theme]

    table = table.sort_values("date")
    dates = sorted(table["date"].unique())
    # first animatable date needs `tail` points of history behind it
    n_frames = min(n_frames, len(dates) - tail - 1)
    frame_dates = dates[-n_frames:]

    # fixed axis range over everything the animation will ever show
    span = table[table["date"] >= dates[-(n_frames + tail)]]
    pad = _axis_range(span)
    lo, hi = 100 - pad, 100 + pad

    by_ticker = {t: g.sort_values("date").reset_index(drop=True)
                 for t, g in table.groupby("ticker")}

    def frame_traces(end_date) -> list[go.Scatter]:
        slices = []
        for i, (ticker, name) in enumerate(config.SECTORS.items()):
            g = by_ticker.get(ticker)
            if g is None:
                continue
            d = g[g["date"] <= end_date].tail(tail + 1)
            if d.empty:
                continue
            slices.append((i, ticker, name, d))
        positions = _label_positions(
            [(d.iloc[-1]["rs_ratio"], d.iloc[-1]["rs_momentum"])
             for *_, d in slices], pad)
        traces = []
        for (i, ticker, name, d), pos in zip(slices, positions):
            traces.extend(_sector_traces(d, ticker, name,
                                         palette[i % len(palette)], th,
                                         textposition=pos))
        return traces

    fig = go.Figure(data=frame_traces(frame_dates[0]))
    _add_quadrants(fig, th, lo, hi)

    fmt = "%d %b %Y"
    frames, steps = [], []
    for dt in frame_dates:
        label = pd.Timestamp(dt).strftime(fmt)
        frames.append(go.Frame(data=frame_traces(dt), name=label))
        steps.append(dict(method="animate", label=label,
                          args=[[label], dict(mode="immediate",
                                              frame=dict(duration=0, redraw=False),
                                              transition=dict(duration=0))]))
    fig.frames = frames

    _apply_layout(fig, th,
                  f"{timeframe_label} · JdK RS-Ratio vs RS-Momentum"
                  f" · tail {tail} · animated, last {len(frame_dates)} periods",
                  lo, hi, benchmark, bottom_margin=170)

    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="left",
            x=0, y=-0.16, xanchor="left", yanchor="top", pad=dict(t=8),
            bgcolor=th["surface"], bordercolor=th["axisline"],
            font=dict(color=th["ink"], size=13),
            buttons=[
                dict(label="▶  Play", method="animate",
                     args=[None, dict(mode="immediate", fromcurrent=True,
                                      frame=dict(duration=frame_ms, redraw=False),
                                      transition=dict(duration=int(frame_ms * 0.8),
                                                      easing="cubic-in-out"))]),
                dict(label="⏸  Pause", method="animate",
                     args=[[None], dict(mode="immediate",
                                        frame=dict(duration=0, redraw=False),
                                        transition=dict(duration=0))]),
            ])],
        sliders=[dict(
            active=0, x=0.22, y=-0.155, xanchor="left", yanchor="top",
            len=0.78, pad=dict(t=4),
            currentvalue=dict(prefix="as of ", visible=True,
                              font=dict(size=13, color=th["ink"])),
            font=dict(size=9, color=th["muted"]),
            bordercolor=th["axisline"], bgcolor=th["grid"],
            tickcolor=th["axisline"],
            steps=steps)],
    )
    return fig


def save_html(fig: go.Figure, path: str) -> None:
    """Self-contained HTML (plotly.js inlined) — works offline, safe for
    screenshots. The camera icon in the toolbar exports a 2x PNG."""
    fig.write_html(path, include_plotlyjs=True,
                   config={"displaylogo": False,
                           "toImageButtonOptions": {"format": "png", "scale": 2}})
