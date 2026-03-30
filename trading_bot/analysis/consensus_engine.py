"""
Multi-agent consensus engine.
Each agent analyses a symbol independently using a different lens.
They then "debate" by comparing their positions, and a weighted consensus is produced.
"""
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import sqlite3
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "trading_bot.db")


@dataclass
class AgentVote:
    agent_name: str
    score: float        # -1.0 (strong sell) to +1.0 (strong buy)
    confidence: float   # 0.0 to 1.0
    signal: str         # STRONG BUY / BUY / HOLD / SELL / STRONG SELL
    reasons: List[str]  # 2-4 bullet points explaining the vote
    weight: float = 1.0 # relative weight in consensus


@dataclass
class ConsensusResult:
    symbol: str
    timestamp: str
    price: float
    change_pct: float

    votes: List[AgentVote]

    consensus_score: float   # -1.0 to 1.0
    recommendation: str      # STRONG BUY / BUY / HOLD / SELL / STRONG SELL
    direction: str           # LONG or SHORT
    confidence: float        # 0.0 to 1.0
    agreement_pct: float     # % of agents that agree with recommendation

    bull_agents: List[str]   # agent names recommending long/buy
    bear_agents: List[str]   # agent names recommending short/sell
    key_reasons: List[str]   # top 3 consensus reasons
    key_risks: List[str]     # top 2 opposing reasons

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @staticmethod
    def score_to_signal(score: float) -> str:
        if score >= 0.6:
            return "STRONG BUY"
        if score >= 0.25:
            return "BUY"
        if score > -0.25:
            return "HOLD"
        if score > -0.6:
            return "SELL"
        return "STRONG SELL"


# ---------------------------------------------------------------------------
# Agent functions
# ---------------------------------------------------------------------------

def technical_agent(ticker: yf.Ticker, hist: pd.DataFrame) -> AgentVote:
    """
    Technical analysis agent using pandas_ta indicators.
    Scores RSI, MACD, Bollinger Bands, EMA crossover, and volume trend.
    """
    reasons: List[str] = []
    scores: List[float] = []
    weights: List[float] = []

    try:
        if hist.empty or len(hist) < 20:
            return AgentVote(
                agent_name="Technical",
                score=0.0,
                confidence=0.1,
                signal="HOLD",
                reasons=["Insufficient price history"],
            )

        df = hist.copy()
        df.columns = [c.lower() for c in df.columns]
        close = df["close"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else None

        # --- RSI(14) ---
        try:
            rsi_series = ta.rsi(close, length=14)
            if rsi_series is not None and not rsi_series.dropna().empty:
                rsi = float(rsi_series.dropna().iloc[-1])
                if rsi < 30:
                    rsi_score = min(1.0, (30 - rsi) / 20)
                    reasons.append(f"RSI={rsi:.1f} oversold → bullish")
                elif rsi > 70:
                    rsi_score = -min(1.0, (rsi - 70) / 20)
                    reasons.append(f"RSI={rsi:.1f} overbought → bearish")
                elif rsi < 45:
                    rsi_score = 0.25
                    reasons.append(f"RSI={rsi:.1f} slightly weak")
                elif rsi > 55:
                    rsi_score = -0.25
                    reasons.append(f"RSI={rsi:.1f} slightly strong")
                else:
                    rsi_score = 0.0
                scores.append(rsi_score)
                weights.append(0.30)
        except Exception as e:
            logger.debug("Technical agent RSI error: %s", e)

        # --- MACD ---
        try:
            macd_df = ta.macd(close, fast=12, slow=26, signal=9)
            if macd_df is not None and not macd_df.empty:
                cols = list(macd_df.columns)
                macd_val = float(macd_df[cols[0]].dropna().iloc[-1]) if not macd_df[cols[0]].dropna().empty else None
                macd_sig = float(macd_df[cols[2]].dropna().iloc[-1]) if not macd_df[cols[2]].dropna().empty else None
                if macd_val is not None and macd_sig is not None:
                    if macd_val > macd_sig:
                        macd_score = 0.6
                        reasons.append(f"MACD bullish crossover (MACD > signal)")
                    else:
                        macd_score = -0.6
                        reasons.append(f"MACD bearish (MACD < signal)")
                    scores.append(macd_score)
                    weights.append(0.25)
        except Exception as e:
            logger.debug("Technical agent MACD error: %s", e)

        # --- Bollinger Bands ---
        try:
            bb = ta.bbands(close, length=20, std=2)
            if bb is not None and not bb.empty:
                bb_cols = list(bb.columns)
                bb_lower = float(bb[bb_cols[0]].dropna().iloc[-1]) if not bb[bb_cols[0]].dropna().empty else None
                bb_upper = float(bb[bb_cols[2]].dropna().iloc[-1]) if not bb[bb_cols[2]].dropna().empty else None
                current_price = float(close.iloc[-1])
                if bb_lower is not None and bb_upper is not None:
                    band_width = bb_upper - bb_lower
                    if band_width > 0:
                        pos = (current_price - bb_lower) / band_width
                        if pos < 0.2:
                            bb_score = 0.8
                            reasons.append(f"Price near lower Bollinger Band → bullish")
                        elif pos > 0.8:
                            bb_score = -0.8
                            reasons.append(f"Price near upper Bollinger Band → bearish")
                        elif pos < 0.4:
                            bb_score = 0.3
                        elif pos > 0.6:
                            bb_score = -0.3
                        else:
                            bb_score = 0.0
                        scores.append(bb_score)
                        weights.append(0.20)
        except Exception as e:
            logger.debug("Technical agent BB error: %s", e)

        # --- EMA 20/50 crossover ---
        try:
            ema20 = ta.ema(close, length=20)
            ema50 = ta.ema(close, length=50)
            if ema20 is not None and ema50 is not None:
                ema20_val = ema20.dropna()
                ema50_val = ema50.dropna()
                if not ema20_val.empty and not ema50_val.empty:
                    e20 = float(ema20_val.iloc[-1])
                    e50 = float(ema50_val.iloc[-1])
                    if e20 > e50:
                        sep = (e20 - e50) / e50
                        ema_score = min(1.0, sep * 20)
                        reasons.append(f"EMA20 > EMA50 (golden cross) → bullish")
                    else:
                        sep = (e50 - e20) / e50
                        ema_score = -min(1.0, sep * 20)
                        reasons.append(f"EMA20 < EMA50 (death cross) → bearish")
                    scores.append(ema_score)
                    weights.append(0.15)
        except Exception as e:
            logger.debug("Technical agent EMA error: %s", e)

        # --- Volume trend ---
        try:
            if volume is not None and len(volume.dropna()) >= 10:
                recent_vol = float(volume.iloc[-5:].mean())
                older_vol = float(volume.iloc[-20:-5].mean())
                if older_vol > 0:
                    vol_ratio = recent_vol / older_vol
                    # Volume confirms direction based on price trend
                    price_trend = float(close.iloc[-1]) / float(close.iloc[-5]) - 1
                    if vol_ratio > 1.2 and price_trend > 0:
                        vol_score = 0.5
                        reasons.append(f"Rising volume confirms uptrend")
                    elif vol_ratio > 1.2 and price_trend < 0:
                        vol_score = -0.5
                        reasons.append(f"Rising volume confirms downtrend")
                    elif vol_ratio < 0.8:
                        vol_score = 0.0  # Declining volume = weak conviction
                    else:
                        vol_score = 0.0
                    scores.append(vol_score)
                    weights.append(0.10)
        except Exception as e:
            logger.debug("Technical agent volume error: %s", e)

        if not scores:
            return AgentVote(
                agent_name="Technical",
                score=0.0,
                confidence=0.1,
                signal="HOLD",
                reasons=["No indicators computable"],
            )

        # Weighted average
        total_weight = sum(weights)
        final_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        final_score = float(max(-1.0, min(1.0, final_score)))
        confidence = min(0.95, total_weight / (0.30 + 0.25 + 0.20 + 0.15 + 0.10))
        signal = ConsensusResult.score_to_signal(final_score)

        if not reasons:
            reasons.append("Mixed technical signals")

        return AgentVote(
            agent_name="Technical",
            score=final_score,
            confidence=confidence,
            signal=signal,
            reasons=reasons[:4],
        )

    except Exception as exc:
        logger.error("TechnicalAgent error: %s", exc)
        return AgentVote(
            agent_name="Technical",
            score=0.0,
            confidence=0.0,
            signal="HOLD",
            reasons=[f"Error: {str(exc)[:80]}"],
        )


def fundamental_agent(ticker: yf.Ticker, hist: pd.DataFrame) -> AgentVote:
    """
    Fundamental analysis agent using yfinance .info.
    Scores P/E, revenue growth, profit margin, debt/equity, and EPS trend.
    """
    reasons: List[str] = []
    scores: List[float] = []
    weights: List[float] = []

    try:
        info = ticker.info or {}

        # --- P/E ratio ---
        pe = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        sector = info.get("sector", "")

        # Approximate sector P/E averages
        sector_pe_avg = {
            "Technology": 28.0,
            "Healthcare": 22.0,
            "Financials": 14.0,
            "Consumer Discretionary": 24.0,
            "Consumer Staples": 20.0,
            "Energy": 12.0,
            "Industrials": 20.0,
            "Materials": 16.0,
            "Real Estate": 30.0,
            "Utilities": 18.0,
            "Communication Services": 22.0,
        }
        benchmark_pe = sector_pe_avg.get(sector, 20.0)

        if pe and isinstance(pe, (int, float)) and pe > 0:
            pe_ratio = pe / benchmark_pe
            if pe_ratio < 0.7:
                pe_score = 0.8
                reasons.append(f"P/E={pe:.1f} well below sector avg ({benchmark_pe:.0f}) → undervalued")
            elif pe_ratio < 0.9:
                pe_score = 0.4
                reasons.append(f"P/E={pe:.1f} below sector avg → fair value")
            elif pe_ratio < 1.2:
                pe_score = 0.0
                reasons.append(f"P/E={pe:.1f} near sector avg")
            elif pe_ratio < 1.5:
                pe_score = -0.3
                reasons.append(f"P/E={pe:.1f} above sector avg → slightly expensive")
            else:
                pe_score = -0.6
                reasons.append(f"P/E={pe:.1f} significantly above sector avg → overvalued")
            scores.append(pe_score)
            weights.append(0.30)

        # --- Revenue growth ---
        rev_growth = info.get("revenueGrowth")
        if rev_growth is not None and isinstance(rev_growth, (int, float)):
            if rev_growth > 0.20:
                rg_score = 0.8
                reasons.append(f"Revenue growth {rev_growth:.1%} YoY → strong growth")
            elif rev_growth > 0.05:
                rg_score = 0.4
                reasons.append(f"Revenue growth {rev_growth:.1%} YoY → positive")
            elif rev_growth > -0.05:
                rg_score = 0.0
            elif rev_growth > -0.15:
                rg_score = -0.4
                reasons.append(f"Revenue declining {rev_growth:.1%} YoY → concerning")
            else:
                rg_score = -0.8
                reasons.append(f"Revenue sharply declining {rev_growth:.1%} YoY → bearish")
            scores.append(rg_score)
            weights.append(0.25)

        # --- Profit margin ---
        profit_margin = info.get("profitMargins")
        if profit_margin is not None and isinstance(profit_margin, (int, float)):
            if profit_margin > 0.20:
                pm_score = 0.7
                reasons.append(f"Profit margin {profit_margin:.1%} → high quality")
            elif profit_margin > 0.10:
                pm_score = 0.4
            elif profit_margin > 0.05:
                pm_score = 0.1
            elif profit_margin > 0:
                pm_score = -0.1
            else:
                pm_score = -0.6
                reasons.append(f"Negative profit margin {profit_margin:.1%} → unprofitable")
            scores.append(pm_score)
            weights.append(0.20)

        # --- Debt/Equity ratio ---
        de_ratio = info.get("debtToEquity")
        if de_ratio is not None and isinstance(de_ratio, (int, float)):
            if de_ratio < 30:
                de_score = 0.5
            elif de_ratio < 100:
                de_score = 0.1
            elif de_ratio < 200:
                de_score = -0.3
                reasons.append(f"Debt/Equity={de_ratio:.0f}% → elevated leverage")
            else:
                de_score = -0.7
                reasons.append(f"Debt/Equity={de_ratio:.0f}% → high debt load bearish")
            scores.append(de_score)
            weights.append(0.15)

        # --- EPS trend (trailing vs forward) ---
        eps_trailing = info.get("trailingEps")
        eps_forward = info.get("forwardEps")
        if eps_trailing and eps_forward and isinstance(eps_trailing, (int, float)) and isinstance(eps_forward, (int, float)):
            if eps_trailing > 0 and eps_forward > eps_trailing:
                eps_growth = (eps_forward - eps_trailing) / abs(eps_trailing)
                if eps_growth > 0.10:
                    eps_score = 0.6
                    reasons.append(f"EPS improving: {eps_trailing:.2f} → {eps_forward:.2f} → bullish")
                else:
                    eps_score = 0.3
            elif eps_forward < eps_trailing:
                eps_score = -0.4
                reasons.append(f"EPS declining: {eps_trailing:.2f} → {eps_forward:.2f} → bearish")
            else:
                eps_score = 0.0
            scores.append(eps_score)
            weights.append(0.10)

        if not scores:
            return AgentVote(
                agent_name="Fundamental",
                score=0.0,
                confidence=0.2,
                signal="HOLD",
                reasons=["Insufficient fundamental data"],
            )

        total_weight = sum(weights)
        final_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        final_score = float(max(-1.0, min(1.0, final_score)))
        # Confidence scales with how much data we have
        confidence = min(0.85, len(scores) / 5.0 * 0.85)
        signal = ConsensusResult.score_to_signal(final_score)

        if not reasons:
            reasons.append("Mixed fundamental signals")

        return AgentVote(
            agent_name="Fundamental",
            score=final_score,
            confidence=confidence,
            signal=signal,
            reasons=reasons[:4],
        )

    except Exception as exc:
        logger.error("FundamentalAgent error: %s", exc)
        return AgentVote(
            agent_name="Fundamental",
            score=0.0,
            confidence=0.0,
            signal="HOLD",
            reasons=[f"Error: {str(exc)[:80]}"],
        )


def momentum_agent(ticker: yf.Ticker, hist: pd.DataFrame, spy_hist: pd.DataFrame) -> AgentVote:
    """
    Momentum agent scoring price momentum across multiple timeframes,
    RSI momentum, and relative strength vs SPY.
    """
    reasons: List[str] = []
    scores: List[float] = []
    weights: List[float] = []

    try:
        if hist.empty or len(hist) < 10:
            return AgentVote(
                agent_name="Momentum",
                score=0.0,
                confidence=0.1,
                signal="HOLD",
                reasons=["Insufficient price history"],
            )

        df = hist.copy()
        df.columns = [c.lower() for c in df.columns]
        close = df["close"].astype(float)
        current_price = float(close.iloc[-1])

        # --- 1-week return (5 trading days) ---
        if len(close) >= 5:
            week_ret = (current_price / float(close.iloc[-5]) - 1)
            week_score = float(max(-1.0, min(1.0, week_ret * 10)))  # 10% = full score
            if week_ret > 0.02:
                reasons.append(f"1-week return +{week_ret:.1%} → bullish momentum")
            elif week_ret < -0.02:
                reasons.append(f"1-week return {week_ret:.1%} → bearish momentum")
            scores.append(week_score)
            weights.append(0.20)

        # --- 1-month return (~21 trading days) ---
        if len(close) >= 21:
            month_ret = (current_price / float(close.iloc[-21]) - 1)
            month_score = float(max(-1.0, min(1.0, month_ret * 5)))  # 20% = full score
            if month_ret > 0.05:
                reasons.append(f"1-month return +{month_ret:.1%} → positive trend")
            elif month_ret < -0.05:
                reasons.append(f"1-month return {month_ret:.1%} → negative trend")
            scores.append(month_score)
            weights.append(0.25)

        # --- 3-month return (~63 trading days) ---
        if len(close) >= 63:
            qtr_ret = (current_price / float(close.iloc[-63]) - 1)
            qtr_score = float(max(-1.0, min(1.0, qtr_ret * 3)))  # 33% = full score
            if qtr_ret > 0.10:
                reasons.append(f"3-month return +{qtr_ret:.1%} → strong medium-term momentum")
            elif qtr_ret < -0.10:
                reasons.append(f"3-month return {qtr_ret:.1%} → weak medium-term momentum")
            scores.append(qtr_score)
            weights.append(0.20)

        # --- RSI momentum (rising vs falling RSI) ---
        try:
            rsi_series = ta.rsi(close, length=14)
            if rsi_series is not None:
                rsi_clean = rsi_series.dropna()
                if len(rsi_clean) >= 5:
                    rsi_now = float(rsi_clean.iloc[-1])
                    rsi_prev = float(rsi_clean.iloc[-5])
                    rsi_delta = rsi_now - rsi_prev
                    rsi_mom_score = float(max(-1.0, min(1.0, rsi_delta / 20)))
                    if rsi_delta > 5:
                        reasons.append(f"RSI rising ({rsi_prev:.0f}→{rsi_now:.0f}) → bullish momentum")
                    elif rsi_delta < -5:
                        reasons.append(f"RSI falling ({rsi_prev:.0f}→{rsi_now:.0f}) → bearish momentum")
                    scores.append(rsi_mom_score)
                    weights.append(0.15)
        except Exception as e:
            logger.debug("Momentum RSI error: %s", e)

        # --- 52-week position ---
        if len(close) >= 50:
            high_52 = float(close.tail(min(252, len(close))).max())
            low_52 = float(close.tail(min(252, len(close))).min())
            if high_52 > low_52:
                pos_52 = (current_price - low_52) / (high_52 - low_52)
                if pos_52 > 0.75:
                    w52_score = 0.7
                    reasons.append(f"Near 52-week high ({pos_52:.0%} range) → strong momentum")
                elif pos_52 < 0.25:
                    w52_score = -0.7
                    reasons.append(f"Near 52-week low ({pos_52:.0%} range) → weak momentum")
                else:
                    w52_score = (pos_52 - 0.5) * 1.0  # linear: -0.5 to +0.5
                scores.append(w52_score)
                weights.append(0.10)

        # --- Relative strength vs SPY (1-month) ---
        try:
            if not spy_hist.empty and len(close) >= 21:
                spy_close = spy_hist["Close"].astype(float) if "Close" in spy_hist.columns else spy_hist["close"].astype(float)
                if len(spy_close) >= 21:
                    spy_ret = (float(spy_close.iloc[-1]) / float(spy_close.iloc[-21]) - 1)
                    stock_ret_1m = (current_price / float(close.iloc[-21]) - 1) if len(close) >= 21 else 0.0
                    rs = stock_ret_1m - spy_ret
                    rs_score = float(max(-1.0, min(1.0, rs * 10)))
                    if rs > 0.03:
                        reasons.append(f"Outperforming SPY by {rs:.1%} (1-month) → relative strength")
                    elif rs < -0.03:
                        reasons.append(f"Underperforming SPY by {abs(rs):.1%} (1-month) → relative weakness")
                    scores.append(rs_score)
                    weights.append(0.10)
        except Exception as e:
            logger.debug("Momentum SPY relative strength error: %s", e)

        if not scores:
            return AgentVote(
                agent_name="Momentum",
                score=0.0,
                confidence=0.1,
                signal="HOLD",
                reasons=["Insufficient data for momentum"],
            )

        total_weight = sum(weights)
        final_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        final_score = float(max(-1.0, min(1.0, final_score)))
        confidence = min(0.90, len(scores) / 6.0 * 0.90)
        signal = ConsensusResult.score_to_signal(final_score)

        if not reasons:
            reasons.append("Neutral momentum signals")

        return AgentVote(
            agent_name="Momentum",
            score=final_score,
            confidence=confidence,
            signal=signal,
            reasons=reasons[:4],
        )

    except Exception as exc:
        logger.error("MomentumAgent error: %s", exc)
        return AgentVote(
            agent_name="Momentum",
            score=0.0,
            confidence=0.0,
            signal="HOLD",
            reasons=[f"Error: {str(exc)[:80]}"],
        )


def sentiment_agent(ticker: yf.Ticker, hist: pd.DataFrame) -> AgentVote:
    """
    Sentiment agent using yfinance ticker.news and keyword scoring.
    """
    BULLISH_KEYWORDS = {
        "beat", "beats", "growth", "record", "profit", "upgrade", "upgraded",
        "buy", "strong", "surge", "surges", "raised", "raise", "expansion",
        "exceeds", "exceed", "outperform", "outperforms", "positive", "gain",
        "gains", "rally", "rallies", "high", "boost", "boosted", "acquire",
        "acquisition", "partnership", "innovative", "breakthrough", "dividend",
    }
    BEARISH_KEYWORDS = {
        "miss", "misses", "loss", "losses", "cut", "cuts", "downgrade",
        "downgraded", "sell", "weak", "decline", "declines", "layoff", "layoffs",
        "lawsuit", "investigation", "concern", "concerns", "warning", "warn",
        "warns", "fell", "fall", "drop", "drops", "disappoint", "disappoints",
        "disappointing", "recall", "recalls", "fraud", "scandal", "risk",
    }

    try:
        news = []
        try:
            raw_news = ticker.news
            if raw_news:
                news = raw_news[:10]
        except Exception:
            pass

        if not news:
            return AgentVote(
                agent_name="Sentiment",
                score=0.0,
                confidence=0.3,
                signal="HOLD",
                reasons=["No recent news available → neutral sentiment"],
            )

        bull_count = 0
        bear_count = 0
        bull_headlines: List[str] = []
        bear_headlines: List[str] = []
        total_weight = 0.0
        weighted_score = 0.0

        now_ts = datetime.now(tz=timezone.utc).timestamp()

        for i, article in enumerate(news):
            # Extract headline
            title = ""
            if isinstance(article, dict):
                title = article.get("title", "") or article.get("headline", "")
                pub_ts = article.get("providerPublishTime", 0) or article.get("publishedAt", 0)
            else:
                title = getattr(article, "title", "") or getattr(article, "headline", "")
                pub_ts = getattr(article, "providerPublishTime", 0) or 0

            if not title:
                continue

            # Time decay: more recent = higher weight (exponential decay over 7 days)
            try:
                age_days = (now_ts - float(pub_ts)) / 86400
            except (TypeError, ValueError):
                age_days = i  # fallback: use position as proxy for age
            time_weight = max(0.1, 1.0 / (1.0 + age_days / 3.0))

            words = set(title.lower().split())
            bull_hits = len(words & BULLISH_KEYWORDS)
            bear_hits = len(words & BEARISH_KEYWORDS)

            if bull_hits > bear_hits:
                article_score = min(1.0, bull_hits * 0.4)
                bull_count += 1
                if len(bull_headlines) < 2:
                    bull_headlines.append(f"Bullish: {title[:80]}")
            elif bear_hits > bull_hits:
                article_score = -min(1.0, bear_hits * 0.4)
                bear_count += 1
                if len(bear_headlines) < 2:
                    bear_headlines.append(f"Bearish: {title[:80]}")
            else:
                article_score = 0.0

            weighted_score += article_score * time_weight
            total_weight += time_weight

        if total_weight == 0:
            final_score = 0.0
            confidence = 0.2
        else:
            final_score = float(max(-1.0, min(1.0, weighted_score / total_weight)))
            # Confidence based on news volume and conviction
            conviction = abs(bull_count - bear_count) / max(1, bull_count + bear_count)
            confidence = min(0.80, 0.3 + conviction * 0.5 + min(len(news), 5) * 0.05)

        signal = ConsensusResult.score_to_signal(final_score)
        reasons: List[str] = []

        if bull_count > 0:
            reasons.append(f"{bull_count} bullish headline(s) in recent news")
        if bear_count > 0:
            reasons.append(f"{bear_count} bearish headline(s) in recent news")
        reasons.extend(bull_headlines[:1])
        reasons.extend(bear_headlines[:1])

        if not reasons:
            reasons.append(f"Analyzed {len(news)} news articles → neutral")

        return AgentVote(
            agent_name="Sentiment",
            score=final_score,
            confidence=confidence,
            signal=signal,
            reasons=reasons[:4],
        )

    except Exception as exc:
        logger.error("SentimentAgent error: %s", exc)
        return AgentVote(
            agent_name="Sentiment",
            score=0.0,
            confidence=0.0,
            signal="HOLD",
            reasons=[f"Error: {str(exc)[:80]}"],
        )


# ---------------------------------------------------------------------------
# ConsensusEngine
# ---------------------------------------------------------------------------

class ConsensusEngine:
    AGENT_WEIGHTS = {
        "Technical": 0.35,
        "Fundamental": 0.25,
        "Momentum": 0.25,
        "Sentiment": 0.15,
    }

    def analyze(self, symbol: str) -> Optional[ConsensusResult]:
        """
        Run all 4 agents in parallel, compute weighted consensus, return ConsensusResult.
        Caches result to analysis_cache table in SQLite.
        """
        try:
            ticker, hist, info, news, spy = self._fetch_data(symbol)

            if hist.empty:
                logger.warning("No price data for %s", symbol)
                return None

            # Current price and change %
            try:
                hist_close = hist["Close"] if "Close" in hist.columns else hist["close"]
                price = float(hist_close.iloc[-1])
                change_pct = 0.0
                if len(hist_close) >= 2:
                    prev = float(hist_close.iloc[-2])
                    change_pct = (price - prev) / prev * 100 if prev else 0.0
            except Exception:
                price = 0.0
                change_pct = 0.0

            # Run agents in parallel
            votes: List[AgentVote] = []
            agent_fns = {
                "Technical": lambda: technical_agent(ticker, hist),
                "Fundamental": lambda: fundamental_agent(ticker, hist),
                "Momentum": lambda: momentum_agent(ticker, hist, spy),
                "Sentiment": lambda: sentiment_agent(ticker, hist),
            }

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(fn): name for name, fn in agent_fns.items()}
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        vote = future.result(timeout=30)
                        vote.weight = self.AGENT_WEIGHTS.get(vote.agent_name, 1.0)
                        votes.append(vote)
                    except Exception as exc:
                        logger.error("Agent %s failed: %s", name, exc)
                        # Add neutral fallback vote
                        votes.append(AgentVote(
                            agent_name=name,
                            score=0.0,
                            confidence=0.0,
                            signal="HOLD",
                            reasons=["Agent failed"],
                            weight=self.AGENT_WEIGHTS.get(name, 1.0),
                        ))

            consensus_score, recommendation, direction, confidence, agreement_pct = \
                self._compute_consensus(votes)

            # Classify bull vs bear agents
            bull_agents = [v.agent_name for v in votes if v.score >= 0.25]
            bear_agents = [v.agent_name for v in votes if v.score <= -0.25]

            # Build key reasons from aligned agents
            key_reasons: List[str] = []
            key_risks: List[str] = []

            is_bullish = consensus_score >= 0
            for vote in sorted(votes, key=lambda v: abs(v.score), reverse=True):
                if is_bullish and vote.score >= 0:
                    for r in vote.reasons:
                        if r not in key_reasons:
                            key_reasons.append(r)
                        if len(key_reasons) >= 3:
                            break
                elif not is_bullish and vote.score <= 0:
                    for r in vote.reasons:
                        if r not in key_reasons:
                            key_reasons.append(r)
                        if len(key_reasons) >= 3:
                            break

            for vote in sorted(votes, key=lambda v: abs(v.score), reverse=True):
                if is_bullish and vote.score < 0:
                    for r in vote.reasons:
                        if r not in key_risks:
                            key_risks.append(r)
                        if len(key_risks) >= 2:
                            break
                elif not is_bullish and vote.score > 0:
                    for r in vote.reasons:
                        if r not in key_risks:
                            key_risks.append(r)
                        if len(key_risks) >= 2:
                            break

            result = ConsensusResult(
                symbol=symbol,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                price=price,
                change_pct=round(change_pct, 4),
                votes=votes,
                consensus_score=round(consensus_score, 4),
                recommendation=recommendation,
                direction=direction,
                confidence=round(confidence, 4),
                agreement_pct=round(agreement_pct, 4),
                bull_agents=bull_agents,
                bear_agents=bear_agents,
                key_reasons=key_reasons[:3],
                key_risks=key_risks[:2],
            )

            self.save_to_cache(result)
            return result

        except Exception as exc:
            logger.error("ConsensusEngine.analyze(%s) error: %s", symbol, exc)
            return None

    def _fetch_data(self, symbol: str):
        """Download 6 months of daily data plus SPY for relative strength."""
        ticker = yf.Ticker(symbol)
        try:
            hist = ticker.history(period="6mo")
        except Exception as e:
            logger.warning("History fetch failed for %s: %s", symbol, e)
            hist = pd.DataFrame()

        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        try:
            raw_news = ticker.news
            news = raw_news[:10] if raw_news else []
        except Exception:
            news = []

        try:
            spy = yf.Ticker("SPY").history(period="3mo")
        except Exception:
            spy = pd.DataFrame()

        return ticker, hist, info, news, spy

    def _compute_consensus(self, votes: List[AgentVote]) -> Tuple[float, str, str, float, float]:
        """
        Compute weighted average consensus from agent votes.
        Returns: (consensus_score, recommendation, direction, confidence, agreement_pct)
        """
        if not votes:
            return 0.0, "HOLD", "LONG", 0.0, 0.0

        total_weight = sum(v.weight for v in votes)
        if total_weight == 0:
            return 0.0, "HOLD", "LONG", 0.0, 0.0

        # Weighted score
        weighted_score = sum(v.score * v.weight for v in votes) / total_weight
        weighted_score = float(max(-1.0, min(1.0, weighted_score)))

        recommendation = ConsensusResult.score_to_signal(weighted_score)
        direction = "LONG" if weighted_score >= 0 else "SHORT"

        # Confidence: weighted average of individual confidence values
        confidence = sum(v.confidence * v.weight for v in votes) / total_weight
        confidence = float(max(0.0, min(1.0, confidence)))

        # Agreement: fraction of agents whose signal matches the consensus direction
        if weighted_score >= 0.25:
            agreeing = sum(1 for v in votes if v.score >= 0.25)
        elif weighted_score <= -0.25:
            agreeing = sum(1 for v in votes if v.score <= -0.25)
        else:
            # HOLD: agents near neutral agree
            agreeing = sum(1 for v in votes if abs(v.score) < 0.25)
        agreement_pct = agreeing / len(votes) * 100 if votes else 0.0

        return weighted_score, recommendation, direction, confidence, agreement_pct

    def save_to_cache(self, result: ConsensusResult) -> None:
        """Persist the latest analysis result to the analysis_cache SQLite table."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    symbol TEXT PRIMARY KEY,
                    analyzed_at TEXT,
                    price REAL,
                    change_pct REAL,
                    consensus_score REAL,
                    recommendation TEXT,
                    direction TEXT,
                    confidence REAL,
                    agreement_pct REAL,
                    details_json TEXT
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO analysis_cache
                    (symbol, analyzed_at, price, change_pct, consensus_score,
                     recommendation, direction, confidence, agreement_pct, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.symbol,
                result.timestamp,
                result.price,
                result.change_pct,
                result.consensus_score,
                result.recommendation,
                result.direction,
                result.confidence,
                result.agreement_pct,
                json.dumps(result.to_dict()),
            ))
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("save_to_cache error for %s: %s", result.symbol, exc)
