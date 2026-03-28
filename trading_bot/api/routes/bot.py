"""Bot control endpoints — start, stop, status."""
import os
import signal
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth_utils import get_current_user

router = APIRouter()

# Simple in-process state tracking
_bot_process: subprocess.Popen | None = None
_bot_mode: str = "paper"

class BotStartRequest(BaseModel):
    mode: str = "paper"   # "paper" | "live"

@router.get("/status")
def bot_status(user=Depends(get_current_user)):
    global _bot_process
    running = _bot_process is not None and _bot_process.poll() is None
    return {
        "running": running,
        "mode": _bot_mode if running else None,
        "pid": _bot_process.pid if running else None,
    }

@router.post("/start")
def start_bot(req: BotStartRequest, user=Depends(get_current_user)):
    global _bot_process, _bot_mode
    if _bot_process and _bot_process.poll() is None:
        return {"success": False, "message": "Bot is already running"}

    bot_dir  = Path(__file__).parent.parent.parent  # trading_bot/
    main_py  = bot_dir / "main.py"
    flag     = "--live" if req.mode == "live" else "--paper"

    _bot_process = subprocess.Popen(
        [sys.executable, str(main_py), flag, "--no-dash"],
        cwd=str(bot_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _bot_mode = req.mode
    return {"success": True, "message": f"Bot started in {req.mode} mode", "pid": _bot_process.pid}

@router.post("/stop")
def stop_bot(user=Depends(get_current_user)):
    global _bot_process
    if not _bot_process or _bot_process.poll() is not None:
        return {"success": False, "message": "Bot is not running"}
    _bot_process.terminate()
    try:
        _bot_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _bot_process.kill()
    _bot_process = None
    return {"success": True, "message": "Bot stopped"}
