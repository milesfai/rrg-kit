"""
rrg-kit configuration — edit this file to customize; nothing else needs touching.

Universes (what to plot), benchmarks, timeframe parameters and chart theme all
live here. Pick a universe at the command line:

    python3 update.py                        # default universe
    python3 update.py --universe countries   # country rotation

Each universe writes to its own folder under output/, so they never overwrite
each other.
"""

# Shared member list, so the cap-weighted and equal-weight country universes
# stay in lockstep — edit once, both charts follow.
COUNTRY_MEMBERS = {
    "SPY":  "United States",
    "EWJ":  "Japan",
    "MCHI": "China",
    "EWH":  "Hong Kong",
    "EWT":  "Taiwan",
    "EWY":  "South Korea",
    "INDA": "India",
    "EWA":  "Australia",
    "EWS":  "Singapore",
    "EWG":  "Germany",
    "EWU":  "United Kingdom",
    "EWQ":  "France",
    "EWL":  "Switzerland",
    "EWC":  "Canada",
    "EWZ":  "Brazil",
    "EWW":  "Mexico",
    # ── other liquid single-country ETFs ──
    # "EWP": "Spain", "EWI": "Italy", "EWN": "Netherlands",
    # "EWD": "Sweden", "EZA": "South Africa", "EIDO": "Indonesia",
    # "THD": "Thailand", "EWM": "Malaysia", "TUR": "Turkey",
}

# ── Universes ────────────────────────────────────────────────────────────────
# Order matters inside `members`: chart colors are assigned in this order.
# When adding, APPEND at the end so existing entries keep their color.
# Up to 16 members get a distinct color; past that colors recycle (every head
# carries its ticker label, so identity still holds, but 16 is the clean max).
#
# `benchmark` is normally a ticker. A value starting with "=" is SYNTHETIC and
# is computed from the members instead of downloaded — see rrg.synthetic_index.
#   "=EW"  equal-weight, daily-rebalanced basket of this universe's members
UNIVERSES = {
    "sectors": dict(
        label="US Sector Rotation",
        noun="GICS sectors",
        benchmark="SPY",        # S&P 500 proxy; "^GSPC" also works
        members={
            "XLK":  "Technology",
            "XLF":  "Financials",
            "XLV":  "Healthcare",
            "XLY":  "Cons. Discretionary",
            "XLP":  "Cons. Staples",
            "XLI":  "Industrials",
            "XLE":  "Energy",
            "XLU":  "Utilities",
            "XLRE": "Real Estate",
            "XLB":  "Materials",
            "XLC":  "Communication Svcs",
            # ── optional finer slices — uncomment to add ──
            # "SMH":  "Semiconductors",
            # "IGV":  "Software",
            # "KRE":  "Regional Banks",
            # "XBI":  "Biotech",
            # "ITA":  "Aerospace & Defense",
        },
    ),

    # Country rotation. Benchmark is MSCI All-Country World (ACWI), so "100"
    # means "in line with global equities" — the US is a MEMBER here, not the
    # yardstick, which is what makes US-vs-rest-of-world readable.
    # NOTE: these are US-listed, USD-denominated ETFs, so relative strength
    # includes the currency move. That is usually what a USD investor wants,
    # but a country can lead purely on FX — see the README.
    "countries": dict(
        label="Global Country Rotation",
        noun="country markets",
        benchmark="ACWI",       # or "VT" (Vanguard Total World)
        members=COUNTRY_MEMBERS,
    ),

    # Same members, equal-weight yardstick. ACWI is ~63% US, so a country
    # "beating ACWI" is largely a statement about beating America — and the US
    # is being measured against itself. Against an equal-weight basket, 100
    # means "in line with the TYPICAL market", which is the breadth question:
    # is the rally broadening beyond the mega-cap US, or not?
    "countries_ew": dict(
        label="Country Rotation vs Equal-Weight",
        noun="country markets",
        benchmark="=EW",                 # synthetic, built from the members
        benchmark_label="EW16",
        members=COUNTRY_MEMBERS,
    ),

    # Hong Kong market: HSI heavyweights vs the Hang Seng Index itself.
    # Stock-level rather than sector-level (HSI industry sub-indices are not
    # reliably available via Yahoo). All HKD, one exchange, one time zone —
    # so unlike the country charts, relative strength here is a pure equity
    # story with no FX component.
    "hongkong": dict(
        label="Hong Kong Market Rotation",
        noun="HSI heavyweights",
        benchmark="^HSI",
        benchmark_label="HSI",
        members={
            "0700.HK": "Tencent 騰訊",
            "9988.HK": "Alibaba 阿里巴巴",
            "3690.HK": "Meituan 美團",
            "1810.HK": "Xiaomi 小米",
            "9618.HK": "JD.com 京東",
            "0005.HK": "HSBC 滙豐",
            "1299.HK": "AIA 友邦",
            "2318.HK": "Ping An 平安",
            "0939.HK": "CCB 建行",
            "0388.HK": "HKEX 港交所",
            "1211.HK": "BYD 比亞迪",
            "0883.HK": "CNOOC 中海油",
            "0941.HK": "China Mobile 中移動",
            "2020.HK": "ANTA 安踏",
            "0016.HK": "SHKP 新鴻基",
            "0027.HK": "Galaxy 銀河娛樂",
            # swap freely — e.g. "1024.HK": "Kuaishou 快手",
            # "2628.HK": "China Life 中人壽", "1398.HK": "ICBC 工行"
        },
    ),

    # Asia-only view — a tighter chart for regional storytelling.
    "asia": dict(
        label="Asia-Pacific Rotation",
        noun="Asia-Pacific markets",
        benchmark="AAXJ",       # MSCI All Country Asia ex-Japan
        members={
            "EWJ":  "Japan",
            "MCHI": "China",
            "EWH":  "Hong Kong",
            "EWT":  "Taiwan",
            "EWY":  "South Korea",
            "INDA": "India",
            "EWS":  "Singapore",
            "EWA":  "Australia",
            "EWM":  "Malaysia",
            "EIDO": "Indonesia",
            "THD":  "Thailand",
            "EPHE": "Philippines",
        },
    ),
}

DEFAULT_UNIVERSE = "sectors"

# ── Active universe (set by activate(); don't edit these by hand) ────────────
UNIVERSE = DEFAULT_UNIVERSE
LABEL = UNIVERSES[DEFAULT_UNIVERSE]["label"]
NOUN = UNIVERSES[DEFAULT_UNIVERSE]["noun"]
BENCHMARK = UNIVERSES[DEFAULT_UNIVERSE]["benchmark"]
BENCHMARK_LABEL = BENCHMARK          # what the charts display
SECTORS = UNIVERSES[DEFAULT_UNIVERSE]["members"]

SYNTHETIC = "="                      # benchmark prefix marking a built series


def is_synthetic(benchmark: str | None = None) -> bool:
    return (benchmark or BENCHMARK).startswith(SYNTHETIC)


def display_ticker(ticker: str) -> str:
    """Chart-label form of a ticker: '0700.HK' -> '0700'. Data files and
    alerts keep the full Yahoo symbol; only visual labels are shortened."""
    return ticker[:-3] if ticker.endswith(".HK") else ticker


def activate(name: str) -> None:
    """Switch the module-level universe. Every other module reads these names
    at call time, so this is all that's needed to retarget the whole kit."""
    global UNIVERSE, LABEL, NOUN, BENCHMARK, BENCHMARK_LABEL, SECTORS, OUTPUT_DIR
    if name not in UNIVERSES:
        raise SystemExit(f"unknown universe {name!r}; "
                         f"choose from {', '.join(UNIVERSES)}")
    u = UNIVERSES[name]
    UNIVERSE, LABEL, NOUN = name, u["label"], u["noun"]
    BENCHMARK, SECTORS = u["benchmark"], u["members"]
    BENCHMARK_LABEL = u.get("benchmark_label", u["benchmark"])
    OUTPUT_DIR = f"output/{name}"

# ── Timeframe presets ────────────────────────────────────────────────────────
# window ............ lookback (in bars AFTER resampling) for normalizing
#                     RS-Ratio / RS-Momentum around 100 (rolling z-score)
# momentum_period ... how many bars back the RS-Ratio rate-of-change looks;
#                     larger = smoother, slower momentum
# smooth ............ SMA applied to raw relative strength before normalizing
#                     (1 = off); daily data benefits from a little smoothing
# tail .............. number of history points drawn behind each head
# vol_window ........ bars for realized volatility & average dollar volume
# ann_factor ........ periods per year, for annualizing volatility
TIMEFRAMES = {
    "weekly": dict(period="3y", resample="W-FRI", window=14,
                   momentum_period=4, smooth=4, tail=12,
                   vol_window=20, ann_factor=52,
                   label="Weekly"),
    "daily":  dict(period="2y", resample=None, window=60,
                   momentum_period=10, smooth=10, tail=12,
                   vol_window=20, ann_factor=252,
                   label="Daily"),
}

# ── Theme ────────────────────────────────────────────────────────────────────
# "dark" suits video production; "light" suits print/reports.
DEFAULT_THEME = "dark"

# Categorical palettes: 16 slots, assigned in `members` order.
# Muted "research desk" hues, machine-optimized for colorblind separation
# (all-pairs Machado protan/deutan): min pair dE 12.2 (dark) / 15.6 (light),
# both above the 12 target. Every chart head still carries a visible ticker
# label — identity is never color-alone. Slots 12-16 were added for the larger
# country universes; the first 11 are unchanged, so sector charts keep their
# existing colors.
PALETTE = {
    "light": ["#1888d8", "#38a088", "#d08800", "#609860", "#804890",
              "#b84838", "#902040", "#b05800", "#4048b0", "#884870", "#0090c0",
              "#42c6d2", "#90c66c", "#54c0fc", "#60cc9c", "#1896a2"],
    "dark":  ["#4888d8", "#00b078", "#d9a441", "#80a048", "#b48ead",
              "#d07868", "#b84840", "#d06800", "#5050b0", "#b848a0", "#4fc3e8",
              "#963660", "#a83c00", "#9c3648", "#4296c6", "#c05a84"],
}

# Chart chrome (surfaces, ink, grid) per theme. Dark leans blue-charcoal
# (terminal feel) rather than pure black; light is a warm paper white.
THEMES = {
    "light": dict(surface="#fdfdfc", page="#f6f6f4",
                  ink="#151515", ink2="#4a4a48", muted="#8a8880",
                  grid="#e8e7e2", axisline="#c8c6bf",
                  quadrant_alpha=0.045),
    "dark":  dict(surface="#16181d", page="#0e0f12",
                  ink="#e8eaed", ink2="#9aa0a6", muted="#6b7280",
                  grid="#22252c", axisline="#3a3f4a",
                  quadrant_alpha=0.06),
}

# Quadrant tint hues (status colors — reserved for state, never used as a
# series color): Leading=good, Weakening=warning, Lagging=critical,
# Improving=blue.
QUADRANT_COLORS = {
    "Leading":   "#2e9e4f",
    "Weakening": "#d99a2b",
    "Lagging":   "#c0392b",
    "Improving": "#3673b5",
}

OUTPUT_DIR = f"output/{DEFAULT_UNIVERSE}"

# How many periods of history to export for the dashboard's timeline slider
# (per timeframe). Bigger = longer scrub range, slightly larger page.
HISTORY_PERIODS = {"weekly": 78, "daily": 150}
