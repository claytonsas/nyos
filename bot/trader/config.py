"""Chargement de la configuration (YAML + variables d'environnement)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StrategyParams:
    ema_fast: int = 50
    ema_slow: int = 200
    breakout_period: int = 20
    adx_period: int = 14
    adx_min: float = 20.0
    atr_period: int = 14
    stop_atr: float = 2.0
    reward_risk: float = 2.0
    allow_short: bool = True


@dataclass
class RiskParams:
    risk_per_trade: float = 0.01      # 1 % du capital risqué par trade
    max_leverage: float = 3.0         # levier max (marge isolée)
    max_open_positions: int = 2
    max_daily_loss: float = 0.03      # -3 % sur la journée => plus de nouveaux trades
    maintenance_margin: float = 0.005  # pour estimer le prix de liquidation


@dataclass
class Costs:
    taker_fee: float = 0.0005         # 0,05 % par ordre
    slippage: float = 0.0005          # 0,05 % de glissement par exécution
    funding_rate_8h: float = 0.0001   # 0,01 % / 8 h, compté comme un coût


@dataclass
class Config:
    mode: str = "paper"               # paper | live
    exchange_id: str = "binanceusdm"
    testnet: bool = False
    quote: str = "USDT"
    symbols: list = field(default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT"])
    timeframe: str = "1h"
    capital: float = 1000.0
    daily_target: float = 35.0
    data_dir: str = "data"
    strategy: StrategyParams = field(default_factory=StrategyParams)
    risk: RiskParams = field(default_factory=RiskParams)
    costs: Costs = field(default_factory=Costs)
    telegram_enabled: bool = False
    api_key: str = ""
    api_secret: str = ""
    api_password: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: str = "config.yaml") -> Config:
    cfg_path = Path(path)
    _load_dotenv(cfg_path.parent / ".env")
    raw = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    raw = raw or {}
    ex = raw.get("exchange", {})
    tg = raw.get("telegram", {})
    cfg = Config(
        mode=raw.get("mode", "paper"),
        exchange_id=ex.get("id", "binanceusdm"),
        testnet=bool(ex.get("testnet", False)),
        quote=raw.get("quote", "USDT"),
        symbols=raw.get("symbols", Config().symbols),
        timeframe=raw.get("timeframe", "1h"),
        capital=float(raw.get("capital", 1000)),
        daily_target=float(raw.get("daily_target", 35)),
        data_dir=raw.get("data_dir", "data"),
        strategy=StrategyParams(**raw.get("strategy", {})),
        risk=RiskParams(**raw.get("risk", {})),
        costs=Costs(**raw.get("costs", {})),
        telegram_enabled=bool(tg.get("enabled", False)),
        api_key=os.getenv("EXCHANGE_API_KEY", ""),
        api_secret=os.getenv("EXCHANGE_API_SECRET", ""),
        api_password=os.getenv("EXCHANGE_API_PASSWORD", ""),
        telegram_token=os.getenv("TELEGRAM_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
    )
    if cfg.mode not in ("paper", "live"):
        raise ValueError(f"mode inconnu : {cfg.mode!r} (paper ou live)")
    if not 0 < cfg.risk.risk_per_trade <= 0.05:
        raise ValueError("risk_per_trade doit être entre 0 et 5 %")
    if not 1 <= cfg.risk.max_leverage <= 10:
        raise ValueError("max_leverage doit être entre 1 et 10")
    return cfg
