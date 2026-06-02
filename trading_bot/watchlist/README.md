# 📈 Weekly Stock Watchlist

A **dynamic stock watchlist** that produces **weekly recommendations** of
*growing* American and European stocks for a holding horizon of up to
**3 months (~90 days)**. Every qualifying name is ranked across three lenses:

| Lens | What it measures | Underlying data |
|------|------------------|-----------------|
| 🚀 **Biggest upside** | Analyst mean price target vs. current price | `targetMeanPrice` |
| 📊 **Financial growth history** | Revenue YoY growth, multi-year revenue CAGR, earnings growth | income statement + `revenueGrowth` |
| 👥 **Analyst consensus** | Aggregated buy/hold/sell recommendation, coverage-weighted | `recommendationMean`, `numberOfAnalystOpinions` |

A weighted **composite score** (default 40% upside · 35% growth · 25% consensus)
produces the overall "Top Picks" ranking. Universe scope: **US (NYSE/Nasdaq)**
and **Europe (LSE, Euronext, Xetra, SIX, Borsa Italiana, BME, OMX, …)** at
**any market cap** — large, mid and small caps are all eligible.

> ⚠️ **Not investment advice.** Output is generated automatically from public
> fundamental/analyst data for research and educational purposes only.

## How to see it

From the `trading_bot/` directory (after `pip install -r requirements.txt`):

```bash
# Rich terminal report (US + EU)
python -m watchlist.cli

# American stocks only, top 15 per list
python -m watchlist.cli --regions US --top 15

# Print Markdown (good for pasting into a doc / PR / email)
python -m watchlist.cli --markdown

# Save JSON + Markdown snapshots to ./watchlists/
python -m watchlist.cli --save --out-dir watchlists

# Only keep names that are also in a positive 3-month uptrend
python -m watchlist.cli --require-momentum
```

### Score your own portfolio

Pass your holdings with `--tickers` to rank exactly what you own (buy / hold /
trim) instead of the built-in universe. Region is inferred from the suffix
(`ASML.AS` → EU, `IREN` → US). By default every holding is shown and ranked;
add `--only-growing` to keep just the names that pass the growth gate.

```bash
python -m watchlist.cli --tickers IREN CRDO RVMD FTNT RKLB GMAB GENI \
                                  NNE PL AUTL XNDU GLUE TYGO INDI
```

This produces the same four ranked tables (composite #1 → weakest), so you can
see at a glance which holdings the data favours and which to be cautious on.

### Thin-coverage upside & high-conviction override

A spectacular price-target upside backed by **only one or two analysts** (common
on micro-caps) is unreliable, so the upside score is **shrunk toward neutral**
in proportion to analyst coverage (fewer than 5 covering analysts → progressive
discount). This stops sparsely-covered names from topping the ranking on a
single estimate.

Because no data source can certify that a company will *"100% become a future
giant"*, that judgement stays human: flag names you have independent conviction
in with `--high-conviction`, and they bypass the penalty.

```bash
python -m watchlist.cli --tickers RKLB XNDU AUTL IREN \
                        --high-conviction RKLB        # RKLB keeps full upside
```

When the bot runs (`python main.py`), the watchlist is also regenerated
automatically **every Monday at 08:00 ET** and saved to
`WATCHLIST_OUTPUT_DIR` (default `./watchlists/`) as
`watchlist_<week_of>.json` and `watchlist_<week_of>.md`.

## Architecture

```
watchlist/
├── universe.py    # curated US + EU candidate list (any market cap)
├── scoring.py     # PURE scoring logic (upside / growth / consensus) — no network
├── screener.py    # yfinance data fetch → scored StockMetrics (tolerant of gaps)
├── watchlist.py   # orchestration: screen → gate "growing" → rank → snapshot
├── report.py      # Markdown + Rich terminal rendering
└── cli.py         # `python -m watchlist.cli`
```

`scoring.py` is fully unit-tested in `tests/test_watchlist.py` and has no
network dependency, so the ranking math is deterministic and verifiable.

## Configuration

Tunable via environment variables (see `config/settings.py`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `WATCHLIST_REGIONS` | `US,EU` | Regions to screen |
| `WATCHLIST_HORIZON_DAYS` | `90` | Recommendation horizon (~3 months) |
| `WATCHLIST_TOP_N` | `10` | Names per ranked list |
| `WATCHLIST_MIN_REVENUE_GROWTH` | `0.05` | Min YoY revenue growth to qualify |
| `WATCHLIST_REQUIRE_MOMENTUM` | `false` | Require positive ≤3-month trend |
| `WATCHLIST_OUTPUT_DIR` | `watchlists` | Snapshot output directory |
| `WATCHLIST_{UPSIDE,GROWTH,CONSENSUS}_WEIGHT` | `0.40 / 0.35 / 0.25` | Composite weights |
