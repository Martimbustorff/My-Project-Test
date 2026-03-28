"""
analysis/technical.py
---------------------
Computes technical analysis indicators using pandas-ta and derives a
scalar technical signal score in [-1, +1].

All indicator logic is deterministic given the same OHLCV input.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Computes a comprehensive set of technical indicators and converts
    them into an actionable signal score.

    Uses pandas-ta for all indicator calculations; falls back to manual
    numpy implementations when pandas-ta is not available.
    """

    def __init__(self):
        self._pandas_ta_available = False
        try:
            import pandas_ta as ta  # type: ignore
            self._pandas_ta_available = True
            logger.debug("pandas-ta loaded successfully.")
        except ImportError:
            logger.warning("pandas-ta not installed; using manual indicator fallbacks.")

    # ------------------------------------------------------------------
    # Primary public method
    # ------------------------------------------------------------------

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicator columns to *df* in-place and return it.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame with columns ``open, high, low, close, volume``
            (case-insensitive).  Must have at least 50 rows for full
            indicator coverage.

        Returns
        -------
        pd.DataFrame
            Original DataFrame with additional columns:
            ``rsi, macd, macd_signal, macd_hist,
              bb_upper, bb_lower, bb_mid,
              ema_20, ema_50,
              atr, vwap,
              obv, stoch_k, stoch_d``.
        """
        if df.empty or len(df) < 10:
            logger.warning("compute_indicators: DataFrame too short (%d rows).", len(df))
            return df

        # Normalise column names
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        # Ensure required columns
        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                logger.error("Missing required column: %s", col)
                return df

        # Convert to float64 to avoid integer arithmetic issues
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)

        if self._pandas_ta_available:
            df = self._compute_with_pandas_ta(df)
        else:
            df = self._compute_manual(df)

        return df

    # ------------------------------------------------------------------
    # Signal scoring
    # ------------------------------------------------------------------

    def get_technical_signal(self, df: pd.DataFrame) -> float:
        """
        Convert computed indicators to a scalar score in ``[-1.0, +1.0]``.

        A positive score means bullish pressure; negative means bearish.
        Requires that :meth:`compute_indicators` has been called on *df*.

        Scoring components (each ±1 contribution, weighted):
        - RSI: oversold (<30) = +1, overbought (>70) = -1
        - MACD: histogram positive = +0.5, MACD above signal = +0.5
        - Bollinger Bands: price near lower = +1, near upper = -1
        - EMA cross: EMA20 > EMA50 = +1, else -1
        - Volume OBV trend: rising = +0.5, falling = -0.5
        - Stochastic: K<20 = +1, K>80 = -1

        Returns
        -------
        float
            Score in ``[-1.0, 1.0]``.
        """
        if df.empty:
            return 0.0

        try:
            last = df.iloc[-1]
            score = 0.0
            total_weight = 0.0

            # --- RSI (weight 0.25) ---
            rsi = last.get("rsi", np.nan)
            if pd.notna(rsi):
                if rsi < 30:
                    # Strongly oversold
                    rsi_score = min(1.0, (30 - rsi) / 20)
                elif rsi > 70:
                    # Strongly overbought
                    rsi_score = -min(1.0, (rsi - 70) / 20)
                elif rsi < 45:
                    rsi_score = 0.25
                elif rsi > 55:
                    rsi_score = -0.25
                else:
                    rsi_score = 0.0
                score += rsi_score * 0.25
                total_weight += 0.25

            # --- MACD (weight 0.25) ---
            macd = last.get("macd", np.nan)
            macd_signal = last.get("macd_signal", np.nan)
            macd_hist = last.get("macd_hist", np.nan)
            if pd.notna(macd) and pd.notna(macd_signal):
                macd_score = 0.0
                if pd.notna(macd_hist):
                    # Positive histogram = bullish momentum
                    macd_score += np.clip(macd_hist / (abs(macd) + 1e-9), -0.5, 0.5)
                if macd > macd_signal:
                    macd_score += 0.5
                else:
                    macd_score -= 0.5
                # Check for recent cross using previous bar
                if len(df) >= 2:
                    prev = df.iloc[-2]
                    prev_macd = prev.get("macd", np.nan)
                    prev_signal = prev.get("macd_signal", np.nan)
                    if pd.notna(prev_macd) and pd.notna(prev_signal):
                        # Bullish crossover
                        if prev_macd < prev_signal and macd > macd_signal:
                            macd_score = min(1.0, macd_score + 0.5)
                        # Bearish crossover
                        elif prev_macd > prev_signal and macd < macd_signal:
                            macd_score = max(-1.0, macd_score - 0.5)
                score += np.clip(macd_score, -1.0, 1.0) * 0.25
                total_weight += 0.25

            # --- Bollinger Bands (weight 0.20) ---
            bb_upper = last.get("bb_upper", np.nan)
            bb_lower = last.get("bb_lower", np.nan)
            bb_mid = last.get("bb_mid", np.nan)
            close = last.get("close", np.nan)
            if pd.notna(bb_upper) and pd.notna(bb_lower) and pd.notna(close):
                band_width = bb_upper - bb_lower
                if band_width > 0:
                    # Position within band: 0 = at lower, 1 = at upper
                    pos = (close - bb_lower) / band_width
                    if pos < 0.2:
                        bb_score = 0.8  # Near lower band = buy signal
                    elif pos > 0.8:
                        bb_score = -0.8  # Near upper band = sell signal
                    elif pos < 0.4:
                        bb_score = 0.3
                    elif pos > 0.6:
                        bb_score = -0.3
                    else:
                        bb_score = 0.0
                else:
                    bb_score = 0.0
                score += bb_score * 0.20
                total_weight += 0.20

            # --- EMA Cross (weight 0.20) ---
            ema20 = last.get("ema_20", np.nan)
            ema50 = last.get("ema_50", np.nan)
            if pd.notna(ema20) and pd.notna(ema50):
                if ema20 > ema50:
                    separation = (ema20 - ema50) / ema50
                    ema_score = min(1.0, separation * 20)  # Scaled
                else:
                    separation = (ema50 - ema20) / ema50
                    ema_score = -min(1.0, separation * 20)
                score += ema_score * 0.20
                total_weight += 0.20

            # --- Stochastic (weight 0.10) ---
            stoch_k = last.get("stoch_k", np.nan)
            if pd.notna(stoch_k):
                if stoch_k < 20:
                    stoch_score = min(1.0, (20 - stoch_k) / 15)
                elif stoch_k > 80:
                    stoch_score = -min(1.0, (stoch_k - 80) / 15)
                else:
                    stoch_score = 0.0
                score += stoch_score * 0.10
                total_weight += 0.10

            if total_weight == 0:
                return 0.0

            # Normalise by actual weight used
            normalised = score / total_weight
            return float(np.clip(normalised, -1.0, 1.0))

        except Exception as exc:
            logger.error("get_technical_signal error: %s", exc)
            return 0.0

    # ------------------------------------------------------------------
    # Pattern detection
    # ------------------------------------------------------------------

    def detect_pattern(self, df: pd.DataFrame) -> str:
        """
        Detect a single dominant candlestick pattern from the last 2–3 bars.

        Returns
        -------
        str
            One of: ``"bullish_engulfing"``, ``"bearish_engulfing"``,
            ``"doji"``, ``"hammer"``, ``"shooting_star"``,
            ``"morning_star"``, ``"evening_star"``, ``"none"``.
        """
        if df.empty or len(df) < 2:
            return "none"

        try:
            df = df.copy()
            df.columns = [c.lower() for c in df.columns]

            c = df["close"].values
            o = df["open"].values
            h = df["high"].values
            low = df["low"].values

            last_body = abs(c[-1] - o[-1])
            last_range = h[-1] - low[-1]
            prev_body = abs(c[-2] - o[-2])

            # Doji: body is < 10% of total range
            if last_range > 0 and last_body / last_range < 0.10:
                return "doji"

            # Hammer: small body at top, long lower shadow, bullish after downtrend
            lower_shadow = min(c[-1], o[-1]) - low[-1]
            upper_shadow = h[-1] - max(c[-1], o[-1])
            if (
                last_body > 0
                and lower_shadow >= 2 * last_body
                and upper_shadow <= last_body * 0.5
                and c[-2] < o[-2]  # Previous bar was bearish
            ):
                return "hammer"

            # Shooting star: small body at bottom, long upper shadow
            if (
                last_body > 0
                and upper_shadow >= 2 * last_body
                and lower_shadow <= last_body * 0.5
                and c[-2] > o[-2]  # Previous bar was bullish
            ):
                return "shooting_star"

            # Bullish engulfing: current bullish bar completely engulfs previous bearish bar
            if (
                c[-1] > o[-1]  # Current is bullish
                and c[-2] < o[-2]  # Previous is bearish
                and o[-1] <= c[-2]  # Open below previous close
                and c[-1] >= o[-2]  # Close above previous open
                and last_body > prev_body  # Must be larger
            ):
                return "bullish_engulfing"

            # Bearish engulfing: current bearish bar engulfs previous bullish bar
            if (
                c[-1] < o[-1]  # Current is bearish
                and c[-2] > o[-2]  # Previous is bullish
                and o[-1] >= c[-2]  # Open above previous close
                and c[-1] <= o[-2]  # Close below previous open
                and last_body > prev_body
            ):
                return "bearish_engulfing"

            # Morning star (3-bar: bearish, doji/small, bullish)
            if len(df) >= 3:
                prev2_body = abs(c[-3] - o[-3])
                if (
                    c[-3] < o[-3]  # First bar bearish
                    and abs(c[-2] - o[-2]) < prev2_body * 0.3  # Middle is small
                    and c[-1] > o[-1]  # Last is bullish
                    and c[-1] > (o[-3] + c[-3]) / 2  # Closes above midpoint
                ):
                    return "morning_star"

                # Evening star
                if (
                    c[-3] > o[-3]  # First bar bullish
                    and abs(c[-2] - o[-2]) < prev2_body * 0.3  # Middle is small
                    and c[-1] < o[-1]  # Last is bearish
                    and c[-1] < (o[-3] + c[-3]) / 2  # Closes below midpoint
                ):
                    return "evening_star"

            return "none"
        except Exception as exc:
            logger.error("detect_pattern error: %s", exc)
            return "none"

    # ------------------------------------------------------------------
    # pandas-ta implementation
    # ------------------------------------------------------------------

    def _compute_with_pandas_ta(self, df: pd.DataFrame) -> pd.DataFrame:
        """Use pandas-ta to compute all indicators."""
        import pandas_ta as ta  # type: ignore

        # RSI (14)
        try:
            rsi = ta.rsi(df["close"], length=14)
            df["rsi"] = rsi
        except Exception as exc:
            logger.warning("pandas-ta RSI error: %s", exc)
            df["rsi"] = np.nan

        # MACD (12, 26, 9)
        try:
            macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd_df is not None and not macd_df.empty:
                df["macd"] = macd_df.iloc[:, 0]
                df["macd_hist"] = macd_df.iloc[:, 1]
                df["macd_signal"] = macd_df.iloc[:, 2]
            else:
                df["macd"] = df["macd_hist"] = df["macd_signal"] = np.nan
        except Exception as exc:
            logger.warning("pandas-ta MACD error: %s", exc)
            df["macd"] = df["macd_hist"] = df["macd_signal"] = np.nan

        # Bollinger Bands (20, 2)
        try:
            bb = ta.bbands(df["close"], length=20, std=2)
            if bb is not None and not bb.empty:
                cols = list(bb.columns)
                # pandas-ta returns: BBL, BBM, BBU, BBB, BBP
                df["bb_lower"] = bb[cols[0]]
                df["bb_mid"] = bb[cols[1]]
                df["bb_upper"] = bb[cols[2]]
            else:
                df["bb_lower"] = df["bb_mid"] = df["bb_upper"] = np.nan
        except Exception as exc:
            logger.warning("pandas-ta BB error: %s", exc)
            df["bb_lower"] = df["bb_mid"] = df["bb_upper"] = np.nan

        # EMA 20 & 50
        try:
            df["ema_20"] = ta.ema(df["close"], length=20)
            df["ema_50"] = ta.ema(df["close"], length=50)
        except Exception as exc:
            logger.warning("pandas-ta EMA error: %s", exc)
            df["ema_20"] = df["ema_50"] = np.nan

        # ATR (14)
        try:
            df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        except Exception as exc:
            logger.warning("pandas-ta ATR error: %s", exc)
            df["atr"] = np.nan

        # VWAP (uses high, low, close, volume)
        try:
            vwap_series = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
            df["vwap"] = vwap_series
        except Exception as exc:
            logger.warning("pandas-ta VWAP error: %s", exc)
            # Manual VWAP fallback
            df["vwap"] = self._manual_vwap(df)

        # OBV
        try:
            df["obv"] = ta.obv(df["close"], df["volume"])
        except Exception as exc:
            logger.warning("pandas-ta OBV error: %s", exc)
            df["obv"] = np.nan

        # Stochastic (14, 3, 3)
        try:
            stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
            if stoch is not None and not stoch.empty:
                cols = list(stoch.columns)
                df["stoch_k"] = stoch[cols[0]]
                df["stoch_d"] = stoch[cols[1]]
            else:
                df["stoch_k"] = df["stoch_d"] = np.nan
        except Exception as exc:
            logger.warning("pandas-ta Stoch error: %s", exc)
            df["stoch_k"] = df["stoch_d"] = np.nan

        return df

    # ------------------------------------------------------------------
    # Manual fallback implementations
    # ------------------------------------------------------------------

    def _compute_manual(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pure numpy/pandas indicator implementations as fallback."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # RSI
        df["rsi"] = self._manual_rsi(close, 14)

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        df["macd"] = macd
        df["macd_signal"] = macd_signal
        df["macd_hist"] = macd - macd_signal

        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df["bb_mid"] = sma20
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_lower"] = sma20 - 2 * std20

        # EMA
        df["ema_20"] = close.ewm(span=20, adjust=False).mean()
        df["ema_50"] = close.ewm(span=50, adjust=False).mean()

        # ATR
        df["atr"] = self._manual_atr(high, low, close, 14)

        # VWAP
        df["vwap"] = self._manual_vwap(df)

        # OBV
        df["obv"] = self._manual_obv(close, volume)

        # Stochastic
        stoch_k, stoch_d = self._manual_stoch(high, low, close, 14, 3)
        df["stoch_k"] = stoch_k
        df["stoch_d"] = stoch_d

        return df

    def _manual_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - 100 / (1 + rs)

    def _manual_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(com=period - 1, adjust=False).mean()

    def _manual_vwap(self, df: pd.DataFrame) -> pd.Series:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        cum_tp_vol = (typical_price * df["volume"]).cumsum()
        cum_vol = df["volume"].cumsum()
        return cum_tp_vol / (cum_vol + 1e-10)

    def _manual_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        direction = np.sign(close.diff().fillna(0))
        return (direction * volume).cumsum()

    def _manual_stoch(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
        d = k.rolling(d_period).mean()
        return k, d
