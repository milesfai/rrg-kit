# rrg-kit — US Sector Rotation Relative Rotation Graph

Interactive RRG (Relative Rotation Graph) tracking the 11 GICS sector ETFs
against SPY, on weekly (core allocation) and daily (short-term timing)
timeframes. Built for two uses: personal trading signal review and
publication-quality screenshots for video production.

## Quickstart

```bash
pip install -r requirements.txt
python3 update.py && python3 make_dashboard.py
open output/sectors/dashboard.html
```

## Universes — what to plot

The kit ships three universes, defined in `config.py`. Each writes to its own
folder under `output/`, so they never overwrite each other.

| `--universe` | Chart | Benchmark | Members |
|---|---|---|---|
| `sectors` *(default)* | US Sector Rotation | SPY | 11 GICS sector ETFs |
| `countries` | Global Country Rotation | ACWI | 16 single-country ETFs |
| `countries_ew` | Country Rotation vs Equal-Weight | **synthetic EW16** | the same 16 |
| `hongkong` | Hong Kong Market Rotation | ^HSI | 16 HSI heavyweight stocks |
| `asia` | Asia-Pacific Rotation | AAXJ | 12 Asia-Pacific markets |

The `hongkong` universe is stock-level (HSI industry sub-indices aren't
reliably on Yahoo). Everything trades in HKD on one exchange, so unlike the
country charts there is no FX or time-zone caveat — relative strength is a
pure equity story. Chart labels drop the `.HK` suffix (`0700.HK` → `0700`);
data files and alerts keep the full Yahoo symbol. Single-stock tails are
noisier than sector/country ETFs: earnings gaps yank a tail in one bar, so
lean on straightness (sustained trend) over velocity (one-week jump), and
treat readings around results dates with extra care.

### Synthetic benchmarks

A `benchmark` value starting with `=` is **built from the members instead of
downloaded**. `"=EW"` is an equal-weight basket rebalanced every bar — the
return of the *typical* member — so 100 means "in line with the average
market" rather than "in line with the cap-weighted index". Add
`benchmark_label` to control what the charts display (`=EW` → `EW16`).

Why it matters: ACWI is ~63% US, so measuring the US against ACWI is largely
self-comparison. Measured empirically, ACWI's variation *independent of the
US* is only 3.4% annualised versus 8.7% for the equal-weight basket — the
cap-weighted yardstick carries about a third of the information about the US.
That is why `countries` puts the US in **Leading** while `countries_ew` puts
it in **Weakening** on the same date. Neither is wrong; they answer different
questions. Use `countries` for a global mandate, `countries_ew` for breadth.

```bash
python3 update.py --universe countries
python3 make_dashboard.py --universe countries
```

Add your own by copying a block in `config.UNIVERSES` — give it a `label`,
`noun`, `benchmark` and `members`. Up to 16 members get a distinct color;
beyond that colors recycle (ticker labels still carry identity, but 16 is the
clean maximum for a readable chart).

### Reading the country chart — three things that differ from sectors

1. **The benchmark is the whole world, and the US is a member.** With ACWI as
   the yardstick, "100" means *in line with global equities*, so SPY sitting
   in Leading is itself the headline — it means US outperformance, which a
   US-benchmarked chart can never show you.
2. **Currency is baked in.** These are US-listed, USD-denominated ETFs, so
   relative strength includes the FX move. That is usually what a USD investor
   wants, but a market can lead purely because its currency rallied — check the
   local index before calling it an equity story.
3. **Trading hours don't line up.** Asian and European markets close before US
   hours, so the ETF price is a US-hours proxy for a market that already shut.
   This mostly washes out weekly; on the daily chart treat single-bar moves in
   EWJ/MCHI/EWH with a pinch of salt.

Otherwise the interpretation below is identical — the quadrants, conviction
metrics and rotation rules all carry over.

### Choosing the benchmark — measure it, don't argue about it

```bash
python3 benchmark_check.py --universe countries
```

`benchmark_check.py` answers three questions with data rather than opinion:

1. **What is the benchmark made of?** It regresses the benchmark on a US proxy
   (SPY) and an ex-US proxy (VEU). The fitted split approximates its real
   country-cap composition, and the R² against the US *alone* shows how much a
   "world" index is really just America.
2. **How different are the candidates?** Annualised return/vol and the full
   correlation matrix across ACWI / VT / URTH / VEU / SPY / equal-weight.
3. **Does the choice change the answer?** It recomputes the whole RRG under
   each candidate and counts how many members land in a different quadrant.

On the 16-country universe (3y daily, run Aug 2026) the verdict was blunt:
ACWI is ~63% US and tracks the US alone with R² 0.94, and **7 of 16 countries
(44%) change quadrant depending on which benchmark you pick**. ACWI and VT are
interchangeable (0 differences); ACWI vs an equal-weight basket differs on 19%;
developed-only (URTH) vs ex-US (VEU) differ on 38%. So pick deliberately:

| If the question is… | Use |
|---|---|
| "Which market should I overweight in a global portfolio?" | **ACWI / VT** — cap-weighted, matches how a global mandate is actually measured |
| "Which market is outperforming the typical market?" | **equal-weight (EQW)** — strips out US mega-cap dominance |
| "Which market is beating America?" | **SPY** — makes the comparison explicit rather than hiding it inside ACWI |
| "Where should I rotate within developed markets?" | **URTH** — don't let EM volatility set the yardstick |

The kit's default is ACWI because a cap-weighted global index is what most
mandates are benchmarked against — but if your video is about *breadth*
(is the rally broadening beyond the US?), the equal-weight basket tells that
story far better.

Options:

```bash
python update.py --timeframe weekly   # one timeframe only
python update.py --theme light        # light theme (dark is default)
python update.py --tail 8             # shorter trails
python update.py --animate            # also write animated versions
python update.py --animate --frames 60   # longer animation (default 40)
python update.py --sample             # offline demo (synthetic data)
```

Each run writes to `output/`:

| File | What it is |
|---|---|
| `rrg_weekly.html`, `rrg_daily.html` | self-contained interactive charts (work offline; camera icon exports a 2× PNG for video) |
| `rrg_weekly_anim.html`, `rrg_daily_anim.html` | (with `--animate`) the same chart with a ▶ play button and a date slider — trails rotate through the quadrants over the last `--frames` periods |
| `rrg_weekly.csv`, `rrg_daily.csv` | the plotted snapshot as a table — the numbers behind every point |
| `rrg_weekly_summary.csv`, `rrg_daily_summary.csv` | one row per sector: quadrant, coordinates, and conviction metrics |
| `rrg_agreement.csv` | weekly-vs-daily cross-check verdicts (when both timeframes run) |
| `alerts.log` | dated rotation events, appended each run (see Rotation alerts) |
| `dashboard.html` | portable one-page summary with a **timeline scrubber** — chart, table, agreement, alerts. ~115 KB, no plotly, works on a phone (see Viewing) |
| `rrg_weekly_history.csv`, `rrg_daily_history.csv` | longer history (78 weeks / 150 days) that feeds the dashboard timeline |

and prints a console summary: each sector's quadrant, coordinates, and whether
its momentum is improving or fading vs the prior bar.

## Files

| File | Role |
|---|---|
| `config.py` | **the only file you normally edit** — sectors, benchmark, timeframe parameters, theme, palette |
| `rrg.py` | data download + JdK RS-Ratio / RS-Momentum math |
| `plot_rrg.py` | plotly figure builder (quadrants, trails, bubbles, labels) |
| `update.py` | CLI entry point |
| `sample_data.py` | deterministic synthetic data for offline testing |

## How the math works

The exact JdK formulas are proprietary (Julius de Kempenaer / Optuma); this is
the standard public approximation, which reproduces the qualitative behavior —
values normalized around 100 and clockwise rotation through the quadrants.

1. **Relative strength**: `RS = 100 × price_sector / price_SPY`. Rising RS =
   outperforming, regardless of absolute direction.
2. **JdK RS-Ratio (x-axis)**: rolling z-score of RS over `window` bars,
   re-centered at 100: `ratio = 100 + (RS − mean(RS)) / std(RS)`. So ">100"
   means "strong vs its own recent range against the benchmark" — every sector
   lands on the same scale even though XLK and XLU have wildly different RS
   levels.
3. **JdK RS-Momentum (y-axis)**: rate of change of RS-Ratio over
   `momentum_period` bars, z-scored the same way. This is the *trend of the
   relative trend*: momentum crosses 100 before ratio does, which is exactly
   why sectors rotate clockwise — Improving → Leading → Weakening → Lagging.
4. RS gets a light SMA (`smooth`) before normalization so trails curl rather
   than jitter. More smoothing = cleaner tails but more lag.

Extra dimensions: **bubble size** = the sector's share of universe-wide
20-period average dollar volume (where the money is trading); **hover** shows
annualized realized volatility, average dollar volume, and quadrant.

## Reading the chart

| Quadrant | Meaning | Classic playbook |
|---|---|---|
| **Leading** (top-right) | strong and still accelerating | hold / add; core overweight zone |
| **Weakening** (bottom-right) | still strong, momentum fading | take profits, tighten stops; do NOT add |
| **Lagging** (bottom-left) | weak and decelerating | avoid / underweight / short candidates |
| **Improving** (top-left) | weak but momentum turning up | watchlist; early entries for aggressive money |

Rules of thumb that survive contact with real data:

- **The rotation is clockwise but not on a timer.** Sectors can loop back
  (Improving → Lagging again) without ever reaching Leading. A quadrant change
  is a *checkpoint*, not a signal by itself.
- **The strongest buy setup** is a sector crossing from Improving into Leading
  (both coordinates pushing through 100) with a *long, straight, rightward*
  tail — long tail = fast rotation = conviction. Short curled tails near
  (100,100) are noise; ignore them.
- **Heading beats position.** A sector at (101, 100.2) heading down is worse
  than one at (99.5, 100.8) heading right. The console summary's
  `heading` column encodes this.
- **Conviction is now quantified.** The summary's three metric columns turn
  the visual tail rules into screenable numbers:
  - `velocity` — RRG units moved per bar over the last 4 bars. Roughly:
    < 0.15 is drift, > 0.35 is a decisive rotation.
  - `straightness` — net move ÷ path length over the last 8 bars. Above
    ~0.8 the tail is a straight arrow (conviction); below ~0.5 it's curling
    in place (noise, whatever quadrant it's in).
  - `dir` — direction of travel: → gaining strength, ↑ gaining momentum,
    ← losing strength, ↓ losing momentum. The strong buy profile is ↗ or →
    with high velocity AND high straightness; the classic exit is ↘/↓ from
    inside Leading.
- **Check the agreement table before acting.** When both timeframes run, the
  final table cross-checks them: `aligned` (same quadrant — act with
  confidence), `partial` (transition in progress — the daily usually shows
  where the weekly is going), `diverging` (stand aside).
- **Distance from center = strength of the trend above the trend.** Extremes
  also mean-revert: a sector at RS-Ratio 103 on the weekly is more often a
  profit-taking zone than an entry.
- **Weekly decides, daily times.** Take allocation decisions from the weekly
  chart; use the daily chart only to time entries into sectors the weekly
  already favors. Acting on daily rotations against the weekly picture is the
  most common RRG mistake.
- **Bubble size is confirmation.** A rotation into Leading on *rising* volume
  share is institutional; the same rotation with a shrinking bubble is often
  just the benchmark falling faster than the sector.

### US-market context worth narrating (for the videos too)

- **Earnings season** (mid-Jan/Apr/Jul/Oct): sector RS gets gappy as
  mega-caps report — XLK/XLC/XLY are dominated by a handful of names, so one
  NVDA or META print can yank the whole sector's tail. Wait for the
  post-earnings bar before trusting a fresh quadrant crossing.
- **Fed policy**: rate-cut expectation phases systematically favor XLU, XLRE,
  XLK (duration-sensitive); hawkish repricing favors XLF (net interest
  margins) and XLE. If the whole left side of the chart is defensives
  (XLP/XLU/XLV improving together), the market is pricing risk-off — that
  *combination* is itself a macro signal.
- **AI capex cycle**: the XLK↔XLU/XLI linkage is new — data-center buildout
  pulls utilities and industrials along with tech. When XLK rotates into
  Weakening but SMH stays Leading (add it in `config.py`), the story is
  breadth narrowing inside tech, not tech dying.

## A simple backtest sketch

Monthly rebalance, hold sectors in Leading (or Improving with strong
momentum), equal weight, benchmark = buy-and-hold SPY:

```python
import pandas as pd
import config
from rrg import download_prices, build_rrg_table

close, volume = download_prices(list(config.SECTORS), config.BENCHMARK, "10y")
table = build_rrg_table(close, volume, config.BENCHMARK, config.TIMEFRAMES["weekly"])

wide_q = table.pivot(index="date", columns="ticker", values="quadrant")
wide_mom = table.pivot(index="date", columns="ticker", values="rs_momentum")
weekly_close = close.resample("W-FRI").last()
rets = weekly_close.pct_change().shift(-1)          # next week's return

# signal: in Leading, or Improving with momentum > 101
hold = (wide_q == "Leading") | ((wide_q == "Improving") & (wide_mom > 101))
hold = hold.reindex(rets.index).ffill()

sect = rets[list(config.SECTORS)]
strat = (sect * hold).sum(axis=1) / hold.sum(axis=1).replace(0, pd.NA)
strat = strat.fillna(0)                              # in cash when nothing qualifies
report = pd.DataFrame({"strategy": (1 + strat).cumprod(),
                       "SPY": (1 + rets[config.BENCHMARK]).cumprod()})
print(report.tail())
```

Honest caveats before trusting any backtest of this:

- `window`, `momentum_period`, and the "momentum > 101" threshold are exactly
  the knobs that overfit. Test *one* parameter set chosen on half the history
  against the other half; if the edge only exists for one magic window value,
  it isn't an edge.
- Sector rotation strategies live or die on **transaction costs and whipsaw**
  — count the number of trades the signal generates.
- Add a regime filter (e.g., only take longs when SPY > its 40-week MA);
  rotation signals degrade badly in high-correlation crash regimes where all
  11 sectors move together.

## Viewing the output

The HTML files are self-contained — no server needed. Ways in:

- **Double-click `Open RRG (live).command`** — starts the local server and
  opens the dashboard **with a working Update button** (see below). Close the
  Terminal window it opens to stop the server.
- **Double-click `Open RRG.command`** — just opens the dashboard and the
  weekly chart as files, no server, no Update button.
- **Finder** — double-click any `.html` in `output/`.
- **Terminal** — `open output/dashboard.html`

### The Update button

A static HTML page can't run Python, so the button adapts to how the page is
being served:

| Opened via | Button | What it does |
|---|---|---|
| `Open RRG (live).command` / `python3 serve.py` | **Update data** (green dot) | Re-runs `update.py` + `make_dashboard.py`, shows progress, reloads with fresh data (~30s) |
| A file, or the hosted copy | **Copy refresh command** (grey dot) | Copies/shows the command to run in Terminal |

`serve.py` serves `output/` on <http://localhost:8760> and exposes
`GET /<universe>/api/status` and `POST /<universe>/api/refresh`; each page
probes for that API on load and picks its mode. Options: `--port N`,
`--animate` (rebuild the animation files on refresh too, slower),
`--no-open`. Launching it twice is safe — a second launch detects the
running instance and just opens the browser.

**The index page** at <http://localhost:8760/> lists every built dashboard
with its data timestamp, a per-universe **Refresh** button, and **Refresh
all** (runs each universe in turn, ~30s apiece, with live status).

**The hosted claude.ai pages are snapshots by design.** An artifact page's
CSP blocks all network access, so it cannot pull new prices no matter what
button it has — its Update button hands you the local command instead.
Updating a hosted page = regenerating locally + asking Claude to republish.

Note: opening these through a chat/file-link UI often shows the raw HTML
source instead of rendering it, and any `localhost:…` address only works
while a preview server is actually running. Finder or `open` always work.

### Reviewing past data — two timelines

**The dashboard timeline** (`dashboard.html`) is the full one: drag the slider,
or use ← / → and **Latest**, and the chart, metrics table, agreement verdicts
and alert list *all* re-render as of that date. Range is 78 weeks on the
weekly tab and 150 days on the daily tab (set in `config.HISTORY_PERIODS`);
each tab remembers its own position. The axis scale is fixed across the whole
history so nothing rescales as you scrub.

**The animation timeline** (`rrg_*_anim.html`, written by `update.py
--animate`) has a play button and date slider covering the last 40 periods.
It only moves the chart — no table or metrics — but it *plays*, which is what
you want for video capture.

One honesty note: price history goes back years, but `alerts.log` only
contains events from the day alert detection was first run. Scrub earlier
than that and the alerts panel is legitimately empty — the chart and table
are still fully accurate, since they're recomputed from prices.

### Export for reports and video

The **Export for report** row under the chart turns whatever is currently on
screen into a finished graphic. It always exports the date the timeline is
on, so you can scrub to any past week and export that week's figure — the
filename carries the date (`rrg_report_weekly_2026-01-30.png`).

| Button | Output | Use |
|---|---|---|
| **Figure PNG** | 16:9, chart + ranked table, titled and dated | drops straight into a slide or a video frame |
| **Chart PNG** | the chart alone, portrait | when the table is in the deck already |
| **Figure SVG** | the 16:9 figure as vector | scales to any size; editable in Illustrator / After Effects |
| **Copy figure** | 16:9 PNG to the clipboard | paste directly into Keynote, PowerPoint, Docs |

The `at 1× / 2× / 3×` selector sets resolution — 2× gives a 3840×2160 figure
(4K), 3× gives 5760×3240 for print or heavy cropping.

How it works: the export doesn't screenshot the page. It rebuilds the chart
(and draws the table) as a fresh standalone SVG with every colour resolved to
a literal value, then rasterises it through a canvas. So the output is clean
at any resolution, has no UI chrome in it, follows the current light/dark
theme, and works identically on the hosted copy — no server, no library.

**If automatic download is blocked.** Embedded viewers (the hosted copy runs
in a sandboxed iframe) forbid `<a download>`, so a click would otherwise do
nothing. The page detects that and shows the finished image inline instead:
right-click → *Save image as…* (long-press on mobile), or use **Copy figure**
and paste straight into your deck. Opening `dashboard.html` locally — via
`Open RRG (live).command` or Finder — downloads normally.

### dashboard.html vs the plotly charts

`update.py` writes the full interactive plotly charts (4.8 MB each — hover,
zoom, legend isolation, PNG export: the working tool). `make_dashboard.py`
writes `dashboard.html`, a 75 KB single page with a hand-drawn SVG version of
the same chart plus the summary table, agreement verdicts and recent alerts —
built to open instantly on a phone and to be published as a hosted page.

```bash
python3 update.py && python3 make_dashboard.py
```

It also writes `dashboard_fragment.html` (the same page without the
`<html>/<head>` wrapper) for embedding or publishing.

## Rotation alerts

Every run compares the latest bar against the prior ones (per timeframe) and
appends *new* events to `output/alerts.log`:

- **Quadrant crossing** — `XLRE Real Estate: Improving → Leading` — the
  headline signal. Only fires once the position has cleared the crossed axis
  by ≥ 0.05, so a sector kissing the 100 line doesn't flap in and out.
- **Confirmed leadership** — a crossing into Leading while the sector's share
  of universe dollar volume is rising gets tagged `CONFIRMED` — rotation
  backed by money, not just price drift.
- **Momentum reversal** — heading flipped up/down vs the prior bar by ≥ 0.15.
  This is the early warning that usually precedes a quadrant change.

Dedup is by event identity (bar date + sector + event type), not by the
exact numbers — so intraday reruns while the market is open won't repeat an
alert just because prices drifted. Detection logic and both thresholds live
at the top of `alerts.py`.

Reading the log: quadrant crossings are actionable checkpoints; momentum
reversals are context. A crossing that appears on the weekly AND the daily
log within a few days of each other is the strongest form.

## Customization

- **Add sectors/industries**: append to `SECTORS` in `config.py` (SMH, IGV,
  KRE, XBI, ITA are pre-typed in comments). Append at the END — colors are
  assigned by position, and existing sectors must keep their colors. Past 11
  entries, colors recycle; prefer swapping IN a focused universe (e.g., 6
  tech-adjacent ETFs) over piling 15+ onto one chart.
- **Benchmark**: any ticker — use QQQ for a tech-internal rotation view, or
  an equal-weight benchmark (RSP) to strip out mega-cap dominance.
- **Parameters**: in `TIMEFRAMES`. `window` sets how far back "normal" is;
  `smooth` trades noise for lag; `tail` is display-only.
- **Theme**: `--theme light` for reports; colors for both themes live in
  `config.PALETTE`.

### Design notes (why the chart looks the way it does)

- Both 11-color palettes use muted "research desk" hues, machine-optimized
  for colorblind separation (Machado protan/deutan simulation, all pairs):
  minimum pair distance dE 12.2 (dark) / 15.6 (light), above the 12 target.
  **Every head still carries a persistent ticker label** and a CSV table view
  ships next to each chart: identity never relies on color alone. If you
  re-color, keep the labels.
- Head labels auto-dodge: when several sectors bunch together, nearby labels
  cycle top → bottom → right → left so they stay readable.
- Dark theme is a blue-charcoal terminal look (`#16181d` surface); light is
  a warm paper white for print/reports. Both live in `config.THEMES`.
- Quadrant tints use reserved status hues (green/amber/red/blue) at low
  alpha — they encode state, and are deliberately never reused as series
  colors.
- Axes are symmetric around 100 with equal x/y scale so the four quadrants
  are visually equal — don't swap in autoscale.
- For video: charts are fixed 980×880 for consistent framing; the toolbar
  camera exports 2× PNG. Click a legend entry twice to isolate one sector for
  a story beat, then screenshot.

### Animation workflow (video)

`--animate` produces `rrg_<timeframe>_anim.html`: press ▶ and screen-record
the browser (QuickTime → New Screen Recording, or OBS), or scrub the date
slider to a specific week while narrating. Notes:

- Playback speed is ~0.7s per period; change `frame_ms` in
  `make_rrg_animation` (in `plot_rrg.py`) to slow it down for narration.
- Isolate one or two sectors via the legend FIRST, then press play — a single
  tail rotating clockwise is the clearest story shot.
- The axis range is fixed across all frames on purpose (no camera jumps);
  don't autoscale mid-recording.
- Weekly default (40 frames ≈ 9 months of rotation) makes a good ~30s clip.

## Automation

### In the cloud — GitHub Actions → GitHub Pages

`.github/workflows/update.yml` rebuilds **every** universe each Friday at
22:00 UTC (18:00 New York, after the US close; 06:00 Saturday Hong Kong) and
publishes the dashboards to GitHub Pages. It can also be run on demand from
the repo's **Actions** tab (*Rebuild RRG dashboards → Run workflow*).

The site is assembled by `build_site.py`, which copies each universe's
portable dashboard into `site/` and writes an index. Only those (~150 KB
each) ship — the multi-megabyte plotly charts stay local and are gitignored.
A verification step fails the run rather than deploying a partial site if any
page is missing, so a bad data day can't quietly replace a good build.

Nothing needs to run on your Mac for this, and no secrets are required — the
data source is public.

**Live site:** <https://milesfai.github.io/rrg-kit/>

Each universe is retried up to three times with backoff, because Yahoo
Finance intermittently throttles datacenter IPs — the single most likely
cause of a failed run. If a run does fail, the previous deploy stays up; fix
by re-running the workflow from the Actions tab.

### Locally — cron (optional)

If you also want local refreshes (they additionally build the plotly charts
and animations, which the cloud build skips):

```
30 17 * * 5 cd ~/path/to/rrg-kit && /usr/bin/python3 update.py --animate >> output/update.log 2>&1
```

Manage with `crontab -l` / `-e` / `-r`. Two caveats: the Mac must be awake at
fire time (cron skips missed runs — just run it manually if it was asleep),
and point it at the python that has the dependencies installed (`which
python3`).

## Caveats

- This is the standard *approximation* of JdK RS-Ratio/Momentum, not the
  proprietary formula — quadrant assignments broadly match StockCharts/Optuma
  but exact coordinates differ.
- yfinance is unofficial; if Yahoo changes something, `--sample` still lets
  you produce demo charts while you patch.
- Not investment advice; sector rotation signals are slow-moving context, not
  trade triggers on their own.
