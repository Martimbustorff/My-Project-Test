"""
execution/order_manager.py
--------------------------
Translates Signal objects into bracket orders and manages the lifecycle
of open positions (trailing stops, forced exits, signal reversals).
"""
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    symbol: str
    action: str
    shares: int
    entry_price: float
    stop_price: float
    take_profit_price: float
    order_id: Optional[str]
    success: bool
    reason: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class OrderManager:
    """
    Translates Signal objects into executable bracket orders.

    Responsibilities:
    - Pre-flight checks (buying power, position limits, heat)
    - Call RiskManager for sizing + stop levels
    - Submit bracket orders via AlpacaBroker
    - Manage existing positions (trailing stops, hard stops, signal reversals)
    - Log all executions
    """

    def __init__(self, broker, risk_manager, trade_logger=None):
        self.broker = broker
        self.risk = risk_manager
        self.logger = trade_logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_signal(
        self,
        signal,               # analysis.signals.Signal
        portfolio_manager,
        atr_map: dict[str, float],
    ) -> Optional[ExecutionResult]:
        """
        Main entry point. Validates signal and submits order if appropriate.
        Returns ExecutionResult or None if no trade was made.
        """
        from analysis.signals import Action

        symbol  = signal.symbol
        action  = signal.action
        price   = signal.current_price

        if price <= 0:
            logger.warning(f"{symbol}: invalid price {price}, skipping")
            return None

        # Get account state
        portfolio_value = portfolio_manager.get_portfolio_value()
        positions = portfolio_manager.get_all_positions()
        atr = atr_map.get(symbol, price * 0.02)  # fallback 2% ATR

        # ---- BUY -------------------------------------------------------
        if action == Action.BUY:
            if portfolio_manager.is_long(symbol):
                logger.debug(f"{symbol}: already long, skip BUY")
                return None
            return self._open_long(signal, portfolio_value, positions, atr)

        # ---- SHORT -----------------------------------------------------
        elif action == Action.SHORT:
            if portfolio_manager.is_short(symbol):
                logger.debug(f"{symbol}: already short, skip SHORT")
                return None
            if not self.broker.is_shortable(symbol):
                logger.info(f"{symbol}: not shortable, skip")
                return None
            return self._open_short(signal, portfolio_value, positions, atr)

        # ---- SELL (close long) -----------------------------------------
        elif action == Action.SELL:
            if not portfolio_manager.is_long(symbol):
                logger.debug(f"{symbol}: not long, skip SELL")
                return None
            return self._close_position(symbol, "SELL", signal.reasoning)

        # ---- COVER (close short) ---------------------------------------
        elif action == Action.COVER:
            if not portfolio_manager.is_short(symbol):
                logger.debug(f"{symbol}: not short, skip COVER")
                return None
            return self._close_position(symbol, "COVER", signal.reasoning)

        return None

    def manage_existing_positions(
        self,
        signals: dict,          # {symbol: Signal}
        portfolio_manager,
        atr_map: dict[str, float],
    ) -> list[ExecutionResult]:
        """
        Review all open positions for:
        1. Hard stop breach (backup for bracket stop)
        2. Trailing stop update (informational — bracket handles execution)
        3. Strong opposing signal → close early
        """
        results = []
        for pos in portfolio_manager.get_all_positions().values():
            symbol      = pos["symbol"]
            side        = pos["side"]
            entry_price = pos["avg_entry_price"]
            current_px  = pos["current_price"]
            atr         = atr_map.get(symbol, current_px * 0.02)

            # Hard stop check
            should_exit, reason = self.risk.should_force_exit(
                symbol, side, entry_price, current_px
            )
            if should_exit:
                logger.warning(f"Hard stop triggered for {symbol}: {reason}")
                result = self._close_position(symbol, f"HARD_STOP_{side.upper()}", [reason])
                if result:
                    results.append(result)
                continue

            # Strong opposing signal
            sig = signals.get(symbol)
            if sig:
                from analysis.signals import Action
                if side == "long"  and sig.action == Action.SELL  and sig.confidence > 0.6:
                    logger.info(f"Strong SELL signal on long {symbol} (conf={sig.confidence:.2f})")
                    result = self._close_position(symbol, "SIGNAL_EXIT_LONG", sig.reasoning)
                    if result:
                        results.append(result)
                elif side == "short" and sig.action == Action.COVER and sig.confidence > 0.6:
                    logger.info(f"Strong COVER signal on short {symbol} (conf={sig.confidence:.2f})")
                    result = self._close_position(symbol, "SIGNAL_EXIT_SHORT", sig.reasoning)
                    if result:
                        results.append(result)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _open_long(self, signal, portfolio_value, positions, atr) -> Optional[ExecutionResult]:
        symbol = signal.symbol
        price  = signal.current_price

        sizing = self.risk.calculate_position_size(
            symbol=symbol,
            current_price=price,
            portfolio_value=portfolio_value,
            atr=atr,
            side="long",
            confidence=signal.confidence,
        )

        # Heat check
        if not self.risk.check_portfolio_heat(positions, portfolio_value, sizing.dollar_risk):
            return ExecutionResult(
                symbol=symbol, action="BUY_SKIPPED", shares=0,
                entry_price=price, stop_price=sizing.stop_price,
                take_profit_price=sizing.take_profit_price,
                order_id=None, success=False, reason="Portfolio heat limit"
            )

        try:
            order = self.broker.submit_bracket_order(
                symbol=symbol,
                qty=sizing.shares,
                side="buy",
                take_profit_price=sizing.take_profit_price,
                stop_loss_price=sizing.stop_price,
            )
            result = ExecutionResult(
                symbol=symbol, action="BUY", shares=sizing.shares,
                entry_price=price, stop_price=sizing.stop_price,
                take_profit_price=sizing.take_profit_price,
                order_id=order["id"], success=True,
                reason="; ".join(signal.reasoning[:3]),
            )
            self._log(result, signal)
            return result
        except Exception as e:
            logger.error(f"Failed to open long {symbol}: {e}")
            return ExecutionResult(
                symbol=symbol, action="BUY_FAILED", shares=0,
                entry_price=price, stop_price=sizing.stop_price,
                take_profit_price=sizing.take_profit_price,
                order_id=None, success=False, reason=str(e)
            )

    def _open_short(self, signal, portfolio_value, positions, atr) -> Optional[ExecutionResult]:
        symbol = signal.symbol
        price  = signal.current_price

        if not self.risk.check_short_capacity(positions):
            return ExecutionResult(
                symbol=symbol, action="SHORT_SKIPPED", shares=0,
                entry_price=price, stop_price=0, take_profit_price=0,
                order_id=None, success=False, reason="Max short positions reached"
            )

        sizing = self.risk.calculate_position_size(
            symbol=symbol,
            current_price=price,
            portfolio_value=portfolio_value,
            atr=atr,
            side="short",
            confidence=signal.confidence,
        )

        if not self.risk.check_portfolio_heat(positions, portfolio_value, sizing.dollar_risk):
            return ExecutionResult(
                symbol=symbol, action="SHORT_SKIPPED", shares=0,
                entry_price=price, stop_price=sizing.stop_price,
                take_profit_price=sizing.take_profit_price,
                order_id=None, success=False, reason="Portfolio heat limit"
            )

        try:
            order = self.broker.submit_bracket_order(
                symbol=symbol,
                qty=sizing.shares,
                side="sell",
                take_profit_price=sizing.take_profit_price,
                stop_loss_price=sizing.stop_price,
            )
            result = ExecutionResult(
                symbol=symbol, action="SHORT", shares=sizing.shares,
                entry_price=price, stop_price=sizing.stop_price,
                take_profit_price=sizing.take_profit_price,
                order_id=order["id"], success=True,
                reason="; ".join(signal.reasoning[:3]),
            )
            self._log(result, signal)
            return result
        except Exception as e:
            logger.error(f"Failed to open short {symbol}: {e}")
            return ExecutionResult(
                symbol=symbol, action="SHORT_FAILED", shares=0,
                entry_price=price, stop_price=sizing.stop_price,
                take_profit_price=sizing.take_profit_price,
                order_id=None, success=False, reason=str(e)
            )

    def _close_position(self, symbol: str, action: str, reasoning: list) -> Optional[ExecutionResult]:
        try:
            # Cancel any pending bracket legs first
            open_orders = self.broker.get_open_orders()
            for o in open_orders:
                if o["symbol"] == symbol:
                    try:
                        self.broker.cancel_order(o["id"])
                    except Exception:
                        pass

            order = self.broker.close_position(symbol)
            result = ExecutionResult(
                symbol=symbol, action=action, shares=int(order.get("qty", 0)),
                entry_price=0, stop_price=0, take_profit_price=0,
                order_id=order["id"], success=True,
                reason="; ".join(str(r) for r in reasoning[:3]),
            )
            if self.logger:
                self.logger.log_trade(order, None, 0)
            return result
        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            return None

    def _log(self, result: ExecutionResult, signal) -> None:
        if self.logger:
            try:
                self.logger.log_trade(
                    {"id": result.order_id, "symbol": result.symbol,
                     "side": result.action, "qty": result.shares,
                     "filled_avg_price": result.entry_price},
                    signal,
                    0,
                )
            except Exception as e:
                logger.warning(f"Failed to log trade: {e}")
