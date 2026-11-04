"""Logique de stratégie : indicateurs + signaux, indépendante de l'exécution.

Utilisée par le live (engine) et le backtest, sur des DataFrames paires OHLCV
columns: time, open, high, low, close, spread(optional)
"""
import pandas as pd


def add_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=cfg.ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=cfg.ema_slow, adjust=False).mean()

    # ATR (average true range)
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(cfg.atr_period, min_periods=1).mean()

    # Momentum : variation % sur les N dernières bougies
    lb = cfg.momentum_lookback
    df["momentum_pct"] = df["close"].pct_change(lb) * 100.0
    return df


def signals(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Colonne 'signal' : 1 = entrée LONG, -1 = entrée SHORT, 0 = rien.

    Logique scalping momentum :
      - croisement EMA rapide au-dessus de la lente + momentum haussier confirmé
      - l'inverse pour le short
    Le signal est calculé à la cloture de la bougie (pas d'anti-anticipation).
    """
    df = add_indicators(df, cfg)

    cross_up = (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1)) & (df["ema_fast"] > df["ema_slow"])
    cross_dn = (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1)) & (df["ema_fast"] < df["ema_slow"])

    mom_up = df["momentum_pct"] > cfg.min_momentum_pct
    mom_dn = df["momentum_pct"] < -cfg.min_momentum_pct

    df["signal"] = 0
    df.loc[cross_up & mom_up, "signal"] = 1
    df.loc[cross_dn & mom_dn, "signal"] = -1
    return df
