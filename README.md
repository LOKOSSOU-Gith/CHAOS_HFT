# HFT Scalper — MetaTrader 5 (démo d'abord)

Scalper momentum sur MT5 Python avec garde-fous pour un solde de 10 $.

## ⚠️ Verdict des backtests honnêtes (obligatoire pour le réel)
Exécuté sur les données réelles de votre broker (compte terminal connecté) :

| Test | Symbole / TF | PF | Rendement | Win% | Verdict |
|---|---|---|---|---|---|
| 36 configs EMA/momentum sur M1 | EURUSDm M1 | 0.08-0.37 | -100% | <27% | ❌ perdant (stop < bruit) |
| 36 configs sur M5 + timeout | EURUSDm M5 | ≤0.81 | -41..-97% | 25-34% | ❌ perdant |
| 4 configs | BTCUSDm M5 | 1.05 (meilleur) | +11.8% | 40% | ⚠️ marginal, DD 46% |

**Conclusion : ne pas brancher les 10 $ en réel avec la config EURUSDm.**
La seule piste néanmoins légèrement positive est BTCUSDm M5 (EMA 9/21, SL 2×ATR, TP 3×ATR),
mais un drawdown de 46% sur 10 $ est inacceptable sans démo/validation plus longue.

## ⚠️ Réalité du HFT à 10 $
Vrai HFT = colocation + microsecondes + ordonnanceur. En retail, cela restera
du scalping M1/M5, où le spread du broker 'm' (micro) mange la stratégie.

**Chiffré sur EURUSDm M1 :** ATR(14) = **1.21 pip** contre un spread de **1.2 pip**,
soit **0.88 x ATR**. Un stop de 1 x ATR est donc entièrement payé en frais d'entrée
avant même que le marché ne bouge. Avec des entrées aléatoires et SL = TP, le taux
passe de **49.6 %** (spread nul) à **14.6 %** (spread réel) : la perte n'est pas un
bug du moteur (`sanity.py` le prouve), c'est le coût du broker.

## Fichiers
- `config.py` — paramètres, risque, symbole (`symbol = "EURUSDm"`, suffixe 'm')
  - `min_momentum_pct` doit rester dans la plage balayée par `sweep.py` (0.003–0.01),
    sinon la config tradée en live n'est pas celle qui a été testée
- `strategy.py` — EMA fast/slow + ATR + momentum filtre + signaux sans anti-anticipation
- `risk.py` — lot calcule pour risque %, limite journalière -10%, max 30 trades/j
- `engine.py` — boucle live, spread filter, SL/TP + timeout de position
- `backtest.py` — backtest (MT5 si terminal ouvert, sinon synthétique), frais = spread
- `sweep.py` — grille de réglages
- `sanity.py` — entrées aléatoires, valide le **moteur** et non la stratégie : ~50 %
  attendu avec un spread nul (49.6 % mesuré). Sort en code 1 si le moteur dérive,
  2 si MT5 est indisponible.

## Installation
```bash
pip install -r requirements.txt
```
Dans MT5 : ouvrir un **compte démo**, autoriser le trading algorithmique
(Outils → Options → Expert Advisors).

## Utilisation
```bash
cd hft_bot
python backtest.py --symbol BTCUSDm      # valeurs de backtest reelles si le terminal est ouvert
python sweep.py                          # grille de reglages EURUSDm M1
python engine.py                         # boucle live DEMO (Ctrl+C pour arreter)
```

## Étape suivante pour que ça vaille quelque chose
1. Démo avec BTCUSDm M5 (meilleure config) pendant 2-4 semaines → evidence avant réel.
2. Explorer mean-reversion (revenir au prix moyen sur extrêmes d'ATR) au lieu du momentum.
3. Augmenter l'historique (plusieurs mois, plusieurs régimes de marché) avant de parler de réel.
