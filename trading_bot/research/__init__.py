"""
research
========
The **AI Hedge Fund Team** — a seven-agent investment *research* committee,
implemented as-is from the guide by @seb.ai.

One ticker goes in; seven agents each do one job and hand off to the next; a
structured research memo comes out:

    Market Scout → Technical → Fundamental → News → Quant → Risk → Portfolio Manager

⚠️ This is a research workflow. It is **not** an autonomous hedge fund, it does
not trade, it does not manage money, and nothing it produces is financial
advice. Every figure must be verified against primary sources.

Public API
----------
    from research import AGENTS, build_packet, build_research_stack

* :mod:`research.agents` — the seven prompts and the five shared rules (pure).
* :mod:`research.packet` — gathers the real raw material for a ticker (I/O).
* :mod:`research.stack`  — assembles the research-stack document (pure).
* :mod:`research.memo`   — the final memo template and checklist (pure).
"""

from .agents import AGENTS, RULES, Agent, get_agent
from .memo import CHECKLIST, DISCLAIMER, MEMO_TEMPLATE
from .packet import NOT_AVAILABLE, ResearchPacket, build_packet
from .stack import build_research_stack

__all__ = [
    "AGENTS",
    "RULES",
    "Agent",
    "get_agent",
    "MEMO_TEMPLATE",
    "CHECKLIST",
    "DISCLAIMER",
    "ResearchPacket",
    "build_packet",
    "build_research_stack",
    "NOT_AVAILABLE",
]
