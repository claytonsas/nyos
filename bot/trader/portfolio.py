"""Portefeuille simulé : exécutions, frais, stops — partagé par le backtest et le paper trading."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from . import risk as rk
from .config import Costs, RiskParams
from .strategy import Signal, levels

MIN_NOTIONAL = 5.0


@dataclass
class Position:
    symbol: str
    side: str
    qty: float
    entry: float
    stop: float
    take: float
    opened_at: int      # timestamp ms
    entry_fee: float


@dataclass
class Trade:
    symbol: str
    side: str
    qty: float
    entry: float
    exit: float
    opened_at: int
    closed_at: int
    pnl: float          # net : frais d'entrée/sortie et funding déduits
    fees: float
    reason: str


def utc_day(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


class DayGuard:
    """Coupe les nouvelles entrées si la perte du jour dépasse max_daily_loss."""

    def __init__(self, max_daily_loss: float):
        self.max_daily_loss = max_daily_loss
        self.day: Optional[str] = None
        self.start_equity = 0.0

    def update(self, day: str, equity: float) -> None:
        if day != self.day:
            self.day, self.start_equity = day, equity

    def allowed(self, equity: float) -> bool:
        return equity > self.start_equity * (1 - self.max_daily_loss)


class SimPortfolio:
    def __init__(self, capital: float, risk: RiskParams, costs: Costs):
        self.equity = capital          # capital réalisé
        self.risk = risk
        self.costs = costs
        self.positions: dict = {}
        self.trades: list = []

    def used_notional(self) -> float:
        return sum(p.qty * p.entry for p in self.positions.values())

    def unrealized(self, prices: dict) -> float:
        total = 0.0
        for p in self.positions.values():
            px = prices.get(p.symbol, p.entry)
            total += (px - p.entry) * p.qty * (1 if p.side == "long" else -1)
        return total

    def open(self, symbol: str, sig: Signal, price: float, ts: int) -> Optional[Position]:
        if symbol in self.positions or len(self.positions) >= self.risk.max_open_positions:
            return None
        slip = self.costs.slippage
        fill = price * (1 + slip) if sig.side == "long" else price * (1 - slip)
        stop, take = levels(sig.side, fill, sig)
        if not rk.stop_is_safe(sig.side, fill, stop, self.risk):
            return None
        qty = rk.position_size(self.equity, fill, stop, self.used_notional(), self.risk, self.costs)
        if qty * fill < MIN_NOTIONAL:
            return None
        fee = qty * fill * self.costs.taker_fee
        self.equity -= fee
        pos = Position(symbol, sig.side, qty, fill, stop, take, ts, fee)
        self.positions[symbol] = pos
        return pos

    def check_exit(self, symbol: str, o: float, h: float, l: float, ts: int) -> Optional[Trade]:
        """Teste stop/objectif sur une bougie. Si les deux sont touchés, on suppose le stop (prudent)."""
        p = self.positions.get(symbol)
        if p is None:
            return None
        if p.side == "long":
            if l <= p.stop:
                return self.close(symbol, min(p.stop, o), ts, "stop")
            if h >= p.take:
                return self.close(symbol, max(p.take, o), ts, "objectif")
        else:
            if h >= p.stop:
                return self.close(symbol, max(p.stop, o), ts, "stop")
            if l <= p.take:
                return self.close(symbol, min(p.take, o), ts, "objectif")
        return None

    def close(self, symbol: str, price: float, ts: int, reason: str) -> Trade:
        p = self.positions.pop(symbol)
        slip = self.costs.slippage
        fill = price * (1 - slip) if p.side == "long" else price * (1 + slip)
        direction = 1 if p.side == "long" else -1
        gross = (fill - p.entry) * p.qty * direction
        exit_fee = p.qty * fill * self.costs.taker_fee
        hours = max(ts - p.opened_at, 0) / 3_600_000
        funding = p.qty * p.entry * self.costs.funding_rate_8h * hours / 8
        self.equity += gross - exit_fee - funding
        trade = Trade(p.symbol, p.side, p.qty, p.entry, fill, p.opened_at, ts,
                      gross - exit_fee - funding - p.entry_fee,
                      p.entry_fee + exit_fee + funding, reason)
        self.trades.append(trade)
        return trade

    # --- persistance (paper trading) ---
    def to_dict(self) -> dict:
        return {"equity": self.equity,
                "positions": {k: asdict(v) for k, v in self.positions.items()}}

    def load_dict(self, data: dict) -> None:
        self.equity = data["equity"]
        self.positions = {k: Position(**v) for k, v in data.get("positions", {}).items()}
