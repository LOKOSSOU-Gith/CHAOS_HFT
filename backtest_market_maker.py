"""Backtesteur du market making Python.

Simule la cotation bid/ask, le remplissage d'ordres, les coûts de spread
et le PnL lié à l'inventaire (skew).

Usage :
  python backtest_market_maker.py           # synthétique
  python backtest_market_maker.py --symbol EURUSDm  # données réelles MT5
"""

import argparse
import math
import sys
import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config, TF_MAP
from strategy_market_maker import mm_signals


def synth_rates(bars: int = 5000, start_price: float = 1.1178,
                spread_pip: float = 1.2, vol_pct_range = (0.01, 0.5)) -> pd.DataFrame:
    """Générer des données synthétiques de type tick/M1 pour le backtest MM.

    Inclut : bid/ask avec spread, mid, volatilité, et événements de news.
    """
    rng = np.random.default_rng(42)
    # Prix de départ
    mid = start_price
    # Parameters
    spread_points = spread_pip  # spread fixe en points pour simplifier
    # Générer une marche aléatoire pour le mid
    n = bars
    steps = rng.normal(0, spread_pip/10000, n)  # petits pas autour du mid
    mid_path = np.cumsum(steps) + mid
    # Générer bid/ask autour du mid avec le spread
    bid = mid_path - spread_points/10000/2  # soulever moitié spread
    ask = mid_path + spread_points/10000/2
    # Ajouter un peu de bruit de spread
    spread_noise = rng.uniform(0, 0.2, n)  # variation du spread
    # Add randomness to low/high around mid
    high_noise = rng.uniform(0, spread_points/10000 * 0.5, n)  # moitié spread pour le high
    low_noise = -rng.uniform(0, spread_points/10000 * 0.5, n)  # moitié spread pour le low
    bid = mid_path - (spread_points + spread_noise)/10000/2
    ask = mid_path + (spread_points + spread_noise)/10000/2
    high = ask + high_noise  # slightly above ask
    low = bid + low_noise  # slightly below bid
    # Volatilité % sur fenêtre glissante
    vol_window = 50
    returns = np.diff(mid_path, prepend=mid_path[0])
    vol_pct = pd.Series(returns).rolling(vol_window).mean().abs().fillna(0) * 100.0
    # Events de 'news' occasionnels (volatilité qui monte)
    news_indices = rng.choice(n, size=max(1, n//200), replace=False)
    for idx in news_indices:
        # Choc de volatilité +5%
        vol_pct.iloc[idx:min(idx+10, n)] *= 1.5
        # Et spread qui s'élargit
        spread_points *= 1.5 if idx < n-1 else 1
    # S'assurer que spread ne devient pas négatif
    spread_points = max(spread_points, 0.5)

    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="1min"),
        "bid": bid,
        "ask": ask,
        "high": high,
        "low": low,
        "close": mid_path,
        "spread_points": spread_points,
        "vol_pct": vol_pct,
    })


def get_mt5_rates(symbol: str = "EURUSDm", timeframe: int = 1,
                  bars: int = 500) -> pd.DataFrame:
    """Récupérer des données de marché réelles depuis MetaTrader5 (timeframe par défaut = M1).

    Returns DataFrame avec colonnes: time, open, high, low, close, spread, vol_pct
    """
    import MetaTrader5 as mt5
    mt5.initialize()

    # Calculer la date de fin (maintenant) et le début (bars minutes auparavant)
    end_time = datetime.now()
    # Chaque bar M1 = 1 minute, donc bars minutes en arrière
    start_time = end_time - timedelta(minutes=bars + 50)  # un peu de marge

    rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)

    if rates is None or len(rates) == 0:
        raise ValueError(f"Aucune donnée récupérée depuis MT5 pour {symbol}")

    df = pd.DataFrame(rates)
    # MT5 retourne des timestamps Unix en secondes, convertir en datetime
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Calculer la volatilité % sur fenêtre glissante
    vol_window = 50
    returns = df['close'].pct_change()
    df['vol_pct'] = pd.Series(returns).rolling(vol_window).mean().abs().fillna(0) * 100.0

    # Calculer spread en points
    df['spread_points'] = df['spread']  # MT5 spread est déjà en points

    # Sélectionner les colonnes nécessaires
    df = df[['time', 'open', 'high', 'low', 'close', 'spread_points', 'vol_pct']]

    # Renommer open/bid et close pour compatibilité
    df = df.rename(columns={'open': 'bid'})

    # Approximer bid/ask à partir de open et spread
    df['ask'] = df['bid'] + df['spread_points'] / 10000

    # S'assurer que high/low couvrent bid/ask
    df['high'] = df[['bid', 'ask']].max(axis=1)
    df['low'] = df[['bid', 'ask']].min(axis=1)

    return df


def run_mm_backtest(df: pd.DataFrame, cfg: Config) -> dict:
    """Backtest du market making.

    Boucle bar par bar :
      - Calculer bid/ask et signaux MM
      - Passer ordres limites (buy at bid, sell at ask)
      - Simulation de remplissage : prix exécuté = ask si on achetait au bid, etc.
      - Frais de spread à chaque aller-retour
      - Inventory PnL : si on finit avec une position, on porte le coût du spread non réalisé
      - À la fin, on vérifie si on est flat (inventory ≈ 0) ou pas

    Retourne un dict de statistiques.
    """
    # Initialisation
    n = len(df)
    if n == 0:
        return {"erreurs": "DataFrame vide"}

    # Paramètres MM depuis cfg
    inner_spread = cfg.inner_spread_points
    max_inv = cfg.max_inv_lots
    vol_min = cfg.min_volatility_pct
    vol_max = cfg.max_volatility_pct
    max_spread = cfg.max_spread_points

    # État
    inventory = 0.0  # lots nets (positif = long, négatif = short)
    balance = 1.0  # en unités de 10$ later
    balance_peak = 1.0
    max_dd = 0.0
    trades = 0
    wins = 0  # trades avec PnL positif (couverture spread)
    losses = 0  # trades avec PnL négatif
    spread_costs = 0.0
    inventory_pnl = 0.0
    order_queue = []  # ordres en cours : [{type, price, filled, entry_inventory}]

    # Track PnL par bar pour courbe
    pnl_history = [1.0]

    for i in range(n):
        bar = df.iloc[i]
        bid = bar["bid"]
        ask = bar["ask"]
        mid = (bid + ask) / 2
        spread_pts = bar["spread_points"]
        vol = bar["vol_pct"]

        # Filtres de marché
        if vol < vol_min or vol > vol_max or spread_pts > max_spread:
            # Marché hors conditions : pas de cotation, laisser orders expirer
            pass

        # 1. Mettre à jour les ordres en cours (simuler remplissage)
        filled = []
        for o in order_queue:
            if o["type"] == "BUY_LIMIT" and bar["low"] <= o["price"]:
                # Rempli au prix du marché (bid approximatif)
                fill_px = max(bid, o["price"])
                # PnL : acheter au bid et on porte le spread
                # On achète au bid (plus bas) mais la position est longue
                # Le coût est le spread que l'on réalisera quand on vendra à l'ask
                pnl_from_trade = -spread_pts / 10000
                inventory += o["volume"]  # devient long
                o["filled"] = True
                o["pnl"] = pnl_from_trade
                filled.append(o)
                trades += 1
            elif o["type"] == "SELL_LIMIT" and bar["high"] >= o["price"]:
                fill_px = min(ask, o["price"])
                # Vendre au ask : on prélève le spread
                pnl_from_trade = spread_pts / 10000  # gain spread realized
                inventory -= o["volume"]  # réduit/réverse la position
                o["filled"] = True
                o["pnl"] = pnl_from_trade
                filled.append(o)
                trades += 1

        order_queue = [o for o in order_queue if not o["filled"]]

        # 2. Calculer les signaux MM pour cette bar
        # Include vol_pct so mm_signals can use it (avoids recalc to 0 for single bar)
        signal_df = pd.DataFrame({
            "bid": [bid],
            "ask": [ask],
            "close": [mid],
            "spread_points": [spread_pts],
            "inventory": [inventory],
            "vol_pct": [vol],  # already computed from bar data above
        })
        signal_df = mm_signals(signal_df, cfg)

        bid_price = signal_df["bid_price"].iloc[0]
        ask_price = signal_df["ask_price"].iloc[0]
        action = signal_df["action"].iloc[0]

        # 3. Décider des actions selon le signal et l'état
        # Règle MM : si pas d'ordre en cours et conditions OK, passer les deux côtés
        if not pd.isna(bid_price) and not pd.isna(ask_price) and action == 0:
            volume = max(cfg.volume_min, min(1.0, (cfg.risk_per_trade * balance) / max(spread_pts/10000, 0.0001)))
            volume = max(volume, cfg.volume_min)

            # Acheter au bid
            order_queue.append({
                "type": "BUY_LIMIT",
                "price": bid_price,
                "volume": volume,
                "entry_inventory": inventory,
                "filled": False,
            })

            # Vendre à l'ask
            order_queue.append({
                "type": "SELL_LIMIT",
                "price": ask_price,
                "volume": volume,
                "entry_inventory": inventory,
                "filled": False,
            })

        # 5. Calculer le PnL de la journée
        iteration_pnl = sum(o.get("pnl", 0) for o in filled)
        balance *= 1 + iteration_pnl
        balance_peak = max(balance_peak, balance)
        max_dd = max(max_dd, 1 - balance / balance_peak)

        # 6. PnL lié à l'inventaire non couvert
        # Si on finit la barre avec une inventory non nulle, on porte le coût du spread
        if True:
            # Coût de porter l'inventaire : coût du spread non réalisé
            # Hypothèse : si on est long, on a acheté au bid, on devra vendre à l'ask plus tard
            # Coût approximatif = inventory * spread moyen / 10000
            carry_pnl = -inventory * (spread_pts / 10000) * 0.5  # factor 0.5 car pas tout le spread à chaque barre
            inventory_pnl += carry_pnl

        pnl_history.append(balance)

    # Résultats finaux
    # Forcer la sortie d'inventaire à prix du marché final
    final_mid = df["close"].iloc[-1]
    final_bid = final_mid - (cfg.inner_spread_points/10000/2)
    final_ask = final_mid + (cfg.inner_spread_points/10000/2)

    # Vendre toute position finale au mid
    final_inventory_pnl = -inventory * (final_ask - final_bid) / final_mid  # réalisation spread final
    balance += final_inventory_pnl
    inventory = 0.0  # plat à la fin

    gross_wins = wins
    gross_losses = losses
    pf = round(gross_wins / max(gross_losses, 1e-9), 2) if trades else 0.0

    win_rate = round(wins / max(trades, 1) * 100, 1) if trades else 0.0

    return {
        "bougies": n,
        "trades": trades,
        "taux_reussite": win_rate,
        "profit_factor": pf,
        "rendement_pct": round((balance - 1) * 100, 1),
        "max_drawdown_pct": round(max_dd * 100, 1),
        "solde_final_10USD": round(10 * balance, 2),
        "inventory_exposure_lots": round(abs(inventory), 2),
        "spread_costs_total": round(spread_costs, 6),
        "inventory_pnl": round(inventory_pnl, 6),
        "strategie": "market_making_python",
    }


def main():
    ap = argparse.ArgumentParser(description="Backtest Market Making Python")
    ap.add_argument("--symbol", default="EURUSDm")
    ap.add_argument("--bars", type=int, default=500)
    ap.add_argument("--real", action="store_true", help="Utiliser des données réelles MT5")
    args = ap.parse_args()

    cfg = Config(symbol=args.symbol)
    cfg.inner_spread_points = 8
    cfg.max_inv_lots = 3.0
    cfg.max_spread_points = 20
    cfg.min_volatility_pct = 0.0001
    cfg.max_volatility_pct = 5.0
    cfg.llm_enabled = False

    if args.real:
        # Utiliser des données réelles MT5
        df = get_mt5_rates(args.symbol, bars=args.bars)
        print(f"Backtest Market Making - Données réelles MT5 - {args.symbol}")
        print(f"Bougies récupérées: {len(df)}")
    else:
        # Utiliser des données synthétiques
        df = synth_rates(args.bars)

    print(f"Backtest Market Making - {len(df)} barres")
    print(f"Spread intérieur cité: {cfg.inner_spread_points} points")
    print()

    stats = run_mm_backtest(df, cfg)
    for k, v in stats.items():
        print(f"  {k:>30} : {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())