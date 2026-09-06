# My-Project-Test

Python trading bot (`trading_bot/`) plus a **weekly stock watchlist** that ranks
growing US & European stocks. A React Native health app (`checkup-direct/`) also
lives here but is unrelated to the bot.

## Commands

```bash
cd trading_bot
PYTHONPATH=. python -m pytest tests/ -q        # full test suite (must stay green)
PYTHONPATH=. python -m watchlist.cli           # watchlist, built-in US+EU universe
PYTHONPATH=. python -m watchlist.cli --tickers IREN CRDO FTNT   # score a portfolio
```

Dependencies: `pip install -r trading_bot/requirements.txt`. The watchlist itself
only needs `yfinance pandas numpy rich requests python-dotenv pytz` — `pandas-ta`,
`feedparser` and `torch/transformers` are optional extras used by the live
trading engine, and are best-effort in the session-start hook.

## Watchlist architecture

```
trading_bot/watchlist/
├── scoring.py     # PURE scoring — no network, no I/O. The formulas live here.
├── screener.py    # yfinance fetch → StockMetrics (retries, records failures)
├── watchlist.py   # orchestration: screen → gate → rank → JSON snapshot
├── report.py      # Markdown + Rich rendering
├── cli.py         # python -m watchlist.cli
└── METHODOLOGY.md # the full spec: formulas, gate, rotation rules
```

Reasoning and I/O are deliberately separated: `scoring.py` is pure so the ranking
math is deterministic and unit-testable, while `screener.py` owns all fetching.
**Keep it that way** — do not add network calls to `scoring.py`.

Read `trading_bot/watchlist/METHODOLOGY.md` before changing any scoring formula,
weight or threshold; it is the source of truth and must be updated alongside.

## Financial-data rules

**IMPORTANT: never fabricate market data.** Prices, analyst targets, consensus
ratings and growth figures must come from a real fetch. If data is unavailable,
say so — do not fill a plausible-looking number.

**YOU MUST keep missing data visible.** A dimension with no underlying figures
scores a neutral 50; that fallback is flagged via `*_estimated` /
`data_coverage` and surfaced in the report's "Data quality" section. Never let a
fallback pass as a genuine reading, and never silently drop a ticker that failed
to fetch — `Screener.failures` exists so the run reports it.

Every generated report keeps its **"Not investment advice"** disclaimer.

## Automation

`.github/workflows/weekly-watchlist.yml` runs Mondays 08:00 UTC (and on demand),
generates the universe + portfolio reports with live data, writes them to the run
summary, and commits them to `trading_bot/watchlists/`. Scheduled workflows only
fire from the default branch.

## Conventions

- Match the surrounding style: type hints, module docstrings, `logger` over
  `print` in library code.
- Tests are network-free — inject a stub screener rather than hitting a provider.
- Add tests for new scoring behaviour; the suite is the guard on ranking logic.
