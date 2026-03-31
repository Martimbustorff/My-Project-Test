"""
Debate Engine — uses Claude API to reason over the 4 agent votes
and produce an intelligent final verdict with conflict resolution.

Requires env var: ANTHROPIC_API_KEY
Falls back to weighted average if key not set.

Install dependencies:
    pip install anthropic requests
"""
import os
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"  # Fast and cheap for per-stock analysis


def run_debate(
    symbol: str,
    price: float,
    change_pct: float,
    votes: list,           # List of AgentVote-like objects with .agent_name, .score, .signal, .reasons
    consensus_score: float,
    recommendation: str,
) -> Optional[dict]:
    """
    Send agent votes to Claude for intelligent debate and final verdict.

    Returns dict with keys:
        final_recommendation: str  (STRONG BUY / BUY / HOLD / SELL / STRONG SELL)
        direction: str             (LONG / SHORT)
        confidence: float          (0.0 to 1.0)
        reasoning: List[str]       (3-4 bullet points)
        key_risk: str
        key_catalyst: str
        debate_summary: str        (one line explaining agent agreement/conflict)

    Returns None if API key not set or call fails.
    """
    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed. Run: pip install anthropic")
        return None

    # Build the agent votes section
    votes_text = ""
    for v in votes:
        reasons_str = "; ".join(v.reasons[:3]) if v.reasons else "No specific reasons"
        votes_text += f"\n• {v.agent_name} Agent: score={v.score:+.2f} → {v.signal}\n  Reasons: {reasons_str}"

    bull_agents = [v.agent_name for v in votes if v.score >= 0.15]
    bear_agents = [v.agent_name for v in votes if v.score <= -0.15]

    if len(bull_agents) > len(bear_agents):
        agreement_text = f"{len(bull_agents)}/4 agents are bullish ({', '.join(bull_agents)})"
    elif len(bear_agents) > len(bull_agents):
        agreement_text = f"{len(bear_agents)}/4 agents are bearish ({', '.join(bear_agents)})"
    else:
        agreement_text = f"Agents are split: bulls={bull_agents}, bears={bear_agents}"

    prompt = f"""You are an expert quantitative financial analyst. Review these 4 independent agent analyses for {symbol} and provide a final investment verdict.

MARKET DATA:
- Symbol: {symbol}
- Current Price: ${price:.2f}
- Today's Change: {change_pct:+.2f}%

AGENT VOTES:{votes_text}

PRELIMINARY CONSENSUS: Score={consensus_score:+.3f} → {recommendation}
AGREEMENT: {agreement_text}

Your job is to:
1. Identify the most important signals from the agents
2. Resolve any conflicts between agents (e.g. if Technical is bullish but Fundamental is bearish, which matters more right now?)
3. Assess whether the consensus score reflects the true opportunity
4. Give a final actionable recommendation

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{{
  "final_recommendation": "BUY",
  "direction": "LONG",
  "confidence": 0.72,
  "reasoning": [
    "RSI oversold at 28 with MACD bullish crossover signals strong technical setup",
    "Revenue growth of 18% YoY supports the bullish thesis despite high P/E",
    "Sentiment turning positive with 3 analyst upgrades this week"
  ],
  "key_risk": "One sentence describing the main risk",
  "key_catalyst": "One sentence describing the main opportunity",
  "debate_summary": "One sentence explaining why agents agree or conflict"
}}

Valid values for final_recommendation: STRONG BUY, BUY, HOLD, SELL, STRONG SELL
Valid values for direction: LONG, SHORT"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # Validate required fields
        required = ["final_recommendation", "direction", "confidence", "reasoning", "key_risk", "key_catalyst", "debate_summary"]
        if not all(k in result for k in required):
            logger.warning("Claude response missing required fields for %s", symbol)
            return None

        # Clamp confidence
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

        # Ensure reasoning is a list
        if isinstance(result["reasoning"], str):
            result["reasoning"] = [result["reasoning"]]

        logger.info("Claude debate complete for %s: %s (confidence=%.2f)",
                    symbol, result["final_recommendation"], result["confidence"])
        return result

    except json.JSONDecodeError as e:
        logger.error("Claude response not valid JSON for %s: %s", symbol, e)
        return None
    except Exception as e:
        logger.error("Claude debate failed for %s: %s", symbol, e)
        return None
