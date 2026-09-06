# 🏛️ AI Hedge Fund Team

A **seven-agent investment research committee**, implemented as-is from the
guide by @seb.ai. One ticker goes in; each agent does one job and hands off to
the next; a structured research memo comes out.

```
STOCK / COMPANY
      ↓
1  MARKET SCOUT          is it worth researching?
2  TECHNICAL ANALYST     charts & price action
3  FUNDAMENTAL ANALYST   financials & valuation
4  NEWS ANALYST          catalysts & risks
5  QUANT ANALYST         data, signals, scenarios
6  RISK MANAGER          attacks the idea
7  PORTFOLIO MANAGER     final call
      ↓
FINAL INVESTMENT MEMO
```

> ⚠️ **Read this first.** This is an AI-powered investment **research** system.
> It is not an autonomous hedge fund, it does not trade, and it does not manage
> money. Nothing it produces is financial advice. AI models make mistakes and
> can state wrong numbers with total confidence — verify every figure and source
> yourself. For educational and research purposes only.

## Why seven agents instead of one prompt

- **Focus.** An agent with one job produces sharper, more honest output.
- **Built-in disagreement.** The Risk Manager exists to argue against the idea.
  One-prompt systems almost never argue with themselves.
- **Checkable.** Each report is short, labeled, and separates facts from
  opinions, so you can verify the numbers before the next step.

## Usage

```bash
cd trading_bot

# Build the research stack for a ticker (fetches key stats + price CSV)
PYTHONPATH=. python -m research.cli AAPL

# Options
PYTHONPATH=. python -m research.cli IREN --out-dir research_stacks --period 5y
PYTHONPATH=. python -m research.cli NVDA --stdout        # print instead of writing
PYTHONPATH=. python -m research.cli --list-agents        # the committee, in order
PYTHONPATH=. python -m research.cli --print-prompt risk  # one agent's prompt
```

This writes:

| File | What it is |
|------|------------|
| `<TICKER>_research_stack.md` | The eight headings, every agent prompt (ticker resolved), the fetched raw material, the memo template and the checklist |
| `<TICKER>_prices.csv` | Daily price history so the Quant Analyst computes rather than imagines |

Then run the agents **top to bottom**, giving each one every report above it.
Claude Code sessions can drive the whole chain with the `ai-hedge-fund` skill.

## The two golden rules

1. **Facts vs. opinions.** Every agent puts verifiable facts (with a source) in
   one section and its interpretation in another.
2. **Verify before you pass it on.** Spot-check the key numbers before feeding a
   report to the next agent — a wrong number at step 3 becomes a wrong
   conclusion at step 7.

## The five rules in every prompt

1. Separate FACTS from OPINIONS.
2. Never invent numbers — write `NOT AVAILABLE — verify manually` instead.
3. Cite where each fact came from.
4. End with a CONFIDENCE line and what would change your mind.
5. Never promise returns or give buy/sell instructions.

The CLI enforces rule 2 at the source: anything the provider did not return is
written as `NOT AVAILABLE — verify manually`, listed in the terminal output, and
called out in the document — so a gap is visible instead of quietly filled.

## Architecture

```
research/
├── agents.py   # the 7 prompts + the 5 shared rules  (PURE — no network)
├── packet.py   # gathers the real raw material for a ticker  (I/O)
├── stack.py    # assembles the research-stack document  (PURE)
├── memo.py     # the 12-section memo template + checklist  (PURE)
└── cli.py      # python -m research.cli
```

Same boundary as the watchlist: prompt/assembly logic is pure and
unit-tested (`tests/test_research.py`), and only `packet.py` touches the network.

Workflow adapted as-is from the "AI Hedge Fund Team" guide by @seb.ai.
