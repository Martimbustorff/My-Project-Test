---
name: ai-hedge-fund
description: Run the AI Hedge Fund Team — a 7-agent investment RESEARCH committee (Market Scout → Technical → Fundamental → News → Quant → Risk → Portfolio Manager) that turns one ticker into a structured research memo. Use when the user asks for deep research, a research memo, a bull/bear case, or a committee review of a specific stock or company. Not for the weekly watchlist ranking (use watchlist.cli) and never for trade execution.
---

# AI Hedge Fund Team

A seven-agent research committee. One ticker in, one structured research memo
out. Each agent does one job, has a fixed prompt and a fixed output format, and
hands its report down the chain.

⚠️ **This is research, not advice.** It does not trade, does not manage money,
and never produces a buy/sell instruction. Say so in the output.

## Run order (never reorder, never skip)

```
Market Scout → Technical → Fundamental → News → Quant → Risk → Portfolio Manager
```

Every agent receives **all** the reports above it. The Risk Manager exists to
argue against the idea — read its report before writing the memo, not after.

## Steps

1. **Build the research stack** (fetches real key stats + a price-history CSV):

   ```bash
   cd trading_bot
   PYTHONPATH=. python -m research.cli <TICKER> --out-dir research_stacks
   ```

   This writes `<TICKER>_research_stack.md` with the eight headings, every
   agent's prompt (ticker already resolved), the fetched raw material and the
   memo template — plus `<TICKER>_prices.csv` for the Quant Analyst.

2. **Read the fetch report.** The CLI prints anything the provider did not
   return. Those fields are `NOT AVAILABLE — verify manually`: no agent may use
   them, and you must not fill them in from memory.

3. **Gather what a feed cannot give you** — or state plainly that it is missing:
   the latest earnings release / 10-K / 10-Q, chart screenshots, and dated news
   headlines with links. An agent with no source must say so.

4. **Run the agents in order.** Take each prompt from the stack document (or
   `--print-prompt <agent>`), give it the raw material plus every earlier
   report, and write the report under its heading. Keep each report under one
   page.

5. **Write the memo.** The Portfolio Manager fills the 12-section template using
   only what the six reports contain. It adds no new facts; if something
   important is missing it says so in the memo.

## The five rules every agent must follow

1. Separate **FACTS** (with sources) from **MY OPINION**.
2. **Never invent numbers** — write `NOT AVAILABLE — verify manually` instead.
3. Cite where each fact came from.
4. End with a **CONFIDENCE** line (Low/Medium/High) and what would change your mind.
5. Never promise returns or tell the user to buy or sell.

## Guardrails

- **Never fabricate market data.** If a figure was not fetched or pasted in, it
  does not exist for this run. This is the repo's standing rule (`CLAUDE.md`).
- **Mark every memo facts row `VERIFY`** unless a human confirmed it.
- If an agent describes data it was never given (a chart it did not see,
  a simulated price series), delete that line and re-run it.
- Keep the disclaimer on every generated document.

## Useful commands

```bash
PYTHONPATH=. python -m research.cli --list-agents          # the committee, in order
PYTHONPATH=. python -m research.cli --print-prompt risk    # one agent's prompt
PYTHONPATH=. python -m research.cli NVDA --stdout          # stack to stdout
PYTHONPATH=. python -m pytest tests/test_research.py -q    # tests
```

Workflow adapted as-is from the "AI Hedge Fund Team" guide by @seb.ai.
