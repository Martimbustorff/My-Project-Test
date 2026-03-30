"""Analysis endpoints — run ConsensusEngine on a symbol."""
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from api.database import get_db

router = APIRouter()

_CACHE_TTL_MINUTES = 30


def _is_cache_fresh(analyzed_at: str) -> bool:
    """Return True if analyzed_at is within the last 30 minutes."""
    try:
        ts = datetime.fromisoformat(analyzed_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - ts < timedelta(minutes=_CACHE_TTL_MINUTES)
    except Exception:
        return False


def _cache_result(symbol: str, result: dict):
    """Write analysis result to analysis_cache."""
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analysis_cache
                   (symbol, analyzed_at, price, change_pct, consensus_score,
                    recommendation, direction, confidence, agreement_pct, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol,
                    datetime.now(timezone.utc).isoformat(),
                    result.get("price"),
                    result.get("change_pct"),
                    result.get("consensus_score"),
                    result.get("recommendation"),
                    result.get("direction"),
                    result.get("confidence"),
                    result.get("agreement_pct"),
                    json.dumps(result),
                )
            )
            conn.commit()
    except Exception as e:
        print(f"Failed to cache analysis for {symbol}: {e}")


@router.get("/{symbol}")
def analyze_symbol(symbol: str):
    """Run ConsensusEngine on a symbol, with 30-minute cache."""
    symbol = symbol.upper()

    # Check cache first
    try:
        with get_db() as conn:
            cached = conn.execute(
                "SELECT * FROM analysis_cache WHERE symbol = ?", (symbol,)
            ).fetchone()
        if cached:
            cached = dict(cached)
            if _is_cache_fresh(cached.get("analyzed_at", "")):
                try:
                    details = json.loads(cached.get("details_json") or "{}")
                    details["cached"] = True
                    details["analyzed_at"] = cached["analyzed_at"]
                    return details
                except Exception:
                    pass
    except Exception:
        pass

    # Run fresh analysis
    try:
        from analysis.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        result = engine.analyze(symbol)
        if hasattr(result, "__dict__"):
            result_dict = result.__dict__
        elif hasattr(result, "_asdict"):
            result_dict = result._asdict()
        else:
            result_dict = dict(result)

        result_dict["symbol"] = symbol
        result_dict["cached"] = False
        _cache_result(symbol, result_dict)
        return result_dict

    except ImportError:
        # consensus_engine not yet available — return cached data or mock
        if cached:
            try:
                details = json.loads(cached.get("details_json") or "{}")
                details["cached"] = True
                details["stale"] = True
                return details
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Analysis engine not available. Try again later."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
