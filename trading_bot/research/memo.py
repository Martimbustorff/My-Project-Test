"""
research/memo.py
----------------
The final investment-memo template, the quick-start checklist and the standing
disclaimer of the AI Hedge Fund Team workflow, reproduced as-is.

The Portfolio Manager fills the memo in; you review it, verify the facts table,
and only then treat the memo as finished. Every row of the facts table stays
marked ``VERIFY`` until a human has actually checked it.

Pure text — no network, no I/O.
"""

from __future__ import annotations

MEMO_TEMPLATE = """```text
INVESTMENT RESEARCH MEMO     [TICKER]  ·  [Company]  ·  [Date]

1. ONE-LINE THESIS
[One sentence a beginner could repeat.]

2. RESEARCH RATING + CONFIDENCE
Rating: [Strong Positive / Positive / Neutral / Negative / Strong Negative]     Confidence: [Low / Medium / High]
(A research opinion about the quality of the idea — not an instruction to buy or sell.)

3. WHAT THE COMPANY DOES
[2-3 sentences.]

4. KEY FACTS
Fact  |  Value & period  |  Source  |  Verified? (YES / VERIFY)
[Revenue]  |  [ ]  |  [ ]  |  VERIFY
[Growth]  |  [ ]  |  [ ]  |  VERIFY
[Margin]  |  [ ]  |  [ ]  |  VERIFY
[Valuation]  |  [ ]  |  [ ]  |  VERIFY
[Debt / cash]  |  [ ]  |  [ ]  |  VERIFY

5. THE BULL CASE  (opinion)
•  [Point — supported by: Fundamental / News / Quant ...]
•  [Point]
•  [Point]

6. THE BEAR CASE  (opinion)
•  [Point — supported by: Risk Manager / Technical ...]
•  [Point]
•  [Point]

7. WHERE THE TEAM DISAGREES
[Which analysts disagree, about what, and which side the PM leans toward and why.]

8. TOP 3 RISKS
1. [ ]     2. [ ]     3. [ ]

9. WHAT TO WATCH NEXT
Catalysts: [date — event]     Price levels: [support / resistance and why]

10. WHAT WOULD CHANGE MY MIND
[Specific evidence that would raise or lower the rating.]

11. NUMBERS TO VERIFY BEFORE ACTING
[List every unverified figure and where to check it.]

12. DISCLAIMER
This memo was produced by an AI research workflow for educational purposes only. It is not financial
advice, it does not predict returns, and every figure should be verified against primary sources. Consult
a licensed professional before making investment decisions.
```"""


CHECKLIST = """## Quick-start checklist

**Before the run**
- [ ] Pick one stock or company (or let the Market Scout suggest candidates).
- [ ] Create the research doc with the eight headings.
- [ ] Download the latest earnings release and 10-K / 10-Q excerpts from the company's investor-relations page.
- [ ] Take 6-month and 2-year chart screenshots.
- [ ] Save the key-stats page and five dated news headlines with links.
- [ ] Export a price-history CSV for the Quant Analyst.

**During the run**
- [ ] Run the agents in order: Scout → Technical → Fundamental → News → Quant → Risk → PM.
- [ ] Give each agent every report from the agents above it.
- [ ] Keep every report under one page.
- [ ] Confirm every report has a FACTS section with sources and a separate OPINION section.
- [ ] If an agent invents a number or describes data you never gave it, delete that line and re-run.

**After the run**
- [ ] Spot-check at least five key numbers against the original source.
- [ ] Read the Risk Manager's report before the Portfolio Manager's memo, not after.
- [ ] Mark every row of the memo's facts table YES or VERIFY.
- [ ] Remember: the memo is research, not advice. The decision — and the responsibility — is yours."""


DISCLAIMER = """> **Important disclaimer.** The AI Hedge Fund Team is an educational research
> workflow. It is not an autonomous hedge fund, it does not execute trades, and
> nothing it produces is financial, investment, legal, or tax advice. AI models
> can produce incorrect or fabricated information — verify all numbers and
> sources independently. No outcome or return is promised or implied. Investing
> involves risk, including the loss of principal. Consult a licensed financial
> professional before making any investment decision.
>
> Workflow adapted as-is from the "AI Hedge Fund Team" guide by @seb.ai."""
