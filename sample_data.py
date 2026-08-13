"""
sample_data.py — synthetic prices/volumes for offline demos and testing.

Generates a benchmark plus sector series whose relative strength slowly
rotates (sine-phased drift per sector), so the RRG shows realistic clockwise
trails without any network access. Deterministic (fixed seed).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


def generate(period_days: int = 756, seed: int = 7):
    """Return (close, volume) shaped like rrg.download_prices output."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(),
                           periods=period_days)
    n = len(dates)
    t = np.arange(n)

    bench_ret = 0.0004 + 0.010 * rng.standard_normal(n)
    bench = 400 * np.exp(np.cumsum(bench_ret))

    tickers = list(config.SECTORS)
    close = {config.BENCHMARK: bench}
    volume = {}
    for i, tk in enumerate(tickers):
        phase = 2 * np.pi * i / len(tickers)
        # relative drift rotates over ~ 1 year so sectors cycle quadrants
        rel_drift = 0.0009 * np.sin(2 * np.pi * t / 252 + phase)
        ret = bench_ret + rel_drift + 0.006 * rng.standard_normal(n)
        close[tk] = 100 * np.exp(np.cumsum(ret))
        base_vol = rng.uniform(4e6, 4e7)
        volume[tk] = (base_vol * np.exp(0.3 * rng.standard_normal(n))).round()

    idx = pd.DatetimeIndex(dates, name="Date")
    return (pd.DataFrame(close, index=idx),
            pd.DataFrame(volume, index=idx))
