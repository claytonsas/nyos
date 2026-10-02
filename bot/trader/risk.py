"""Taille de position, levier et garde-fous."""
from .config import Costs, RiskParams


def liquidation_price(side: str, entry: float, leverage: float, mmr: float) -> float:
    """Approximation du prix de liquidation en marge isolée."""
    if side == "long":
        return entry * (1 - 1 / leverage + mmr)
    return entry * (1 + 1 / leverage - mmr)


def position_size(equity: float, entry: float, stop: float, used_notional: float,
                  risk: RiskParams, costs: Costs) -> float:
    """Quantité telle qu'un stop touché coûte ~risk_per_trade du capital (frais inclus).

    La taille est plafonnée par le levier max : notional total <= capital x max_leverage.
    Le levier n'est donc qu'une conséquence du risque choisi, jamais un multiplicateur aveugle.
    """
    stop_dist = abs(entry - stop)
    if equity <= 0 or stop_dist <= 0:
        return 0.0
    # perte par unité si le stop est touché : écart + frais/glissement aller-retour
    loss_per_unit = stop_dist + entry * 2 * (costs.taker_fee + costs.slippage)
    qty = equity * risk.risk_per_trade / loss_per_unit
    room = equity * risk.max_leverage - used_notional
    if room <= 0:
        return 0.0
    qty = min(qty, room / entry)
    return max(qty, 0.0)


def stop_is_safe(side: str, entry: float, stop: float, risk: RiskParams) -> bool:
    """Le stop doit être déclenché bien avant la liquidation."""
    liq = liquidation_price(side, entry, risk.max_leverage, risk.maintenance_margin)
    if side == "long":
        return stop > liq + (entry - liq) * 0.2
    return stop < liq - (liq - entry) * 0.2
