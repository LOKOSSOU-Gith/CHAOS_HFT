"""Configuration du bot scalper momentum - MetaTrader 5."""
from dataclasses import dataclass

@dataclass
class Config:
    # Marché
    symbol: str = "EURUSDm"  # suffixe "m" = broker micro (vérifier dans Market Watch)
    timeframe_str: str = "M1"

    # Paramètres stratégie scalping momentum
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    momentum_lookback: int = 5          # nb de bougies pour mesurer le momentum
    # Variation % minimale sur le lookback (filtre d'entree).
    # IMPORTANT : cette valeur doit rester dans la plage reellement balayee par
    # sweep.py (0.003 / 0.006 / 0.01). Avec 0.03, la configuration utilisee par
    # engine.py et backtest.py n'avait jamais ete testee (10x le max du sweep).
    min_momentum_pct: float = 0.006

    # Exécution du trade
    sl_atr_mult: float = 1.0            # stop-loss = 1 x ATR
    tp_atr_mult: float = 1.5            # take-profit = 1.5 x ATR (ratio R:R 1.5)
    max_positions: int = 1
    max_spread_points: int = 15         # refuse d'entrer si spread > 15 points

    # Risque (obligatoire pour les 10$)
    risk_per_trade: float = 0.02        # 2% du solde par trade
    daily_loss_limit_pct: float = 0.10  # stop le bot si -10% dans la journée
    max_trades_per_day: int = 30
    exit_timeout_bars: int = 30         # coupe la position apres N bougies si SL/TP pas touches
    volume_min: float = 0.01            # lot minimum

    # Divers
    magic: int = 860001
    comment: str = "hft_scalper_demo"
    poll_seconds: float = 2.0           # rythme de la boucle live
    mt5_terminal_path: str = ""         # chemin du terminal64.exe si auto-détection échoue

    # Garde-fou : le bot refuse de trader un compte REEL (cf. README) tant que
    # cette option reste False.
    allow_real_trading: bool = False


TF_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
}
