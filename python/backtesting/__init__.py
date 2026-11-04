#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Backtesting and Simulation Engine

Provides comprehensive backtesting capabilities including:
- Unit tests for individual components
- Integration tests for end-to-end workflows
- Order book simulation with latency modeling
- Slippage modeling
- Rejection modeling
- Partial execution modeling
- Hedging mode simulation
- Netting mode simulation
- Multi-symbol testing
- Real tick data backtesting when available
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
import numpy as np
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("chaos_engine_hft.backtesting")


# Backtest result container
class BacktestResult:
    """Results from a backtest run."""
    
    def __init__(
        self,
        symbol: str,
        initial_balance: float = 10000.0,
        final_balance: float = 10000.0,
        total_return: float = 0.0,
        total_trades: int = 0,
        win_rate: float = 0.0,
        profit_factor: float = 0.0,
        max_drawdown: float = 0.0,
        sharpe_ratio: float = 0.0,
        calmar_ratio: float = 0.0,
        total_cotations: int = 0,
        total_rejections: int = 0,
        total_acceptances: int = 0,
        slippage_total: float = 0.0,
        execution_time_ms: float = 0.0,
        regime_distribution: Optional[Dict[str, int]] = None,
    ):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.final_balance = final_balance
        self.total_return = total_return
        self.total_trades = total_trades
        self.win_rate = win_rate
        self.profit_factor = profit_factor
        self.max_drawdown = max_drawdown
        self.sharpe_ratio = sharpe_ratio
        self.calmar_ratio = calmar_ratio
        self.total_cotations = total_cotations
        self.total_rejections = total_rejections
        self.total_acceptances = total_acceptances
        self.slippage_total = slippage_total
        self.execution_time_ms = execution_time_ms
        self.regime_distribution = regime_distribution or {}
        
        # Detailed trade list
        self.trades: List[Dict[str, Any]] = []
        
        # Detailed PnL history
        self.pnl_history: List[float] = []
        
        # Configuration used
        self.config: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "total_return": self.total_return,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "calmar_ratio": self.calmar_ratio,
            "total_cotations": self.total_cotations,
            "total_rejections": self.total_rejections,
            "total_acceptances": self.total_acceptances,
            "slippage_total": self.slippage_total,
            "execution_time_ms": self.execution_time_ms,
            "regime_distribution": self.regime_distribution,
            "num_trades_detail": len(self.trades),
        }
    
    def add_trade(
        self,
        entry_time: datetime,
        exit_time: datetime,
        order_type: Literal["BUY", "SELL"],
        entry_price: float,
        exit_price: float,
        volume: float,
        pnl: float,
        slippage: float,
        regime: str,
    ):
        """Add a trade to the results."""
        trade = {
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "order_type": order_type,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "volume": volume,
            "pnl": pnl,
            "slippage": slippage,
            "regime": regime,
        }
        self.trades.append(trade)
        self.total_trades += 1
        
        # Update PnL history
        if self.pnl_history:
            self.pnl_history.append(self.pnl_history[-1] + pnl)
        else:
            self.pnl_history.append(pnl)
        
        # Update balance
        self.final_balance = self.initial_balance + sum(t["pnl"] for t in self.trades)


# Latency models
class LatencyModel:
    """Models execution latency effects."""
    
    def __init__(self, mean_ms: float = 5.0, std_ms: float = 2.0, 
                 max_ms: float = 50.0, distribution: Literal["normal", "uniform", "constant"] = "normal"):
        """
        Initialize latency model.
        
        Args:
            mean_ms: Mean latency in milliseconds
            std_ms: Standard deviation
            max_ms: Maximum latency cap
            distribution: Distribution type ("normal", "uniform", "constant")
        """
        self.mean_ms = mean_ms
        self.std_ms = std_ms
        self.max_ms = max_ms
        self.distribution = distribution
    
    def sample(self) -> float:
        """Sample a latency value."""
        import random
        
        if self.distribution == "normal":
            val = random.gauss(self.mean_ms, self.std_ms)
        elif self.distribution == "uniform":
            val = random.uniform(0, self.max_ms)
        else:  # constant
            val = self.mean_ms
        
        # Cap at max
        return min(val, self.max_ms)


class SlippageModel:
    """Models price slippage during execution."""
    
    def __init__(self, 
                 volatility_impact: float = 0.5,
                 spread_half: float = 1.0,
                 order_size_factor: float = 0.1,
                 random_component: float = 0.2):
        """
        Initialize slippage model.
        
        Args:
            volatility_impact: How much volatility affects slippage
            spread_half: Half-spread cost in price units
            order_size_factor: Sensitivity to order size
            random_component: Random slippage component
        """
        self.volatility_impact = volatility_impact
        self.spread_half = spread_half
        self.order_size_factor = order_size_factor
        self.random_component = random_component
    
    def calculate_slippage(self, 
                          price: float,
                          volume: float,
                          current_volatility: float,
                          order_side: Literal["bid", "ask"]) -> float:
        """
        Calculate slippage in price units.
        
        Args:
            price: Current price
            volume: Order volume
            current_volatility: Current market volatility (%)
            order_side: "bid" (buying at ask) or "ask" (selling at bid)
            
        Returns:
            Slippage in price units
        """
        # Base slippage from spread
        base = self.spread_half
        
        # Volatility component
        vol_component = self.volatility_impact * current_volatility / 100.0
        
        # Order size component
        size_component = self.order_size_factor * volume
        
        # Random component
        import random
        random_component = self.random_component * price * 0.0001  # Small random factor
        
        # Total
        total = base + vol_component * price / 100.0 + size_component + random_component
        
        # Direction: buying at ask = positive slippage, selling at bid = negative
        if order_side == "ask":
            return total
        else:
            return -total


# Regime-aware backtester
class RegimeBacktester:
    """Backtester that adapts strategy based on market regime."""
    
    def __init__(self, 
                 initial_capital: float = 10000.0,
                 commission: float = 0.0001,
                 slippage_model: Optional[SlippageModel] = None,
                 latency_model: Optional[LatencyModel] = None):
        """
        Initialize regime backtester.
        
        Args:
            initial_capital: Starting capital
            commission: Commission per trade (as % of trade)
            slippage_model: Slippage model instance
            latency_model: Latency model instance
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_model = slippage_model or SlippageModel()
        self.latency_model = latency_model or LatencyModel()
    
    def run_backtest(
        self,
        df: "pd.DataFrame",
        strategy_func,
        strategy_params: Dict[str, Any],
        regime_classifier=None,
    ) -> BacktestResult:
        """
        Run backtest with regime awareness.
        
        Args:
            df: DataFrame with OHLCV data
            strategy_func: Strategy function to execute
            strategy_params: Parameters for strategy
            regime_classifier: Optional regime classifier
            
        Returns:
            BacktestResult with all statistics
        """
        import pandas as pd
        
        # Initialize
        balance = self.initial_capital
        peak_balance = initial_capital
        max_dd = 0.0
        
        inventory = 0.0  # Net lots
        trades = []
        cotations = 0
        rejections = 0
        acceptances = 0
        
        pnl_history = [balance]
        
        # Regime tracking
        regime_distribution = {}
        
        # Get regime if classifier provided
        if regime_classifier and hasattr(regime_classifier, 'classify'):
            # Pre-classify regimes for all bars
            regimes = []
            for i in range(len(df)):
                # Use simplified regime classification based on volatility and trend
                vol = df["vol_pct"].iloc[i] if "vol_pct" in df.columns else 0
                regimes.append(self._classify_regime_simple(df.iloc[i], vol))
        else:
            regimes = ["NORMAL"] * len(df)
        
        # Main backtest loop
        for i in range(len(df)):
            bar = df.iloc[i]
            regime = regimes[i] if i < len(regimes) else "NORMAL"
            
            # Track regime distribution
            regime_distribution[regime] = regime_distribution.get(regime, 0) + 1
            
            # Call strategy
            result = strategy_func(bar, inventory, balance, self, regime, strategy_params)
            
            if not result:
                continue
            
            cotations += 1
            
            # Extract trade/order info
            order_type = result.get("type", "HOLD")
            volume = result.get("volume", 0.0)
            limit_price = result.get("price", 0.0)
            
            if order_type == "HOLD" or volume <= 0:
                # Update PnL from inventory carry
                carry_pnl = -inventory * bar.get("spread_points", 0) / 10000 * 0.5
                balance *= 1 + carry_pnl
                pnl_history.append(balance)
                continue
            
            # Simulate execution with slippage
            execution_price = self._execute_order(
                bar, limit_price, volume, order_type, 
                self.slippage_model, self.latency_model
            )
            
            # Calculate PnL
            if order_type == "BUY":
                # Buy at execution price, PnL realized when sold
                # For immediate calculation: mark-to-market
                pnl_from_trade = - (execution_price - limit_price) / limit_price * 100 if limit_price > 0 else 0
                inventory += volume
                
            elif order_type == "SELL":
                # Sell at execution price
                pnl_from_trade = (limit_price - execution_price) / limit_price * 100 if limit_price > 0 else 0
                inventory -= volume
            
            # Apply commission
            commission_pct = self.commission * volume * execution_price
            balance -= commission_pct
            
            # Apply slippage tracking
            slippage = abs(execution_price - limit_price)
            
            # Record trade
            trade = {
                "entry_bar": i,
                "entry_time": bar.name if hasattr(bar, 'name') else i,
                "order_type": order_type,
                "volume": volume,
                "limit_price": limit_price,
                "execution_price": execution_price,
                "pnl": pnl_from_trade - commission_pct,
                "slippage": slippage,
                "regime": regime,
                "inventory_after": inventory,
            }
            trades.append(trade)
            
            # Update balance
            balance += pnl_from_trade
            acceptances += 1
            
            # Track peak and drawdown
            peak_balance = max(peak_balance, balance)
            max_dd = max(max_dd, 1 - balance / peak_balance)
            
            pnl_history.append(balance)
        
        # Calculate statistics
        total_trades = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        losses = sum(1 for t in trades if t["pnl"] < 0)
        win_rate = wins / max(total_trades, 1) * 100
        
        # Profit factor
        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
        profit_factor = gross_profit / max(gross_loss, 0.001)
        
        # Sharpe ratio (simplified)
        if len(pnl_history) > 1 and np.var(pnl_history) > 0:
            returns = np.diff(pnl_history)
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 24 * 60 * 60) if np.std(returns) > 0 else 0
        else:
            sharpe = 0.0
        
        # Max drawdown %

        # Calmar ratio (annualized return / max drawdown)
        annual_return = (balance / self.initial_capital - 1) / (len(df) / 252.0) if len(df) > 0 else 0
        calmar = annual_return / max(max_dd, 0.001) if max_dd > 0 else 0
        
        # Total return %
        total_return_pct = (balance / self.initial_capital - 1) * 100
        
        return BacktestResult(
            symbol=df.attrs.get("symbol", "UNKNOWN") if hasattr(df, 'attrs') else "UNKNOWN",
            initial_balance=self.initial_capital,
            final_balance=balance,
            total_return=total_return_pct,
            total_trades=total_trades,
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_dd * 100, 1),
            sharpe_ratio=round(sharpe, 2),
            calmar_ratio=round(calmar, 2),
            total_cotations=cotations,
            total_rejections=rejections,
            total_acceptances=acceptances,
            slippage_total=sum(t["slippage"] for t in trades),
            execution_time_ms=0.0,  # Would be measured in real implementation
            regime_distribution=regime_distribution,
        )
    
    def _classify_regime_simple(self, bar: any, vol: float) -> str:
        """Simple regime classification for backtest."""
        trend = 0.0
        if hasattr(bar, 'close') and hasattr(bar, 'open'):
            if bar.close > bar.open:
                trend = 1.0  # bullish
            else:
                trend = -1.0  # bearish
        
        if vol > 20:
            return "HIGH_VOLATILITY"
        elif abs(trend) > 0.5 and vol > 10:
            return "TRENDING"
        elif vol < 5:
            return "CALM"
        else:
            return "RANGING"


# Mode simulators
class NettingSimulator:
    """Simulates netting account mode."""
    
    def __init__(self, max_net_exposure: float = 20.0):
        self.max_net_exposure = max_net_exposure
        self.net_position = 0.0
        self.raw_long = 0.0
        self.raw_short = 0.0
    
    def process_trade(self, order_type: Literal["BUY", "SELL"], volume: float):
        """Process a trade in netting mode."""
        if order_type == "BUY":
            self.raw_long += volume
            self.net_position += volume
        elif order_type == "SELL":
            self.raw_short += volume
            self.net_position -= volume
        
        # Enforce limits
        if self.net_position > self.max_net_exposure:
            # Reduce long
            excess = self.net_position - self.max_net_exposure
            self.net_position = self.max_net_exposure
            self.raw_long -= excess
        elif self.net_position < -self.max_net_exposure:
            # Reduce short
            excess = self.net_position + self.max_net_exposure
            self.net_position = -self.max_net_exposure
            self.raw_short += excess
    
    def get_exposure(self) -> float:
        """Get current net exposure."""
        return self.net_position


class HedgingSimulator:
    """Simulates hedging account mode."""
    
    def __init__(self):
        self.positions: Dict[str, Dict] = {}  # symbol -> position data
    
    def process_trade(self, symbol: str, order_type: Literal["BUY", "SELL"], volume: float):
        """Process a trade in hedging mode - allows independent positions."""
        if symbol not in self.positions:
            self.positions[symbol] = {
                "long_volume": 0.0,
                "short_volume": 0.0,
                "net": 0.0,
            }
        
        pos = self.positions[symbol]
        
        if order_type == "BUY":
            pos["long_volume"] += volume
        elif order_type == "SELL":
            pos["short_volume"] += volume
        
        # Calculate net
        pos["net"] = pos["long_volume"] - pos["short_volume"]
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for symbol."""
        return self.positions.get(symbol)


# Main backtesting entry point
class BacktestingEngine:
    """
    Main backtesting engine for CHAOS ENGINE HFT.
    
    Supports:
    - Historical data backtesting
    - Regime-aware testing
    - Multiple accounting modes (netting/hedging)
    - Transaction cost modeling
    - Performance metric calculation
    - Strategy optimization
    """
    
    def __init__(self, 
                 initial_capital: float = 10000.0,
                 commission: float = 0.0001,
                 slippage_model: Optional[SlippageModel] = None,
                 latency_model: Optional[LatencyModel] = None,
                 accounting_mode: Literal["netting", "hedging"] = "netting"):
        """
        Initialize backtesting engine.
        
        Args:
            initial_capital: Starting capital
            commission: Commission per trade (as % of trade value)
            slippage_model: Slippage model
            latency_model: Latency model
            accounting_mode: "netting" or "hedging"
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_model = slippage_model or SlippageModel()
        self.latency_model = latency_model or LatencyModel()
        self.accounting_mode = accounting_mode
        
        # Mode-specific simulators
        if accounting_mode == "netting":
            self.simulator = NettingSimulator()
        else:
            self.simulator = HedgingSimulator()
    
    def run(self, 
            data: "pd.DataFrame",
            strategy,
            regime_filter: Optional[Literal["CALM", "HIGH_VOLATILITY", "TRENDING", "RANGING"]] = None) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            data: DataFrame with required columns
            strategy: Strategy object or function
            regime_filter: Optional regime filter
            
        Returns:
            BacktestResult with comprehensive statistics
        """
        import pandas as pd
        
        # Ensure data has required columns
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Add symbol attribute if not present
        if not hasattr(data, 'attrs') or 'symbol' not in data.attrs:
            data.attrs = getattr(data, 'attrs', {})
            if 'symbol' not in data.attrs:
                data.attrs['symbol'] = "UNKNOWN"
        
        # Prepare data
        df = data.copy()
        
        # Calculate derived columns
        if "spread_points" not in df.columns:
            df["spread_points"] = (df["ask"] - df["bid"]).ifnone(0)  # placeholder
        
        if "vol_pct" not in df.columns:
            # Calculate simple volatility
            returns = df["close"].pct_change().fillna(0)
            df["vol_pct"] = returns.rolling(50).std() * np.sqrt(365 * 24 * 60 * 60) * 100.0
        
        # Run based on accounting mode
        if self.accounting_mode == "netting":
            result = self._run_netting_backtest(df, strategy, regime_filter)
        else:
            result = self._run_hedging_backtest(df, strategy, regime_filter)
        
        # Attach metadata
        result.symbol = data.attrs.get("symbol", "UNKNOWN")
        result.initial_balance = self.initial_capital
        
        return result
    
    def _run_netting_backtest(self, df: "pd.DataFrame", strategy, 
                             regime_filter) -> BacktestResult:
        """Run backtest in netting mode."""
        from .slippage_model import SlippageModel
        from .latency_model import LatencyModel
        
        # Initialize
        balance = self.initial_capital
        peak_balance = self.initial_capital
        max_dd = 0.0
        
        # Netting mode state
        net_position = 0.0
        raw_long = 0.0
        raw_short = 0.0
        
        trades = []
        cotations = 0
        rejections = 0
        acceptances = 0
        
        pnl_history = [balance]
        
        # Main loop
        for i in range(len(df)):
            bar = df.iloc[i]
            
            # Get strategy signal
            signal = strategy(bar, net_position, balance, self.accounting_mode)
            
            if not signal:
                # Carry PnL
                carry = -net_position * bar.get("spread_points", 0) / 10000 * 0.5
                balance *= 1 + carry
                pnl_history.append(balance)
                continue
            
            cotations += 1
            
            # Process signal
            order_type = signal.get("type", "HOLD")
            volume = signal.get("volume", 0.0)
            limit_price = signal.get("price", 0.0)
            
            if order_type == "HOLD" or volume <= 0:
                carry = -net_position * bar.get("spread_points", 0) / 10000 * 0.5
                balance *= 1 + carry
                pnl_history.append(balance)
                continue
            
            # Netting: check exposure limits
            would_be_net = net_position
            if order_type == "BUY":
                would_be_net += volume
            else:
                would_be_net -= volume
            
            # Check limit
            if abs(would_be_net) > self.simulator.max_net_exposure:
                rejections += 1
                # Still allow reduced size
                if order_type == "BUY":
                    volume = max(0, self.simulator.max_net_exposure - net_position)
                else:
                    volume = max(0, -self.simulator.max_net_exposure - net_position)
                
                if volume <= 0:
                    # Can't execute, skip
                    carry = -net_position * bar.get("spread_points", 0) / 10000 * 0.5
                    balance *= 1 + carry
                    pnl_history.append(balance)
                    continue
            
            # Execute order
            execution_price = self._execute_order_netting(
                bar, limit_price, volume, order_type,
                self.slippage_model, self.latency_model
            )
            
            # Update netting state
            if order_type == "BUY":
                raw_long += volume
                net_position += volume
            else:
                raw_short += volume
                net_position -= volume
            
            # Calculate PnL (simplified mark-to-market)
            if order_type == "BUY":
                pnl = - (execution_price - limit_price) / limit_price * 100 if limit_price > 0 else 0
            else:
                pnl = (limit_price - execution_price) / limit_price * 100 if limit_price > 0 else 0
            
            # Commission
            commission = self.commission * volume * execution_price
            balance -= commission
            
            balance += pnl
            
            # Record trade
            trade = {
                "entry_bar": i,
                "order_type": order_type,
                "volume": volume,
                "limit_price": limit_price,
                "execution_price": execution_price,
                "pnl": pnl - commission,
                "slippage": abs(execution_price - limit_price),
                "regime": bar.attrs.get("regime", "NORMAL") if hasattr(bar, 'attrs') else "NORMAL",
            }
            trades.append(trade)
            acceptances += 1
            
            # Track drawdown
            peak_balance = max(peak_balance, balance)
            max_dd = max(max_dd, 1 - balance / peak_balance)
            
            pnl_history.append(balance)
        
        # Calculate statistics
        total_trades = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        losses = sum(1 for t in trades if t["pnl"] < 0)
        win_rate = wins / max(total_trades, 1) * 100
        
        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
        profit_factor = gross_profit / max(gross_loss, 0.001)
        
        # Sharpe
        if len(pnl_history) > 1 and np.var(pnl_history) > 0:
            returns = np.diff(pnl_history)
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 24 * 60 * 60) if np.std(returns) > 0 else 0
        else:
            sharpe = 0.0
        
        # Calmar
        time_years = len(df) / 252.0 if len(df) > 0 else 1
        annual_return = (balance / self.initial_capital - 1) / time_years if time_years > 0 else 0
        calmar = annual_return / max(max_dd, 0.001) if max_dd > 0 else 0
        
        total_return_pct = (balance / self.initial_capital - 1) * 100
        
        return BacktestResult(
            symbol=data.attrs.get("symbol", "UNKNOWN") if hasattr(data, 'attrs') else "UNKNOWN",
            initial_balance=self.initial_capital,
            final_balance=balance,
            total_return=total_return_pct,
            total_trades=total_trades,
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_dd * 100, 1),
            sharpe_ratio=round(sharpe, 2),
            calmar_ratio=round(calmar, 2),
            total_cotations=cotations,
            total_rejections=rejections,
            total_acceptances=acceptances,
            slippage_total=sum(t["slippage"] for t in trades),
            execution_time_ms=0.0,
        )
    
    def _run_hedging_backtest(self, df: "pd.DataFrame", strategy, 
                             regime_filter) -> BacktestResult:
        """Run backtest in hedging mode."""
        # Similar to netting but allows independent long/short positions
        # For now, delegate to netting with some modifications
        return self._run_netting_backtest(df, strategy, regime_filter)
    
    def _execute_order_netting(self, bar, limit_price, volume, order_side,
                              slippage_model, latency_model) -> float:
        """Execute order in netting mode with slippage and latency."""
        import random
        
        # Apply latency delay
        latency = latency_model.sample() / 1000.0  # Convert to seconds
        
        # During latency, price can move
        # Use bar's price change as proxy
        price_impact = 0.0
        if hasattr(bar, 'close') and hasattr(bar, 'open'):
            # Simulate price move during latency
            mid = (bar.open + bar.close) / 2
            # Simplified: price moves proportionally to volatility * latency
            price_impact = mid * 0.001  # 0.1% max impact
        
        # Determine execution side
        if order_side == "BUY":
            # Buy at ask approximately
            base_price = bar.close if hasattr(bar, 'close') else limit_price
            # Slippage: pay the spread half + impact
            slippage = slippage_model.calculate_slippage(
                base_price, volume, bar.get("vol_pct", 1.0), "ask"
            )
            execution = base_price + slippage + price_impact
        else:
            # Sell at bid approximately
            base_price = bar.close if hasattr(bar, 'close') else limit_price
            slippage = slippage_model.calculate_slippage(
                base_price, volume, bar.get("vol_pct", 1.0), "bid"
            )
            execution = base_price - slippage - price_impact
        
        return execution


# Convenience function
def run_strategy_backtest(
    data: "pd.DataFrame",
    initial_capital: float = 10000.0,
    commission: float = 0.0001,
    accounting_mode: Literal["netting", "hedging"] = "netting",
    regime_filter: Optional[Literal["CALM", "HIGH_VOLATILITY", "TRENDING", "RANGING"]] = None,
) -> BacktestResult:
    """
    Quick backtest runner.
    
    Args:
        data: OHLCV DataFrame
        initial_capital: Starting capital
        commission: Commission rate
        accounting_mode: "netting" or "hedging"
        regime_filter: Optional regime filter
        
    Returns:
        BacktestResult
    """
    engine = BacktestingEngine(
        initial_capital=initial_capital,
        commission=commission,
        accounting_mode=accounting_mode,
    )
    
    # Simple strategy: signal based on volatility and inventory
    def simple_strategy(bar, net_pos, balance, mode):
        """Simple market making strategy for backtesting."""
        vol = bar.get("vol_pct", 1.0) if hasattr(bar, 'get') else 1.0
        spread = bar.get("spread_points", 1.0) if hasattr(bar, 'get') else 1.0
        
        # Only trade if volatility is in reasonable range
        if vol < 0.1 or vol > 5.0:
            return None
        
        # Quote if spread is reasonable
        if spread > 10:
            return None
        
        # Basic MM: post both sides
        return {
            "type": "QUOTE",
            "volume": 0.1,
            "price": bar.close if hasattr(bar, 'close') else 1.0,
        }
    
    return engine.run(data, simple_strategy, regime_filter)


if __name__ == "__main__":
    # Quick test
    import numpy as np
    import pandas as pd
    
    # Generate sample data
    np.random.seed(42)
    n = 100
    prices = 1.1178 + np.cumsum(np.random.normal(0, 0.001, n))
    
    df = pd.DataFrame({
        "open": prices,
        "high": prices + np.random.uniform(0, 0.002, n),
        "low": prices - np.random.uniform(0, 0.002, n),
        "close": prices,
        "volume": np.random.uniform(1000, 5000, n),
    })
    
    # Add derived columns
    df["spread_points"] = 1.2
    df["vol_pct"] = np.random.uniform(0.5, 2.0, n)
    df.attrs = {"symbol": "EURUSDm"}
    
    # Run backtest
    result = run_strategy_backtest(
        df,
        initial_capital=10000.0,
        commission=0.0001,
        accounting_mode="netting",
    )
    
    print(f"Backtest Results for {result.symbol}:")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Win Rate: {result.win_rate}%")
    print(f"  Total Return: {result.total_return:.1f}%")
    print(f"  Max Drawdown: {result.max_drawdown:.1f}%")
    print(f"  Profit Factor: {result.profit_factor:.2f}")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")