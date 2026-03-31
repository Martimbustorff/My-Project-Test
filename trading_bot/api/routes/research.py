"""
api/routes/research.py
-----------------------
Free-form research endpoint. User submits a natural-language query;
Claude parses intent, selects a symbol universe, runs all 5 agents in
parallel, and returns ranked buy/sell opportunities with projected upside.
"""

from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter

router = APIRouter()

# ── Prompt templates ──────────────────────────────────────────────────────────

_PARSE_PROMPT = """You are a financial research assistant. Parse the user query and return JSON only.

User query: "{query}"

Return JSON with exactly these fields:
- universes: list of universe keys (choose from: small_cap, large_cap, tech, growth, value, crypto, healthcare, energy, etf, general)
- direction: "long" or "short" or "both"
- time_horizon: "short" (days-weeks), "medium" (1-6 months), "long" (1-3 years)
- strategy: one-line description of what the user wants
- max_symbols: integer between 15 and 40
- filters: object with key "recommendation" as list of strings

Examples:
- "best small cap for 2 years" → {{"universes":["small_cap"],"direction":"long","time_horizon":"long","strategy":"Small cap growth for 2yr","max_symbols":25,"filters":{{"recommendation":["BUY","STRONG BUY"]}}}}
- "crypto short opportunities" → {{"universes":["crypto"],"direction":"short","time_horizon":"short","strategy":"Crypto shorts","max_symbols":15,"filters":{{"recommendation":["SELL","STRONG SELL"]}}}}
- "tech momentum stocks" → {{"universes":["tech","growth"],"direction":"long","time_horizon":"medium","strategy":"Tech momentum longs","max_symbols":30,"filters":{{"recommendation":["BUY","STRONG BUY"]}}}}

Return ONLY valid JSON, no markdown fences."""

_SUMMARY_PROMPT = """User asked: '{query}'

Top results from 5-agent consensus analysis (Technical 30%, Fundamental 20%, Momentum 20%, Sentiment 15%, Macro 15%):
{symbols_summary}

Write a 2-3 sentence investment summary for these results. Be direct and data-driven. Mention the time horizon, key theme, and why these names stand out. No disclaimers."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_intent(query: str) -> dict:
    return {
        "universes": ["general"],
        "direction": "long",
        "time_horizon": "medium",
        "strategy": query,
        "max_symbols": 25,
        "filters": {"recommendation": ["BUY", "STRONG BUY"]},
    }


async def _parse_intent(query: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _default_intent(query)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": _PARSE_PROMPT.format(query=query)}],
        )
        text = msg.content[0].text.strip()
        # strip markdown fences if present
        if "```" in text:
            parts = text.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                try:
                    return json.loads(p)
                except Exception:
                    continue
        return json.loads(text)
    except Exception:
        return _default_intent(query)


async def _generate_summary(query: str, top: list[dict], time_horizon: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not top:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        symbols_summary = ", ".join(
            f"{r['symbol']} ({r['recommendation']}, score {r['consensus_score']:.2f})"
            for r in top[:5]
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": _SUMMARY_PROMPT.format(query=query, symbols_summary=symbols_summary),
            }],
        )
        return msg.content[0].text.strip()
    except Exception:
        return ""


def _project_upside(score: float, time_horizon: str) -> str:
    """Estimate % upside range from consensus score and horizon."""
    multiplier = {"short": 1.0, "medium": 2.2, "long": 4.0}.get(time_horizon, 2.0)
    base = abs(score) * 25 * multiplier
    low  = round(base * 0.65, 1)
    high = round(base * 1.40, 1)
    if score < 0:
        return f"-{high}% to -{low}%"
    return f"+{low}% to +{high}%"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/query")
async def research_query(body: dict):
    query = (body.get("query") or "").strip()
    if not query:
        return {"error": "Query is required"}

    # 1. Parse intent
    intent = await _parse_intent(query)

    # 2. Resolve symbol universe
    from data.symbol_universes import get_symbols_for_query
    symbols = get_symbols_for_query(intent)

    direction     = intent.get("direction", "long")
    time_horizon  = intent.get("time_horizon", "medium")
    filters       = intent.get("filters", {})
    target_recs: list[str] = filters.get(
        "recommendation",
        ["SELL", "STRONG SELL"] if direction == "short" else ["BUY", "STRONG BUY"],
    )

    # 3. Run consensus engine on all symbols in parallel (batches of 6)
    from analysis.consensus_engine import run_consensus

    matches: list[dict] = []
    batch_size = 6

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        batch_results = await asyncio.gather(
            *[asyncio.to_thread(run_consensus, sym) for sym in batch],
            return_exceptions=True,
        )
        for res in batch_results:
            if isinstance(res, Exception) or not res:
                continue
            if res.get("recommendation") in target_recs:
                matches.append(res)

    # 4. Sort by absolute consensus score
    matches.sort(
        key=lambda x: x.get("consensus_score", 0),
        reverse=(direction != "short"),
    )
    top = matches[:10]

    # 5. Enrich with projected upside
    for r in top:
        r["projected_upside"] = _project_upside(r.get("consensus_score", 0), time_horizon)
        r["time_horizon"] = time_horizon

    # 6. Generate narrative summary
    summary = await _generate_summary(query, top, time_horizon)

    return {
        "query": query,
        "intent": intent,
        "total_scanned": len(symbols),
        "total_matches": len(matches),
        "summary": summary,
        "results": top,
    }
