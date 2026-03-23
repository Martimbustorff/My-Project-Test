"""
analysis/signals.py
-------------------
Combines technical, sentiment, momentum and fundamental scores into
a final trading signal: BUY / SELL / SHORT / COVER / HOLD.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging
import pandas as pd
import numpy as np
from datetime import datetime, time
import pytz

logger = logging.getLogger(__name__)

class Action(str, Enum):
    BUY   = "BUY"
    SELL  = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"
    HOLD  = "HOLD"

@dataclass
class Signal:
    symbol: str
    action: Action
    confidence: float          # 0.0 – 1.0
    combined_score: float      # -1.0 – +1.0
    technical_score: float
    sentiment_score: float
    momentum_score: float
    fundamental_score: float
    current_price: float
    reasoning: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

class SignalGenerator:
    """
    Fuses weighted sub-scores into a single tradeable signal.

    Score weights (from Settings):
        TECHNICAL_WEIGHT   = 0.35
        SENTIMENT_WEIGHT   = 0.30
        MOMENTUM_WEIGHT    = 0.20
        FUNDAMENTAL_WEIGHT = 0.15

    Action thresholds:
        combined >  0.35  → BUY   (if not already long)
        combined < -0.35  → SHORT (if shortable & regime allows)
        combined < -0.20  → SELL  (if currently long)
        combined >  0.20  → COVER (if currently short)
        otherwise         → HOLD
    """

    def __init__(self, settings=None):
        from config.settings import Settings
        self.cfg = settings or Settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_signal(
        self,
        symbol: str,
        price_df: pd.DataFrame,
        technical_score: float,
        sentiment_score: float,
        news_items: list,
        fundamentals: dict,
        market_regime: str,   # 'bull' | 'bear' | 'neutral'
        vix: float,
        is_long: bool = False,
        is_short: bool = False,
        is_shortable: bool = True,
    ) -> Signal:
        """Generate a Signal for *symbol* given pre-computed sub-scores."""

        reasoning: list[str] = []

        # ---- momentum score -------------------------------------------
        momentum_score = self._momentum_score(price_df, reasoning)

        # ---- fundamental score ----------------------------------------
        fund_score = self._fundamental_score(fundamentals, reasoning)

        # ---- combine --------------------------------------------------
        combined = (
            self.cfg.TECHNICAL_WEIGHT   * technical_score
            + self.cfg.SENTIMENT_WEIGHT * sentiment_score
            + self.cfg.MOMENTUM_WEIGHT  * momentum_score
            + self.cfg.FUNDAMENTAL_WEIGHT * fund_score
        )
        combined = float(np.clip(combined, -1.0, 1.0))

        # ---- contextual overrides -------------------------------------
        if vix > 40:
            reasoning.append(f"VIX={vix:.1f} > 40: reducing signal strength by 50%")
            combined *= 0.5

        if market_regime == "bear" and combined > 0:
            reasoning.append("Bear regime: dampening long signal by 30%")
            combined *= 0.7

        if market_regime == "bull" and combined < 0:
            reasoning.append("Bull regime: dampening short signal by 30%")
            combined *= 0.7

        # ---- blackout window ------------------------------------------
        if self._in_blackout_window():
            reasoning.append("Within 30-min market open/close blackout → HOLD")
            return Signal(
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.0,
                combined_score=combined,
                technical_score=technical_score,
                sentiment_score=sentiment_score,
                momentum_score=momentum_score,
                fundamental_score=fund_score,
                current_price=self._latest_price(price_df),
                reasoning=reasoning,
            )

        # ---- determine action -----------------------------------------
        action, confidence = self._decide_action(
            combined, is_long, is_short, is_shortable, market_regime, reasoning
        )

        reasoning.insert(0,
            f"combined={combined:.3f} "
            f"(tech={technical_score:.2f}, sent={sentiment_score:.2f}, "
            f"mom={momentum_score:.2f}, fund={fund_score:.2f})"
        )

        return Signal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            combined_score=combined,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            momentum_score=momentum_score,
            fundamental_score=fund_score,
            current_price=self._latest_price(price_df),
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _momentum_score(self, df: pd.DataFrame, reasoning: list) -> float:
        """Rate-of-change momentum over multiple lookbacks."""
        if df is None or df.empty or "close" not in df.columns:
            return 0.0
        close = df["close"].dropna()
        if len(close) < 21:
            return 0.0
        scores = []
        weights = []
        for lb, w in [(5, 0.5), (10, 0.3), (20, 0.2)]:
            if len(close) > lb:
                roc = (close.iloc[-1] / close.iloc[-lb] - 1)
                scores.append(float(np.clip(roc * 10, -1, 1)))   # scale ~10% move → ±1
                weights.append(w)
        if not scores:
            return 0.0
        score = float(np.average(scores, weights=weights))
        reasoning.append(f"Momentum score: {score:.3f}")
        return score

    def _fundamental_score(self, fund: dict, reasoning: list) -> float:
        """Score based on P/E, beta, earnings growth."""
        if not fund:
            return 0.0
        score = 0.0
        count = 0
        # P/E: prefer 10-25 range
        pe = fund.get("pe_ratio")
        if pe and pe > 0:
            if pe < 10:
                score += 0.3
            elif pe < 20:
                score += 0.6
            elif pe < 30:
                score += 0.3
            elif pe < 50:
                score -= 0.2
            else:
                score -= 0.5
            count += 1
            reasoning.append(f"P/E={pe:.1f}")
        # EPS growth
        eps_growth = fund.get("eps_growth")
        if eps_growth is not None:
            score += float(np.clip(eps_growth * 2, -1, 1))
            count += 1
            reasoning.append(f"EPS growth={eps_growth:.1%}")
        # Beta: prefer moderate beta 0.8-1.5
        beta = fund.get("beta")
        if beta is not None and beta > 0:
            if 0.8 <= beta <= 1.5:
                score += 0.2
            elif beta > 2.5:
                score -= 0.3
            count += 1
        return float(np.clip(score / max(count, 1), -1, 1))

    def _decide_action(
        self,
        combined: float,
        is_long: bool,
        is_short: bool,
        is_shortable: bool,
        market_regime: str,
        reasoning: list,
    ) -> tuple[Action, float]:
        confidence = min(abs(combined), 1.0)

        if is_long:
            if combined < -0.20:
                reasoning.append(f"SELL: long position, combined={combined:.3f} < -0.20")
                return Action.SELL, confidence
        elif is_short:
            if combined > 0.20:
                reasoning.append(f"COVER: short position, combined={combined:.3f} > 0.20")
                return Action.COVER, confidence
        else:
            if combined > 0.35:
                reasoning.append(f"BUY: combined={combined:.3f} > 0.35")
                return Action.BUY, confidence
            if combined < -0.35 and is_shortable and market_regime != "bull":
                reasoning.append(f"SHORT: combined={combined:.3f} < -0.35")
                return Action.SHORT, confidence

        reasoning.append(f"HOLD: combined={combined:.3f} within thresholds")
        return Action.HOLD, confidence

    @staticmethod
    def _in_blackout_window() -> bool:
        """True if within 30 min of market open (9:30 ET) or close (16:00 ET)."""
        et = pytz.timezone("America/New_York")
        now = datetime.now(et).time()
        open_blackout_end   = time(10, 0)
        close_blackout_start = time(15, 30)
        market_open  = time(9, 30)
        market_close = time(16, 0)
        return (market_open <= now < open_blackout_end) or \
               (close_blackout_start <= now <= market_close)

    @staticmethod
    def _latest_price(df: pd.DataFrame) -> float:
        if df is None or df.empty:
            return 0.0
        for col in ("close", "price", "vwap"):
            if col in df.columns:
                val = df[col].dropna()
                if not val.empty:
                    return float(val.iloc[-1])
        return 0.0
