import numpy as np
import pandas as pd
import pytest

from trader import indicators as ind
from trader import live
from trader import risk as rk
from trader.backtest import run_backtest
from trader.config import Config, Costs, RiskParams, StrategyParams
from trader.data import synthetic
from trader.portfolio import SimPortfolio
from trader.strategy import Signal, prepare, signal_at


def test_indicators_basic():
    df = synthetic(bars=500, seed=1)
    assert ind.atr(df, 14).dropna().gt(0).all()
    a = ind.adx(df, 14).dropna()
    assert a.between(0, 100).all()
    flat = pd.Series([5.0] * 50)
    assert ind.ema(flat, 10).dropna().eq(5.0).all()


def test_position_size_risks_one_percent():
    risk, costs = RiskParams(risk_per_trade=0.01, max_leverage=10), Costs(0, 0, 0)
    qty = rk.position_size(1000, 100, 98, 0, risk, costs)
    assert qty * 2 == pytest.approx(10)          # perte au stop = 10 = 1 % de 1000


def test_position_size_capped_by_leverage():
    risk, costs = RiskParams(risk_per_trade=0.05, max_leverage=2), Costs(0, 0, 0)
    qty = rk.position_size(1000, 100, 99.9, 0, risk, costs)
    assert qty * 100 == pytest.approx(2000)      # notional <= 2 x capital
    assert rk.position_size(1000, 100, 99, 2000, risk, costs) == 0


def test_liquidation_and_stop_safety():
    assert rk.liquidation_price("long", 100, 3, 0.005) == pytest.approx(67.1666, rel=1e-3)
    risk = RiskParams(max_leverage=3)
    assert rk.stop_is_safe("long", 100, 97, risk)
    assert not rk.stop_is_safe("long", 100, 70, risk)
    assert rk.stop_is_safe("short", 100, 103, risk)


def test_stop_assumed_first_when_both_hit():
    pf = SimPortfolio(1000, RiskParams(), Costs(0, 0, 0))
    pf.open("X", Signal("long", 2.0, 2.0), 100, 0)
    t = pf.check_exit("X", 100, 110, 90, 3_600_000)   # bougie qui touche stop ET objectif
    assert t.reason == "stop" and t.pnl < 0


def test_gap_through_stop_fills_at_open():
    pf = SimPortfolio(1000, RiskParams(), Costs(0, 0, 0))
    pf.open("X", Signal("short", 2.0, 2.0), 100, 0)
    t = pf.check_exit("X", 105, 106, 104, 3_600_000)
    assert t.exit == 105


def test_costs_reduce_profit():
    frames = {"A": synthetic(bars=3000, seed=3)}
    free = Config(costs=Costs(0, 0, 0))
    paid = Config(costs=Costs(0.001, 0.001, 0.0001))
    assert run_backtest(frames, paid)["pnl_total"] < run_backtest(frames, free)["pnl_total"]


def test_no_lookahead():
    """Modifier le futur ne doit pas changer les trades déjà ouverts avant."""
    df = synthetic(bars=3000, seed=5)
    cut = df.index[2000]
    altered = df.copy()
    altered.loc[altered.index > cut, ["open", "high", "low", "close"]] *= 1.5
    cfg = Config()
    a = run_backtest({"A": df}, cfg)["_trades"]
    b = run_backtest({"A": altered}, cfg)["_trades"]
    a, b = a[a.closed_at < cut], b[b.closed_at < cut]
    assert len(a) > 0
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))


def test_signal_long_on_breakout():
    p = StrategyParams(ema_fast=5, ema_slow=10, breakout_period=5, adx_min=0)
    closes = np.linspace(100, 200, 80)
    df = pd.DataFrame({"open": closes - 0.5, "high": closes + 0.5,
                       "low": closes - 1, "close": closes, "volume": 1.0})
    sig = signal_at(prepare(df, p).iloc[-1], p)
    assert sig is not None and sig.side == "long"


class FakeExchange:
    id = "fake"

    def __init__(self, df):
        self.df = df
        self.now = int(df.index[400]) + 60_000

    def parse_timeframe(self, tf):
        return 3600

    def milliseconds(self):
        return self.now

    def fetch_ohlcv(self, symbol, tf, limit=500):
        d = self.df[self.df.index <= self.now].tail(limit)
        return [[int(ts), *row] for ts, row in zip(d.index, d.values.tolist())]


def test_paper_engine_trades_and_persists(tmp_path, monkeypatch):
    df = synthetic(bars=3000, seed=3)
    fake = FakeExchange(df)
    monkeypatch.setattr(live, "make_exchange", lambda *a, **k: fake)
    cfg = Config(symbols=["A/USDT:USDT"], data_dir=str(tmp_path))
    eng = live.Engine(cfg)
    for _ in range(2000):
        fake.now += 3_600_000
        eng._tick(fake.now // 3_600_000 * 3_600_000)
        eng._save()
    assert eng.journal.exists()
    journal = pd.read_csv(eng.journal)
    assert len(journal) > 5
    assert eng.broker.equity() == pytest.approx(cfg.capital + journal.pnl.sum(), abs=1e-6)
    eng2 = live.Engine(cfg)                     # redémarrage : l'état est rechargé
    assert eng2.broker.equity() == pytest.approx(eng.broker.equity())
    assert eng2.last_ts == eng.last_ts


class FakeCcxt:
    """Imite l'API ccxt pour vérifier les ordres envoyés en live."""

    def __init__(self, fail_stop=False):
        self.orders, self.fail_stop, self.size = [], fail_stop, 0.0

    def load_markets(self): pass
    def market(self, s): return {"limits": {"amount": {"min": 0.001}, "cost": {"min": 5}}}
    def amount_to_precision(self, s, q): return f"{q:.3f}"
    def price_to_precision(self, s, p): return f"{p:.2f}"
    def fetch_balance(self): return {"total": {"USDT": 1000.0}}
    def set_margin_mode(self, *a): pass
    def set_leverage(self, *a): pass
    def cancel_all_orders(self, s): self.orders.append(("cancel", s))
    def fetch_positions(self, syms): return [{"symbol": syms[0], "contracts": self.size}]
    def fetch_my_trades(self, s, since=None): return [{"side": "sell", "amount": 0.25, "price": 95.0, "fee": {"cost": 0.01}}]

    def create_order(self, symbol, type_, side, qty, price=None, params=None):
        params = params or {}
        if "stopLossPrice" in params and self.fail_stop:
            raise RuntimeError("refusé")
        self.orders.append((side, qty, params))
        if not params:
            self.size = qty
        return {"average": 100.0}


def test_live_open_places_exchange_side_stop_and_target():
    ex = FakeCcxt()
    b = live.LiveBroker(Config(), ex)
    pos = b.open("A/USDT:USDT", Signal("long", 2.0, 2.0), 100.0, 0)
    assert pos and pos.stop == 98.0 and pos.take == 104.0
    kinds = [list(o[2].keys()) for o in ex.orders]
    assert ["stopLossPrice", "reduceOnly"] in kinds and ["takeProfitPrice", "reduceOnly"] in kinds
    ex.size = 0.0                                    # le stop a été exécuté chez l'exchange
    t = b.update("A/USDT:USDT", None)
    assert t.reason == "stop" and t.pnl < 0 and "A/USDT:USDT" not in b.positions


def test_live_closes_position_if_stop_cannot_be_placed():
    ex = FakeCcxt(fail_stop=True)
    b = live.LiveBroker(Config(), ex)
    with pytest.raises(RuntimeError):
        b.open("A/USDT:USDT", Signal("long", 2.0, 2.0), 100.0, 0)
    assert ex.orders[-2][2] == {"reduceOnly": True}   # fermeture d'urgence envoyée
    assert not b.positions
