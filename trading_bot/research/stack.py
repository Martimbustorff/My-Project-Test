"""
research/stack.py
-----------------
Builds the "[TICKER] — Research Stack" document the AI Hedge Fund Team workflow
runs on: the eight headings, every agent's copy/paste prompt with ``[TICKER]``
already resolved, the gathered raw material, the final memo template and the
quick-start checklist.

Pure assembly — no network, no I/O (:mod:`research.packet` does the fetching),
so the document layout is deterministic and unit-testable.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from .agents import AGENTS
from .memo import MEMO_TEMPLATE, CHECKLIST, DISCLAIMER
from .packet import ResearchPacket, NOT_AVAILABLE

MAX_INLINE_CSV_ROWS = 40


def _raw_material_section(packet: ResearchPacket) -> str:
    lines: list[str] = ["## Step 0 — Raw material", ""]
    lines.append(
        f"*Fetched {packet.generated_at} for `{packet.symbol}`. "
        "Every figure below came from the data provider — verify it against the "
        "primary source before the team relies on it.*"
    )
    lines.append("")

    lines.append("### Key statistics (fetched)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for label, value in packet.key_stats.items():
        lines.append(f"| {label} | {value} |")
    lines.append("")

    if packet.missing_stats:
        lines.append(
            "> ⚠️ **Not returned by the provider — do not let any agent use "
            "these:** " + ", ".join(f"`{m}`" for m in packet.missing_stats)
        )
        lines.append("")

    if packet.fetch_errors:
        lines.append("> ❌ **Fetch problems:** " + "; ".join(packet.fetch_errors))
        lines.append("")

    lines.append("### Price history (for the Quant Analyst)")
    lines.append("")
    if packet.has_price_history:
        rows = packet.price_history_csv.strip().splitlines()
        header, body = rows[0], rows[1:]
        shown = body[-MAX_INLINE_CSV_ROWS:]
        lines.append(
            f"{packet.history_rows} daily rows over `{packet.history_period}`. "
            f"Last {len(shown)} shown; the full CSV is saved alongside this file."
        )
        lines.append("")
        lines.append("```csv")
        lines.append(header)
        lines.extend(shown)
        lines.append("```")
    else:
        lines.append(
            f"{NOT_AVAILABLE} — no price history was returned. Export a CSV of "
            "daily closes yourself and paste it into the Quant Analyst step; do "
            "not let that agent simulate data."
        )
    lines.append("")

    lines.append("### Still to gather by hand")
    lines.append("")
    for item in packet.manual_inputs:
        lines.append(f"- [ ] {item}")
    lines.append("")
    return "\n".join(lines)


def build_research_stack(packet: ResearchPacket,
                         run_date: Optional[date] = None) -> str:
    """
    Render the full research-stack document for *packet*.

    Each agent gets its heading, its resolved prompt, and an empty slot for its
    report. Run the agents top to bottom, pasting every earlier report into the
    next agent, exactly as the workflow prescribes.
    """
    ticker = packet.symbol
    today = (run_date or date.today()).isoformat()

    out: list[str] = []
    out.append(f"# {ticker} — Research Stack")
    out.append("")
    out.append(f"*AI Hedge Fund Team · 7-agent research committee · {today}*")
    out.append("")
    out.append("> ⚠️ **Read this first.** This is an AI-powered investment "
               "RESEARCH system. It is not an autonomous hedge fund, it does not "
               "trade, and it does not manage money. Nothing here is financial "
               "advice. AI models make mistakes and can state wrong numbers with "
               "total confidence — verify every figure and source yourself "
               "before you rely on it. Past results never guarantee future "
               "returns. For educational and research purposes only.")
    out.append("")

    out.append("## The committee")
    out.append("")
    out.append("| # | Agent | Job | The one question it answers |")
    out.append("|---|-------|-----|------------------------------|")
    for agent in AGENTS:
        out.append(f"| {agent.order} | **{agent.name}** | {agent.job} | "
                   f"{agent.question} |")
    out.append("")
    out.append("**The two golden rules.** *Facts vs. opinions* — every agent "
               "separates verifiable facts (with a source) from its own "
               "interpretation. *Verify before you pass it on* — spot-check the "
               "key numbers before feeding a report to the next agent; a wrong "
               "number at step 3 becomes a wrong conclusion at step 7.")
    out.append("")

    out.append(_raw_material_section(packet))

    for agent in AGENTS:
        out.append(f"## {agent.order}. {agent.name}")
        out.append("")
        out.append(f"*{agent.question}*")
        out.append("")
        out.append("<details><summary>Prompt (copy/paste)</summary>")
        out.append("")
        out.append("```text")
        out.append(agent.prompt(ticker))
        out.append("```")
        out.append("")
        out.append("</details>")
        out.append("")
        out.append(f"### {agent.name} — report")
        out.append("")
        out.append("_Paste this agent's report here._")
        out.append("")

    out.append("## Final memo")
    out.append("")
    out.append(MEMO_TEMPLATE.replace("[TICKER]", ticker).replace("[Date]", today))
    out.append("")

    out.append(CHECKLIST)
    out.append("")
    out.append("---")
    out.append("")
    out.append(DISCLAIMER)
    return "\n".join(out)
