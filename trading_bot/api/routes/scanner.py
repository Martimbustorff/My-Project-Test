"""Market scanner endpoints."""
import json
import threading
from fastapi import APIRouter
from api.database import get_db

router = APIRouter()

# In-process scan state
_scan_state = {
    "scanning": False,
    "progress": 0,
    "total": 0,
    "last_scan": None,
}
_scan_lock = threading.Lock()


def _run_scan():
    global _scan_state
    with _scan_lock:
        _scan_state["scanning"] = True
        _scan_state["progress"] = 0

    try:
        from analysis.market_scanner import MarketScanner
        scanner = MarketScanner()
        results = scanner.run_scan()

        top_longs = []
        top_shorts = []
        symbols_scanned = 0

        if results:
            top_longs = results.get("top_longs", [])
            top_shorts = results.get("top_shorts", [])
            symbols_scanned = results.get("symbols_scanned", 0)

        with get_db() as conn:
            conn.execute(
                """INSERT INTO scanner_results (top_longs_json, top_shorts_json, symbols_scanned)
                   VALUES (?, ?, ?)""",
                (json.dumps(top_longs), json.dumps(top_shorts), symbols_scanned)
            )
            conn.commit()
            row = conn.execute(
                "SELECT scanned_at FROM scanner_results ORDER BY id DESC LIMIT 1"
            ).fetchone()
            last_scan = row["scanned_at"] if row else None

    except ImportError:
        # market_scanner not yet available — write mock data
        mock_longs = [
            {"symbol": "AAPL", "score": 0.8, "recommendation": "BUY"},
            {"symbol": "MSFT", "score": 0.75, "recommendation": "BUY"},
        ]
        mock_shorts = [
            {"symbol": "META", "score": -0.6, "recommendation": "SHORT"},
        ]
        with get_db() as conn:
            conn.execute(
                """INSERT INTO scanner_results (top_longs_json, top_shorts_json, symbols_scanned)
                   VALUES (?, ?, ?)""",
                (json.dumps(mock_longs), json.dumps(mock_shorts), 0)
            )
            conn.commit()
            row = conn.execute(
                "SELECT scanned_at FROM scanner_results ORDER BY id DESC LIMIT 1"
            ).fetchone()
            last_scan = row["scanned_at"] if row else None

    except Exception as e:
        print(f"Scan error: {e}")
        last_scan = None

    with _scan_lock:
        _scan_state["scanning"] = False
        _scan_state["progress"] = _scan_state["total"]
        if last_scan:
            _scan_state["last_scan"] = last_scan


@router.get("/results")
def latest_results():
    """Return the latest scanner results row."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM scanner_results ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return {
            "last_scan": None,
            "top_longs": [],
            "top_shorts": [],
            "status": "no_data",
            "scanning": _scan_state["scanning"],
            "progress": _scan_state["progress"],
            "total": _scan_state["total"],
        }

    r = dict(row)
    try:
        top_longs = json.loads(r.get("top_longs_json") or "[]")
    except Exception:
        top_longs = []
    try:
        top_shorts = json.loads(r.get("top_shorts_json") or "[]")
    except Exception:
        top_shorts = []

    return {
        "last_scan": r.get("scanned_at"),
        "top_longs": top_longs,
        "top_shorts": top_shorts,
        "symbols_scanned": r.get("symbols_scanned", 0),
        "status": "ok",
        "scanning": _scan_state["scanning"],
        "progress": _scan_state["progress"],
        "total": _scan_state["total"],
    }


@router.post("/run")
def trigger_scan():
    """Start a background market scan. Returns current status if already scanning."""
    with _scan_lock:
        if _scan_state["scanning"]:
            return {
                "message": "Scan already in progress",
                "scanning": True,
                "progress": _scan_state["progress"],
                "total": _scan_state["total"],
            }

    thread = threading.Thread(target=_run_scan, daemon=True)
    thread.start()
    return {"message": "Scan started"}


@router.get("/status")
def scan_status():
    """Return current scan status."""
    with _scan_lock:
        last_scan = _scan_state.get("last_scan")

    if not last_scan:
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT scanned_at FROM scanner_results ORDER BY id DESC LIMIT 1"
                ).fetchone()
            last_scan = row["scanned_at"] if row else None
        except Exception:
            last_scan = None

    return {
        "scanning": _scan_state["scanning"],
        "progress": _scan_state["progress"],
        "total": _scan_state["total"],
        "last_scan": last_scan,
    }
