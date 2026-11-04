"""Logique de market making : indicateurs + signaux, independante de l'execution.

Utilisee par le live (engine) et le backtest, sur des DataFrames paires OHLCV
columns: time, open, high, low, close, spread(optional)

Colonne 'signal' enrichie :
  - bid_price, ask_price : prix de cotation (bas sur mid + spread/2 +/- skew)
  - action : 1 = passer ordre BUY limit au bid, -1 = passer ordre SELL limit au ask, 0 = rien
  - inventory : position nette actuelle (lots)

La strategie est calculee a la cloture de la bougie (pas d'anti-anticipation).
"""
import pandas as pd
import numpy as np

def add_market_making_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["spread_points"] = ((df["ask"] - df["bid"]) / df["mid"]).abs() * 10000
    if "spread_points" in df.columns and df["spread_points"].std() > 100:
        pass
    df["vol_pct"] = df["close"].pct_change(getattr(cfg, "lookback", 5)).abs().fillna(0) * 100.0
    return df

def mm_signals(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Signaux de market making enrichis.

    Colonnes ajoutees :
      - bid_price : prix où on cite l'achat (limit sur bid)
      - ask_price : prix où on cite la vente (limit sur ask)
      - action : 1 = acheter au bid, -1 = vendre à l'ask, 0 = rien
      - inventory : position nette du bot (lots)
      - spread_quote : spread cité par le bot (points)

    Logique :
      - On cite toujours dans le spread (bid < ask)
      - Si inventory > max_inv_lots -> on augmente l'ask (décourage les achats)
      - Si inventory < -max_inv_lots -> on baisse le bid (décourage les ventes)
      - Si spread reel > max_spread_points -> on ne cite pas (sortie)
      - Si volatilité hors plage -> on ne cite pas
    """
    # Preserve existing vol_pct if provided (backtest passes it), otherwise compute from data
    existing_vol_pct = df["vol_pct"].iloc[-1] if "vol_pct" in df.columns and not pd.isna(df["vol_pct"].iloc[-1]) else None
    
    df = add_market_making_indicators(df, cfg)
    # Restore original vol_pct if it was provided (avoids recalculation giving 0 for single bar)
    if existing_vol_pct is not None:
        df["vol_pct"] = existing_vol_pct
    df["inventory"] = 0.0
    df["mid"] = df["mid"].fillna(df["close"])
    last_mid = df["mid"].iloc[-1] if len(df) > 0 else df["close"].iloc[-1]
    spread_real = df["spread_points"].iloc[-1] if "spread_points" in df.columns and not pd.isna(df["spread_points"].iloc[-1]) else getattr(cfg, "inner_spread_points", 8)
    vol_pct = df["vol_pct"].iloc[-1] if "vol_pct" in df.columns and not pd.isna(df["vol_pct"].iloc[-1]) else 0.0
    min_vol = getattr(cfg, "min_volatility_pct", 0.0)
    max_vol = getattr(cfg, "max_volatility_pct", 5.0)
    if spread_real > getattr(cfg, "max_spread_points", 20):
        df["bid_price"] = float("nan")
        df["ask_price"] = float("nan")
        df["action"] = 0
        df["spread_quote"] = float("nan")
        df["inventory"] = 0.0
        return df
    if vol_pct > max_vol or vol_pct < min_vol:
        df["bid_price"] = float("nan")
        df["ask_price"] = float("nan")
        df["action"] = 0
        df["spread_quote"] = float("nan")
        df["inventory"] = 0.0
        return df
    inv = df["inventory"].iloc[-1]
    skew_offset_bid = 0.0
    skew_offset_ask = 0.0
    if inv > cfg.max_inv_lots:
        skew_offset_ask = min(inv - cfg.max_inv_lots, 10) * cfg.skew_price_offset_points
        skew_offset_bid = -min(inv - cfg.max_inv_lots, 10) * cfg.skew_price_offset_points
    elif inv < -cfg.max_inv_lots:
        skew_offset_ask = min(-inv - cfg.max_inv_lots, 10) * cfg.skew_price_offset_points
        skew_offset_bid = -min(-inv - cfg.max_inv_lots, 10) * cfg.skew_price_offset_points
    else:
        skew_offset_ask = 0.0
        skew_offset_bid = 0.0
    half_spread = cfg.inner_spread_points / 2.0
    bid_price = last_mid - half_spread * last_mid * 0.0001 + skew_offset_bid * last_mid * 0.0001
    ask_price = last_mid + half_spread * last_mid * 0.0001 + skew_offset_ask * last_mid * 0.0001
    if bid_price >= ask_price:
        ask_price = bid_price + cfg.inner_spread_points * last_mid * 0.0001 + 1e-6
    action = 0
    if not pd.isna(bid_price) and not pd.isna(ask_price):
        action = 0
    df["bid_price"] = bid_price
    df["ask_price"] = ask_price
    df["action"] = action
    df["spread_quote"] = cfg.inner_spread_points
    return df
