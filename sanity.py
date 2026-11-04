"""Test de sanite : entrees ALEATOIRES dans le moteur de backtest.

Le but est de valider le MOTEUR (execution, SL/TP, calcul du R, comptage des
gains/perdés), pas la strategie ni le broker. On l'isole donc du spread : avec
des entrees aleatoires et SL = TP, un moteur correct doit rendre ~50%.

Mesure sur EURUSDm M1 (20 000 bougies reelles) :
  spread = 0        -> 49.6% de reussite   -> moteur sain
  spread = 1.2 pips -> 14.6% de reussite   -> normal, ce n'est PAS un bug :
      l'ATR(14) M1 vaut ~1.21 pip, donc le spread du broker (1.2 pip) vaut
      0.88 x ATR : le stop de 1 x ATR est entierement mange par le cout
      d'entree. C'est la raison de fond pour laquelle la strategie perd
      (cf. README), et non un defaut du moteur.

Codes de sortie : 0 = moteur sain, 1 = resultat anormal, 2 = donnees MT5
indisponibles.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config
from backtest import mt5_rates, run_backtest

# Bornes serrees : le moteur doit rendre ~50% avec un spread nul. Elles ne
# servent qu'a detecter un moteur casse, jamais a juger la strategie.
MIN_WIN_RATE = 45.0
MAX_WIN_RATE = 55.0
MIN_TRADES = 100

# Spread realiste du broker, utilise seulement pour l'affichage informatif.
SPREAD_PRICE = 0.00012


def _random_signal_frame(df: pd.DataFrame, atr: pd.Series, seed: int = 7) -> pd.DataFrame:
    """DataFrame avec un signal aleatoire : long dans ~5% des bougies, short 5%."""
    rng = np.random.default_rng(seed)
    rand = rng.random(len(df))
    sig = df.copy()
    sig["signal"] = np.where(rand < 0.05, 1, np.where(rand > 0.95, -1, 0))
    sig["atr"] = atr
    return sig


def _run_with(df, cfg, sig, spread_price: float) -> dict:
    """run_backtest, mais avec les signaux aleatoires a la place de la strategie."""
    import backtest as bt
    orig_signals = bt.signals
    bt.signals = lambda d, c: sig
    try:
        return bt.run_backtest(df, cfg, spread_price)
    finally:
        bt.signals = orig_signals


def main() -> int:
    cfg = Config(symbol="EURUSDm")
    # La docstring suppose SL = TP = 1 ATR : on force explicitement ces valeurs
    # au lieu d'heriter du defaut (tp_atr_mult = 1.5), sinon le taux attendu ne
    # correspond plus a celui annonce ci-dessus.
    cfg.sl_atr_mult = 1.0
    cfg.tp_atr_mult = 1.0

    df = mt5_rates(cfg, 20000)
    if df is None or len(df) == 0:
        print(f"Pas de donnees MT5 pour {cfg.symbol} : test du moteur impossible.")
        return 2

    df = df.reset_index(drop=True)
    atr = (df["high"] - df["low"]).rolling(14, min_periods=1).mean()
    sig = _random_signal_frame(df, atr)

    # 1) Integrite du moteur : spread nul, sinon on mesure le broker et non le code.
    clean = _run_with(df, cfg, sig, 0.0)
    print("=== Sanity check (entrees aleatoires, spread = 0) ===")
    for k, v in clean.items():
        print(f"  {k:>20} : {v}")

    # 2) Pour information : meme test avec le spread reel du broker.
    real = _run_with(df, cfg, sig, SPREAD_PRICE)
    print(
        f"\n(information) avec le spread reel de {SPREAD_PRICE} : "
        f"{real['taux_reussite']}% de reussite sur {real['trades']} trades"
    )
    print("Ce chiffre mesure le cout du broker, pas la sante du moteur.")

    failures = []
    if clean["trades"] < MIN_TRADES:
        failures.append(
            f"seulement {clean['trades']} trades (< {MIN_TRADES}) : echantillon trop faible"
        )
    wr = clean["taux_reussite"]
    if not MIN_WIN_RATE <= wr <= MAX_WIN_RATE:
        failures.append(
            f"taux de reussite {wr}% hors de la plage attendue "
            f"[{MIN_WIN_RATE}%, {MAX_WIN_RATE}%] -> moteur suspect"
        )

    if failures:
        print("\n[ECHEC] " + "\n[ECHEC] ".join(failures))
        return 1
    print(f"\n[OK] moteur coherent ({clean['trades']} trades, {wr}% de reussite)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
