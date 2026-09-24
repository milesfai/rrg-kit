"""
build_site.py — assemble the static site published to GitHub Pages.

Collects each universe's portable dashboard (the small, self-contained one —
not the 5MB plotly files) into ./site/ and writes an index over them.

    python3 build_site.py           # -> site/

The published pages are snapshots: a static host cannot re-run Python.
Freshness comes from CI rebuilding and redeploying — weekly on a schedule, or
on demand: on a CI build the index's Refresh button (and each dashboard's
Update button) opens the workflow's GitHub page, whose "Run workflow" rebuilds
everything. The index states each page's last data bar.
"""

from __future__ import annotations

import datetime
import os
import shutil

import config

SITE = "site"


def universe_rows() -> list[dict]:
    rows = []
    for name, spec in config.UNIVERSES.items():
        src = os.path.join("output", name, "dashboard.html")
        if not os.path.exists(src):
            continue
        # last bar in the data, so the index states data freshness honestly
        # instead of the build time
        try:
            import csv
            with open(os.path.join("output", name, "rrg_weekly.csv")) as f:
                last = max(r["date"] for r in csv.DictReader(f))
        except Exception:
            last = "?"
        rows.append(dict(
            name=name, label=spec["label"], last=last,
            benchmark=spec.get("benchmark_label", spec["benchmark"]),
            members=len(spec["members"]),
            size_kb=round(os.path.getsize(src) / 1024),
            src=src,
        ))
    return rows


INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RRG dashboards</title>
<style>
:root{{color-scheme:light dark;--line:#363b45;--accent:#5b9bd5;--muted:#767d88}}
@media(prefers-color-scheme:light){{:root{{--line:#cfccc6;--muted:#8a8880}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:#14161a;color:#e6e8ec;
font:15px system-ui,-apple-system,"Segoe UI",sans-serif;
display:flex;min-height:100vh;align-items:center;justify-content:center}}
@media(prefers-color-scheme:light){{body{{background:#faf9f7;color:#16181d}}}}
.w{{max-width:620px;padding:32px;width:100%}}
h1{{font-size:22px;margin:0 0 4px;letter-spacing:-.02em}}
.sub{{color:var(--muted);margin:0 0 24px;font-size:14px;line-height:1.5}}
a.row{{display:flex;align-items:center;gap:14px;padding:14px 16px;
margin-bottom:8px;border:1px solid var(--line);border-radius:6px;
text-decoration:none;color:inherit}}
a.row:hover{{border-color:var(--accent)}}
a.row:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.t{{flex:1;min-width:0}}
.t b{{display:block;font-size:15px}}
.t span,.kb{{font-family:ui-monospace,Menlo,monospace;font-size:11px;
color:var(--muted);letter-spacing:.05em}}
footer{{margin-top:24px;padding-top:16px;border-top:1px solid var(--line);
font-size:12.5px;color:var(--muted);line-height:1.6}}
code{{font-family:ui-monospace,Menlo,monospace;font-size:12px}}
.top{{display:flex;align-items:baseline;justify-content:space-between;
gap:12px;flex-wrap:wrap;margin-bottom:4px}}
.top h1{{margin:0}}
a.btn{{font-family:ui-monospace,Menlo,monospace;font-size:11px;
letter-spacing:.06em;text-transform:uppercase;padding:7px 14px;
border:1px solid var(--line);border-radius:4px;color:inherit;
text-decoration:none;white-space:nowrap}}
a.btn:hover{{border-color:var(--accent)}}
a.btn:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
</style></head><body><div class="w">
<div class="top"><h1>Relative Rotation Graphs</h1>{refresh}</div>
<p class="sub">Rebuilt automatically every week from Yahoo Finance data.
Each page carries {history} weeks of history on a timeline you can scrub,
plus conviction metrics and rotation alerts.</p>
{rows}
<footer>Built <b>{built}</b> &middot; rebuilt weekly by GitHub Actions; each
row states the last bar in its data.<br>
{refresh_note}<br>
Standard public approximation of JdK RS-Ratio / RS-Momentum. Sector rotation
is context, not a trade trigger; not investment advice.</footer>
</div></body></html>"""


def main() -> None:
    rows = universe_rows()
    if not rows:
        raise SystemExit("no dashboards found — run update.py + "
                         "make_dashboard.py first")

    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)

    html_rows = []
    for r in rows:
        dest = os.path.join(SITE, f"{r['name']}.html")
        shutil.copyfile(r["src"], dest)
        html_rows.append(
            f'<a class="row" href="{r["name"]}.html"><span class="t">'
            f'<b>{r["label"]}</b>'
            f'<span>{r["members"]} members &middot; vs {r["benchmark"]}'
            f' &middot; data to {r["last"]}</span>'
            f'</span><span class="kb">{r["size_kb"]} KB</span></a>')

    built = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d %b %Y %H:%M UTC")
    url = config.ci_refresh_url()
    if url:
        refresh = (f'<a class="btn" href="{url}" target="_blank" '
                   f'rel="noopener">Refresh now</a>')
        note = ("<b>Refresh now</b> opens GitHub Actions &mdash; click "
                "<i>Run workflow</i> and every page is rebuilt from fresh "
                "data in about two minutes.")
    else:
        refresh = ""
        note = ("Run <code>python3 update.py</code> locally for on-demand "
                "refreshes.")
    page = INDEX.format(rows="".join(html_rows), built=built,
                        history=config.HISTORY_PERIODS.get("weekly", 78),
                        refresh=refresh, refresh_note=note)
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(page)

    total = sum(r["size_kb"] for r in rows)
    print(f"site/: {len(rows)} dashboards + index ({total} KB total)")
    for r in rows:
        print(f"  {r['name']}.html  {r['label']}")


if __name__ == "__main__":
    main()
