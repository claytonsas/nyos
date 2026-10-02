"""Backtest multi-actifs, bougie par bougie, sans regarder le futur.

Signal calculé à la clôture de la bougie t -> entrée à l'ouverture de t+1.
"""
from dataclasses import asdict

import numpy as np
import pandas as pd

from .config import Config
from .portfolio import DayGuard, SimPortfolio, utc_day
from .strategy import prepare, signal_at


def run_backtest(frames: dict, cfg: Config) -> dict:
    data = {s: prepare(df, cfg.strategy) for s, df in frames.items()}
    pf = SimPortfolio(cfg.capital, cfg.risk, cfg.costs)
    guard = DayGuard(cfg.risk.max_daily_loss)
    pending: dict = {}
    last_close: dict = {}
    curve = []
    timeline = sorted(set().union(*(df.index for df in data.values())))
    rows = {s: df.to_dict("index") for s, df in data.items()}

    for ts in timeline:
        guard.update(utc_day(int(ts)), pf.equity)
        for sym, bars in rows.items():
            bar = bars.get(ts)
            if bar is None:
                continue
            sig = pending.pop(sym, None)
            if sig is not None and guard.allowed(pf.equity):
                pf.open(sym, sig, bar["open"], int(ts))
            pf.check_exit(sym, bar["open"], bar["high"], bar["low"], int(ts))
            last_close[sym] = bar["close"]
            if sym not in pf.positions:
                s = signal_at(pd.Series(bar), cfg.strategy)
                if s is not None:
                    pending[sym] = s
        curve.append((int(ts), pf.equity + pf.unrealized(last_close)))

    # clôture des positions restantes au dernier prix
    for sym in list(pf.positions):
        pf.close(sym, last_close[sym], int(timeline[-1]), "fin du test")
    if curve:
        curve[-1] = (curve[-1][0], pf.equity)
    return summarize(pf, curve, cfg)


def summarize(pf: SimPortfolio, curve: list, cfg: Config) -> dict:
    trades = pd.DataFrame([asdict(t) for t in pf.trades])
    eq = pd.Series({ts: v for ts, v in curve})
    eq.index = pd.to_datetime(eq.index, unit="ms", utc=True)
    daily_eq = eq.resample("1D").last().dropna()
    daily_pnl = daily_eq.diff().fillna(daily_eq.iloc[0] - cfg.capital) if len(daily_eq) else pd.Series(dtype=float)
    peak = eq.cummax()
    max_dd = float(((eq - peak) / peak).min()) if len(eq) else 0.0

    n = len(trades)
    wins = trades[trades.pnl > 0] if n else trades
    losses = trades[trades.pnl <= 0] if n else trades
    gross_win = float(wins.pnl.sum()) if n else 0.0
    gross_loss = float(-losses.pnl.sum()) if n else 0.0
    days = max(len(daily_pnl), 1)
    sharpe = float(daily_pnl.mean() / daily_pnl.std() * np.sqrt(365)) if days > 1 and daily_pnl.std() > 0 else 0.0

    return {
        "capital_initial": cfg.capital,
        "capital_final": pf.equity,
        "pnl_total": pf.equity - cfg.capital,
        "rendement_pct": (pf.equity / cfg.capital - 1) * 100,
        "jours": days,
        "pnl_moyen_jour": (pf.equity - cfg.capital) / days,
        "trades": n,
        "taux_reussite_pct": len(wins) / n * 100 if n else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else float("inf") if gross_win else 0.0,
        "gain_moyen": float(wins.pnl.mean()) if len(wins) else 0.0,
        "perte_moyenne": float(losses.pnl.mean()) if len(losses) else 0.0,
        "frais_totaux": float(trades.fees.sum()) if n else 0.0,
        "drawdown_max_pct": max_dd * 100,
        "sharpe": sharpe,
        "meilleur_jour": float(daily_pnl.max()) if len(daily_pnl) else 0.0,
        "pire_jour": float(daily_pnl.min()) if len(daily_pnl) else 0.0,
        "jours_objectif_pct": float((daily_pnl >= cfg.daily_target).mean() * 100) if len(daily_pnl) else 0.0,
        "jours_negatifs_pct": float((daily_pnl < 0).mean() * 100) if len(daily_pnl) else 0.0,
        "_trades": trades,
        "_daily": daily_pnl,
    }


def format_report(r: dict, target: float) -> str:
    lines = [
        "══════════ RÉSULTAT DU BACKTEST ══════════",
        f"Capital            : {r['capital_initial']:.2f} → {r['capital_final']:.2f}  ({r['rendement_pct']:+.1f} %)",
        f"PnL total          : {r['pnl_total']:+.2f}  sur {r['jours']} jours",
        f"PnL moyen / jour   : {r['pnl_moyen_jour']:+.2f}   (objectif {target:.0f})",
        f"Trades             : {r['trades']}   réussite {r['taux_reussite_pct']:.1f} %",
        f"Profit factor      : {r['profit_factor']:.2f}   (>1,3 = intéressant)",
        f"Gain / perte moy.  : {r['gain_moyen']:+.2f} / {r['perte_moyenne']:+.2f}",
        f"Frais payés        : {r['frais_totaux']:.2f}",
        f"Drawdown max       : {r['drawdown_max_pct']:.1f} %",
        f"Sharpe (annualisé) : {r['sharpe']:.2f}",
        f"Meilleur / pire j. : {r['meilleur_jour']:+.2f} / {r['pire_jour']:+.2f}",
        f"Jours ≥ objectif   : {r['jours_objectif_pct']:.1f} %   jours négatifs : {r['jours_negatifs_pct']:.1f} %",
    ]
    if r["pnl_moyen_jour"] > 0:
        needed = target / r["pnl_moyen_jour"] * r["capital_initial"]
        lines.append(f"→ Capital nécessaire pour {target:.0f}/jour à ce rythme : ~{needed:,.0f}".replace(",", " "))
    else:
        lines.append("→ Stratégie perdante sur cette période : NE PAS passer en réel.")
    lines.append("Rappel : un backtest passé ne garantit rien pour la suite.")
    return "\n".join(lines)
