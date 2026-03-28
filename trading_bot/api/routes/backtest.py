"""Backtest endpoints — run and retrieve results."""
import json
import threading
import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.database import get_db, init_users_table
from api.auth_utils import get_current_user

router = APIRouter()

# In-memory job store (good enough for single-user deployment)
_jobs: dict[str, dict] = {}

def _init_backtest_table():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id           TEXT PRIMARY KEY,
                symbols      TEXT,
                start_date   TEXT,
                end_date     TEXT,
                total_return REAL,
                ann_return   REAL,
                sharpe       REAL,
                max_drawdown REAL,
                win_rate     REAL,
                profit_factor REAL,
                total_trades INTEGER,
                long_trades  INTEGER,
                short_trades INTEGER,
                created_at   TEXT DEFAULT (datetime('now')),
                status       TEXT DEFAULT 'running'
            )
        """)
        conn.commit()

_init_backtest_table()

class BacktestRequest(BaseModel):
    symbols: list[str]
    start_date: str   # "YYYY-MM-DD"
    end_date: str
    initial_capital: float = 100_000.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15

def _run_backtest_job(job_id: str, req: BacktestRequest):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

    try:
        from backtesting.backtest import Backtester, BacktestConfig
        cfg = BacktestConfig(
            symbols=req.symbols,
            start_date=date.fromisoformat(req.start_date),
            end_date=date.fromisoformat(req.end_date),
            initial_capital=req.initial_capital,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_pct=req.take_profit_pct,
        )
        bt = Backtester(cfg)
        results = bt.run()

        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO backtest_results
                (id, symbols, start_date, end_date, total_return, ann_return,
                 sharpe, max_drawdown, win_rate, profit_factor, total_trades,
                 long_trades, short_trades, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'completed')
            """, (
                job_id,
                json.dumps(req.symbols),
                req.start_date, req.end_date,
                results.total_return(),
                results.annualised_return(),
                results.sharpe_ratio(),
                results.max_drawdown(),
                results.win_rate(),
                results.profit_factor(),
                results.total_trades(),
                results.long_trades(),
                results.short_trades(),
            ))
            conn.commit()
        _jobs[job_id]["status"] = "completed"
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        with get_db() as conn:
            conn.execute(
                "UPDATE backtest_results SET status='failed' WHERE id=?", (job_id,)
            )
            conn.commit()

@router.post("/run")
def run_backtest(req: BacktestRequest, user=Depends(get_current_user)):
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "running"}

    with get_db() as conn:
        conn.execute(
            "INSERT INTO backtest_results (id, symbols, start_date, end_date, status) VALUES (?,?,?,?,'running')",
            (job_id, json.dumps(req.symbols), req.start_date, req.end_date)
        )
        conn.commit()

    thread = threading.Thread(target=_run_backtest_job, args=(job_id, req), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "running"}

@router.get("/status/{job_id}")
def backtest_job_status(job_id: str, user=Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/results")
def backtest_results(user=Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM backtest_results WHERE status='completed' ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]

@router.get("/results/{job_id}")
def backtest_result(job_id: str, user=Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM backtest_results WHERE id=?", (job_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")
    r = dict(row)
    try:
        r["symbols"] = json.loads(r["symbols"])
    except Exception:
        pass
    return r
