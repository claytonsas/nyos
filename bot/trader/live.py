"""Boucle temps réel : paper trading (argent fictif) ou live (vrais ordres sur l'exchange)."""
import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from . import risk as rk
from .config import Config
from .data import make_exchange, to_frame
from .notify import Telegram
from .portfolio import DayGuard, Position, SimPortfolio, Trade, utc_day
from .strategy import levels, prepare, signal_at

log = logging.getLogger(__name__)


# ─────────────────────────── brokers ───────────────────────────

class PaperBroker:
    """Ordres simulés avec les vrais prix du marché. Aucun argent réel."""

    def __init__(self, cfg: Config):
        self.pf = SimPortfolio(cfg.capital, cfg.risk, cfg.costs)

    @property
    def positions(self) -> dict:
        return self.pf.positions

    def equity(self) -> float:
        return self.pf.equity

    def open(self, symbol, sig, price, ts) -> Optional[Position]:
        return self.pf.open(symbol, sig, price, ts)

    def update(self, symbol: str, bars) -> Optional[Trade]:
        pos = self.pf.positions.get(symbol)
        if pos is None:
            return None
        for ts, b in bars.iterrows():
            if ts >= pos.opened_at:
                t = self.pf.check_exit(symbol, b["open"], b["high"], b["low"], int(ts))
                if t:
                    return t
        return None

    def close_all(self, prices: dict, ts: int) -> list:
        return [self.pf.close(s, prices.get(s, p.entry), ts, "arrêt manuel")
                for s, p in list(self.pf.positions.items())]

    def dump(self) -> dict:
        return self.pf.to_dict()

    def load(self, data: dict) -> None:
        self.pf.load_dict(data)


class LiveBroker:
    """Vrais ordres. Stop-loss et take-profit posés CHEZ L'EXCHANGE dès l'entrée :
    si le bot ou le serveur plante, la position reste protégée."""

    def __init__(self, cfg: Config, exchange):
        self.cfg = cfg
        self.ex = exchange
        self.ex.load_markets()
        self.positions: dict = {}

    def equity(self) -> float:
        bal = self.ex.fetch_balance()
        return float((bal.get("total") or {}).get(self.cfg.quote, 0.0) or 0.0)

    def _prepare_symbol(self, symbol: str) -> None:
        lev = int(self.cfg.risk.max_leverage)
        for call in (lambda: self.ex.set_margin_mode("isolated", symbol),
                     lambda: self.ex.set_leverage(lev, symbol)):
            try:
                call()
            except Exception as e:  # déjà réglé, ou non supporté : on continue
                log.debug("réglage %s ignoré : %s", symbol, e)

    def open(self, symbol, sig, price, ts) -> Optional[Position]:
        cfg = self.cfg
        if symbol in self.positions or len(self.positions) >= cfg.risk.max_open_positions:
            return None
        est_stop, _ = levels(sig.side, price, sig)
        if not rk.stop_is_safe(sig.side, price, est_stop, cfg.risk):
            return None
        used = sum(p.qty * p.entry for p in self.positions.values())
        qty = rk.position_size(self.equity(), price, est_stop, used, cfg.risk, cfg.costs)
        qty = float(self.ex.amount_to_precision(symbol, qty)) if qty > 0 else 0.0
        limits = self.ex.market(symbol).get("limits", {})
        min_amt = (limits.get("amount") or {}).get("min") or 0
        min_cost = (limits.get("cost") or {}).get("min") or 5
        if qty <= 0 or qty < min_amt or qty * price < min_cost:
            log.info("%s : taille trop petite pour le capital, trade ignoré", symbol)
            return None

        self._prepare_symbol(symbol)
        side = "buy" if sig.side == "long" else "sell"
        exit_side = "sell" if side == "buy" else "buy"
        order = self.ex.create_order(symbol, "market", side, qty)
        fill = float(order.get("average") or order.get("price") or price)
        stop, take = levels(sig.side, fill, sig)
        try:
            self.ex.create_order(symbol, "market", exit_side, qty, None,
                                 {"stopLossPrice": float(self.ex.price_to_precision(symbol, stop)),
                                  "reduceOnly": True})
            self.ex.create_order(symbol, "market", exit_side, qty, None,
                                 {"takeProfitPrice": float(self.ex.price_to_precision(symbol, take)),
                                  "reduceOnly": True})
        except Exception:
            # jamais de position sans stop : on referme immédiatement
            log.exception("pose du stop impossible sur %s, fermeture de la position", symbol)
            self.ex.create_order(symbol, "market", exit_side, qty, None, {"reduceOnly": True})
            self._cancel(symbol)
            raise
        fee = qty * fill * cfg.costs.taker_fee
        pos = Position(symbol, sig.side, qty, fill, stop, take, ts, fee)
        self.positions[symbol] = pos
        return pos

    def _cancel(self, symbol: str) -> None:
        try:
            self.ex.cancel_all_orders(symbol)
        except Exception as e:
            log.warning("annulation des ordres %s : %s", symbol, e)

    def _open_size(self, symbol: str) -> float:
        total = 0.0
        for p in self.ex.fetch_positions([symbol]):
            if p.get("symbol") == symbol:
                total += abs(float(p.get("contracts") or 0))
        return total

    def update(self, symbol: str, bars) -> Optional[Trade]:
        pos = self.positions.get(symbol)
        if pos is None or self._open_size(symbol) > 0:
            return None
        # position fermée par le stop ou l'objectif côté exchange
        self._cancel(symbol)
        self.positions.pop(symbol)
        fills = self.ex.fetch_my_trades(symbol, since=pos.opened_at)
        exit_side = "sell" if pos.side == "long" else "buy"
        closing = [f for f in fills if f.get("side") == exit_side]
        qty = sum(float(f["amount"]) for f in closing) or pos.qty
        exit_px = (sum(float(f["price"]) * float(f["amount"]) for f in closing) / qty) if closing else bars["close"].iloc[-1]
        fees = pos.entry_fee + sum(float((f.get("fee") or {}).get("cost") or 0) for f in closing)
        direction = 1 if pos.side == "long" else -1
        pnl = (exit_px - pos.entry) * pos.qty * direction - fees
        reason = "stop" if abs(exit_px - pos.stop) < abs(exit_px - pos.take) else "objectif"
        return Trade(symbol, pos.side, pos.qty, pos.entry, exit_px, pos.opened_at,
                     int(time.time() * 1000), pnl, fees, reason)

    def close_all(self, prices: dict, ts: int) -> list:
        for symbol, pos in list(self.positions.items()):
            exit_side = "sell" if pos.side == "long" else "buy"
            self._cancel(symbol)
            try:
                self.ex.create_order(symbol, "market", exit_side, pos.qty, None, {"reduceOnly": True})
            except Exception as e:
                log.error("fermeture %s impossible : %s", symbol, e)
        closed = [self.update(s, _last_bar(prices.get(s, p.entry))) for s, p in list(self.positions.items())]
        return [t for t in closed if t]

    def dump(self) -> dict:
        return {"positions": {k: asdict(v) for k, v in self.positions.items()}}

    def load(self, data: dict) -> None:
        self.positions = {k: Position(**v) for k, v in data.get("positions", {}).items()}


def _last_bar(price: float):
    import pandas as pd
    return pd.DataFrame({"open": [price], "high": [price], "low": [price], "close": [price]})


# ─────────────────────────── moteur ───────────────────────────

class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        if cfg.mode == "live":
            if os.getenv("CONFIRM_LIVE") != "OUI":
                raise SystemExit("Mode live refusé : ajoute CONFIRM_LIVE=OUI dans .env "
                                 "après avoir validé la stratégie en paper trading.")
            if not (cfg.api_key and cfg.api_secret):
                raise SystemExit("Mode live : EXCHANGE_API_KEY et EXCHANGE_API_SECRET manquants.")
        self.ex = make_exchange(cfg.exchange_id, cfg.api_key, cfg.api_secret,
                                cfg.api_password, cfg.testnet)
        self.broker = LiveBroker(cfg, self.ex) if cfg.mode == "live" else PaperBroker(cfg)
        self.tg = Telegram(cfg.telegram_token, cfg.telegram_chat_id, cfg.telegram_enabled)
        self.guard = DayGuard(cfg.risk.max_daily_loss)
        self.tf_ms = self.ex.parse_timeframe(cfg.timeframe) * 1000
        self.state_path = Path(cfg.data_dir) / f"state_{cfg.mode}.json"
        self.journal = Path(cfg.data_dir) / f"trades_{cfg.mode}.csv"
        self.last_ts: dict = {}
        self.paused = False
        self.day_pnl: dict = {}
        self.prices: dict = {}
        self.last_day = ""
        self._load()

    # --- état ---
    def _load(self) -> None:
        if self.state_path.exists():
            s = json.loads(self.state_path.read_text())
            self.broker.load(s.get("broker", {}))
            self.last_ts = s.get("last_ts", {})
            self.paused = s.get("paused", False)
            self.day_pnl = s.get("day_pnl", {})
            self.last_day = s.get("last_day", "")

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"broker": self.broker.dump(), "last_ts": self.last_ts,
                                   "paused": self.paused, "day_pnl": self.day_pnl,
                                   "last_day": self.last_day}, indent=2))
        tmp.replace(self.state_path)

    def _record(self, t: Trade) -> None:
        day = utc_day(t.closed_at)
        self.day_pnl[day] = self.day_pnl.get(day, 0.0) + t.pnl
        new = not self.journal.exists()
        with self.journal.open("a") as f:
            if new:
                f.write("symbol,side,qty,entry,exit,opened_at,closed_at,pnl,fees,reason\n")
            f.write(",".join(str(v) for v in asdict(t).values()) + "\n")
        emoji = "✅" if t.pnl > 0 else "❌"
        self.tg.send(f"{emoji} {t.symbol} {t.side.upper()} fermé ({t.reason})\n"
                     f"{t.entry:.4f} → {t.exit:.4f}   PnL {t.pnl:+.2f} {self.cfg.quote}\n"
                     f"Aujourd'hui : {self.day_pnl[day]:+.2f} / objectif {self.cfg.daily_target:.0f}")

    # --- commandes Telegram ---
    def _status(self) -> str:
        eq = self.broker.equity()
        lines = [f"Mode {self.cfg.mode.upper()} — {'⏸ en pause' if self.paused else '▶ actif'}",
                 f"Capital : {eq:.2f} {self.cfg.quote}",
                 f"Aujourd'hui : {self.day_pnl.get(utc_day(self.ex.milliseconds()), 0.0):+.2f}"]
        for p in self.broker.positions.values():
            px = self.prices.get(p.symbol, p.entry)
            u = (px - p.entry) * p.qty * (1 if p.side == "long" else -1)
            lines.append(f"• {p.symbol} {p.side} {p.qty:g} @ {p.entry:.4f}  "
                         f"SL {p.stop:.4f} TP {p.take:.4f}  latent {u:+.2f}")
        return "\n".join(lines)

    def _handle_commands(self) -> bool:
        for cmd in self.tg.commands():
            if cmd == "/status":
                self.tg.send(self._status())
            elif cmd == "/pnl":
                last = sorted(self.day_pnl.items())[-7:]
                self.tg.send("PnL 7 derniers jours :\n" + "\n".join(f"{d} : {v:+.2f}" for d, v in last)
                             if last else "Aucun trade fermé pour l'instant.")
            elif cmd == "/pause":
                self.paused = True
                self.tg.send("⏸ Pause : plus de nouvelles entrées (les stops restent actifs).")
            elif cmd == "/resume":
                self.paused = False
                self.tg.send("▶ Reprise.")
            elif cmd == "/stop":
                self.paused = True
                for t in self.broker.close_all(self.prices, self.ex.milliseconds()):
                    self._record(t)
                self.tg.send("🛑 Tout fermé, bot en pause. /resume pour relancer.")
            elif cmd == "/help":
                self.tg.send("/status /pnl /pause /resume /stop")
        return True

    # --- cycle principal ---
    def _tick(self, closed_until: int) -> None:
        p = self.cfg.strategy
        limit = max(p.ema_slow * 3, 300)
        today = utc_day(closed_until)
        if self.last_day and today != self.last_day:
            pnl = self.day_pnl.get(self.last_day, 0.0)
            self.tg.send(f"📊 Bilan du {self.last_day} : {pnl:+.2f} {self.cfg.quote} "
                         f"(objectif {self.cfg.daily_target:.0f}) — capital {self.broker.equity():.2f}")
        self.last_day = today
        self.guard.update(today, self.broker.equity())
        for sym in self.cfg.symbols:
            df = to_frame(self.ex.fetch_ohlcv(sym, self.cfg.timeframe, limit=limit))
            df = df[df.index < closed_until]              # bougies clôturées seulement
            if len(df) < p.ema_slow + 10:
                log.warning("%s : historique insuffisant", sym)
                continue
            new = df[df.index > self.last_ts.get(sym, 0)]
            self.last_ts[sym] = int(df.index[-1])
            self.prices[sym] = float(df["close"].iloc[-1])
            t = self.broker.update(sym, new)
            if t:
                self._record(t)
            if new.empty or sym in self.broker.positions or self.paused:
                continue
            if not self.guard.allowed(self.broker.equity()):
                continue
            sig = signal_at(prepare(df, p).iloc[-1], p)
            if sig is None:
                continue
            pos = self.broker.open(sym, sig, self.prices[sym], closed_until)
            if pos:
                self.tg.send(f"🚀 {sym} {pos.side.upper()} {pos.qty:g} @ {pos.entry:.4f}\n"
                             f"Stop {pos.stop:.4f}   Objectif {pos.take:.4f}")

    def run(self) -> None:
        self.tg.send(f"🤖 Bot démarré — mode {self.cfg.mode.upper()} sur {self.cfg.exchange_id}, "
                     f"{', '.join(self.cfg.symbols)} en {self.cfg.timeframe}.")
        processed = 0
        errors = 0
        while True:
            try:
                self._handle_commands()
                now = self.ex.milliseconds()
                closed_until = now // self.tf_ms * self.tf_ms
                if closed_until > processed and now - closed_until > 5_000:
                    self._tick(closed_until)
                    processed = closed_until
                    self._save()
                errors = 0
            except KeyboardInterrupt:
                self._save()
                self.tg.send("Bot arrêté.")
                return
            except Exception as e:
                errors += 1
                log.exception("erreur de cycle")
                if errors in (3, 20):
                    self.tg.send(f"⚠️ {errors} erreurs d'affilée : {e}")
                time.sleep(min(60 * errors, 600))
            time.sleep(15)
