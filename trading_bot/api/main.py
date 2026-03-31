"""
api/main.py
-----------
FastAPI REST API that exposes the trading bot's data and controls
to the mobile app. Reads from the SQLite database written by the bot.

Run with:
    cd trading_bot
    uvicorn api.main:app --reload --port 8000
"""
# Load .env file if present (keys: ANTHROPIC_API_KEY, FINNHUB_API_KEY, FRED_API_KEY)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import auth, portfolio, signals, trades, bot, backtest
from api.routes import portfolio_positions, watchlist, scanner, analysis_route, insights
from api.routes import research
from api.database import init_db

app = FastAPI(title="Trading Bot API", version="1.0.0")

@app.on_event("startup")
def startup():
    init_db()
    # Kick off initial market scan in background (non-blocking)
    import threading
    def _initial_scan():
        try:
            from analysis.market_scanner import MarketScanner
            MarketScanner().run_scan()
        except Exception as e:
            print(f"Initial scan failed: {e}")
    threading.Thread(target=_initial_scan, daemon=True).start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,               prefix="/api/auth",      tags=["auth"])
app.include_router(portfolio.router,          prefix="/api/portfolio", tags=["portfolio"])
app.include_router(signals.router,            prefix="/api/signals",   tags=["signals"])
app.include_router(trades.router,             prefix="/api/trades",    tags=["trades"])
app.include_router(bot.router,                prefix="/api/bot",       tags=["bot"])
app.include_router(backtest.router,           prefix="/api/backtest",  tags=["backtest"])
app.include_router(portfolio_positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(watchlist.router,          prefix="/api/watchlist", tags=["watchlist"])
app.include_router(scanner.router,            prefix="/api/scanner",   tags=["scanner"])
app.include_router(analysis_route.router,     prefix="/api/analysis",  tags=["analysis"])
app.include_router(insights.router,           prefix="/api/insights",  tags=["insights"])
app.include_router(research.router,           prefix="/api/research",  tags=["research"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
