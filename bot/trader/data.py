"""Historique des prix : téléchargement via ccxt (avec cache CSV) ou données synthétiques."""
import time
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def make_exchange(exchange_id: str, api_key: str = "", secret: str = "",
                  password: str = "", testnet: bool = False):
    import ccxt
    cls = getattr(ccxt, exchange_id)
    ex = cls({"apiKey": api_key, "secret": secret, "password": password,
              "enableRateLimit": True, "options": {"defaultType": "swap"}})
    if testnet:
        ex.set_sandbox_mode(True)
    return ex


def to_frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates("ts").sort_values("ts")
    return df.set_index("ts").astype(float)


def fetch_history(exchange, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - days * 86_400_000
    rows = []
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not batch:
            break
        rows += batch
        since = batch[-1][0] + tf_ms
        if since >= exchange.milliseconds() - tf_ms:
            break
        time.sleep(exchange.rateLimit / 1000)
    df = to_frame(rows)
    # la dernière bougie est encore ouverte : on l'écarte
    return df[df.index <= exchange.milliseconds() - tf_ms]


def cached_history(exchange, symbol: str, timeframe: str, days: int, data_dir: str) -> pd.DataFrame:
    safe = symbol.replace("/", "-").replace(":", "_")
    path = Path(data_dir) / f"{exchange.id}_{safe}_{timeframe}_{days}d.csv"
    if path.exists() and time.time() - path.stat().st_mtime < 6 * 3600:
        return pd.read_csv(path, index_col="ts")
    df = fetch_history(exchange, symbol, timeframe, days)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    if "ts" not in df.columns:
        for alt in ("timestamp", "time", "date"):
            if alt in df.columns:
                col = df[alt]
                df["ts"] = col if np.issubdtype(col.dtype, np.number) else \
                    pd.to_datetime(col, utc=True).astype("int64") // 1_000_000
                break
    return to_frame(df[COLUMNS].values.tolist())


def synthetic(bars: int = 24 * 365, seed: int = 7, start_price: float = 30_000.0,
              tf_ms: int = 3_600_000) -> pd.DataFrame:
    """Marché FICTIF à régimes (tendances / range) — uniquement pour tester le code."""
    rng = np.random.default_rng(seed)
    drift = np.zeros(bars)
    i = 0
    while i < bars:
        length = rng.integers(48, 400)
        drift[i:i + length] = rng.choice([-0.0006, 0.0, 0.0, 0.0006])
        i += length
    vol = 0.006 * np.exp(rng.normal(0, 0.25, bars))
    rets = drift + vol * rng.standard_normal(bars)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start_price], close[:-1]])
    wick = np.abs(rng.normal(0, 0.003, (2, bars))) * close
    high = np.maximum(open_, close) + wick[0]
    low = np.minimum(open_, close) - wick[1]
    ts = 1_700_000_000_000 + np.arange(bars) * tf_ms
    return to_frame(np.column_stack([ts, open_, high, low, close, rng.uniform(10, 100, bars)]).tolist())
