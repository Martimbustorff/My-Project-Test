#!/usr/bin/env python3
"""
watchlist/cli.py
----------------
Command-line entry point for generating the weekly stock watchlist.

Usage
-----
    # From the trading_bot directory:
    python -m watchlist.cli                       # screen US+EU, print to terminal
    python -m watchlist.cli --regions US          # American only
    python -m watchlist.cli --top 15              # surface 15 names per list
    python -m watchlist.cli --markdown            # emit Markdown to stdout
    python -m watchlist.cli --save                # also save JSON snapshot
    python -m watchlist.cli --out-dir watchlists  # JSON/MD output directory

A weekly schedule can be wired via cron / APScheduler to call this module
every Monday morning (see ``main.py`` ``weekly_watchlist`` job).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .watchlist import WatchlistBuilder, save_watchlist
from .scoring import GrowthGate
from .report import to_markdown, print_report


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate the weekly dynamic stock watchlist "
                    "(growing US & European stocks, ≤3-month horizon)."
    )
    p.add_argument("--tickers", nargs="+", default=None,
                   help="Screen an explicit list of tickers (e.g. your own "
                        "portfolio: --tickers IREN CRDO RVMD FTNT) instead of "
                        "the built-in universe. EU tickers keep their suffix "
                        "(ASML.AS, SAP.DE).")
    p.add_argument("--only-growing", action="store_true",
                   help="With --tickers, keep only holdings that pass the "
                        "growing-stock gate (default: show & rank them all).")
    p.add_argument("--regions", nargs="+", default=["US", "EU"],
                   help="Regions to include (US EU). Default: US EU. "
                        "Ignored when --tickers is given.")
    p.add_argument("--top", type=int, default=10,
                   help="Number of names to surface per ranked list (default 10).")
    p.add_argument("--horizon-days", type=int, default=90,
                   help="Target holding horizon in days (default 90 ≈ 3 months).")
    p.add_argument("--min-revenue-growth", type=float, default=0.05,
                   help="Minimum YoY revenue growth to qualify (fraction, default 0.05).")
    p.add_argument("--require-momentum", action="store_true",
                   help="Require a positive ≤3-month price trend to qualify.")
    p.add_argument("--high-conviction", nargs="*", default=None, metavar="SYM",
                   help="Tickers to exempt from the thin-coverage upside penalty "
                        "— a manual 'high-conviction disruptor' override "
                        "(e.g. --high-conviction RKLB XNDU). Use sparingly.")
    p.add_argument("--markdown", action="store_true",
                   help="Print Markdown instead of the Rich terminal report.")
    p.add_argument("--save", action="store_true",
                   help="Save a JSON snapshot (and Markdown) to --out-dir.")
    p.add_argument("--out-dir", default="watchlists",
                   help="Directory for saved snapshots (default ./watchlists).")
    p.add_argument("--label", default="watchlist",
                   help="Filename prefix for snapshots, keeping report kinds in "
                        "separate history series (e.g. --label portfolio).")
    p.add_argument("--compare", action="store_true",
                   help="Include a week-over-week 'what changed' section, diffed "
                        "against the most recent earlier snapshot in --out-dir.")
    p.add_argument("--no-compare", dest="compare", action="store_false",
                   help="Skip the week-over-week comparison even when saving.")
    p.set_defaults(compare=None)
    p.add_argument("--verbose", action="store_true", help="Verbose logging.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    gate = GrowthGate(
        min_revenue_growth=args.min_revenue_growth,
        require_positive_momentum=args.require_momentum,
    )
    builder = WatchlistBuilder(
        regions=args.regions,
        horizon_days=args.horizon_days,
        top_n=args.top,
        gate=gate,
        high_conviction=set(args.high_conviction) if args.high_conviction else None,
    )

    if args.tickers:
        from .universe import candidates_from_tickers
        cands = candidates_from_tickers(args.tickers)
        watchlist = builder.build(candidates=cands, include_all=not args.only_growing)
    else:
        watchlist = builder.build()

    # Week-over-week memory: diff against the previous snapshot. Defaults to on
    # whenever we are also saving (so each run builds on the last), and the
    # first run simply has no history to compare against.
    delta = None
    compare = args.compare if args.compare is not None else args.save
    if compare:
        from .history import delta_against_previous
        delta = delta_against_previous(watchlist, args.out_dir, args.label)

    if args.markdown:
        print(to_markdown(watchlist, delta))
    else:
        print_report(watchlist)

    if args.save:
        out_dir = Path(args.out_dir)
        # Write the snapshot only after diffing, so we compare against the
        # previous run rather than the file we are about to create.
        json_path = save_watchlist(watchlist, out_dir, label=args.label)
        md_path = out_dir / f"{args.label}_{watchlist.week_of}.md"
        md_path.write_text(to_markdown(watchlist, delta), encoding="utf-8")
        latest_path = out_dir / f"{args.label}_latest.md"
        latest_path.write_text(to_markdown(watchlist, delta), encoding="utf-8")
        print(f"\nSaved: {json_path}\nSaved: {md_path}\nSaved: {latest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
