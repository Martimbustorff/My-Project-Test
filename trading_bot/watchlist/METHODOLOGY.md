# Watchlist Methodology — full specification

A self-contained spec of the dynamic weekly stock watchlist: the scope, the
exact scoring formulas, the qualification gate, the ranking output, and a
ready-to-paste prompt so the same watchlist can be reproduced by any AI agent
(e.g. eToro's) or by hand.

> ⚠️ **Not investment advice.** Built on public fundamental/analyst data for
> research and education only. Extreme analyst targets (e.g. +400%) can be
> unrealistic. Do your own due diligence.

## 1. Objective
A weekly watchlist of **growing** stocks, holding horizon **≤ 3 months (90 days)**,
ranked by three lenses plus a composite. **American and European** stocks only,
**any market cap** (large / mid / small).

## 2. Universe
- **US:** NYSE / Nasdaq — bare tickers (`AAPL`, `NVDA`, `IREN`).
- **Europe:** LSE, Euronext (Paris/Amsterdam/Brussels), Xetra, Borsa Italiana,
  BME, SIX, Nasdaq Stockholm/Copenhagen/Helsinki, Oslo — suffixed tickers
  (`ASML.AS`, `SAP.DE`, `AZN.L`, `RACE.MI`, `NESN.SW`).
- **Data note:** analyst target/consensus is readily available for US names;
  for many European names it requires a paid data tier.

## 3. Horizon & cadence
- Recommendation horizon: up to ~3 months.
- Regeneration: weekly (e.g. Monday morning) with live prices/targets.

## 4. Data inputs per stock (source: yfinance / FMP-style)
- current price
- analyst mean target (`targetMeanPrice`)
- revenue growth YoY (`revenueGrowth`) — fraction (`0.25` = +25%)
- multi-year revenue CAGR — optional
- earnings / EPS growth (`earningsGrowth`) — optional
- mean recommendation 1–5 (1 = Strong Buy … 5 = Strong Sell)
- number of analysts (`numberOfAnalystOpinions`)
- 3-month price change — optional (trend)

## 5. Scoring (0–100 each) — exact formulas

### A. Upside (target vs price)
```
upside% = (target / price) - 1
score   = linear map:  -10% -> 0 ;  0% -> 25 ;  +30% -> 100     (clamp 0..100)

# thin-coverage discount:
if num_analysts < 5:
    score = 50 + (score - 50) * (num_analysts / 5)

# override: if high_conviction (manual human call) -> skip the discount
# missing upside -> 50
```

### B. Growth (financial history)
```
# map each metric: -10% -> 0 ; 0% -> 30 ; +25% -> 90 ; +50% -> 100
# weighted blend of whatever is present, renormalised:
#   revenue YoY 0.5 · revenue CAGR 0.3 · earnings growth 0.2
# missing everything -> 50
```

### C. Consensus (analysts)
```
score = map: recommendation 1.0 -> 100 ; 3.0 -> 50 ; 5.0 -> 0
if num_analysts < 5:  shrink toward 50 (same as upside)
# missing -> 50
```

### D. Composite
```
composite = 0.40*upside + 0.35*growth + 0.25*consensus
```

## 6. "Growing stock" gate (to be listed)
- revenue YoY ≥ **+5%**, **and**
- (upside ≥ 0%  **or**  recommendation ≤ 3.0)
- (optional) 3-month trend > 0

Each rule is skipped when its data is missing (does not disqualify the name).

## 7. Output
Four ranked tables: **Composite**, **Biggest Upside**, **Financial Growth**,
**Analyst Consensus**. #1 = best; bottom = avoid / caution.

## 8. Reading rules
- Big upside with **few analysts** = weak signal (already discounted).
- Target **below** price (negative upside) = analysts see downside → caution.
- High growth with upside ~0 = "priced in" → don't chase.
- High score driven by a **falling** price (falling knife) = not strength.

## 9. Rotation rules (how to decide moves)
- Trim/exit the clear laggards (no upside, Hold, target below price).
- Stop reinforcing names whose upside is exhausted (target ≈ price).
- Add candidates that **out-screen** current holdings on the composite.
- Keep the quality core.
- Do **not** do a wholesale rotation off a 3-month score — it risks selling low
  / buying high, plus costs and taxes. Swapping one speculative name for another
  is re-theming, not de-risking.

## 10. Moonshots (2-year, high-asymmetry — lottery, size 1–3% each)
Basket across distinct themes; expect most to fail. Examples of the *profile*:
quantum (IONQ), nuclear SMR (OKLO), space (RKLB), AI drug discovery (RXRX),
Bitcoin-leverage (IREN / MARA). Each needs a concrete catalyst (launch, trial,
first reactor, halving).

## 11. Ready-to-paste prompt for an AI agent (e.g. eToro)
> Create and weekly-update a watchlist of growing American and European stocks,
> horizon up to 3 months, any market cap. For each stock get: price, analyst
> mean target, revenue growth YoY, mean recommendation (1–5) and number of
> analysts. Compute three 0–100 scores: UPSIDE [(target/price−1): −10%→0, 0%→25,
> +30%→100; if <5 analysts shrink toward 50 proportional to coverage], GROWTH
> [revenue YoY: −10%→0, 0%→30, +25%→90, +50%→100] and CONSENSUS [rec 1→100,
> 3→50, 5→0; <5 analysts shrink toward 50]. COMPOSITE = 0.40×upside +
> 0.35×growth + 0.25×consensus. Only include stocks with revenue YoY ≥ +5% and
> (upside ≥0 or rec ≤3). Show four rankings: composite, upside, growth,
> consensus. Flag: target<price = caution; big upside with few analysts = weak
> signal; high growth with upside ~0 = priced in. Assess my portfolio [paste
> tickers] and say what to add / hold / trim / avoid, and whether a partial
> rotation makes sense.

## 12. Reference implementation
This methodology is implemented in code under `trading_bot/watchlist/`
(`scoring.py` = the exact formulas above, fully unit-tested) and runs weekly via
the `Weekly Stock Watchlist` GitHub Action, which commits reports to
`trading_bot/watchlists/`.
