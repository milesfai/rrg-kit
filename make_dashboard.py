"""
make_dashboard.py — build a self-contained, phone-friendly RRG dashboard.

Reads the CSVs and alerts.log that update.py writes, and emits ONE HTML file
with no external dependencies (no plotly, no CDN) — small enough to open
instantly on a phone and to publish as a hosted page.

    python3 make_dashboard.py            # -> output/dashboard.html

The page carries a TIMELINE: history for every sector is embedded, and the
chart, table, agreement verdicts and alert list are all rendered in the
browser for whatever date the slider is on. The desktop plotly charts stay
the working tool; this is the portable, scrubbable view.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re

import pandas as pd

import config

KIT_DIR = os.path.dirname(os.path.abspath(__file__))


def out_paths() -> tuple[str, str]:
    """(standalone, fragment) paths for the ACTIVE universe."""
    return (os.path.join(config.OUTPUT_DIR, "dashboard.html"),
            os.path.join(config.OUTPUT_DIR, "dashboard_fragment.html"))


def REFRESH_CMD() -> str:
    u = ("" if config.UNIVERSE == config.DEFAULT_UNIVERSE
         else f" --universe {config.UNIVERSE}")
    # The absolute `cd` is load-bearing locally and only there. The button
    # exists so a double-clicked output/<u>/dashboard.html can hand you a
    # command that pastes into a Terminal sitting anywhere, and OUTPUT_DIR
    # is relative (config.py:188), so the kit root has to be named. On a CI
    # build KIT_DIR is the runner's ephemeral checkout — /home/runner/work/…
    # — a path that exists on no reader's machine and not even on the runner
    # once the job ends. Publish the location-independent form there.
    where = "" if os.environ.get("GITHUB_ACTIONS") else f"cd {KIT_DIR} && "
    return (f"{where}python3 update.py{u} && "
            f"python3 make_dashboard.py{u}")

TAIL = 12          # trail length drawn behind the head
MOVE_W = 4         # bars for velocity / heading
SHAPE_W = 8        # bars for straightness


# ── data assembly ────────────────────────────────────────────────────────────

def load_timeframe(tf: str) -> dict | None:
    """History for one timeframe, aligned onto a single date axis.

    Returns {label, dates, dlabels, series:[{t,name,i,pts}]} where pts[k] is
    [rs_ratio, rs_momentum, vol_share, volatility] or null when that sector
    has no bar on dates[k].
    """
    hist_p = os.path.join(config.OUTPUT_DIR, f"rrg_{tf}_history.csv")
    snap_p = os.path.join(config.OUTPUT_DIR, f"rrg_{tf}.csv")
    path = hist_p if os.path.exists(hist_p) else snap_p
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    dates = sorted(df["date"].unique())
    index = {d: k for k, d in enumerate(dates)}

    series = []
    for i, (tk, name) in enumerate(config.SECTORS.items()):
        d = df[df["ticker"] == tk]
        if d.empty:
            continue
        pts: list = [None] * len(dates)
        for row in d.itertuples():
            pts[index[row.date]] = [
                round(float(row.rs_ratio), 2),
                round(float(row.rs_momentum), 2),
                round(float(row.vol_share), 4) if pd.notna(row.vol_share) else 0,
                round(float(row.volatility), 4) if pd.notna(row.volatility) else 0,
            ]
        series.append(dict(t=config.display_ticker(tk),
                           name=name, i=i, pts=pts))

    ts = [pd.Timestamp(d) for d in dates]
    return dict(label=config.TIMEFRAMES[tf]["label"],
                dates=[d.strftime("%Y-%m-%d") for d in ts],
                dlabels=[d.strftime("%d %b %Y") for d in ts],
                series=series)


def load_alerts(limit: int = 400) -> list[dict]:
    """All recent alerts, newest first, parsed so the page can filter by date."""
    p = os.path.join(config.OUTPUT_DIR, "alerts.log")
    if not os.path.exists(p):
        return []
    out = []
    pat = re.compile(r"^(\S+) \[(\w+)\] (\S+) ([^:]+): (.+?)( \(ratio.*)?$")
    for line in reversed([l for l in open(p).read().splitlines() if l.strip()]):
        m = pat.match(line)
        if not m:
            continue
        date, tf, tk, name, body, _ = m.groups()
        out.append(dict(date=date, tf=tf, ticker=tk, sector=name.strip(),
                        body=body.strip(), crossing="\u2192" in body,
                        confirmed="CONFIRMED" in body))
        if len(out) >= limit:
            break
    return out


def axis_pad(frames: list[dict]) -> float:
    """One symmetric half-span covering every point in every timeframe, so
    scrubbing the timeline never rescales the axes under you."""
    dev = 0.0
    for f in frames:
        for s in f["series"]:
            for p in s["pts"]:
                if p:
                    dev = max(dev, abs(p[0] - 100), abs(p[1] - 100))
    return max(2.0, dev * 1.10)


# ── page ─────────────────────────────────────────────────────────────────────

def build(frames: dict, alerts: list) -> str:
    sect_light = ";".join(f"--s{i}:{c}" for i, c in
                          enumerate(config.PALETTE["light"]))
    sect_dark = ";".join(f"--s{i}:{c}" for i, c in
                         enumerate(config.PALETTE["dark"]))

    payload = json.dumps({
        "frames": frames,
        "alerts": alerts,
        "pad": round(axis_pad(list(frames.values())), 3),
        "tail": TAIL, "moveW": MOVE_W, "shapeW": SHAPE_W,
        "benchmark": config.BENCHMARK_LABEL,
        "cmd": REFRESH_CMD(),
        "title": config.LABEL,
    }, separators=(",", ":"))

    tabs = "".join(
        f'<button role="tab" aria-selected="{str(k == "weekly").lower()}" '
        f'data-go="{k}">{v["label"]}</button>' for k, v in frames.items())

    return f"""<style>
:root {{
  color-scheme: light dark;
  {sect_light};
  --ground:#faf9f7; --surface:#ffffff; --sunk:#f2f1ee;
  --ink:#16181d; --ink2:#4d525b; --muted:#858b95;
  --line:#e2e0dc; --line2:#cfccc6;
  --leading:#2e7d4f; --improving:#3673b5; --weakening:#b8860b; --lagging:#b03a2e;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",sans-serif;
  --r:5px;
}}
@media (prefers-color-scheme:dark) {{
  :root {{
    {sect_dark};
    --ground:#14161a; --surface:#1b1e24; --sunk:#101216;
    --ink:#e6e8ec; --ink2:#a8aeb8; --muted:#767d88;
    --line:#272b33; --line2:#363b45;
    --leading:#4caf6a; --improving:#5b9bd5; --weakening:#d9a441; --lagging:#e06c5b;
  }}
}}
:root[data-theme="dark"] {{
  {sect_dark};
  --ground:#14161a; --surface:#1b1e24; --sunk:#101216;
  --ink:#e6e8ec; --ink2:#a8aeb8; --muted:#767d88;
  --line:#272b33; --line2:#363b45;
  --leading:#4caf6a; --improving:#5b9bd5; --weakening:#d9a441; --lagging:#e06c5b;
}}
:root[data-theme="light"] {{
  {sect_light};
  --ground:#faf9f7; --surface:#ffffff; --sunk:#f2f1ee;
  --ink:#16181d; --ink2:#4d525b; --muted:#858b95;
  --line:#e2e0dc; --line2:#cfccc6;
  --leading:#2e7d4f; --improving:#3673b5; --weakening:#b8860b; --lagging:#b03a2e;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--sans); font-size:15px; line-height:1.55;
  -webkit-text-size-adjust:100%; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:28px 20px 64px;
  display:flex; flex-direction:column; gap:22px; }}

header {{ display:flex; flex-direction:column; gap:10px;
  border-bottom:1px solid var(--line); padding-bottom:18px; }}
.eyebrow {{ font-family:var(--mono); font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); }}
h1 {{ margin:0; font-size:clamp(24px,4.6vw,34px); font-weight:650;
  letter-spacing:-.02em; text-wrap:balance; }}
.sub {{ color:var(--ink2); font-size:14px; max-width:62ch; margin:0; }}
.hrow {{ display:flex; align-items:center; justify-content:space-between;
  gap:16px; flex-wrap:wrap; }}

.btn {{ display:inline-flex; align-items:center; gap:8px; flex:none;
  font-family:var(--mono); font-size:11.5px; letter-spacing:.08em;
  text-transform:uppercase; padding:8px 14px; border-radius:var(--r);
  border:1px solid var(--line2); background:var(--surface); color:var(--ink);
  cursor:pointer; }}
.btn:hover:not(:disabled) {{ border-color:var(--muted); }}
.btn:focus-visible {{ outline:2px solid var(--improving); outline-offset:2px; }}
.btn:disabled {{ opacity:.55; cursor:default; }}
.btn-dot {{ width:6px; height:6px; border-radius:50%; background:var(--muted);
  flex:none; }}
.btn[data-mode="live"] .btn-dot {{ background:var(--leading); }}
.btn[data-mode="busy"] .btn-dot {{ background:var(--weakening); }}
@media (prefers-reduced-motion:no-preference) {{
  .btn[data-mode="busy"] .btn-dot {{ animation:pulse 1s ease-in-out infinite; }}
  @keyframes pulse {{ 50% {{ opacity:.25; }} }}
}}
.updmsg {{ font-family:var(--mono); font-size:12px; color:var(--ink2);
  background:var(--sunk); border:1px solid var(--line);
  border-left:2px solid var(--muted); border-radius:var(--r);
  padding:9px 12px; overflow-wrap:anywhere; }}
.updmsg.err {{ border-left-color:var(--lagging); color:var(--lagging); }}
.updmsg.ok {{ border-left-color:var(--leading); }}
.updmsg code {{ font-family:var(--mono); color:var(--ink);
  background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:1px 5px; display:inline-block; margin-top:4px;
  -webkit-user-select:all; user-select:all; }}

.strip {{ display:flex; flex-wrap:wrap; gap:0; border:1px solid var(--line);
  border-radius:var(--r); background:var(--surface); overflow:hidden; }}
.stat {{ flex:1 1 150px; padding:12px 16px; border-right:1px solid var(--line); }}
.stat:last-child {{ border-right:0; }}
.stat dt {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--muted); margin:0 0 3px; }}
.stat dd {{ margin:0; font-family:var(--mono); font-size:17px; font-weight:600;
  font-variant-numeric:tabular-nums; letter-spacing:-.01em; }}
.stat dd small {{ font-size:12px; font-weight:400; color:var(--ink2); }}

.panel {{ background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r); }}
.panel-h {{ display:flex; align-items:center; justify-content:space-between;
  gap:12px; padding:13px 16px; border-bottom:1px solid var(--line);
  flex-wrap:wrap; }}
.panel-h h2 {{ margin:0; font-size:13px; font-weight:600; letter-spacing:.04em;
  text-transform:uppercase; font-family:var(--mono); color:var(--ink2); }}

.tabs {{ display:flex; gap:2px; background:var(--sunk); padding:2px;
  border-radius:var(--r); }}
.tabs button {{ font-family:var(--mono); font-size:11.5px; letter-spacing:.08em;
  text-transform:uppercase; padding:5px 13px; border:0; border-radius:3px;
  background:transparent; color:var(--muted); cursor:pointer; }}
.tabs button[aria-selected="true"] {{ background:var(--surface); color:var(--ink);
  box-shadow:0 1px 2px rgba(0,0,0,.14); }}
.tabs button:focus-visible {{ outline:2px solid var(--improving);
  outline-offset:1px; }}

/* timeline */
.tl {{ display:flex; align-items:center; gap:12px; padding:12px 16px;
  border-bottom:1px solid var(--line); flex-wrap:wrap; }}
.tl-date {{ font-family:var(--mono); font-size:13px; font-weight:600;
  font-variant-numeric:tabular-nums; min-width:104px; }}
.tl-back {{ font-family:var(--mono); font-size:10.5px; color:var(--weakening);
  letter-spacing:.06em; text-transform:uppercase; }}
.tl-range {{ flex:1 1 220px; display:flex; align-items:center; }}
input[type=range] {{ width:100%; accent-color:var(--improving); height:22px;
  background:transparent; cursor:pointer; }}
input[type=range]:focus-visible {{ outline:2px solid var(--improving);
  outline-offset:3px; }}
.tl-btns {{ display:flex; gap:4px; }}
.tl-btns button {{ font-family:var(--mono); font-size:12px; min-width:30px;
  padding:4px 8px; border:1px solid var(--line2); border-radius:3px;
  background:var(--surface); color:var(--ink2); cursor:pointer; }}
.tl-btns button:hover:not(:disabled) {{ color:var(--ink);
  border-color:var(--muted); }}
.tl-btns button:disabled {{ opacity:.4; cursor:default; }}
.tl-btns button:focus-visible {{ outline:2px solid var(--improving);
  outline-offset:1px; }}

.chartwrap {{ padding:14px 12px 4px; }}
svg.rrg {{ width:100%; max-width:720px; height:auto; display:block;
  margin:0 auto; }}
.q {{ opacity:.055; }}
@media (prefers-color-scheme:dark) {{ .q {{ opacity:.085; }} }}
:root[data-theme="dark"] .q {{ opacity:.085; }}
:root[data-theme="light"] .q {{ opacity:.055; }}
.q-leading {{ fill:var(--leading); }} .q-improving {{ fill:var(--improving); }}
.q-weakening {{ fill:var(--weakening); }} .q-lagging {{ fill:var(--lagging); }}
.grid {{ stroke:var(--line); stroke-width:.6; stroke-dasharray:2 3; }}
.axis {{ stroke:var(--line2); stroke-width:.9; }}
.frame {{ fill:none; stroke:var(--line2); stroke-width:.7; }}
.tick {{ fill:var(--muted); font-family:var(--mono); font-size:10px;
  font-variant-numeric:tabular-nums; }}
.qlabel {{ fill:var(--muted); font-family:var(--mono); font-size:9.5px;
  letter-spacing:.16em; opacity:.75; }}
.axlabel {{ fill:var(--muted); font-family:var(--mono); font-size:9.5px;
  letter-spacing:.14em; }}
.trail {{ fill:none; stroke-width:1.5; stroke-opacity:.55;
  stroke-linejoin:round; stroke-linecap:round; }}
.bub {{ stroke:var(--surface); stroke-width:1.5; }}
.tk {{ fill:var(--ink); font-family:var(--mono); font-size:10.5px;
  font-weight:600; letter-spacing:.02em;
  paint-order:stroke fill; stroke:var(--surface); stroke-width:2.6px;
  stroke-linejoin:round; }}

.rot {{ display:inline-flex; align-items:center; gap:6px; }}
.rot svg {{ width:15px; height:15px; flex:none; }}
.rot circle {{ fill:none; stroke:var(--line2); stroke-width:.8;
  stroke-dasharray:2 2.5; }}
.rot path {{ fill:none; stroke:var(--muted); stroke-width:1.4;
  stroke-linecap:round; stroke-linejoin:round; }}

.tablewrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--line);
  white-space:nowrap; }}
thead th {{ font-family:var(--mono); font-size:10px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted); font-weight:500;
  border-bottom:1px solid var(--line2); }}
tbody tr:last-child td {{ border-bottom:0; }}
.num {{ text-align:right; font-family:var(--mono);
  font-variant-numeric:tabular-nums; }}
.c-tk b {{ font-family:var(--mono); font-size:12.5px; }}
.c-name {{ color:var(--ink2); margin-left:8px; font-size:12.5px; }}
.swatch {{ display:inline-block; width:9px; height:9px; border-radius:2px;
  margin-right:8px; vertical-align:baseline; }}
.dir {{ letter-spacing:.02em; color:var(--ink2); }}
.conv-high {{ color:var(--leading); font-weight:600; }}
.conv-low {{ color:var(--muted); }}

.pill {{ display:inline-block; font-family:var(--mono); font-size:10.5px;
  letter-spacing:.06em; text-transform:uppercase; padding:2px 8px;
  border-radius:99px; border:1px solid; }}
.p-leading {{ color:var(--leading); border-color:var(--leading); }}
.p-improving {{ color:var(--improving); border-color:var(--improving); }}
.p-weakening {{ color:var(--weakening); border-color:var(--weakening); }}
.p-lagging {{ color:var(--lagging); border-color:var(--lagging); }}

.cards {{ display:none; }}
.card {{ padding:12px 14px; border-bottom:1px solid var(--line); }}
.card:last-child {{ border-bottom:0; }}
.card-h {{ display:flex; align-items:center; gap:0; flex-wrap:wrap; }}
.card-h b {{ font-family:var(--mono); font-size:13px; }}
.card-h .pill {{ margin-left:auto; }}
.card-d {{ display:grid; grid-template-columns:repeat(5,1fr); gap:6px;
  margin:9px 0 0; }}
.card-d dt {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted); }}
.card-d dd {{ margin:1px 0 0; font-family:var(--mono); font-size:13px;
  font-variant-numeric:tabular-nums; }}

.agrid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(178px,1fr));
  gap:8px; padding:14px 16px; }}
.ag {{ display:flex; flex-direction:column; gap:4px; font-family:var(--mono);
  padding:8px 11px; border-radius:var(--r);
  background:var(--sunk); border-left:2px solid var(--line2); }}
.ag-top {{ display:flex; align-items:baseline; gap:8px; }}
.ag-top b {{ font-size:12.5px; }}
.ag-v {{ margin-left:auto; font-size:9.5px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted); }}
.ag-tf {{ display:flex; align-items:baseline; gap:5px; font-size:11px;
  color:var(--ink2); flex-wrap:wrap; }}
.ag-tf span {{ font-size:9px; letter-spacing:.06em; color:var(--muted);
  border:1px solid var(--line2); border-radius:2px; padding:0 3px; }}
.ag-aligned {{ border-left-color:var(--leading); }}
.ag-aligned .ag-v {{ color:var(--leading); }}
.ag-partial {{ border-left-color:var(--weakening); }}
.ag-partial .ag-v {{ color:var(--weakening); }}
.ag-diverging {{ border-left-color:var(--lagging); }}
.ag-diverging .ag-v {{ color:var(--lagging); }}

ul.alerts {{ list-style:none; margin:0; padding:6px 0; max-height:420px;
  overflow-y:auto; }}
.al {{ display:flex; gap:10px; align-items:baseline; flex-wrap:wrap;
  padding:8px 16px; font-size:13px; border-left:2px solid transparent; }}
.al-d {{ font-family:var(--mono); font-size:11px; color:var(--muted);
  font-variant-numeric:tabular-nums; }}
.al-tf {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted); border:1px solid var(--line2);
  border-radius:3px; padding:0 5px; }}
.al-t {{ font-family:var(--mono); font-size:12px; font-weight:600; }}
.al-b {{ color:var(--ink2); flex:1 1 200px; }}
.al-cross {{ border-left-color:var(--improving); background:var(--sunk); }}
.al-cross .al-b {{ color:var(--ink); }}
.al-conf {{ border-left-color:var(--leading); }}
.muted {{ color:var(--muted); }}

.legend {{ display:flex; flex-wrap:wrap; gap:6px 18px; padding:0 16px 14px;
  font-family:var(--mono); font-size:11px; color:var(--muted); }}

.exp {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px;
  padding:12px 16px; border-top:1px solid var(--line); }}
.exp-l {{ font-family:var(--mono); font-size:10px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--muted); margin-right:2px; }}
.exp button {{ font-family:var(--mono); font-size:11px; letter-spacing:.06em;
  padding:6px 11px; border:1px solid var(--line2); border-radius:3px;
  background:var(--surface); color:var(--ink2); cursor:pointer; }}
.exp button:hover:not(:disabled) {{ color:var(--ink); border-color:var(--muted); }}
.exp button:disabled {{ opacity:.5; cursor:default; }}
.exp button:focus-visible {{ outline:2px solid var(--improving);
  outline-offset:1px; }}
.exp-scale {{ display:inline-flex; align-items:center; gap:5px;
  font-family:var(--mono); font-size:11px; color:var(--muted); }}
.exp-scale select {{ font-family:var(--mono); font-size:11px; padding:4px 6px;
  border:1px solid var(--line2); border-radius:3px; background:var(--surface);
  color:var(--ink2); }}
.exp-msg {{ font-family:var(--mono); font-size:11px; color:var(--leading); }}
.exp-msg.err {{ color:var(--lagging); }}
.exp-out:not(:empty) {{ padding:0 16px 16px; display:flex;
  flex-direction:column; gap:10px; align-items:flex-start; }}
.exp-hint {{ margin:0; font-size:13px; color:var(--ink2); max-width:70ch;
  background:var(--sunk); border-left:2px solid var(--improving);
  border-radius:var(--r); padding:9px 12px; }}
.exp-img {{ max-width:100%; height:auto; border:1px solid var(--line2);
  border-radius:var(--r); display:block; }}
.exp-cap, .exp-link {{ font-family:var(--mono); font-size:11px;
  color:var(--muted); margin:0; }}
.exp-link {{ color:var(--improving); }}
.exp-close {{ font-family:var(--mono); font-size:11px; padding:5px 10px;
  border:1px solid var(--line2); border-radius:3px; background:var(--surface);
  color:var(--ink2); cursor:pointer; }}
.exp-close:hover {{ color:var(--ink); border-color:var(--muted); }}
footer {{ color:var(--muted); font-size:12.5px; border-top:1px solid var(--line);
  padding-top:16px; }}
footer code {{ font-family:var(--mono); font-size:12px; color:var(--ink2); }}

@media (max-width:720px) {{
  .wrap {{ padding:20px 14px 48px; gap:18px; }}
  .tablewrap {{ display:none; }}
  .cards {{ display:block; }}
  .stat {{ flex:1 1 50%; border-bottom:1px solid var(--line); }}
  .chartwrap {{ padding:10px 6px 0; }}
  .tl {{ gap:9px; }}
}}
@media (prefers-reduced-motion:no-preference) {{
  .panel, .strip {{ animation:rise .4s ease-out both; }}
  @keyframes rise {{ from {{ opacity:0; transform:translateY(6px); }} }}
}}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">Relative Rotation Graph &middot; vs {config.BENCHMARK_LABEL}
    &middot; <span id="hdr-date">&mdash;</span></div>
  <div class="hrow">
    <h1>{config.LABEL}</h1>
    <button id="upd" class="btn" type="button" disabled>
      <span class="btn-dot" aria-hidden="true"></span>
      <span id="upd-label">Checking&#8230;</span></button>
  </div>
  <p class="sub">Where capital is rotating across {len(config.SECTORS)}
  {config.NOUN} &mdash; position measured against {config.BENCHMARK_LABEL}, and whether
  that position is still accelerating. Drag the timeline to replay any past
  period.</p>
  <div id="upd-msg" class="updmsg" hidden></div>
</header>

<dl class="strip">
  <div class="stat"><dt>Showing</dt><dd id="st-date">&mdash;</dd></div>
  <div class="stat"><dt>Leading</dt><dd><span id="st-lead">&mdash;</span>
    <small id="st-of"></small></dd></div>
  <div class="stat"><dt>Quadrant changes</dt><dd><span id="st-cross">&mdash;</span>
    <small>to date</small></dd></div>
  <div class="stat"><dt>Benchmark</dt><dd>{config.BENCHMARK_LABEL}</dd></div>
</dl>

<section class="panel">
  <div class="panel-h">
    <h2>Rotation map</h2>
    <div class="tabs" role="tablist" aria-label="Timeframe">{tabs}</div>
  </div>
  <div class="tl">
    <div>
      <div class="tl-date" id="tl-date">&mdash;</div>
      <div class="tl-back" id="tl-back"></div>
    </div>
    <div class="tl-range">
      <input type="range" id="tl" min="0" max="0" value="0" step="1"
             aria-label="Timeline: choose the date to display">
    </div>
    <div class="tl-btns">
      <button type="button" id="tl-prev" title="Previous period"
        aria-label="Previous period">&#8592;</button>
      <button type="button" id="tl-next" title="Next period"
        aria-label="Next period">&#8594;</button>
      <button type="button" id="tl-last" title="Jump to latest">Latest</button>
    </div>
  </div>
  <div class="chartwrap"><div id="chart"></div></div>
  <div class="tablewrap"><table>
    <thead><tr><th>Sector</th><th>Quadrant</th><th class="num">Ratio</th>
    <th class="num">Mom</th>
    <th class="num" title="RRG units moved per bar over the last 4 bars">Vel</th>
    <th class="num" title="net move / path length over 8 bars — 1.00 is a dead-straight tail">Straight</th>
    <th class="num">Dir</th></tr></thead>
    <tbody id="tbody"></tbody></table></div>
  <div class="cards" id="cards"></div>
  <div class="legend">
    <span class="rot"><svg viewBox="0 0 22 22" aria-hidden="true"
      ><circle cx="11" cy="11" r="8"/><path d="M11 3 A8 8 0 1 1 3 11"/><path
      class="tip" d="M1 7 l2 4 l4 -2"/></svg>Sectors rotate clockwise</span>
    <span>Bubble = share of universe dollar volume</span>
    <span>Tail = {TAIL} periods</span>
    <span>Vel = units/bar &middot; Straight = 1.00 is a straight tail</span></div>
  <div class="exp">
    <span class="exp-l">Export for report</span>
    <button type="button" data-exp="report"
      title="Chart + ranked table, 16:9 — drops straight into a slide or video frame">Figure PNG</button>
    <button type="button" data-exp="chart"
      title="The chart alone, portrait">Chart PNG</button>
    <button type="button" data-exp="svg"
      title="The 16:9 figure as vector — scales to any size, editable in Illustrator/After Effects">Figure SVG</button>
    <button type="button" data-exp="copy"
      title="Copy the 16:9 figure to the clipboard">Copy figure</button>
    <span class="exp-scale">
      <label for="exp-x">at</label>
      <select id="exp-x"><option value="1">1&times;</option>
        <option value="2" selected>2&times;</option>
        <option value="3">3&times;</option></select>
    </span>
    <span class="exp-msg" id="exp-msg" role="status"></span>
  </div>
  <div class="exp-out" id="exp-out"></div>
</section>

<section class="panel">
  <div class="panel-h"><h2>Timeframe agreement</h2>
    <span class="eyebrow">weekly / daily</span></div>
  <div class="agrid" id="agrid"></div>
</section>

<section class="panel">
  <div class="panel-h"><h2>Rotation alerts</h2>
    <span class="eyebrow" id="al-note"></span></div>
  <ul class="alerts" id="alerts"></ul>
</section>

<footer>Generated from the local rrg-kit &mdash; regenerate with
<code>python3 update.py &amp;&amp; python3 make_dashboard.py</code>.
Source: Yahoo Finance. Standard public approximation of JdK RS-Ratio /
RS-Momentum; sector rotation is context, not a trade trigger.</footer>
</div>

<script>
var D = {payload};

// ── geometry ───────────────────────────────────────────────────────────────
var VIEW = 640, PAD_L = 52, PAD_B = 46, PAD_T = 20, PAD_R = 20;
var W = VIEW - PAD_L - PAD_R, H = VIEW - PAD_T - PAD_B;
var LO = 100 - D.pad, HI = 100 + D.pad;
var px = function (v) {{ return PAD_L + (v - LO) / (HI - LO) * W; }};
var py = function (v) {{ return PAD_T + (1 - (v - LO) / (HI - LO)) * H; }};
var ARROWS = ['\\u2192','\\u2197','\\u2191','\\u2196','\\u2190','\\u2199',
              '\\u2193','\\u2198'];
var QORDER = ['Leading','Improving','Weakening','Lagging'];

function quadrant(x, y) {{
  if (x >= 100 && y >= 100) return 'Leading';
  if (x >= 100) return 'Weakening';
  return y >= 100 ? 'Improving' : 'Lagging';
}}
function esc(s) {{
  return String(s).replace(/[&<>"]/g, function (c) {{
    return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c];
  }});
}}
function hypot(a, b) {{ return Math.sqrt(a * a + b * b); }}

// Trailing points for one sector up to `idx`, skipping dates it has no bar on.
function trail(series, idx, n) {{
  var out = [];
  for (var k = idx; k >= 0 && out.length < n; k--) {{
    if (series.pts[k]) out.unshift({{k: k, p: series.pts[k]}});
  }}
  return out;
}}

// velocity / straightness / heading, computed the same way as rrg.py
function metrics(series, idx) {{
  var pts = trail(series, idx, D.shapeW + 1).map(function (o) {{ return o.p; }});
  if (!pts.length) return null;
  var cur = pts[pts.length - 1], out = {{x: cur[0], y: cur[1],
    share: cur[2], vol: cur[3], velocity: 0, straight: 0, heading: 0}};
  var mv = pts.slice(Math.max(0, pts.length - 1 - D.moveW));
  if (mv.length > 1) {{
    var dx = mv[mv.length - 1][0] - mv[0][0], dy = mv[mv.length - 1][1] - mv[0][1];
    out.velocity = hypot(dx, dy) / (mv.length - 1);
    out.heading = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
  }}
  if (pts.length > 1) {{
    var path = 0;
    for (var i = 1; i < pts.length; i++)
      path += hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    var net = hypot(pts[pts.length - 1][0] - pts[0][0],
                    pts[pts.length - 1][1] - pts[0][1]);
    out.straight = path > 0 ? net / path : 0;
  }}
  out.rising = pts.length > 1 ? cur[1] > pts[pts.length - 2][1] : false;
  return out;
}}

// ── chart ──────────────────────────────────────────────────────────────────
function renderChart(f, idx) {{
  var s = [], cx = px(100), cy = py(100);
  [['leading', cx, PAD_T, PAD_L + W - cx, cy - PAD_T],
   ['weakening', cx, cy, PAD_L + W - cx, PAD_T + H - cy],
   ['lagging', PAD_L, cy, cx - PAD_L, PAD_T + H - cy],
   ['improving', PAD_L, PAD_T, cx - PAD_L, cy - PAD_T]].forEach(function (q) {{
    s.push('<rect class="q q-' + q[0] + '" x="' + q[1].toFixed(1) + '" y="' +
      q[2].toFixed(1) + '" width="' + q[3].toFixed(1) + '" height="' +
      q[4].toFixed(1) + '"/>');
  }});
  for (var v = Math.ceil(LO); v <= HI; v++) {{
    if (Math.abs(v - 100) < 1e-9) continue;
    s.push('<line class="grid" x1="' + px(v).toFixed(1) + '" y1="' + PAD_T +
      '" x2="' + px(v).toFixed(1) + '" y2="' + (PAD_T + H) + '"/>');
    s.push('<line class="grid" x1="' + PAD_L + '" y1="' + py(v).toFixed(1) +
      '" x2="' + (PAD_L + W) + '" y2="' + py(v).toFixed(1) + '"/>');
    s.push('<text class="tick" x="' + px(v).toFixed(1) + '" y="' +
      (PAD_T + H + 16) + '" text-anchor="middle">' + v + '</text>');
    s.push('<text class="tick" x="' + (PAD_L - 8) + '" y="' +
      (py(v) + 3.5).toFixed(1) + '" text-anchor="end">' + v + '</text>');
  }}
  s.push('<line class="axis" x1="' + cx.toFixed(1) + '" y1="' + PAD_T +
    '" x2="' + cx.toFixed(1) + '" y2="' + (PAD_T + H) + '"/>');
  s.push('<line class="axis" x1="' + PAD_L + '" y1="' + cy.toFixed(1) +
    '" x2="' + (PAD_L + W) + '" y2="' + cy.toFixed(1) + '"/>');
  s.push('<rect class="frame" x="' + PAD_L + '" y="' + PAD_T + '" width="' +
    W + '" height="' + H + '"/>');
  [['IMPROVING', PAD_L + 9, PAD_T + 18, 'start'],
   ['LEADING', PAD_L + W - 9, PAD_T + 18, 'end'],
   ['LAGGING', PAD_L + 9, PAD_T + H - 9, 'start'],
   ['WEAKENING', PAD_L + W - 9, PAD_T + H - 9, 'end']].forEach(function (q) {{
    s.push('<text class="qlabel" x="' + q[1] + '" y="' + q[2] +
      '" text-anchor="' + q[3] + '">' + q[0] + '</text>');
  }});

  var placed = [], labels = [];
  f.series.forEach(function (ser) {{
    var tr = trail(ser, idx, D.tail + 1);
    if (!tr.length) return;
    var col = 'var(--s' + ser.i + ')';
    var pl = tr.map(function (o) {{
      return px(o.p[0]).toFixed(1) + ',' + py(o.p[1]).toFixed(1);
    }}).join(' ');
    s.push('<polyline class="trail" points="' + pl + '" stroke="' + col + '"/>');
    var last = tr[tr.length - 1].p;
    var X = px(last[0]), Y = py(last[1]);
    var rr = 6 + 12 * Math.pow(Math.min(last[2] / 0.25, 1), 0.5);
    s.push('<g><title>' + esc(ser.t + ' ' + ser.name) + '</title>' +
      '<circle class="bub" cx="' + X.toFixed(1) + '" cy="' + Y.toFixed(1) +
      '" r="' + rr.toFixed(1) + '" fill="' + col + '"/></g>');

    var tw = ser.t.length * 6.6 + 3, th = 12;
    var cands = [[X, Y - rr - 6, 'middle'], [X, Y + rr + 13, 'middle'],
                 [X + rr + 6, Y + 4, 'start'], [X - rr - 6, Y + 4, 'end']];
    var pick = null;
    for (var ci = 0; ci < cands.length; ci++) {{
      var c = cands[ci];
      var x0 = c[2] === 'middle' ? c[0] - tw / 2
             : (c[2] === 'start' ? c[0] : c[0] - tw);
      var box = [x0, c[1] - th, x0 + tw, c[1] + 3];
      var hit = placed.some(function (o) {{
        return box[0] < o[2] && o[0] < box[2] && box[1] < o[3] && o[1] < box[3];
      }});
      if (!hit) {{ pick = {{c: c, box: box}}; break; }}
    }}
    if (!pick) {{
      var c0 = cands[0], x1 = c0[0] - tw / 2, y1 = c0[1] - th - 2;
      pick = {{c: [c0[0], y1, 'middle'], box: [x1, y1 - th, x1 + tw, y1 + 3]}};
    }}
    placed.push(pick.box);
    labels.push('<text class="tk" x="' + pick.c[0].toFixed(1) + '" y="' +
      pick.c[1].toFixed(1) + '" text-anchor="' + pick.c[2] + '">' +
      ser.t + '</text>');
  }});
  s = s.concat(labels);
  s.push('<text class="axlabel" x="' + (PAD_L + W / 2) + '" y="' + (VIEW - 6) +
    '" text-anchor="middle">RS-RATIO \\u00b7 RELATIVE STRENGTH \\u2192</text>');
  s.push('<text class="axlabel" transform="translate(13,' + (PAD_T + H / 2) +
    ') rotate(-90)" text-anchor="middle">RS-MOMENTUM \\u00b7 IMPROVING \\u2192</text>');

  document.getElementById('chart').innerHTML =
    '<svg viewBox="0 0 ' + VIEW + ' ' + VIEW + '" class="rrg" role="img" ' +
    'aria-label="Relative rotation graph">' + s.join('') + '</svg>';
}}

// ── table ──────────────────────────────────────────────────────────────────
function rowsFor(f, idx) {{
  var rows = [];
  f.series.forEach(function (ser) {{
    var m = metrics(ser, idx);
    if (!m) return;
    m.ser = ser;
    m.q = quadrant(m.x, m.y);
    rows.push(m);
  }});
  rows.sort(function (a, b) {{
    var d = QORDER.indexOf(a.q) - QORDER.indexOf(b.q);
    return d !== 0 ? d : b.x - a.x;
  }});
  return rows;
}}

function renderTable(rows) {{
  var tb = [], cd = [];
  rows.forEach(function (m) {{
    var conv = (m.velocity >= 0.35 && m.straight >= 0.7) ? 'high'
             : (m.velocity < 0.15 || m.straight < 0.45) ? 'low' : 'mid';
    var dir = ARROWS[Math.round(m.heading / 45) % 8] + ' ' +
              Math.round(m.heading) + '\\u00b0';
    var sw = '<span class="swatch" style="background:var(--s' + m.ser.i +
             ')"></span>';
    tb.push('<tr><td class="c-tk">' + sw + '<b>' + m.ser.t +
      '</b><span class="c-name">' + esc(m.ser.name) + '</span></td>' +
      '<td><span class="pill p-' + m.q.toLowerCase() + '">' + m.q +
      '</span></td><td class="num">' + m.x.toFixed(2) +
      '</td><td class="num">' + m.y.toFixed(2) +
      '</td><td class="num">' + m.velocity.toFixed(2) +
      '</td><td class="num conv conv-' + conv + '">' + m.straight.toFixed(2) +
      '</td><td class="num dir">' + dir + '</td></tr>');
    cd.push('<div class="card"><div class="card-h">' + sw + '<b>' + m.ser.t +
      '</b><span class="c-name">' + esc(m.ser.name) +
      '</span><span class="pill p-' + m.q.toLowerCase() + '">' + m.q +
      '</span></div><dl class="card-d">' +
      '<div><dt>Ratio</dt><dd>' + m.x.toFixed(2) + '</dd></div>' +
      '<div><dt>Mom</dt><dd>' + m.y.toFixed(2) + '</dd></div>' +
      '<div><dt>Vel</dt><dd>' + m.velocity.toFixed(2) + '</dd></div>' +
      '<div><dt>Straight</dt><dd>' + m.straight.toFixed(2) + '</dd></div>' +
      '<div><dt>Dir</dt><dd>' + dir + '</dd></div></dl></div>');
  }});
  document.getElementById('tbody').innerHTML = tb.join('');
  document.getElementById('cards').innerHTML = cd.join('');
}}

// ── agreement (weekly quadrant vs the daily bar on/just before that date) ───
function renderAgreement(isoDate) {{
  var wf = D.frames.weekly, df = D.frames.daily, el = document.getElementById('agrid');
  if (!wf || !df) {{ el.innerHTML = ''; return; }}
  var wi = -1;
  for (var i = 0; i < wf.dates.length; i++) if (wf.dates[i] <= isoDate) wi = i;
  var di = -1;
  for (var j = 0; j < df.dates.length; j++) if (df.dates[j] <= isoDate) di = j;
  if (wi < 0 || di < 0) {{ el.innerHTML = '<div class="al muted">No daily data ' +
    'for this date.</div>'; return; }}

  var dmap = {{}};
  df.series.forEach(function (s) {{ dmap[s.t] = metrics(s, di); }});
  var out = [];
  rowsFor(wf, wi).forEach(function (m) {{
    var dm = dmap[m.ser.t];
    if (!dm) return;
    var dq = quadrant(dm.x, dm.y);
    var verdict = m.q === dq ? 'aligned'
                : (m.rising === dm.rising ? 'partial' : 'diverging');
    out.push('<div class="ag ag-' + verdict + '"><div class="ag-top"><b>' +
      m.ser.t + '</b><span class="ag-v">' + verdict + '</span></div>' +
      '<div class="ag-tf"><span>W</span>' + m.q + '<span>D</span>' + dq +
      '</div></div>');
  }});
  el.innerHTML = out.join('');
}}

// ── alerts, filtered to the selected date ──────────────────────────────────
function renderAlerts(isoDate) {{
  var shown = D.alerts.filter(function (a) {{ return a.date <= isoDate; }});
  var el = document.getElementById('alerts');
  el.innerHTML = shown.slice(0, 40).map(function (a) {{
    return '<li class="al' + (a.crossing ? ' al-cross' : '') +
      (a.confirmed ? ' al-conf' : '') + '"><span class="al-d">' + a.date +
      '</span><span class="al-tf">' + a.tf + '</span><span class="al-t">' +
      a.ticker + '</span><span class="al-b">' + esc(a.body) + '</span></li>';
  }}).join('') || '<li class="al muted">No alerts on or before this date.</li>';
  document.getElementById('al-note').textContent =
    shown.length ? 'on or before ' + isoDate : '';
  return shown;
}}

// ── state ──────────────────────────────────────────────────────────────────
var state = {{tf: 'weekly', idx: {{}}}};
Object.keys(D.frames).forEach(function (k) {{
  state.idx[k] = D.frames[k].dates.length - 1;
}});

function render() {{
  var f = D.frames[state.tf], idx = state.idx[state.tf];
  var iso = f.dates[idx], label = f.dlabels[idx];
  var last = f.dates.length - 1;

  renderChart(f, idx);
  var rows = rowsFor(f, idx);
  renderTable(rows);
  renderAgreement(iso);
  var shown = renderAlerts(iso);

  document.getElementById('hdr-date').textContent = label;
  document.getElementById('tl-date').textContent = label;
  document.getElementById('st-date').textContent = label;
  document.getElementById('st-lead').textContent =
    rows.filter(function (r) {{ return r.q === 'Leading'; }}).length;
  document.getElementById('st-of').textContent = 'of ' + rows.length;
  document.getElementById('st-cross').textContent =
    shown.filter(function (a) {{ return a.crossing; }}).length;

  var back = last - idx;
  document.getElementById('tl-back').textContent = back === 0 ? 'latest'
    : back + ' ' + (f.label === 'Weekly' ? 'week' : 'day') +
      (back === 1 ? '' : 's') + ' back';
  var sl = document.getElementById('tl');
  sl.max = last; sl.value = idx;
  document.getElementById('tl-prev').disabled = idx <= 0;
  document.getElementById('tl-next').disabled = idx >= last;
  document.getElementById('tl-last').disabled = idx >= last;
}}

function step(n) {{
  var f = D.frames[state.tf];
  state.idx[state.tf] = Math.max(0, Math.min(f.dates.length - 1,
    state.idx[state.tf] + n));
  render();
}}

document.getElementById('tl').addEventListener('input', function (e) {{
  state.idx[state.tf] = parseInt(e.target.value, 10);
  render();
}});
document.getElementById('tl-prev').addEventListener('click', function () {{ step(-1); }});
document.getElementById('tl-next').addEventListener('click', function () {{ step(1); }});
document.getElementById('tl-last').addEventListener('click', function () {{
  state.idx[state.tf] = D.frames[state.tf].dates.length - 1; render();
}});
document.querySelectorAll('[data-go]').forEach(function (b) {{
  b.addEventListener('click', function () {{
    state.tf = b.dataset.go;
    document.querySelectorAll('[data-go]').forEach(function (o) {{
      o.setAttribute('aria-selected', String(o === b));
    }});
    render();
  }});
}});
render();

// ── Export for reports ─────────────────────────────────────────────────────
// The on-page chart is styled with CSS custom properties, which don't survive
// serialisation. So exports are rebuilt as a standalone SVG with every colour
// resolved to a literal value and every style as an attribute — that SVG is
// valid on its own (vector export) and rasterises cleanly to PNG via canvas.
// NB: single quotes inside — these are dropped into font-family="..." on SVG
// elements, so a double-quoted family name would terminate the attribute and
// make the document unparseable (and rasterising would fail silently).
var MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
var SANS = "system-ui, -apple-system, 'Segoe UI', sans-serif";

function themeColors() {{
  var cs = getComputedStyle(document.documentElement), C = {{}};
  ['surface','ground','ink','ink2','muted','line','line2',
   'leading','improving','weakening','lagging'].forEach(function (n) {{
    C[n] = cs.getPropertyValue('--' + n).trim() || '#888';
  }});
  C.s = [];
  for (var i = 0; i < 24; i++) {{
    var v = cs.getPropertyValue('--s' + i).trim();
    if (v) C.s.push(v);
  }}
  return C;
}}

function qColor(C, q) {{ return C[q.toLowerCase()]; }}

// chart drawn into the 640-unit space, all styles explicit
function chartMarkup(f, idx, C) {{
  var s = [], cx = px(100), cy = py(100);
  [['leading', cx, PAD_T, PAD_L + W - cx, cy - PAD_T],
   ['weakening', cx, cy, PAD_L + W - cx, PAD_T + H - cy],
   ['lagging', PAD_L, cy, cx - PAD_L, PAD_T + H - cy],
   ['improving', PAD_L, PAD_T, cx - PAD_L, cy - PAD_T]].forEach(function (q) {{
    s.push('<rect x="' + q[1].toFixed(1) + '" y="' + q[2].toFixed(1) +
      '" width="' + q[3].toFixed(1) + '" height="' + q[4].toFixed(1) +
      '" fill="' + C[q[0]] + '" fill-opacity="0.07"/>');
  }});
  for (var v = Math.ceil(LO); v <= HI; v++) {{
    if (Math.abs(v - 100) < 1e-9) continue;
    var gs = ' stroke="' + C.line + '" stroke-width="0.6" stroke-dasharray="2 3"';
    s.push('<line x1="' + px(v).toFixed(1) + '" y1="' + PAD_T + '" x2="' +
      px(v).toFixed(1) + '" y2="' + (PAD_T + H) + '"' + gs + '/>');
    s.push('<line x1="' + PAD_L + '" y1="' + py(v).toFixed(1) + '" x2="' +
      (PAD_L + W) + '" y2="' + py(v).toFixed(1) + '"' + gs + '/>');
    var ts = ' fill="' + C.muted + '" font-family="' + MONO + '" font-size="10"';
    s.push('<text x="' + px(v).toFixed(1) + '" y="' + (PAD_T + H + 16) +
      '" text-anchor="middle"' + ts + '>' + v + '</text>');
    s.push('<text x="' + (PAD_L - 8) + '" y="' + (py(v) + 3.5).toFixed(1) +
      '" text-anchor="end"' + ts + '>' + v + '</text>');
  }}
  s.push('<line x1="' + cx.toFixed(1) + '" y1="' + PAD_T + '" x2="' +
    cx.toFixed(1) + '" y2="' + (PAD_T + H) + '" stroke="' + C.line2 +
    '" stroke-width="0.9"/>');
  s.push('<line x1="' + PAD_L + '" y1="' + cy.toFixed(1) + '" x2="' +
    (PAD_L + W) + '" y2="' + cy.toFixed(1) + '" stroke="' + C.line2 +
    '" stroke-width="0.9"/>');
  s.push('<rect x="' + PAD_L + '" y="' + PAD_T + '" width="' + W + '" height="' +
    H + '" fill="none" stroke="' + C.line2 + '" stroke-width="0.7"/>');
  [['IMPROVING', PAD_L + 9, PAD_T + 18, 'start'],
   ['LEADING', PAD_L + W - 9, PAD_T + 18, 'end'],
   ['LAGGING', PAD_L + 9, PAD_T + H - 9, 'start'],
   ['WEAKENING', PAD_L + W - 9, PAD_T + H - 9, 'end']].forEach(function (q) {{
    s.push('<text x="' + q[1] + '" y="' + q[2] + '" text-anchor="' + q[3] +
      '" fill="' + C.muted + '" font-family="' + MONO + '" font-size="9.5" ' +
      'letter-spacing="1.5" opacity="0.8">' + q[0] + '</text>');
  }});

  var placed = [], labels = [];
  f.series.forEach(function (ser) {{
    var tr = trail(ser, idx, D.tail + 1);
    if (!tr.length) return;
    var col = C.s[ser.i % C.s.length];
    var pl = tr.map(function (o) {{
      return px(o.p[0]).toFixed(1) + ',' + py(o.p[1]).toFixed(1);
    }}).join(' ');
    s.push('<polyline points="' + pl + '" fill="none" stroke="' + col +
      '" stroke-width="1.5" stroke-opacity="0.55" stroke-linejoin="round" ' +
      'stroke-linecap="round"/>');
    var last = tr[tr.length - 1].p;
    var X = px(last[0]), Y = py(last[1]);
    var rr = 6 + 12 * Math.pow(Math.min(last[2] / 0.25, 1), 0.5);
    s.push('<circle cx="' + X.toFixed(1) + '" cy="' + Y.toFixed(1) + '" r="' +
      rr.toFixed(1) + '" fill="' + col + '" stroke="' + C.surface +
      '" stroke-width="1.5"/>');

    var tw = ser.t.length * 6.6 + 3, th = 12;
    var cands = [[X, Y - rr - 6, 'middle'], [X, Y + rr + 13, 'middle'],
                 [X + rr + 6, Y + 4, 'start'], [X - rr - 6, Y + 4, 'end']];
    var pick = null;
    for (var ci = 0; ci < cands.length; ci++) {{
      var c = cands[ci];
      var x0 = c[2] === 'middle' ? c[0] - tw / 2
             : (c[2] === 'start' ? c[0] : c[0] - tw);
      var box = [x0, c[1] - th, x0 + tw, c[1] + 3];
      var hit = placed.some(function (o) {{
        return box[0] < o[2] && o[0] < box[2] && box[1] < o[3] && o[1] < box[3];
      }});
      if (!hit) {{ pick = {{c: c, box: box}}; break; }}
    }}
    if (!pick) {{
      var c0 = cands[0], x1 = c0[0] - tw / 2, y1 = c0[1] - th - 2;
      pick = {{c: [c0[0], y1, 'middle'], box: [x1, y1 - th, x1 + tw, y1 + 3]}};
    }}
    placed.push(pick.box);
    labels.push('<text x="' + pick.c[0].toFixed(1) + '" y="' +
      pick.c[1].toFixed(1) + '" text-anchor="' + pick.c[2] + '" fill="' +
      C.ink + '" font-family="' + MONO + '" font-size="10.5" ' +
      'font-weight="600" paint-order="stroke" stroke="' + C.surface +
      '" stroke-width="2.6" stroke-linejoin="round">' + ser.t + '</text>');
  }});
  s = s.concat(labels);
  var al = ' fill="' + C.muted + '" font-family="' + MONO +
           '" font-size="9.5" letter-spacing="1.3"';
  s.push('<text x="' + (PAD_L + W / 2) + '" y="' + (VIEW - 6) +
    '" text-anchor="middle"' + al + '>RS-RATIO \\u00b7 RELATIVE STRENGTH \\u2192</text>');
  s.push('<text transform="translate(13,' + (PAD_T + H / 2) +
    ') rotate(-90)" text-anchor="middle"' + al +
    '>RS-MOMENTUM \\u00b7 IMPROVING \\u2192</text>');
  return s.join('');
}}

// the ranked table, drawn as SVG so it can live inside the exported figure
function tableMarkup(rows, C, x, y, rowH) {{
  var cols = [110, 210, 140, 88, 88, 76, 96], s = [];
  var head = ['SECTOR', '', 'QUADRANT', 'RATIO', 'MOM', 'VEL', 'STRAIGHT', 'DIR'];
  var xs = [x], acc = x;
  cols.forEach(function (w) {{ acc += w; xs.push(acc); }});
  var right = [3, 4, 5, 6, 7];

  // right edge of column i is xs[i] + cols[i] (its OWN width), not cols[i-1]
  head.forEach(function (h, i) {{
    if (!h) return;
    var isR = right.indexOf(i) >= 0 && i < cols.length;
    s.push('<text x="' + (isR ? xs[i] + cols[i] - 8 : xs[i]) + '" y="' + y +
      '" text-anchor="' + (isR ? 'end' : 'start') + '" fill="' + C.muted +
      '" font-family="' + MONO + '" font-size="15" letter-spacing="1.6">' +
      h + '</text>');
  }});
  s.push('<line x1="' + x + '" y1="' + (y + 14) + '" x2="' + (xs[7] + 110) +
    '" y2="' + (y + 14) + '" stroke="' + C.line2 + '" stroke-width="1"/>');

  rows.forEach(function (m, r) {{
    var ry = y + 46 + r * rowH;
    if (r) s.push('<line x1="' + x + '" y1="' + (ry - rowH + 14) + '" x2="' +
      (xs[7] + 110) + '" y2="' + (ry - rowH + 14) + '" stroke="' + C.line +
      '" stroke-width="1"/>');
    var col = C.s[m.ser.i % C.s.length];
    s.push('<rect x="' + x + '" y="' + (ry - 12) + '" width="12" height="12" ' +
      'rx="2.5" fill="' + col + '"/>');
    s.push('<text x="' + (x + 22) + '" y="' + ry + '" fill="' + C.ink +
      '" font-family="' + MONO + '" font-size="21" font-weight="600">' +
      m.ser.t + '</text>');
    s.push('<text x="' + xs[1] + '" y="' + ry + '" fill="' + C.ink2 +
      '" font-family="' + SANS + '" font-size="19">' + esc(m.ser.name) +
      '</text>');
    var qc = qColor(C, m.q);
    s.push('<rect x="' + xs[2] + '" y="' + (ry - 17) + '" width="126" ' +
      'height="24" rx="12" fill="none" stroke="' + qc + '" stroke-width="1.2"/>');
    s.push('<text x="' + (xs[2] + 63) + '" y="' + (ry - 1) +
      '" text-anchor="middle" fill="' + qc + '" font-family="' + MONO +
      '" font-size="13" letter-spacing="0.8">' + m.q.toUpperCase() + '</text>');

    var nums = [m.x.toFixed(2), m.y.toFixed(2), m.velocity.toFixed(2),
                m.straight.toFixed(2)];
    nums.forEach(function (n, i) {{
      var ci = i + 3;
      var strong = (ci === 6 && m.velocity >= 0.35 && m.straight >= 0.7);
      s.push('<text x="' + (xs[ci] + cols[ci] - 8) + '" y="' + ry +
        '" text-anchor="end" fill="' + (strong ? C.leading : C.ink) +
        '" font-family="' + MONO + '" font-size="21"' +
        (strong ? ' font-weight="600"' : '') + '>' + n + '</text>');
    }});
    var dir = ARROWS[Math.round(m.heading / 45) % 8] + ' ' +
              Math.round(m.heading) + '\\u00b0';
    s.push('<text x="' + (xs[7] + 106) + '" y="' + ry + '" text-anchor="end" ' +
      'fill="' + C.ink2 + '" font-family="' + MONO + '" font-size="21">' +
      dir + '</text>');
  }});
  return s.join('');
}}

function buildExport(mode) {{
  var f = D.frames[state.tf], idx = state.idx[state.tf];
  var C = themeColors(), rows = rowsFor(f, idx);
  var when = f.dlabels[idx], iso = f.dates[idx];
  var sub = f.label.toUpperCase() + '  \\u00b7  VS ' + D.benchmark.toUpperCase() +
            '  \\u00b7  ' + when.toUpperCase();
  var foot = 'JdK RS-Ratio vs RS-Momentum (standard public approximation) ' +
             '\\u00b7 bubble = share of universe dollar volume \\u00b7 tail = ' +
             D.tail + ' periods \\u00b7 source: Yahoo Finance';
  var g = [], w, h, cw, cx0, cy0;

  if (mode === 'chart') {{
    w = 1240; h = 1400; cw = 1128; cx0 = 56; cy0 = 150;
  }} else {{
    w = 1920; h = 1080; cw = 830; cx0 = 56; cy0 = 176;
  }}
  g.push('<rect width="' + w + '" height="' + h + '" fill="' + C.ground + '"/>');
  g.push('<text x="64" y="' + (mode === 'chart' ? 84 : 90) + '" fill="' + C.ink +
    '" font-family="' + SANS + '" font-size="' + (mode === 'chart' ? 40 : 46) +
    '" font-weight="650" letter-spacing="-0.8">' + esc(D.title) + '</text>');
  g.push('<text x="64" y="' + (mode === 'chart' ? 116 : 126) + '" fill="' +
    C.muted + '" font-family="' + MONO + '" font-size="' +
    (mode === 'chart' ? 16 : 19) + '" letter-spacing="2">' + sub + '</text>');
  g.push('<line x1="64" y1="' + (mode === 'chart' ? 136 : 152) + '" x2="' +
    (w - 64) + '" y2="' + (mode === 'chart' ? 136 : 152) + '" stroke="' +
    C.line + '" stroke-width="1"/>');

  var sc = cw / VIEW;
  g.push('<g transform="translate(' + cx0 + ',' + cy0 + ') scale(' +
    sc.toFixed(4) + ')">' + chartMarkup(f, idx, C) + '</g>');

  if (mode === 'report') {{
    g.push(tableMarkup(rows, C, 960, 210, 68));
  }}
  g.push('<text x="64" y="' + (h - 34) + '" fill="' + C.muted +
    '" font-family="' + MONO + '" font-size="15">' + foot + '</text>');

  return {{
    w: w, h: h,
    name: 'rrg_' + mode + '_' + state.tf + '_' + iso,
    svg: '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' +
      h + '" viewBox="0 0 ' + w + ' ' + h + '">' + g.join('') + '</svg>'
  }};
}}

// Embedded (iframe) views sandbox downloads away, so a[download] silently
// does nothing there. Detect it and offer the image inline instead.
var EMBEDDED = (function () {{
  try {{ return window.self !== window.top; }} catch (e) {{ return true; }}
}})();

// Rasterise to a canvas. Data URIs throughout: some hosts' CSP blocks blob:
// under img-src, and a[download] with a blob: URL is likewise unreliable in
// sandboxed frames.
function rasterise(spec, scale) {{
  var src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(spec.svg);
  return new Promise(function (res, rej) {{
    var img = new Image();
    img.onload = function () {{
      var cv = document.createElement('canvas');
      cv.width = Math.round(spec.w * scale);
      cv.height = Math.round(spec.h * scale);
      cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
      res(cv);
    }};
    img.onerror = function () {{
      rej(new Error('could not rasterise the chart'));
    }};
    img.src = src;
  }});
}}

function toPNG(spec, scale) {{
  return rasterise(spec, scale).then(function (cv) {{
    return new Promise(function (res, rej) {{
      cv.toBlob(function (b) {{
        b ? res(b) : rej(new Error('canvas export failed'));
      }}, 'image/png');
    }});
  }});
}}

function toPNGURL(spec, scale) {{
  return rasterise(spec, scale).then(function (cv) {{
    return {{url: cv.toDataURL('image/png'), w: cv.width, h: cv.height}};
  }});
}}

// Best-effort download. Returns false when we know it cannot work.
function download(url, filename) {{
  if (EMBEDDED) return false;
  var a = document.createElement('a');
  a.href = url; a.download = filename; a.rel = 'noopener';
  document.body.appendChild(a); a.click(); a.remove();
  return true;
}}

// The fallback that always works: put the finished image on the page so it
// can be saved with the browser's own right-click / long-press.
function showResult(url, filename, dims, isSvg) {{
  var box = document.getElementById('exp-out');
  box.innerHTML = '';
  var hint = document.createElement('p');
  hint.className = 'exp-hint';
  hint.textContent = EMBEDDED
    ? 'This view blocks automatic downloads. Right-click the image below and '
      + 'choose \\u201cSave image as\\u2026\\u201d (long-press on mobile), or '
      + 'use Copy figure to paste it straight into your deck.'
    : 'Saved as ' + filename + '. Right-click below to save again.';
  box.appendChild(hint);

  if (isSvg) {{
    var a = document.createElement('a');
    a.href = url; a.download = filename; a.className = 'exp-link';
    a.textContent = 'Right-click \\u2192 Save link as\\u2026 ' + filename;
    box.appendChild(a);
  }} else {{
    var im = document.createElement('img');
    im.src = url; im.alt = 'Exported figure, ' + dims;
    im.className = 'exp-img';
    box.appendChild(im);
    var cap = document.createElement('p');
    cap.className = 'exp-cap';
    cap.textContent = filename + '  \\u00b7  ' + dims;
    box.appendChild(cap);
  }}
  var close = document.createElement('button');
  close.type = 'button'; close.className = 'exp-close';
  close.textContent = 'Close preview';
  close.addEventListener('click', function () {{ box.innerHTML = ''; }});
  box.appendChild(close);
  box.scrollIntoView({{block: 'nearest', behavior: 'smooth'}});
}}

(function () {{
  var out = document.getElementById('exp-msg');
  var note = function (t, err) {{
    out.textContent = t;
    out.className = 'exp-msg' + (err ? ' err' : '');
    clearTimeout(note.t);
    note.t = setTimeout(function () {{ out.textContent = ''; }}, 4000);
  }};
  document.querySelectorAll('[data-exp]').forEach(function (b) {{
    b.addEventListener('click', function () {{
      var kind = b.dataset.exp;
      var scale = parseInt(document.getElementById('exp-x').value, 10) || 2;
      var spec = buildExport(kind === 'chart' ? 'chart' : 'report');

      if (kind === 'svg') {{
        var url = 'data:image/svg+xml;charset=utf-8,' +
                  encodeURIComponent(spec.svg);
        var name = spec.name + '.svg';
        var did = download(url, name);
        showResult(url, name, '', true);
        return note(did ? 'SVG saved \\u2014 vector, scales to any size'
                        : 'Download blocked here \\u2014 save from the link below');
      }}

      b.disabled = true;
      note('Rendering\\u2026');

      if (kind === 'copy') {{
        return toPNG(spec, scale).then(function (blob) {{
          if (!(navigator.clipboard && window.ClipboardItem &&
                window.isSecureContext)) throw new Error('clipboard unavailable');
          return navigator.clipboard.write([
            new ClipboardItem({{'image/png': blob}})
          ]).then(function () {{
            note('Copied \\u2014 paste into your deck');
          }});
        }}).catch(function () {{
          // clipboard refused (permission, or an embedded view) — fall back
          return toPNGURL(spec, scale).then(function (r) {{
            showResult(r.url, spec.name + '.png', r.w + '\\u00d7' + r.h, false);
            note('Clipboard blocked \\u2014 save the image below instead', true);
          }});
        }}).then(function () {{ b.disabled = false; }});
      }}

      toPNGURL(spec, scale).then(function (r) {{
        var name = spec.name + '.png', dims = r.w + '\\u00d7' + r.h;
        var did = download(r.url, name);
        showResult(r.url, name, dims, false);
        note(did ? 'Saved ' + name + ' (' + dims + ')'
                 : 'Download blocked here \\u2014 save the image below');
      }}).catch(function (e) {{
        note('Export failed: ' + e.message, true);
      }}).then(function () {{ b.disabled = false; }});
    }});
  }});
}})();

// ── Update button ──────────────────────────────────────────────────────────
// Static pages can't run Python. When served by serve.py an API is present and
// the button re-runs the pipeline for real; otherwise it degrades to handing
// over the command to run.
(function () {{
  if (!document.querySelector('meta[name="viewport"]')) {{
    var mv = document.createElement('meta');
    mv.name = 'viewport';
    mv.content = 'width=device-width, initial-scale=1';
    document.head.appendChild(mv);
  }}
  var btn = document.getElementById('upd');
  var label = document.getElementById('upd-label');
  var msg = document.getElementById('upd-msg');
  var live = false;

  function say(text, cls, cmd) {{
    msg.className = 'updmsg' + (cls ? ' ' + cls : '');
    msg.textContent = text;
    if (cmd) {{
      var c = document.createElement('code');
      c.textContent = cmd;
      msg.appendChild(document.createElement('br'));
      msg.appendChild(c);
    }}
    msg.hidden = false;
  }}
  function mode(m, text) {{
    btn.dataset.mode = m; label.textContent = text;
    btn.disabled = (m === 'busy');
  }}
  function ask(path, opts) {{
    var ctl = new AbortController();
    var t = setTimeout(function () {{ ctl.abort(); }}, 4000);
    opts = opts || {{}}; opts.signal = ctl.signal; opts.cache = 'no-store';
    return fetch(path, opts).then(function (r) {{
      clearTimeout(t);
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    }});
  }}
  ask('api/status').then(function (s) {{
    live = !!(s && s.live);
    mode(live ? 'live' : 'static',
         live ? 'Update data' : 'Copy refresh command');
    if (live && s.running) poll();
  }}).catch(function () {{ mode('static', 'Copy refresh command'); }});

  function poll() {{
    mode('busy', 'Updating\\u2026');
    say('Downloading prices and rebuilding charts. This takes about half a minute.');
    (function tick() {{
      setTimeout(function () {{
        ask('api/status').then(function (s) {{
          if (s.running) return tick();
          if (s.error) {{ mode('live', 'Update data');
            say('Update failed: ' + s.error, 'err'); }}
          else {{ say('Updated. Reloading\\u2026', 'ok'); location.reload(); }}
        }}).catch(function () {{ tick(); }});
      }}, 1500);
    }})();
  }}
  btn.addEventListener('click', function () {{
    if (!live) {{
      var done = function () {{
        say('Run this in Terminal, then reload this page:', null, D.cmd);
      }};
      if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(D.cmd).then(function () {{
          say('Command copied. Run it in Terminal, then reload this page:',
              'ok', D.cmd);
        }}).catch(done);
      }} else {{ done(); }}
      return;
    }}
    mode('busy', 'Updating\\u2026');
    ask('api/refresh', {{method: 'POST'}}).then(poll).catch(function (e) {{
      mode('live', 'Update data');
      say('Could not start the update: ' + e.message, 'err');
    }});
  }});
}})();
</script>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the portable RRG dashboard")
    ap.add_argument("--universe", choices=list(config.UNIVERSES),
                    default=config.DEFAULT_UNIVERSE)
    config.activate(ap.parse_args().universe)
    OUT, OUT_FRAGMENT = out_paths()

    frames = {}
    for tf in ("weekly", "daily"):
        f = load_timeframe(tf)
        if f:
            frames[tf] = f
    if "weekly" not in frames:
        raise SystemExit(f"run `python3 update.py --universe "
                         f"{config.UNIVERSE}` first — no CSVs in "
                         f"{config.OUTPUT_DIR}")

    body = build(frames, load_alerts())
    # Pure ASCII: every non-ASCII glyph becomes a numeric character reference,
    # so the page renders identically whatever charset a host assumes.
    body = body.encode("ascii", "xmlcharrefreplace").decode("ascii")

    asof = frames["weekly"]["dlabels"][-1]
    standalone = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{config.LABEL} &mdash; RRG &middot; {asof}</title>\n'
        '</head>\n<body>\n' + body + '\n</body>\n</html>\n')

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        f.write(standalone)
    with open(OUT_FRAGMENT, "w") as f:
        f.write(body)
    span = len(frames["weekly"]["dates"])
    print(f"dashboard: {OUT}  ({os.path.getsize(OUT) / 1024:.0f} KB, "
          f"{span} weekly periods on the timeline)")
    print(f"fragment:  {OUT_FRAGMENT}")


if __name__ == "__main__":
    main()
