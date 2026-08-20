"""
rrg.py — data download and JdK RS-Ratio / RS-Momentum calculation.

The exact JdK formulas (Julius de Kempenaer, Relative Rotation Graphs) are
proprietary. This module implements the standard public approximation used by
most open RRG tools, which reproduces the qualitative behavior (clockwise
rotation through the four quadrants, values normalized around 100):

  1. Relative strength:        RS      = 100 * price_sector / price_benchmark
  2. JdK RS-Ratio (x-axis):    ratio   = 100 + z-score of RS over a rolling
                                          window  -> >100 means the sector is
                                          strong RELATIVE TO ITS OWN RECENT
                                          RANGE vs the benchmark
  3. JdK RS-Momentum (y-axis): mom     = 100 + z-score of the rate-of-change
                                          of RS-Ratio -> >100 means relative
                                          strength is still ACCELERATING

Because both axes are z-scores, "100" is always the sector's own recent
average — the chart shows the trend OF the relative trend, which is what
makes RRG rotation readable.
"""

from __future__ import annotations

import pandas as pd

import config


# ── data ─────────────────────────────────────────────────────────────────────

def synthetic_index(close: pd.DataFrame, members: list[str],
                    kind: str = "EW") -> pd.Series:
    """Build a benchmark out of the members instead of downloading one.

    "EW" — equal-weight, rebalanced every bar: the return of the *typical*
    member. Against it, 100 means "in line with the average market", which
    asks a breadth question a cap-weighted index cannot: is strength broad,
    or concentrated in whatever dominates the cap-weighted index?

    Only dates where every member trades are used, so the basket's membership
    never silently changes underneath the series.
    """
    if kind != "EW":
        raise SystemExit(f"unknown synthetic benchmark {kind!r}")
    panel = close[members].dropna(how="any")
    rets = panel.pct_change().mean(axis=1)          # equal weight = mean return
    idx = 100 * (1 + rets.fillna(0)).cumprod()
    return idx.reindex(close.index)


def download_prices(tickers: list[str], benchmark: str, period: str = "3y"):
    """Download adjusted close and volume for tickers + benchmark from Yahoo.

    Returns (close, volume): two DataFrames indexed by date, one column per
    ticker (benchmark included in `close`, excluded from `volume`). A
    benchmark whose name starts with "=" is not downloaded — it is computed
    from the members (see synthetic_index).
    """
    import yfinance as yf

    synthetic = benchmark.startswith("=")
    to_fetch = list(dict.fromkeys(tickers if synthetic
                                  else tickers + [benchmark]))
    raw = yf.download(to_fetch, period=period, interval="1d",
                      auto_adjust=True, progress=False)
    close = raw["Close"][to_fetch].dropna(how="all")
    volume = raw["Volume"][tickers].reindex(close.index)
    # Yahoo throttles datacenter IPs by dropping symbols from the response
    # rather than erroring, and yfinance turns each dropped symbol into an
    # all-NaN column. Everything downstream tolerates that — rrg() drops NaN
    # rows, update.py skips series shorter than 2 bars, make_dashboard.py
    # skips empty ones — so the run would exit 0 and publish a clean-looking
    # chart quietly missing members, with CI's retry loop never firing. A
    # missing constituent is a WRONG chart, not a thin one. Checked here,
    # before synthetic_index: `close[members].dropna(how="any")` turns one
    # NaN member into an all-NaN =EW benchmark, which blanks the universe.
    have = close.notna().sum()
    typical = have[have > 0].median()
    dead = [c for c in to_fetch if have.get(c, 0) == 0]
    thin = [c for c in to_fetch if 0 < have.get(c, 0) < 0.8 * typical]
    if dead or thin:
        raise SystemExit(
            f"incomplete Yahoo download — no data: {dead or '[]'}; short "
            f"history: {thin or '[]'}. Usually throttling; rerunning is the "
            f"first thing to try. If a symbol is permanently retired or "
            f"renumbered, remove it from config.UNIVERSES.")
    if synthetic:
        close = close.copy()
        close[benchmark] = synthetic_index(close, tickers, benchmark[1:])
    return close, volume


def resample_ohlc(close: pd.DataFrame, volume: pd.DataFrame, rule: str | None):
    """Resample daily bars to e.g. weekly ('W-FRI'). Close takes the last bar
    of the period, volume the period sum. rule=None returns inputs unchanged."""
    if rule is None:
        return close, volume
    rc = close.resample(rule).last().dropna(how="all")
    rv = volume.resample(rule).sum(min_count=1).reindex(rc.index)
    # the last bin is labeled by its END (e.g. Friday) even when the latest
    # bar is earlier in the week — clamp so "as of" never shows a future date
    last = close.index.max()
    rc.index = rc.index.where(rc.index <= last, last)
    rv.index = rc.index
    return rc, rv


# ── JdK approximation ────────────────────────────────────────────────────────

def _roll_z(s: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling z-score: how far today's value sits from its own trailing
    mean, in units of trailing standard deviation."""
    mean = s.rolling(window).mean()
    std = s.rolling(window).std(ddof=0)
    return (s - mean) / std


def jdk_rs_ratio(prices: pd.DataFrame, benchmark: pd.Series,
                 window: int, smooth: int = 1) -> pd.DataFrame:
    """JdK RS-Ratio (x-axis), normalized around 100.

    RS = 100 * price / benchmark measures relative performance; the rolling
    z-score re-expresses it as "strong or weak vs its own recent history",
    which puts every sector on the same 100-centered scale.
    """
    rs = 100 * prices.div(benchmark, axis=0)
    if smooth > 1:
        rs = rs.rolling(smooth).mean()
    return 100 + _roll_z(rs, window)


def jdk_rs_momentum(rs_ratio: pd.DataFrame, window: int,
                    momentum_period: int = 4) -> pd.DataFrame:
    """JdK RS-Momentum (y-axis), normalized around 100.

    Momentum is the rate of change of RS-Ratio over `momentum_period` bars —
    the "trend of the relative trend". It is z-scored over the same rolling
    window so 100 = flat relative strength, >100 = improving, <100 = fading.
    Momentum crosses 100 BEFORE ratio does, which is why sectors rotate
    clockwise: Improving -> Leading -> Weakening -> Lagging.
    """
    roc = rs_ratio.diff(momentum_period)
    return 100 + _roll_z(roc, window)


def quadrant(x: float, y: float) -> str:
    """Map an (RS-Ratio, RS-Momentum) point to its RRG quadrant."""
    if x >= 100 and y >= 100:
        return "Leading"
    if x >= 100:
        return "Weakening"
    if y >= 100:
        return "Improving"
    return "Lagging"


# ── assembled table ──────────────────────────────────────────────────────────

def build_rrg_table(close: pd.DataFrame, volume: pd.DataFrame,
                    benchmark: str, tf: dict) -> pd.DataFrame:
    """Compute everything the chart needs, as one tidy DataFrame.

    Columns: date, ticker, rs_ratio, rs_momentum, quadrant,
             dollar_vol (rolling avg $ volume), vol_share (share of universe),
             volatility (annualized realized vol).
    """
    close, volume = resample_ohlc(close, volume, tf["resample"])
    tickers = [t for t in close.columns if t != benchmark]

    ratio = jdk_rs_ratio(close[tickers], close[benchmark],
                         window=tf["window"], smooth=tf["smooth"])
    mom = jdk_rs_momentum(ratio, window=tf["window"],
                          momentum_period=tf["momentum_period"])

    # 3rd dimension — turnover: rolling average dollar volume, and each
    # sector's share of the universe total (drives bubble size).
    dollar_vol = (close[tickers] * volume[tickers]).rolling(tf["vol_window"]).mean()
    vol_share = dollar_vol.div(dollar_vol.sum(axis=1), axis=0)

    # 4th dimension — risk: annualized realized volatility of sector returns.
    rets = close[tickers].pct_change()
    volatility = rets.rolling(tf["vol_window"]).std(ddof=0) * (tf["ann_factor"] ** 0.5)

    frames = []
    for t in tickers:
        frames.append(pd.DataFrame({
            "date": close.index, "ticker": t,
            "rs_ratio": ratio[t].values, "rs_momentum": mom[t].values,
            "dollar_vol": dollar_vol[t].values,
            "vol_share": vol_share[t].values,
            "volatility": volatility[t].values,
        }))
    table = pd.concat(frames, ignore_index=True).dropna(
        subset=["rs_ratio", "rs_momentum"])
    table["quadrant"] = [quadrant(x, y) for x, y in
                         zip(table["rs_ratio"], table["rs_momentum"])]
    return table


def latest_snapshot(table: pd.DataFrame, tail: int = 12) -> pd.DataFrame:
    """Trim the tidy table to the last `tail`+1 points per ticker (the trail
    plus the head)."""
    return (table.sort_values("date")
                 .groupby("ticker", group_keys=False)
                 .tail(tail + 1))


def conviction_metrics(table: pd.DataFrame, move_window: int = 4,
                       shape_window: int = 8) -> pd.DataFrame:
    """Quantify tail quality per sector — the numbers behind the visual
    "long straight tail = conviction" rule.

    velocity ....... net distance moved per bar over the last `move_window`
                     bars (in RRG units). Fast movement = decisive rotation.
    straightness ... net displacement / path length over the last
                     `shape_window` bars. 1.0 = dead straight (conviction);
                     near 0 = curling in place (noise).
    heading_deg .... direction of travel over `move_window`, 0 = due east
                     (gaining strength), 90 = due north (gaining momentum),
                     180 = losing strength, 270 = losing momentum.
    """
    import math

    rows = []
    for ticker, g in table.groupby("ticker"):
        g = g.sort_values("date")
        if len(g) < shape_window + 1:
            continue
        pts = g[["rs_ratio", "rs_momentum"]].to_numpy()

        mv = pts[-(move_window + 1):]
        net_x, net_y = mv[-1] - mv[0]
        velocity = math.hypot(net_x, net_y) / move_window
        heading = math.degrees(math.atan2(net_y, net_x)) % 360

        sh = pts[-(shape_window + 1):]
        path = sum(math.hypot(*(sh[i + 1] - sh[i])) for i in range(len(sh) - 1))
        net = math.hypot(*(sh[-1] - sh[0]))
        straightness = net / path if path > 0 else 0.0

        rows.append(dict(ticker=ticker, velocity=velocity,
                         straightness=straightness, heading_deg=heading))
    return pd.DataFrame(rows)
