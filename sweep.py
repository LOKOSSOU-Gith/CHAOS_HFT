"""Sweep parametrique du scalper sur donnees reelles MT5 (EURUSDm M1).

Objectif : montrer honnetement quels parametres fonctionnent/ne fonctionnent pas.
Usage : python sweep.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config
from strategy import signals
from backtest import mt5_rates, run_backtest  # noqa: F401


def sweep(df: pd.DataFrame, spread_price: float):
    df = df.reset_index(drop=True)
    results = []
    for ema_f, ema_s in [(5, 15), (9, 21), (12, 36)]:
        for mom_thr in [0.003, 0.006, 0.01]:
            for sl_m, tp_m in [(1.0, 1.0), (1.0, 1.5), (2.0, 3.0)]:
                cfg = Config(symbol="EURUSDm")
                cfg.ema_fast, cfg.ema_slow = ema_f, ema_s
                cfg.min_momentum_pct = mom_thr
                cfg.sl_atr_mult, cfg.tp_atr_mult = sl_m, tp_m
                stats = run_backtest(df, cfg, spread_price)
                results.append((ema_f, ema_s, mom_thr, sl_m, tp_m, stats))
    results.sort(key=lambda t: t[5]["profit_factor"], reverse=True)
    print(f"{'EMA':>8} {'mom%':>6} {'SLxTP':>7} | {'PF':>5} {'ret%':>7} {'trades':>6} {'DD%':>5}")
    for ef, es, mt_, sl_m, tp_m, s in results[:12]:
        print(f"{ef:>3}/{es:<4} {mt_:>6} {sl_m:>3}x{tp_m:<3} | {s['profit_factor']:>5} {s['rendement_pct']:>7} {s['trades']:>6} {s['max_drawdown_pct']:>5}")
    print("\n--- les 3 pires (pour reference) ---")
    for ef, es, mt_, sl_m, tp_m, s in results[-3:]:
        print(f"{ef:>3}/{es:<4} {mt_:>6} {sl_m:>3}x{tp_m:<3} | PF={s['profit_factor']} ret={s['rendement_pct']}%")


if __name__ == "__main__":
    cfg = Config(symbol="EURUSDm")
    df = mt5_rates(cfg, 20000)
    if df is None or len(df) == 0:
        print(
            f"Aucune donnee MT5 pour {cfg.symbol} : ouvrez le terminal, connectez "
            "le compte demo et verifiez que le symbole est visible dans Market Watch."
        )
        print(
            "Le sweep ne se rabat PAS sur des donnees synthetiques : classer des "
            "parametres sur du bruit n'a aucune valeur."
        )
        sys.exit(2)
    print(f"{len(df)} bougies M1 {cfg.symbol}")
    sweep(df, 0.00012)
