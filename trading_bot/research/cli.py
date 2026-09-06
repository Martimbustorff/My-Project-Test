#!/usr/bin/env python3
"""
research/cli.py
---------------
Command-line entry point for the AI Hedge Fund Team research committee.

Usage
-----
    # From the trading_bot directory:
    python -m research.cli AAPL                     # build the research stack
    python -m research.cli IREN --out-dir research  # choose the output directory
    python -m research.cli NVDA --period 5y         # longer price history
    python -m research.cli --print-prompt risk      # just show one agent's prompt
    python -m research.cli --list-agents            # the committee, in order

Writes ``<TICKER>_research_stack.md`` (the eight headings, every agent prompt
with the ticker resolved, the fetched raw material, the memo template and the
checklist) plus ``<TICKER>_prices.csv`` for the Quant Analyst.

Then run the agents top to bottom, pasting each report into the doc and giving
every agent the reports above it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .agents import AGENTS, get_agent
from .packet import build_packet
from .stack import build_research_stack


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build an AI Hedge Fund Team research stack for a ticker "
                    "(7-agent research committee). Educational research only — "
                    "not financial advice.",
    )
    p.add_argument("ticker", nargs="?",
                   help="Ticker to research (e.g. AAPL, ASML.AS).")
    p.add_argument("--out-dir", default="research_stacks",
                   help="Directory for the generated stack (default ./research_stacks).")
    p.add_argument("--period", default="2y",
                   help="Price-history window for the Quant Analyst (default 2y).")
    p.add_argument("--stdout", action="store_true",
                   help="Print the stack instead of writing files.")
    p.add_argument("--list-agents", action="store_true",
                   help="List the seven agents in run order and exit.")
    p.add_argument("--print-prompt", metavar="AGENT",
                   help="Print one agent's prompt (e.g. market_scout, risk) and exit.")
    p.add_argument("--verbose", action="store_true", help="Verbose logging.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    if args.list_agents:
        for agent in AGENTS:
            print(f"{agent.order}. {agent.key:18s} {agent.name:22s} {agent.question}")
        return 0

    if args.print_prompt:
        try:
            agent = get_agent(args.print_prompt)
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 2
        print(agent.prompt(args.ticker or "[TICKER]"))
        return 0

    if not args.ticker:
        build_arg_parser().print_usage(sys.stderr)
        print("\nerror: a ticker is required (or use --list-agents / "
              "--print-prompt).", file=sys.stderr)
        return 2

    ticker = args.ticker.strip().upper()
    packet = build_packet(ticker, history_period=args.period)
    document = build_research_stack(packet)

    if args.stdout:
        print(document)
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stack_path = out_dir / f"{ticker}_research_stack.md"
    stack_path.write_text(document, encoding="utf-8")
    print(f"Saved: {stack_path}")

    if packet.has_price_history:
        csv_path = out_dir / f"{ticker}_prices.csv"
        csv_path.write_text(packet.price_history_csv, encoding="utf-8")
        print(f"Saved: {csv_path}  ({packet.history_rows} daily rows)")

    if packet.fetch_errors:
        print("\nFetch problems (the agents must treat these as unavailable):")
        for err in packet.fetch_errors:
            print(f"  - {err}")
    if packet.missing_stats:
        print("\nNot returned by the provider — do not let any agent use these:")
        for stat in packet.missing_stats:
            print(f"  - {stat}")

    print("\nNext: run the agents top to bottom, giving each one every report "
          "above it. Verify the numbers before you pass them on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
