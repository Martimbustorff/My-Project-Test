"""
execution/broker.py
-------------------
Thin wrapper around the Alpaca trading and data APIs.
Handles authentication, rate-limiting retry, and normalises responses
into plain Python dicts so the rest of the bot stays broker-agnostic.
"""
import logging
import time
from typing import Optional
from functools import wraps

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import pandas as pd

logger = logging.getLogger(__name__)


def _retry(max_attempts: int = 3, backoff: float = 2.0):
    """Decorator: retry on exception with exponential backoff."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff ** attempt
                    logger.warning(f"{fn.__name__} attempt {attempt+1} failed ({exc}); retrying in {wait}s")
                    time.sleep(wait)
        return wrapper
    return decorator


class AlpacaBroker:
    """
    Wraps Alpaca trading + market data clients.

    All methods return plain Python dicts/lists (no SDK objects) so the
    rest of the codebase is broker-agnostic.
    """

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        base_url = (
            "https://paper-api.alpaca.markets"
            if paper
            else "https://api.alpaca.markets"
        )
        self.paper = paper
        self._trading = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper,
        )
        self._data = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key,
        )
        logger.info(f"AlpacaBroker initialised (paper={paper})")

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    @_retry()
    def get_account(self) -> dict:
        """Return account information as a dict."""
        acct = self._trading.get_account()
        return {
            "id": str(acct.id),
            "equity": float(acct.equity),
            "portfolio_value": float(acct.portfolio_value),
            "cash": float(acct.cash),
            "buying_power": float(acct.buying_power),
            "daytrade_count": int(acct.daytrade_count),
            "pattern_day_trader": acct.pattern_day_trader,
            "shorting_enabled": acct.shorting_enabled,
            "status": str(acct.status),
        }

    def get_portfolio_value(self) -> float:
        return self.get_account()["portfolio_value"]

    def get_buying_power(self) -> float:
        return self.get_account()["buying_power"]

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    @_retry()
    def get_positions(self) -> list[dict]:
        """Return all open positions as a list of dicts."""
        positions = self._trading.get_all_positions()
        result = []
        for p in positions:
            result.append({
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": "long" if float(p.qty) > 0 else "short",
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price) if p.current_price else 0.0,
                "market_value": float(p.market_value) if p.market_value else 0.0,
                "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0.0,
                "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else 0.0,
                "cost_basis": float(p.cost_basis) if p.cost_basis else 0.0,
            })
        return result

    @_retry()
    def get_position(self, symbol: str) -> Optional[dict]:
        """Return a single position or None if not held."""
        try:
            p = self._trading.get_open_position(symbol)
            return {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": "long" if float(p.qty) > 0 else "short",
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price) if p.current_price else 0.0,
                "market_value": float(p.market_value) if p.market_value else 0.0,
                "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0.0,
                "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else 0.0,
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    @_retry()
    def submit_bracket_order(
        self,
        symbol: str,
        qty: int,
        side: str,             # "buy" | "sell"  (sell = short entry)
        take_profit_price: float,
        stop_loss_price: float,
        limit_price: Optional[float] = None,
    ) -> dict:
        """
        Submit a bracket order (entry + take-profit + stop-loss).
        Uses market entry by default; pass limit_price for limit entry.
        """
        alpaca_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        take_profit = TakeProfitRequest(limit_price=round(take_profit_price, 2))
        stop_loss   = StopLossRequest(stop_price=round(stop_loss_price, 2))

        if limit_price:
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                order_class=OrderClass.BRACKET,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
        else:
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )

        order = self._trading.submit_order(req)
        logger.info(f"Bracket order submitted: {symbol} {side} {qty} shares | TP={take_profit_price:.2f} SL={stop_loss_price:.2f}")
        return self._order_to_dict(order)

    @_retry()
    def submit_market_order(self, symbol: str, qty: int, side: str) -> dict:
        """Simple market order (used for closing positions quickly)."""
        alpaca_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=symbol,
            qty=abs(qty),
            side=alpaca_side,
            time_in_force=TimeInForce.DAY,
        )
        order = self._trading.submit_order(req)
        logger.info(f"Market order submitted: {symbol} {side} {abs(qty)} shares")
        return self._order_to_dict(order)

    @_retry()
    def close_position(self, symbol: str) -> dict:
        """Close entire position in *symbol* at market."""
        order = self._trading.close_position(symbol)
        logger.info(f"Closed position: {symbol}")
        return self._order_to_dict(order)

    @_retry()
    def get_open_orders(self) -> list[dict]:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = self._trading.get_orders(filter=req)
        return [self._order_to_dict(o) for o in orders]

    @_retry()
    def cancel_order(self, order_id: str) -> None:
        self._trading.cancel_order_by_id(order_id)
        logger.info(f"Cancelled order {order_id}")

    @_retry()
    def cancel_all_orders(self) -> None:
        self._trading.cancel_orders()
        logger.info("Cancelled all open orders")

    # ------------------------------------------------------------------
    # Asset info
    # ------------------------------------------------------------------

    @_retry()
    def is_shortable(self, symbol: str) -> bool:
        try:
            asset = self._trading.get_asset(symbol)
            return asset.shortable and asset.easy_to_borrow
        except Exception:
            return False

    @_retry()
    def get_asset_info(self, symbol: str) -> dict:
        try:
            a = self._trading.get_asset(symbol)
            return {
                "symbol": a.symbol,
                "name": a.name,
                "exchange": str(a.exchange),
                "tradable": a.tradable,
                "shortable": a.shortable,
                "easy_to_borrow": a.easy_to_borrow,
                "marginable": a.marginable,
                "fractionable": a.fractionable,
            }
        except Exception as e:
            logger.warning(f"Could not get asset info for {symbol}: {e}")
            return {}

    # ------------------------------------------------------------------
    # Market status
    # ------------------------------------------------------------------

    def is_market_open(self) -> bool:
        try:
            clock = self._trading.get_clock()
            return clock.is_open
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    @_retry()
    def get_bars(
        self,
        symbols: list[str],
        timeframe: str = "1Min",
        limit: int = 200,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch OHLCV bars. Returns {symbol: DataFrame}.
        timeframe: '1Min' | '5Min' | '15Min' | '1Hour' | '1Day'
        """
        tf_map = {
            "1Min":  TimeFrame(1,  TimeFrameUnit.Minute),
            "5Min":  TimeFrame(5,  TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1,  TimeFrameUnit.Hour),
            "1Day":  TimeFrame(1,  TimeFrameUnit.Day),
        }
        tf = tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Minute))

        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            limit=limit,
        )
        bars = self._data.get_stock_bars(req)
        result: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            try:
                df = bars[sym].df.rename(columns=str.lower)
                df.index.name = "timestamp"
                result[sym] = df
            except Exception:
                result[sym] = pd.DataFrame()
        return result

    @_retry()
    def get_latest_quotes(self, symbols: list[str]) -> dict[str, float]:
        """Return latest ask price for each symbol."""
        req = StockLatestQuoteRequest(symbol_or_symbols=symbols)
        quotes = self._data.get_stock_latest_quote(req)
        return {
            sym: float(quotes[sym].ask_price or quotes[sym].bid_price or 0)
            for sym in symbols
            if sym in quotes
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _order_to_dict(order) -> dict:
        return {
            "id": str(order.id),
            "client_order_id": str(order.client_order_id),
            "symbol": order.symbol,
            "qty": float(order.qty) if order.qty else 0,
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
            "side": str(order.side),
            "type": str(order.type),
            "status": str(order.status),
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "submitted_at": str(order.submitted_at),
        }
