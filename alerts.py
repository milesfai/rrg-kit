"""
alerts.py — rotation event detection.

Derives discrete EVENTS from the RRG table by comparing the latest bar with
the ones before it, per sector:

  * quadrant crossing ....... "Weakening → Lagging" (the headline signal)
  * momentum reversal ....... heading flipped up/down vs the prior bar
                              (early warning, one bar before it shows in
                              quadrant terms)
  * confirmed leadership .... crossed INTO Leading while its share of
                              universe dollar volume is rising (rotation
                              backed by money, not just price drift)

Events are plain strings; update.py appends the new ones to
output/alerts.log (deduped — reruns on the same bar don't repeat).
"""

from __future__ import annotations

import pandas as pd

import config


# thresholds that keep intraday wobble out of the log
MIN_FLIP = 0.15      # momentum reversal must move at least this much
MIN_CLEARANCE = 0.05  # a quadrant crossing must clear the axis by this much

Event = tuple[str, str]  # (stable dedup key, human-readable line)


def detect_events(table: pd.DataFrame, tf_label: str) -> list[Event]:
    """Events triggered on the latest bar of `table` (one timeframe).

    Each event carries a stable key (no coordinates in it) so reruns on the
    same bar — including intraday refreshes where prices drift — do not
    re-fire the same alert with slightly different numbers.
    """
    events: list[Event] = []
    for ticker, name in config.SECTORS.items():
        d = table[table["ticker"] == ticker].sort_values("date")
        if len(d) < 4:
            continue
        t0, t1, t2 = d.iloc[-1], d.iloc[-2], d.iloc[-3]
        when = f"{t0['date']:%Y-%m-%d}"
        where = (f"(ratio {t0['rs_ratio']:.2f}, mom {t0['rs_momentum']:.2f})")

        # quadrant crossing — the headline event. Require the position to
        # have actually cleared the crossed axis, not just kissed it.
        if t0["quadrant"] != t1["quadrant"]:
            clears = min(abs(t0["rs_ratio"] - 100), abs(t0["rs_momentum"] - 100))
            if clears >= MIN_CLEARANCE:
                line = (f"{when} [{tf_label}] {ticker} {name}: "
                        f"{t1['quadrant']} → {t0['quadrant']} {where}")
                # crossing INTO Leading with rising volume share = confirmed
                if t0["quadrant"] == "Leading":
                    vs = d["vol_share"].tail(4)
                    if vs.notna().all() and vs.iloc[-1] > vs.iloc[0]:
                        line += " — volume share rising, CONFIRMED"
                events.append((f"{when}|{tf_label}|{ticker}|cross|"
                               f"{t1['quadrant']}>{t0['quadrant']}", line))

        # momentum reversal — heading flipped vs prior bar, by enough to mean it
        chg_now = t0["rs_momentum"] - t1["rs_momentum"]
        chg_prev = t1["rs_momentum"] - t2["rs_momentum"]
        if chg_now * chg_prev < 0 and abs(chg_now) >= MIN_FLIP:
            direction = "UP" if chg_now > 0 else "DOWN"
            events.append((f"{when}|{tf_label}|{ticker}|flip|{direction}",
                           f"{when} [{tf_label}] {ticker} {name}: momentum "
                           f"turned {direction} in {t0['quadrant']} {where}"))
    return events


def append_new(events: list[Event], log_path: str) -> list[str]:
    """Append events whose KEY hasn't been logged; return the new lines.

    Keys live in a sidecar file (<log>.seen) so the log itself stays a clean
    human-readable record.
    """
    seen_path = log_path + ".seen"
    try:
        with open(seen_path) as f:
            seen = set(f.read().splitlines())
    except FileNotFoundError:
        seen = set()
    fresh = [(k, line) for k, line in events if k not in seen]
    if fresh:
        with open(log_path, "a") as f:
            f.write("\n".join(line for _, line in fresh) + "\n")
        with open(seen_path, "a") as f:
            f.write("\n".join(k for k, _ in fresh) + "\n")
    return [line for _, line in fresh]
