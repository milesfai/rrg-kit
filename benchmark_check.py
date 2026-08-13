"""
benchmark_check.py — evidence for choosing a benchmark.

The benchmark defines the question an RRG answers, so this measures the
choice instead of arguing about it:

  1. What is the benchmark actually made of?  Regress the benchmark on a
     US proxy and an ex-US proxy: the fitted weights approximate its real
     country-cap composition, and R^2 vs the US alone shows how much the
     "world" benchmark is just America.
  2. How different are the candidates?  Correlation and tracking difference
     between ACWI / VT / VEU / URTH / equal-weight.
  3. Does it change the answer?  Recompute the RRG under each candidate and
     count how many members land in a different quadrant. If nothing moves,
     the choice is cosmetic; if a third of the board moves, it is the single
     most important setting in config.py.

    python3 benchmark_check.py --universe countries
"""

from __future__ import annotations

import argparse
import itertools
import os

import numpy as np
import pandas as pd

import config
from rrg import build_rrg_table, download_prices, quadrant

# Benchmark candidates to compare, beyond the universe's configured one.
CANDIDATES = {
    "ACWI": "MSCI All-Country World (dev + EM, cap-weighted)",
    "VT":   "Vanguard Total World (broader, incl. small cap)",
    "URTH": "MSCI World (developed markets only)",
    "VEU":  "FTSE All-World ex-US",
    "SPY":  "S&P 500 (US only)",
    "EQW":  "Equal-weight basket of this universe's members",
}


def composition(close: pd.DataFrame, bench: str) -> None:
    """Approximate what the benchmark is made of, from returns alone."""
    print(f"\n{'=' * 72}\n1. WHAT IS {bench} ACTUALLY MADE OF?\n{'=' * 72}")
    r = close.pct_change().dropna()
    if not {"SPY", "VEU"} <= set(r.columns):
        print("  (need SPY and VEU to decompose)")
        return

    y = r[bench].values
    # constrained two-factor fit: bench ~ w*US + (1-w)*exUS
    us, ex = r["SPY"].values, r["VEU"].values
    w = float(np.clip(np.dot(y - ex, us - ex) / np.dot(us - ex, us - ex), 0, 1))
    resid = y - (w * us + (1 - w) * ex)
    r2_two = 1 - resid.var() / y.var()

    # how much is explained by the US alone
    b_us = np.polyfit(us, y, 1)
    r2_us = np.corrcoef(us, y)[0, 1] ** 2

    print(f"  implied US weight            {w:6.1%}   "
          f"(ex-US {1 - w:.1%})")
    print(f"  fit quality of that split    R2 = {r2_two:.3f}")
    print(f"  explained by the US ALONE    R2 = {r2_us:.3f}  "
          f"(beta {b_us[0]:.2f})")
    print(f"\n  -> {bench} moves with the US {r2_us:.0%} of the time. A country")
    print(f"     'beating {bench}' is therefore mostly a statement about")
    print(f"     beating America, whether or not you intended that.")


def candidates(close: pd.DataFrame, members: list[str]) -> pd.DataFrame:
    """Correlation + annualised return/vol of each benchmark candidate."""
    print(f"\n{'=' * 72}\n2. HOW DIFFERENT ARE THE CANDIDATES?\n{'=' * 72}")
    have = [c for c in CANDIDATES if c in close.columns or c == "EQW"]
    px = close.copy()
    if "EQW" in have:
        # equal-weight basket, rebalanced daily (a "typical country" line)
        px["EQW"] = (px[members].pct_change().mean(axis=1)
                     .fillna(0).add(1).cumprod())
    r = px[have].pct_change().dropna()

    stats = pd.DataFrame({
        "ann_return": (r.mean() * 252),
        "ann_vol": (r.std() * np.sqrt(252)),
        "corr_vs_ACWI": r.corrwith(r["ACWI"]) if "ACWI" in r else np.nan,
    })
    stats["description"] = [CANDIDATES[c] for c in stats.index]
    print(stats.to_string(float_format=lambda v: f"{v:7.3f}"))

    print("\n  pairwise correlation of daily returns")
    print(r.corr().to_string(float_format=lambda v: f"{v:5.3f}"))
    return px


def sensitivity(close: pd.DataFrame, volume: pd.DataFrame,
                members: list[str], tf: dict) -> None:
    """Does the benchmark change which quadrant each member lands in?"""
    print(f"\n{'=' * 72}\n3. DOES THE CHOICE CHANGE THE ANSWER?\n{'=' * 72}")
    results = {}
    for cand in CANDIDATES:
        if cand not in close.columns:
            continue
        sub = close[[c for c in members if c != cand] + [cand]]
        vol = volume[[c for c in members if c != cand]]
        try:
            t = build_rrg_table(sub, vol, cand, tf)
        except Exception:
            continue
        last = t.sort_values("date").groupby("ticker").tail(1)
        results[cand] = dict(zip(last["ticker"], last["quadrant"]))

    if len(results) < 2:
        print("  not enough candidates downloaded to compare")
        return

    grid = pd.DataFrame(results)
    grid.index.name = "ticker"
    grid["names"] = [config.SECTORS.get(t, t) for t in grid.index]
    cols = [c for c in results]
    grid["n_distinct"] = grid[cols].nunique(axis=1)
    grid = grid.sort_values("n_distinct", ascending=False)
    print(grid[["names"] + cols + ["n_distinct"]].to_string())

    print("\n  quadrant disagreement between benchmark pairs "
          "(out of %d members)" % len(grid))
    for a, b in itertools.combinations(cols, 2):
        diff = int((grid[a] != grid[b]).sum())
        print(f"    {a:5s} vs {b:5s}   {diff:2d} differ  "
              f"({diff / len(grid):.0%})")

    moved = int((grid["n_distinct"] > 1).sum())
    verdict = ("a cosmetic choice — the picture is robust" if moved == 0 else
               "NOT cosmetic — it is the most consequential setting in "
               "config.py")
    print(f"\n  -> {moved} of {len(grid)} members ({moved / len(grid):.0%}) sit in a "
          f"different quadrant\n     depending on the benchmark. The benchmark "
          f"is {verdict}.")

    # Which readings survive the benchmark choice? That is what separates a
    # signal you can act on from one that is an artefact of the yardstick.
    print(f"\n{'=' * 72}\n4. WHICH READINGS ARE BENCHMARK-ROBUST?\n{'=' * 72}")
    robust = grid[grid["n_distinct"] == 1]
    fragile = grid[grid["n_distinct"] > 1]
    bench = config.BENCHMARK if config.BENCHMARK in cols else cols[0]

    print(f"  ROBUST — same quadrant under every benchmark tested "
          f"({len(robust)}):")
    for q in ["Leading", "Improving", "Weakening", "Lagging"]:
        names = [f"{t} {robust.at[t, 'names']}"
                 for t in robust.index if robust.at[t, bench] == q]
        if names:
            print(f"    {q:10s} {', '.join(names)}")

    print(f"\n  FRAGILE — quadrant depends on the yardstick ({len(fragile)}):")
    for t in fragile.index:
        seen = {grid.at[t, c] for c in cols if pd.notna(grid.at[t, c])}
        print(f"    {t:5s} {fragile.at[t, 'names']:16s} "
              f"{fragile.at[t, bench]:10s} under {bench}, but also "
              f"{', '.join(sorted(seen - {fragile.at[t, bench]}))}")
    print("\n  -> Treat the ROBUST list as the actionable board. A FRAGILE "
          "reading is\n     not wrong, it just means the conclusion is a "
          "statement about the\n     benchmark as much as about the market.")

    out = os.path.join(config.OUTPUT_DIR, "benchmark_robustness.csv")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    grid.to_csv(out)
    print(f"\n  saved: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark evidence for an RRG")
    ap.add_argument("--universe", choices=list(config.UNIVERSES),
                    default=config.DEFAULT_UNIVERSE)
    ap.add_argument("--timeframe", choices=list(config.TIMEFRAMES),
                    default="weekly")
    args = ap.parse_args()
    config.activate(args.universe)

    members = list(config.SECTORS)
    extra = [c for c in CANDIDATES if c != "EQW"]
    tickers = list(dict.fromkeys(members + extra))
    print(f"universe: {config.LABEL} ({len(members)} members), "
          f"configured benchmark {config.BENCHMARK}")
    close, volume = download_prices(tickers, config.BENCHMARK, period="3y")

    composition(close, config.BENCHMARK)
    px = candidates(close, members)
    sensitivity(px, volume, members, config.TIMEFRAMES[args.timeframe])


if __name__ == "__main__":
    main()
