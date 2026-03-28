"""
analysis/sentiment.py
---------------------
Financial news sentiment analysis using ProsusAI/finbert.
Falls back to TextBlob when transformers is not available.

FinBERT outputs three labels: positive, negative, neutral.
We map these to a scalar in [-1, +1] and take a weighted average
across articles.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    Scores financial news text using ProsusAI/finbert.

    The model is loaded lazily on first use and cached for subsequent
    calls.  When ``transformers`` is not installed the class falls back
    to TextBlob polarity scoring.

    Parameters
    ----------
    model_name : str
        HuggingFace model identifier.  Defaults to ``"ProsusAI/finbert"``.
    batch_size : int
        Number of texts processed in a single inference batch.
    """

    # Label-to-score mapping for FinBERT output
    _LABEL_SCORES = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}

    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        batch_size: int = 8,
    ):
        self._model_name = model_name
        self._batch_size = batch_size
        self._pipeline = None  # Lazy-loaded
        self._use_transformers = False
        self._use_textblob = False
        self._transformers_checked = False

    # ------------------------------------------------------------------
    # Lazy model initialisation
    # ------------------------------------------------------------------

    def _ensure_model_loaded(self) -> None:
        """Load FinBERT pipeline on first use; fall back to TextBlob."""
        if self._transformers_checked:
            return

        self._transformers_checked = True

        try:
            from transformers import pipeline  # type: ignore

            logger.info("Loading FinBERT model '%s' …", self._model_name)
            self._pipeline = pipeline(
                "text-classification",
                model=self._model_name,
                tokenizer=self._model_name,
                return_all_scores=True,
                truncation=True,
                max_length=512,
            )
            self._use_transformers = True
            logger.info("FinBERT loaded successfully.")
        except ImportError:
            logger.warning(
                "transformers not installed — falling back to TextBlob sentiment."
            )
            self._try_load_textblob()
        except Exception as exc:
            logger.error(
                "Failed to load FinBERT ('%s'): %s — falling back to TextBlob.",
                self._model_name,
                exc,
            )
            self._try_load_textblob()

    def _try_load_textblob(self) -> None:
        """Attempt to import TextBlob as fallback."""
        try:
            from textblob import TextBlob  # type: ignore  # noqa: F401

            self._use_textblob = True
            logger.info("TextBlob fallback loaded.")
        except ImportError:
            logger.warning("Neither transformers nor TextBlob available; sentiment will be 0.0.")

    # ------------------------------------------------------------------
    # Core scoring methods
    # ------------------------------------------------------------------

    def analyze(self, texts: list[str]) -> float:
        """
        Score a list of texts and return a single weighted-average sentiment.

        Parameters
        ----------
        texts : list[str]
            Raw text strings (headlines, descriptions, etc.).

        Returns
        -------
        float
            Aggregated sentiment score in ``[-1.0, +1.0]``.
            Empty input returns ``0.0``.
        """
        self._ensure_model_loaded()

        if not texts:
            return 0.0

        cleaned = [t.strip() for t in texts if t and t.strip()]
        if not cleaned:
            return 0.0

        if self._use_transformers:
            return self._score_with_finbert(cleaned)
        elif self._use_textblob:
            return self._score_with_textblob(cleaned)
        else:
            return 0.0

    def get_symbol_sentiment(self, symbol: str, news_items: list[dict]) -> float:
        """
        Derive a sentiment score for a symbol from its news items.

        Parameters
        ----------
        symbol : str
            Ticker symbol (used only for logging).
        news_items : list[dict]
            Articles as returned by :class:`~data.news_fetcher.NewsFetcher`.
            Each dict should have ``title`` and/or ``description`` keys.

        Returns
        -------
        float
            Sentiment score in ``[-1.0, +1.0]``.
        """
        if not news_items:
            logger.debug("No news items for %s; sentiment = 0.0", symbol)
            return 0.0

        texts = self._extract_texts(news_items)
        score = self.analyze(texts)
        logger.debug("Sentiment for %s: %.3f (%d articles)", symbol, score, len(texts))
        return score

    def get_market_sentiment(self, market_news: list[dict]) -> float:
        """
        Compute overall market sentiment from general market news.

        Parameters
        ----------
        market_news : list[dict]
            News articles from :meth:`~data.news_fetcher.NewsFetcher.fetch_market_news`.

        Returns
        -------
        float
            Market-wide sentiment score in ``[-1.0, +1.0]``.
        """
        if not market_news:
            return 0.0
        texts = self._extract_texts(market_news)
        return self.analyze(texts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_texts(self, news_items: list[dict]) -> list[str]:
        """Concatenate title + description for each article."""
        texts = []
        for item in news_items:
            parts = []
            if item.get("title"):
                parts.append(item["title"])
            if item.get("description"):
                parts.append(item["description"])
            if parts:
                texts.append(" ".join(parts))
        return texts

    def _score_with_finbert(self, texts: list[str]) -> float:
        """Run FinBERT inference in batches and average the scores."""
        all_scores = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i: i + self._batch_size]
            # Truncate each text to avoid token limit issues
            batch = [t[:1000] for t in batch]
            try:
                results = self._pipeline(batch)
                for result in results:
                    score = self._parse_finbert_result(result)
                    all_scores.append(score)
            except Exception as exc:
                logger.warning("FinBERT inference error on batch: %s", exc)
                # Fall back to 0 for failed batch items
                all_scores.extend([0.0] * len(batch))

        if not all_scores:
            return 0.0

        # Weighted average — weight more-confident predictions higher
        weights = [abs(s) + 0.1 for s in all_scores]  # avoid 0-weight
        weighted_sum = sum(s * w for s, w in zip(all_scores, weights))
        total_weight = sum(weights)
        return float(np.clip(weighted_sum / total_weight, -1.0, 1.0))

    def _parse_finbert_result(self, result) -> float:
        """
        Convert FinBERT result (list of label/score dicts) to scalar.

        Parameters
        ----------
        result : list[dict] | dict
            Output from the ``text-classification`` pipeline with
            ``return_all_scores=True``.

        Returns
        -------
        float
            Signed sentiment value in ``[-1.0, +1.0]``.
        """
        try:
            if isinstance(result, list):
                # Format: [{'label': 'positive', 'score': 0.9}, ...]
                label_scores = {
                    item["label"].lower(): item["score"] for item in result
                }
            elif isinstance(result, dict):
                label_scores = {result["label"].lower(): result["score"]}
            else:
                return 0.0

            pos = label_scores.get("positive", 0.0)
            neg = label_scores.get("negative", 0.0)
            neu = label_scores.get("neutral", 0.0)

            # Net sentiment: positive minus negative, scaled by confidence
            net = pos - neg
            # Dampen by neutral weight (high neutral = less conviction)
            confidence = 1.0 - neu * 0.5
            return float(np.clip(net * confidence, -1.0, 1.0))

        except Exception as exc:
            logger.debug("_parse_finbert_result error: %s", exc)
            return 0.0

    def _score_with_textblob(self, texts: list[str]) -> float:
        """Use TextBlob polarity as a fallback scorer."""
        try:
            from textblob import TextBlob  # type: ignore

            scores = []
            for text in texts:
                blob = TextBlob(text)
                # polarity is in [-1, 1]
                scores.append(blob.sentiment.polarity)
            if not scores:
                return 0.0
            return float(np.clip(np.mean(scores), -1.0, 1.0))
        except Exception as exc:
            logger.error("TextBlob scoring error: %s", exc)
            return 0.0

    def is_ready(self) -> bool:
        """Return True if any sentiment backend is available."""
        self._ensure_model_loaded()
        return self._use_transformers or self._use_textblob
