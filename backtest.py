"""Backtesteur du scalper momentum.

Donnees : MT5 si le terminal est connecte, sinon random-walk synthetiques
(la boucle de verification fonctionne sans terminal).
- signaux calcules a la cloture (pas d'anti-anticipation)
- execution a la bougie suivante : frais = spread parametre
- risque : lot = risk_per_trade du solde, SL = sl_atr_mult x ATR

Usage :
  python backtest.py                    # synthetique si terminal absent
  python backtest.py --symbol EURUSDm
"""
import argparse
import math
import sys
import os

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config, TF_MAP
from strategy import signals


def synth_rates(bars: int = 5000, start_price: float = 1.0800) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    # random walk avec tendance + clusters de volatilite (mieux que du bruit pur)
    vol = np.abs(rng.normal(0, 0.00012, bars)) + 0.00003
    steps = rng.normal(0, 1, bars) * vol + 0.0000012
    close = start_price + np.cumsum(steps)
    spread = 0.00012  # ~1.2 pips sur EURUSD
    high = close + np.abs(rng.normal(0, vol / 2))
    low = close - np.abs(rng.normal(0, vol / 2))
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=bars, freq="1min"),
        "open": np.r_[close[0], close[:-1]],
        "high": np.maximum(high, np.r_[close[0], close[:-1]]),
        "low": np.minimum(low, np.r_[close[0], close[:-1]]),
        "close": close,
        "spread_points": np.full(bars, 15),
    })


def mt5_rates(cfg: Config, bars: int) -> pd.DataFrame | None:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    if not mt5.initialize():
        return None
    mt5.symbol_select(cfg.symbol, True)  # active le symbole dans Market Watch
    rates = mt5.copy_rates_from_pos(cfg.symbol, TF_MAP[cfg.timeframe_str], 0, bars)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["spread_points"] = 15
    return df


def run_backtest(df: pd.DataFrame, cfg: Config, spread_price: float) -> dict:
    sig = signals(df, cfg)
    entry = sig["signal"].shift(1).fillna(0)   # execute a la bougie suivante
    atr = sig["atr"].shift(1)
    o = df["open"]  # execute a l'ouverture de la bougie suivante

    balance = 1.0
    peak = 1.0
    max_dd = 0.0
    wins = losses = 0
    in_pos = False
    pos_dir = 0
    pos_age = 0
    entry_px = sl = tp = 0.0
    trades = []

    for i in range(len(df)):
        if in_pos:
            dirpx = 1 if pos_dir == 1 else -1
            pos_age += 1
            exit_px = None
            if pos_dir == 1:
                if df["low"][i] <= sl:
                    exit_px = sl
                elif df["high"][i] >= tp:
                    exit_px = tp
            else:
                if df["high"][i] >= sl:
                    exit_px = sl
                elif df["low"][i] <= tp:
                    exit_px = tp
            # time-out : coupe a la cloture apres N bougies sans resolution
            if exit_px is None and cfg.exit_timeout_bars and pos_age >= cfg.exit_timeout_bars:
                exit_px = df["close"][i] - spread_price * dirpx  # sortie au spread
            if exit_px is not None:
                pnl_per_unit = dirpx * (exit_px - entry_px) / entry_px
                risk_frac = cfg.risk_per_trade
                sl_pct = cfg.sl_atr_mult * float(atr[i - 1]) / entry_px
                r = pnl_per_unit / sl_pct if sl_pct > 0 else 0.0
                ret = risk_frac * r
                balance *= 1 + ret
                if ret > 0:
                    wins += 1
                else:
                    losses += 1
                trades.append(ret)
                in_pos = False
        if not in_pos and entry[i] != 0 and not math.isnan(atr[i - 1]) and atr[i - 1] > 0:
            pos_dir = int(entry[i])
            entry_px = o[i] + spread_price * (1 if pos_dir == 1 else -1)
            sl_dist = cfg.sl_atr_mult * float(atr[i - 1])
            tp_dist = cfg.tp_atr_mult * float(atr[i - 1])
            sl = entry_px - sl_dist if pos_dir == 1 else entry_px + sl_dist
            tp = entry_px + tp_dist if pos_dir == 1 else entry_px - tp_dist
            pos_age = 0
            in_pos = True
        peak = max(peak, balance)
        max_dd = max(max_dd, 1 - balance / peak)

    n = wins + losses
    gross_w = sum(t for t in trades if t > 0)
    gross_l = abs(sum(t for t in trades if t < 0)) or 1e-9
    return {
        "bougies": len(df),
        "trades": n,
        "gagnants": wins,
        "taux_reussite": round(wins / n * 100, 1) if n else 0.0,
        "profit_factor": round(gross_w / gross_l, 2) if n else 0.0,
        "rendement_pct": round((balance - 1) * 100, 1),
        "max_drawdown_pct": round(max_dd * 100, 1),
        "solde_final_10USD": round(10 * balance, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--bars", type=int, default=5000)
    args = ap.parse_args()

    cfg = Config(symbol=args.symbol)
    df = mt5_rates(cfg, args.bars)
    source = f"MT5 {cfg.symbol}"
    if df is None:
        df = synth_rates(args.bars)
        source = "SYNTHETIQUE (terminal MT5 non connecte) - resultats non fiables pour le reel"
        cfg.symbol = "SYNTH"

    spread_price = 0.00012 if cfg.symbol in ("EURUSD", "SYNTH") else 0.0002
    stats = run_backtest(df, cfg, spread_price)
    print(f"Source : {source}")
    for k, v in stats.items():
        print(f"  {k:>20} : {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
