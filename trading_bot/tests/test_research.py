"""
tests/test_research.py
----------------------
Unit tests for the AI Hedge Fund Team research committee.

All tests are pure (no network): the prompt/assembly layers take a hand-built
ResearchPacket, so nothing here touches a data provider.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from research.agents import AGENTS, RULES, get_agent
from research.memo import CHECKLIST, DISCLAIMER, MEMO_TEMPLATE
from research.packet import NOT_AVAILABLE, ResearchPacket
from research.stack import build_research_stack


def _packet(**kw) -> ResearchPacket:
    base = dict(
        symbol="AAPL",
        generated_at="2026-09-06T12:00:00+00:00",
        key_stats={"Company name": "Apple", "Current price": "225.72"},
        price_history_csv="Date,Close\n2026-09-01,220.0\n2026-09-02,225.7\n",
        history_period="2y",
        history_rows=2,
    )
    base.update(kw)
    return ResearchPacket(**base)


# ---------------------------------------------------------------------------
# The committee
# ---------------------------------------------------------------------------

class TestAgents:
    def test_there_are_seven_agents(self):
        assert len(AGENTS) == 7

    def test_run_order_is_sequential(self):
        assert [a.order for a in AGENTS] == [1, 2, 3, 4, 5, 6, 7]

    def test_expected_committee_members(self):
        assert [a.key for a in AGENTS] == [
            "market_scout", "technical", "fundamental",
            "news", "quant", "risk", "portfolio_manager",
        ]

    def test_portfolio_manager_is_last(self):
        assert AGENTS[-1].key == "portfolio_manager"

    def test_risk_manager_precedes_portfolio_manager(self):
        keys = [a.key for a in AGENTS]
        assert keys.index("risk") < keys.index("portfolio_manager")

    def test_get_agent_by_key(self):
        assert get_agent("risk").name == "Risk Manager"

    def test_get_agent_unknown_raises(self):
        with pytest.raises(KeyError):
            get_agent("nope")


class TestPrompts:
    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.key)
    def test_every_prompt_carries_the_five_rules(self, agent):
        assert RULES in agent.prompt("AAPL")

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.key)
    def test_ticker_is_substituted(self, agent):
        prompt = agent.prompt("nvda")
        assert "[TICKER]" not in prompt
        assert "NVDA" in prompt

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.key)
    def test_never_invent_numbers_rule_present(self, agent):
        assert NOT_AVAILABLE in agent.prompt("AAPL")

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.key)
    def test_no_financial_advice_rule_present(self, agent):
        assert "not financial advice" in agent.prompt("AAPL")

    def test_risk_manager_is_adversarial(self):
        prompt = get_agent("risk").prompt("AAPL")
        assert "attack the idea" in prompt
        assert "too optimistic" in prompt

    def test_portfolio_manager_embeds_the_memo_sections(self):
        prompt = get_agent("portfolio_manager").prompt("AAPL")
        for section in ("ONE-LINE THESIS", "THE BULL CASE", "THE BEAR CASE",
                        "WHERE THE TEAM DISAGREES", "TOP 3 RISKS"):
            assert section in prompt

    def test_portfolio_manager_must_not_add_new_facts(self):
        assert "Do not add new facts" in get_agent("portfolio_manager").prompt("AAPL")

    def test_quant_must_not_simulate_missing_data(self):
        assert "do not simulate any" in get_agent("quant").prompt("AAPL")

    def test_technical_must_not_describe_unseen_charts(self):
        assert "do not describe a chart you have not seen" in \
            get_agent("technical").prompt("AAPL")


# ---------------------------------------------------------------------------
# Memo + checklist
# ---------------------------------------------------------------------------

class TestMemo:
    def test_memo_has_all_twelve_sections(self):
        for n in range(1, 13):
            assert f"{n}." in MEMO_TEMPLATE

    def test_facts_table_defaults_to_verify(self):
        assert "VERIFY" in MEMO_TEMPLATE

    def test_memo_carries_disclaimer(self):
        # The template wraps lines, so compare with whitespace normalised.
        flat = " ".join(MEMO_TEMPLATE.split())
        assert "not financial advice" in flat
        assert "it does not predict returns" in flat

    def test_checklist_covers_all_three_phases(self):
        assert "Before the run" in CHECKLIST
        assert "During the run" in CHECKLIST
        assert "After the run" in CHECKLIST

    def test_checklist_enforces_agent_order(self):
        assert "Scout → Technical → Fundamental → News → Quant → Risk → PM" in CHECKLIST

    def test_disclaimer_denies_being_a_hedge_fund(self):
        assert "not an autonomous hedge fund" in DISCLAIMER


# ---------------------------------------------------------------------------
# Research stack assembly
# ---------------------------------------------------------------------------

class TestResearchStack:
    def test_includes_every_agent_heading(self):
        doc = build_research_stack(_packet())
        for agent in AGENTS:
            assert f"{agent.order}. {agent.name}" in doc

    def test_agents_appear_in_run_order(self):
        doc = build_research_stack(_packet())
        positions = [doc.index(f"{a.order}. {a.name}") for a in AGENTS]
        assert positions == sorted(positions)

    def test_ticker_in_title(self):
        assert build_research_stack(_packet()).startswith("# AAPL — Research Stack")

    def test_contains_raw_material_and_stats(self):
        doc = build_research_stack(_packet())
        assert "Step 0 — Raw material" in doc
        assert "Apple" in doc

    def test_price_history_is_embedded(self):
        doc = build_research_stack(_packet())
        assert "```csv" in doc
        assert "2026-09-02" in doc

    def test_missing_history_tells_you_to_export_it(self):
        doc = build_research_stack(_packet(price_history_csv=None, history_rows=0))
        assert NOT_AVAILABLE in doc
        assert "do not let that agent simulate data" in doc

    def test_missing_stats_are_called_out(self):
        doc = build_research_stack(
            _packet(key_stats={"Analyst mean target": NOT_AVAILABLE})
        )
        assert "do not let any agent use" in doc

    def test_fetch_errors_are_surfaced(self):
        doc = build_research_stack(_packet(fetch_errors=["key statistics: boom"]))
        assert "Fetch problems" in doc
        assert "boom" in doc

    def test_manual_inputs_listed(self):
        doc = build_research_stack(_packet())
        assert "Still to gather by hand" in doc
        assert "investor-relations" in doc

    def test_memo_template_and_checklist_included(self):
        doc = build_research_stack(_packet())
        assert "INVESTMENT RESEARCH MEMO" in doc
        assert "Quick-start checklist" in doc

    def test_document_carries_disclaimers(self):
        doc = build_research_stack(_packet())
        assert "not financial advice" in doc.lower()
        assert "not an autonomous hedge fund" in doc

    def test_golden_rules_present(self):
        doc = build_research_stack(_packet())
        assert "Facts vs. opinions" in doc
        assert "Verify before you pass it on" in doc


class TestPacketHelpers:
    def test_missing_stats_detects_unavailable(self):
        p = _packet(key_stats={"a": "1", "b": NOT_AVAILABLE})
        assert p.missing_stats == ["b"]

    def test_has_price_history_false_when_empty(self):
        assert _packet(price_history_csv=None, history_rows=0).has_price_history is False

    def test_has_price_history_true_when_rows(self):
        assert _packet().has_price_history is True
