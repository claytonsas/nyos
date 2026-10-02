"""Stratégie : suivi de tendance + cassure (long et short).

Règles, évaluées sur la bougie CLÔTURÉE :
  LONG  : EMA rapide > EMA lente, clôture > EMA lente, ADX >= seuil,
          clôture au-dessus du plus haut des N bougies précédentes.
  SHORT : miroir exact.
Stop à `stop_atr` x ATR du prix d'entrée, objectif à `reward_risk` x le risque.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import indicators as ind
from .config import StrategyParams


@dataclass
class Signal:
    side: str          # "long" | "short"
    stop_dist: float   # distance du stop en prix
    reward_risk: float


def prepare(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["ema_f"] = ind.ema(out["close"], p.ema_fast)
    out["ema_s"] = ind.ema(out["close"], p.ema_slow)
    out["atr"] = ind.atr(out, p.atr_period)
    out["adx"] = ind.adx(out, p.adx_period)
    out["dc_high"] = out["high"].rolling(p.breakout_period).max().shift(1)
    out["dc_low"] = out["low"].rolling(p.breakout_period).min().shift(1)
    return out


def signal_at(row: pd.Series, p: StrategyParams) -> Optional[Signal]:
    needed = ("ema_f", "ema_s", "atr", "adx", "dc_high", "dc_low")
    if any(pd.isna(row[c]) for c in needed) or row["atr"] <= 0:
        return None
    if row["adx"] < p.adx_min:
        return None
    stop_dist = p.stop_atr * row["atr"]
    up = row["ema_f"] > row["ema_s"] and row["close"] > row["ema_s"]
    down = row["ema_f"] < row["ema_s"] and row["close"] < row["ema_s"]
    if up and row["close"] > row["dc_high"]:
        return Signal("long", stop_dist, p.reward_risk)
    if p.allow_short and down and row["close"] < row["dc_low"]:
        return Signal("short", stop_dist, p.reward_risk)
    return None


def levels(side: str, entry: float, sig: Signal) -> tuple:
    """Prix du stop et de l'objectif pour une entrée donnée."""
    risk = sig.stop_dist
    if side == "long":
        return entry - risk, entry + risk * sig.reward_risk
    return entry + risk, entry - risk * sig.reward_risk
