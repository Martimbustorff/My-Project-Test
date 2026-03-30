"""
api/main.py
-----------
FastAPI REST API that exposes the trading bot's data and controls
to the mobile app. Reads from the SQLite database written by the bot.

Run with:
    cd trading_bot
    uvicorn api.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import auth, portfolio, signals, trades, bot, backtest
from api.database import init_db

app = FastAPI(title="Trading Bot API", version="1.0.0")

@app.on_event("startup")
def startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["auth"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(signals.router,   prefix="/api/signals",   tags=["signals"])
app.include_router(trades.router,    prefix="/api/trades",    tags=["trades"])
app.include_router(bot.router,       prefix="/api/bot",       tags=["bot"])
app.include_router(backtest.router,  prefix="/api/backtest",  tags=["backtest"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
