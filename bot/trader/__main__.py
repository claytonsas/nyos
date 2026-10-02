"""Point d'entrée : python -m trader <commande>."""
import argparse
import logging
import sys
from pathlib import Path

from .backtest import format_report, run_backtest
from .config import load_config
from .data import cached_history, load_csv, make_exchange, synthetic


def cmd_backtest(args, cfg) -> int:
    if args.demo:
        print("⚠️  DONNÉES FICTIVES (--demo) : sert à vérifier le code, pas la stratégie.\n")
        frames = {f"DEMO{i}": synthetic(seed=i + 1, start_price=p)
                  for i, p in enumerate((30_000, 2_000))}
    elif args.csv:
        frames = {Path(c).stem: load_csv(c) for c in args.csv}
    else:
        ex = make_exchange(cfg.exchange_id)
        frames = {}
        for sym in cfg.symbols:
            print(f"Téléchargement {sym} {cfg.timeframe} ({args.days} jours)…")
            frames[sym] = cached_history(ex, sym, cfg.timeframe, args.days, cfg.data_dir)
    result = run_backtest(frames, cfg)
    print(format_report(result, cfg.daily_target))
    out = Path(cfg.data_dir)
    out.mkdir(parents=True, exist_ok=True)
    result["_trades"].to_csv(out / "backtest_trades.csv", index=False)
    result["_daily"].rename("pnl").to_csv(out / "backtest_jours.csv")
    print(f"\nDétail : {out / 'backtest_trades.csv'} et {out / 'backtest_jours.csv'}")
    return 0


def cmd_run(args, cfg) -> int:
    from .live import Engine
    Engine(cfg).run()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="trader", description="NYOS Trader — bot crypto long/short")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    bt = sub.add_parser("backtest", help="tester la stratégie sur l'historique")
    bt.add_argument("--days", type=int, default=365)
    bt.add_argument("--csv", nargs="+", help="fichiers OHLCV CSV au lieu de l'exchange")
    bt.add_argument("--demo", action="store_true", help="données fictives (test du code)")
    sub.add_parser("run", help="lancer le bot (paper ou live selon config.yaml)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    return {"backtest": cmd_backtest, "run": cmd_run}[args.cmd](args, cfg)


if __name__ == "__main__":
    sys.exit(main())
