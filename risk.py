"""Garde-fous du risque : dimensionnement de lot et limites journalières.

Un solde de 10$ ne pardonne rien : le lot suit le risque réel et une limite
journalière coupe le bot avant que le solde ne fonde.
"""


class RiskManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.trades_today = 0
        self.day_start_balance = None
        self.day_key = None

    def reset_day_if_needed(self, balance):
        """Réinitialise les compteurs quand le jour change."""
        import datetime as dt
        key = dt.date.today().isoformat()
        if key != self.day_key:
            self.day_key = key
            self.trades_today = 0
            self.day_start_balance = balance

    def daily_loss_hit(self, balance) -> bool:
        if self.day_start_balance is None or self.day_start_balance <= 0:
            return False
        loss = (self.day_start_balance - balance) / self.day_start_balance
        return loss >= self.cfg.daily_loss_limit_pct

    def can_trade(self, balance) -> tuple[bool, str]:
        self.reset_day_if_needed(balance)
        if self.daily_loss_hit(balance):
            return False, "limite de perte journaliere atteinte"
        if self.trades_today >= self.cfg.max_trades_per_day:
            return False, "nombre max de trades journalier atteint"
        return True, ""

    def hedge_distance(self, atr: float) -> float:
        """Distance d'arret en unites de prix."""
        return max(atr * self.cfg.sl_atr_mult, 0.0001)

    def position_size(self, balance, sl_distance_price, tick_value_per_lot, tick_size) -> float:
        """Lot adapte au risque : perte au SL = risk_per_trade * balance."""
        if sl_distance_price <= 0 or tick_value_per_lot <= 0 or tick_size <= 0:
            return self.cfg.volume_min
        risk_amount = self.cfg.risk_per_trade * balance
        sl_ticks = sl_distance_price / tick_size
        loss_per_lot = sl_ticks * tick_value_per_lot
        if loss_per_lot <= 0:
            return self.cfg.volume_min
        lot = round(risk_amount / loss_per_lot, 2)
        return max(lot, self.cfg.volume_min)
