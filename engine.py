"""Moteur live : boucle de polling MT5, exécution des ordres, gestion SL/TP.

Démo uniquement tant que les backtests ne sont pas validés.
"""
import sys
import time

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # le module n'existe que sous Windows avec MT5 installé

from config import Config, TF_MAP
from risk import RiskManager
from strategy import signals

ORDER_FILL_MODES = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN] if mt5 else []
ACCOUNT_MODES = {0: "DEMO", 1: "CONCOURS", 2: "REEL"}


def connect(cfg: Config) -> bool:
    if mt5 is None:
        print("Module MetaTrader5 absent : pip install MetaTrader5 (Windows + terminal MT5 requis)")
        return False
    ok = mt5.initialize(path=cfg.mt5_terminal_path) if cfg.mt5_terminal_path else mt5.initialize()
    if not ok:
        print(f"Echec connexion MT5 : {mt5.last_error()}")
        return False
    acc = mt5.account_info()
    if acc is None:
        print("Aucun compte charge dans le terminal : ouvrez MT5 et connectez un COMPTE DEMO.")
        return False

    mode = ACCOUNT_MODES.get(acc.trade_mode, f"inconnu({acc.trade_mode})")
    print(f"Compte #{acc.login} | type={mode} | solde={acc.balance:.2f} {acc.currency}")

    # Garde-fou : le README interdit le reel tant que les backtests sont perdants.
    if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL and not cfg.allow_real_trading:
        print("[STOP] Compte REEL detecte. Ce bot n'est valide qu'en demo : "
              "passez allow_real_trading=True dans config.py pour forcer.")
        return False

    term = mt5.terminal_info()
    if term is not None and not term.trade_allowed:
        print("[ATTENTION] Trading algorithmique desactive dans le terminal : activez le bouton "
              "'Algo Trading' (Outils -> Options -> Expert Advisors), sinon tout ordre sera refuse.")
    return True


def get_rates(cfg: Config, count: int = 300) -> pd.DataFrame | None:
    tf = TF_MAP[cfg.timeframe_str]
    if mt5.symbol_info_tick(cfg.symbol) is None and not mt5.symbol_select(cfg.symbol, True):
        print(f"Symbole {cfg.symbol} introuvable")
        return None
    rates = mt5.copy_rates_from_pos(cfg.symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        print(f"Pas de donnees pour {cfg.symbol}: {mt5.last_error()}")
        return None
    df = pd.DataFrame(rates)
    # L'objet Tick n'expose PAS de champ 'spread' (seulement bid/ask/last/volume) :
    # le spread en points vient des bougies renvoyees par copy_rates_from_pos.
    df["spread_points"] = df["spread"] if "spread" in df.columns else 0
    return df


def _try_order_send(request):
    """Envoie l'ordre en essayant les modes d'execution du broker."""
    res = None
    for mode in ORDER_FILL_MODES:
        request["type_filling"] = mode
        res = mt5.order_send(request)
        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
            return res
    if res is None:
        print(f"Ordre refuse : order_send a renvoye None | last_error={mt5.last_error()}")
        return None
    # res.comment porte la raison reelle du refus. NE PAS se fier a
    # mt5.last_error() ici : il renvoie (1, 'Success') alors meme que l'ordre
    # vient d'etre refuse (constate avec le retcode 10027).
    print(f"Ordre refuse : retcode={res.retcode} ({res.comment})")
    if res.retcode == mt5.TRADE_RETCODE_CLIENT_DISABLES_AT:
        print("  -> activez le bouton 'Algo Trading' dans le terminal MT5.")
    return None


def place_order(cfg: Config, direction: int, atr: float, balance: float, rm: RiskManager) -> bool:
    tick = mt5.symbol_info_tick(cfg.symbol)
    info = mt5.symbol_info(cfg.symbol)
    if tick is None or info is None:
        return False

    # tick.spread n'existe pas dans l'API MT5 : le spread courant en points est
    # expose par symbol_info().
    if info.spread > cfg.max_spread_points:
        return False

    sl_dist = rm.hedge_distance(atr)
    tick_size = info.trade_tick_size or info.point
    tick_value = info.trade_tick_value
    lot = rm.position_size(balance, sl_dist, tick_value, tick_size)
    lot = min(lot, info.volume_max)
    if lot < info.volume_min:
        return False

    price = tick.ask if direction == 1 else tick.bid
    if direction == 1:
        sl = price - sl_dist
        tp = price + atr * cfg.tp_atr_mult
        order_type = mt5.ORDER_TYPE_BUY
    else:
        sl = price + sl_dist
        tp = price - atr * cfg.tp_atr_mult
        order_type = mt5.ORDER_TYPE_SELL

    digits = info.digits
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": cfg.symbol,
        "volume": round(lot, 2),
        "type": order_type,
        "price": round(price, digits),
        "sl": round(sl, digits),
        "tp": round(tp, digits),
        "deviation": 10,
        "magic": cfg.magic,
        "comment": cfg.comment,
    }
    res = _try_order_send(request)
    if res is not None:
        rm.trades_today += 1
        print(f"-> {'BUY' if direction == 1 else 'SELL'} lot={lot} sl={sl:.{digits}f} tp={tp:.{digits}f}")
        return True
    return False


def open_positions_count(cfg: Config) -> int:
    positions = mt5.positions_get(symbol=cfg.symbol)
    if positions is None:
        return 0
    return sum(1 for p in positions if p.magic == cfg.magic)


def close_older_than(cfg: Config, max_bars: int):
    """Ferme les positions ouvries plus longtemps que max_bars x timeframe."""
    positions = mt5.positions_get(symbol=cfg.symbol)
    if not positions:
        return
    tf_minutes = TF_MAP[cfg.timeframe_str]
    if cfg.timeframe_str.startswith("M") and tf_minutes < 60:
        seconds = tf_minutes * 60 * max_bars
    else:
        seconds = tf_minutes * max_bars  # H/D en heures/jours approx via constantes
    now = time.time()
    for p in positions:
        if p.magic != cfg.magic:
            continue
        if now - p.time > seconds:
            tick = mt5.symbol_info_tick(cfg.symbol)
            if tick is None:
                continue
            opposite = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": p.ticket,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": opposite,
                "price": price,
                "deviation": 10,
                "magic": cfg.magic,
                "comment": cfg.comment + "_timeout",
            }
            res = _try_order_send(request)
            if res is not None:
                print(f"-> TIMEOUT close ticket {p.ticket} apres {max_bars} barres")


def run(cfg: Config):
    rm = RiskManager(cfg)
    if not connect(cfg):
        return 1
    try:
        while True:
            acc = mt5.account_info()
            if acc is None:
                break
            rm.reset_day_if_needed(acc.balance)
            if not rm.can_trade(acc.balance)[0]:
                print("[STOP] " + rm.can_trade(acc.balance)[1])
                break

            df = get_rates(cfg)
            if df is None:
                time.sleep(cfg.poll_seconds)
                continue

            close_older_than(cfg, cfg.exit_timeout_bars)

            last_closed = signals(df.iloc[:-1], cfg).iloc[-1]  # bougie fermee uniquement
            if open_positions_count(cfg) >= cfg.max_positions:
                time.sleep(cfg.poll_seconds)
                continue

            if last_closed["signal"] != 0 and not pd.isna(last_closed["atr"]):
                place_order(cfg, int(last_closed["signal"]), float(last_closed["atr"]), acc.balance, rm)

            time.sleep(cfg.poll_seconds)
    except KeyboardInterrupt:
        print("Arret demandé (Ctrl+C)")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(run(Config()))
