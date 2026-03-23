"""
config/settings.py
------------------
Central configuration module. Loads all settings from environment variables
via python-dotenv. Provides a singleton Settings object used throughout the bot.
"""

import os
import logging
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    """
    All application settings loaded from environment variables.
    Provides defaults for optional parameters.
    """

    # ---------------------------------------------------------------------------
    # Alpaca credentials
    # ---------------------------------------------------------------------------
    ALPACA_API_KEY: str = os.environ.get("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.environ.get("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.environ.get(
        "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
    )

    # Derived flag: paper trading when base URL contains "paper"
    IS_PAPER_TRADING: bool = "paper" in ALPACA_BASE_URL.lower()

    # ---------------------------------------------------------------------------
    # News API
    # ---------------------------------------------------------------------------
    NEWS_API_KEY: str = os.environ.get("NEWS_API_KEY", "")

    # ---------------------------------------------------------------------------
    # General trading mode
    # ---------------------------------------------------------------------------
    TRADING_MODE: str = os.environ.get("TRADING_MODE", "paper")  # "paper" or "live"

    # ---------------------------------------------------------------------------
    # Logging
    # ---------------------------------------------------------------------------
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    # ---------------------------------------------------------------------------
    # Trading universe — S&P 500 top 50 most liquid stocks
    # ---------------------------------------------------------------------------
    TRADING_UNIVERSE: list = [
        "AAPL",   # Apple
        "MSFT",   # Microsoft
        "GOOGL",  # Alphabet
        "AMZN",   # Amazon
        "NVDA",   # NVIDIA
        "META",   # Meta Platforms
        "TSLA",   # Tesla
        "BRK-B",  # Berkshire Hathaway B
        "JPM",    # JPMorgan Chase
        "V",      # Visa
        "UNH",    # UnitedHealth
        "JNJ",    # Johnson & Johnson
        "XOM",    # Exxon Mobil
        "WMT",    # Walmart
        "MA",     # Mastercard
        "PG",     # Procter & Gamble
        "HD",     # Home Depot
        "CVX",    # Chevron
        "LLY",    # Eli Lilly
        "MRK",    # Merck
        "ABBV",   # AbbVie
        "PFE",    # Pfizer
        "AVGO",   # Broadcom
        "COST",   # Costco
        "KO",     # Coca-Cola
        "PEP",    # PepsiCo
        "TMO",    # Thermo Fisher
        "CSCO",   # Cisco
        "ACN",    # Accenture
        "MCD",    # McDonald's
        "ABT",    # Abbott Laboratories
        "DHR",    # Danaher
        "TXN",    # Texas Instruments
        "NEE",    # NextEra Energy
        "WFC",    # Wells Fargo
        "BMY",    # Bristol-Myers Squibb
        "CRM",    # Salesforce
        "QCOM",   # Qualcomm
        "ORCL",   # Oracle
        "AMD",    # Advanced Micro Devices
        "INTC",   # Intel
        "HON",    # Honeywell
        "UPS",    # United Parcel Service
        "CAT",    # Caterpillar
        "BA",     # Boeing
        "GS",     # Goldman Sachs
        "MS",     # Morgan Stanley
        "AMGN",   # Amgen
        "INTU",   # Intuit
        "SBUX",   # Starbucks
    ]

    # ---------------------------------------------------------------------------
    # Risk parameters
    # ---------------------------------------------------------------------------
    MAX_POSITION_SIZE: float = float(os.environ.get("MAX_POSITION_SIZE", "0.05"))
    """Maximum fraction of portfolio allocated to a single position (5%)."""

    MAX_PORTFOLIO_HEAT: float = float(os.environ.get("MAX_PORTFOLIO_HEAT", "0.20"))
    """Maximum total risk exposure across all positions (20%)."""

    STOP_LOSS_PCT: float = float(os.environ.get("STOP_LOSS_PCT", "0.05"))
    """Default stop-loss distance from entry as a fraction (5%)."""

    TAKE_PROFIT_PCT: float = float(os.environ.get("TAKE_PROFIT_PCT", "0.15"))
    """Default take-profit distance from entry as a fraction (15%)."""

    MAX_DAILY_DRAWDOWN: float = float(os.environ.get("MAX_DAILY_DRAWDOWN", "0.03"))
    """Maximum allowed daily portfolio drawdown before halting trading (3%)."""

    MAX_SHORT_POSITIONS: int = int(os.environ.get("MAX_SHORT_POSITIONS", "5"))
    """Maximum concurrent short positions allowed."""

    RISK_PER_TRADE: float = float(os.environ.get("RISK_PER_TRADE", "0.01"))
    """Fraction of portfolio risked per individual trade for position sizing (1%)."""

    # ---------------------------------------------------------------------------
    # Signal combination weights (must sum to ~1.0)
    # ---------------------------------------------------------------------------
    TECHNICAL_WEIGHT: float = float(os.environ.get("TECHNICAL_WEIGHT", "0.35"))
    SENTIMENT_WEIGHT: float = float(os.environ.get("SENTIMENT_WEIGHT", "0.30"))
    MOMENTUM_WEIGHT: float = float(os.environ.get("MOMENTUM_WEIGHT", "0.20"))
    FUNDAMENTAL_WEIGHT: float = float(os.environ.get("FUNDAMENTAL_WEIGHT", "0.15"))

    # ---------------------------------------------------------------------------
    # Signal thresholds
    # ---------------------------------------------------------------------------
    BUY_THRESHOLD: float = float(os.environ.get("BUY_THRESHOLD", "0.35"))
    SELL_THRESHOLD: float = float(os.environ.get("SELL_THRESHOLD", "-0.20"))
    SHORT_THRESHOLD: float = float(os.environ.get("SHORT_THRESHOLD", "-0.35"))
    COVER_THRESHOLD: float = float(os.environ.get("COVER_THRESHOLD", "0.20"))
    VIX_MAX: float = float(os.environ.get("VIX_MAX", "40.0"))
    """VIX level above which we stop opening new positions."""

    # ---------------------------------------------------------------------------
    # Scheduling
    # ---------------------------------------------------------------------------
    SIGNAL_SCAN_INTERVAL_MINUTES: int = int(
        os.environ.get("SIGNAL_SCAN_INTERVAL_MINUTES", "1")
    )
    PORTFOLIO_REFRESH_INTERVAL_MINUTES: int = int(
        os.environ.get("PORTFOLIO_REFRESH_INTERVAL_MINUTES", "5")
    )
    NEWS_REFRESH_INTERVAL_MINUTES: int = int(
        os.environ.get("NEWS_REFRESH_INTERVAL_MINUTES", "60")
    )

    # ---------------------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------------------
    DB_PATH: str = os.environ.get("DB_PATH", "trading_bot.db")

    # ---------------------------------------------------------------------------
    # Data settings
    # ---------------------------------------------------------------------------
    BARS_LIMIT: int = int(os.environ.get("BARS_LIMIT", "200"))
    """Number of historical bars to fetch for TA computation."""

    NEWS_DAYS_BACK: int = int(os.environ.get("NEWS_DAYS_BACK", "2"))
    """How many calendar days back to fetch news articles."""

    MAX_NEWS_ARTICLES: int = int(os.environ.get("MAX_NEWS_ARTICLES", "10"))
    """Max news articles to process per symbol per cycle."""

    # ---------------------------------------------------------------------------
    # Market timing
    # ---------------------------------------------------------------------------
    MARKET_OPEN_BUFFER_MINUTES: int = 30
    """Minutes after market open / before market close to avoid trading."""

    # ---------------------------------------------------------------------------
    # FinBERT / model settings
    # ---------------------------------------------------------------------------
    FINBERT_MODEL: str = os.environ.get("FINBERT_MODEL", "ProsusAI/finbert")
    SENTIMENT_BATCH_SIZE: int = int(os.environ.get("SENTIMENT_BATCH_SIZE", "8"))

    # ---------------------------------------------------------------------------
    # Sector ETF mapping used for sector performance
    # ---------------------------------------------------------------------------
    SECTOR_ETFS: dict = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Real Estate": "XLRE",
        "Utilities": "XLU",
        "Communication Services": "XLC",
    }

    def validate(self) -> bool:
        """
        Validate that required credentials are present.

        Returns
        -------
        bool
            True if all required settings are set, False otherwise.
        """
        missing = []
        if not self.ALPACA_API_KEY:
            missing.append("ALPACA_API_KEY")
        if not self.ALPACA_SECRET_KEY:
            missing.append("ALPACA_SECRET_KEY")
        if not self.NEWS_API_KEY:
            missing.append("NEWS_API_KEY (optional but recommended)")

        if missing:
            logger.warning("Missing environment variables: %s", ", ".join(missing))
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"Settings(mode={self.TRADING_MODE}, paper={self.IS_PAPER_TRADING}, "
            f"universe_size={len(self.TRADING_UNIVERSE)})"
        )


# Module-level singleton instance
settings = Settings()
