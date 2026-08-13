"""
update.py — one-command refresh of the RRG charts.

Usage:
    python update.py                     # weekly + daily charts from Yahoo
    python update.py --timeframe weekly  # just one timeframe
    python update.py --theme light       # light theme (default: config)
    python update.py --tail 8            # shorter trails
    python update.py --sample            # offline demo with synthetic data

Outputs into ./output/:
    rrg_weekly.html / rrg_daily.html     interactive charts (self-contained)
    rrg_weekly.csv  / rrg_daily.csv      latest snapshot table (the "table
                                         view" companion to the chart)
and prints a quadrant summary to the console.
"""

from __future__ import annotations

import argparse
import os

import pandas as pd

import config
from alerts import append_new, detect_events
from rrg import (build_rrg_table, conviction_metrics, download_prices,
                 latest_snapshot)
from plot_rrg import make_rrg_animation, make_rrg_figure, save_html

ARROWS = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"]  # heading glyphs, 45° steps


def run(timeframe: str, close, volume, theme: str, tail: int | None,
        animate: bool = False, n_frames: int = 40) -> pd.DataFrame:
    tf = config.TIMEFRAMES[timeframe]
    tail = tail or tf["tail"]
    table = build_rrg_table(close, volume, config.BENCHMARK, tf)

    fig = make_rrg_figure(table, timeframe_label=tf["label"], tail=tail,
                          theme=theme, benchmark=config.BENCHMARK_LABEL)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    html_path = os.path.join(config.OUTPUT_DIR, f"rrg_{timeframe}.html")
    csv_path = os.path.join(config.OUTPUT_DIR, f"rrg_{timeframe}.csv")
    save_html(fig, html_path)
    latest_snapshot(table, tail).to_csv(csv_path, index=False)

    # longer history for the dashboard's timeline scrubber
    n_hist = config.HISTORY_PERIODS.get(timeframe, 78)
    (table.sort_values("date").groupby("ticker", group_keys=False)
          .tail(n_hist)
          .to_csv(os.path.join(config.OUTPUT_DIR,
                               f"rrg_{timeframe}_history.csv"), index=False))

    anim_path = None
    if animate:
        anim = make_rrg_animation(table, timeframe_label=tf["label"],
                                  tail=tail, theme=theme,
                                  benchmark=config.BENCHMARK_LABEL,
                                  n_frames=n_frames)
        anim_path = os.path.join(config.OUTPUT_DIR,
                                 f"rrg_{timeframe}_anim.html")
        save_html(anim, anim_path)

    print(f"\n=== {config.LABEL} · {tf['label']} — quadrant summary "
          f"(as of {table['date'].max():%Y-%m-%d}) ===")
    summ = summary(table)
    print(summ.to_string(index=False))
    summ.to_csv(os.path.join(config.OUTPUT_DIR,
                             f"rrg_{timeframe}_summary.csv"), index=False)
    events = detect_events(table, tf["label"].lower())
    fresh = append_new(events, os.path.join(config.OUTPUT_DIR, "alerts.log"))
    if fresh:
        print(f"\n*** ROTATION ALERTS ({len(fresh)} new) ***")
        for e in fresh:
            print(f"  {e}")
    else:
        print("\nno new rotation alerts")

    print(f"chart: {html_path}\ntable: {csv_path}")
    if anim_path:
        print(f"animation: {anim_path}")
    return summ


def summary(table: pd.DataFrame) -> pd.DataFrame:
    """Per-sector one-liner: quadrant, position, direction, and the
    conviction metrics (tail velocity / straightness / heading angle)."""
    rows = []
    for ticker, name in config.SECTORS.items():
        d = table[table["ticker"] == ticker].sort_values("date")
        if len(d) < 2:
            continue
        cur, prev = d.iloc[-1], d.iloc[-2]
        rows.append({
            "ticker": ticker, "sector": name, "quadrant": cur["quadrant"],
            "rs_ratio": round(cur["rs_ratio"], 2),
            "rs_momentum": round(cur["rs_momentum"], 2),
            "heading": ("improving" if cur["rs_momentum"] > prev["rs_momentum"]
                        else "fading"),
        })
    df = pd.DataFrame(rows)

    met = conviction_metrics(table)
    df = df.merge(met, on="ticker", how="left")
    df["velocity"] = df["velocity"].round(2)
    df["straightness"] = df["straightness"].round(2)
    df["dir"] = [f"{ARROWS[int(round(h / 45)) % 8]} {h:3.0f}°"
                 if pd.notna(h) else "n/a" for h in df["heading_deg"]]
    df = df.drop(columns="heading_deg")

    order = ["Leading", "Improving", "Weakening", "Lagging"]
    df["_q"] = df["quadrant"].map(order.index)
    return (df.sort_values(["_q", "rs_ratio"], ascending=[True, False])
              .drop(columns="_q"))


def agreement(weekly: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Cross-check the two timeframes: 'weekly decides, daily times'.

    aligned ..... same quadrant on both — act with confidence
    partial ..... different quadrant but same heading — transition in progress
    diverging ... daily contradicts weekly — stand aside / wait
    """
    w = weekly.set_index("ticker")
    d = daily.set_index("ticker")
    rows = []
    for t in w.index:
        if t not in d.index:
            continue
        if w.at[t, "quadrant"] == d.at[t, "quadrant"]:
            verdict = "aligned"
        elif w.at[t, "heading"] == d.at[t, "heading"]:
            verdict = "partial"
        else:
            verdict = "diverging"
        rows.append({"ticker": t, "sector": w.at[t, "sector"],
                     "weekly": w.at[t, "quadrant"],
                     "daily": d.at[t, "quadrant"], "verdict": verdict})
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Refresh US sector rotation RRGs")
    p.add_argument("--timeframe", choices=[*config.TIMEFRAMES, "all"],
                   default="all")
    p.add_argument("--theme", choices=["light", "dark"],
                   default=config.DEFAULT_THEME)
    p.add_argument("--tail", type=int, default=None,
                   help="trail length in periods (default per timeframe)")
    p.add_argument("--sample", action="store_true",
                   help="use synthetic offline data instead of Yahoo")
    p.add_argument("--animate", action="store_true",
                   help="also write rrg_<timeframe>_anim.html with a "
                        "play button + date slider")
    p.add_argument("--frames", type=int, default=40,
                   help="animation length in periods (default 40)")
    p.add_argument("--universe", choices=list(config.UNIVERSES),
                   default=config.DEFAULT_UNIVERSE,
                   help="what to plot (default: %(default)s)")
    args = p.parse_args()
    config.activate(args.universe)
    print(f"universe: {config.LABEL} "
          f"({len(config.SECTORS)} members vs {config.BENCHMARK_LABEL})")

    if args.sample:
        from sample_data import generate
        close, volume = generate()
        print("using synthetic sample data (offline mode)")
    else:
        period = max((tf["period"] for tf in config.TIMEFRAMES.values()),
                     key=lambda s: int(s.rstrip("ymo") or 0))
        close, volume = download_prices(list(config.SECTORS),
                                        config.BENCHMARK, period=period)
        print(f"downloaded {len(close)} daily bars "
              f"({close.index[0]:%Y-%m-%d} → {close.index[-1]:%Y-%m-%d})")

    frames = list(config.TIMEFRAMES) if args.timeframe == "all" \
        else [args.timeframe]
    summaries = {}
    for tfname in frames:
        summaries[tfname] = run(tfname, close, volume, args.theme, args.tail,
                                animate=args.animate, n_frames=args.frames)

    if {"weekly", "daily"} <= summaries.keys():
        agree = agreement(summaries["weekly"], summaries["daily"])
        print("\n=== Timeframe agreement (weekly decides, daily times) ===")
        print(agree.to_string(index=False))
        agree.to_csv(os.path.join(config.OUTPUT_DIR, "rrg_agreement.csv"),
                     index=False)


if __name__ == "__main__":
    main()
