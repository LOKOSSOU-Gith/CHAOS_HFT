#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Market Data Module

Provides market data feed handling for the Python Quant Engine.
Handles tick reception, processing, and storage from MQL5 IPC bridge.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
import time
import logging

logger = logging.getLogger("chaos_engine_hft.market_data")


class Tick:
    """Represents a single market tick."""
    
    def __init__(
        self,
        symbol: str,
        bid: float,
        ask: float,
        timestamp: float,
        spread: float = 0.0,
        volume: Optional[float] = None,
        chaos_score: float = 0.0,
    ):
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.timestamp = timestamp
        self.spread = spread
        self.volume = volume
        self.chaos_score = chaos_score
        
        # Derived fields
        self.mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
        self.points = ask - bid if bid > 0 and ask > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tick to dictionary for IPC serialization."""
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "timestamp": self.timestamp,
            "spread": self.spread,
            "volume": self.volume,
            "chaos_score": self.chaos_score,
            "mid": self.mid,
            "points": self.points,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tick":
        """Create Tick from dictionary."""
        return cls(
            symbol=data.get("symbol", ""),
            bid=float(data.get("bid", 0)),
            ask=float(data.get("ask", 0)),
            timestamp=float(data.get("timestamp", time.time())),
            spread=float(data.get("spread", 0)),
            volume=float(data.get("volume")) if data.get("volume") is not None else None,
            chaos_score=float(data.get("chaos_score", 0)),
        )


class MarketDataFeed:
    """
    Market data feed that receives and processes ticks from MQL5.
    
    Responsibilities:
    1. Receive ticks via IPC from MQL5 Expert Advisor
    2. Maintain rolling window of recent ticks
    3. Calculate derived metrics (volatility, spreads, etc.)
    4. Provide latest tick data to other modules
    5. Store tick history for analysis
    """
    
    def __init__(self, max_window: int = 1000):
        """
        Initialize market data feed.
        
        Args:
            max_window: Maximum number of ticks to keep in rolling window
        """
        self.max_window = max_window
        self.tick_window: Dict[str, Any] = {}  # symbol -> list of ticks
        self.latest_tick: Optional[Tick] = None
        self.last_update = 0.0
        self.update_count = 0
        self.symbol = ""
        
        # Volatility calculation window
        self.vol_window = 50  # number of ticks for rolling volatility
        self.price_history: list = []
        
        logger.info("MarketDataFeed initialized")
    
    def start(self):
        """Start the market data feed."""
        self.update_count = 0
        self.price_history = []
        logger.info("MarketDataFeed started")
    
    def stop(self):
        """Stop the market data feed."""
        logger.info("MarketDataFeed stopped")
    
    def update(self, tick_data: Dict[str, Any]):
        """
        Update feed with new tick data.
        
        Args:
            tick_data: Dictionary with tick fields
        """
        try:
            tick = Tick.from_dict(tick_data)
            self.symbol = tick.symbol
            
            # Add to window
            if tick.symbol not in self.tick_window:
                self.tick_window[tick.symbol] = []
            
            self.tick_window[tick.symbol].append(tick)
            
            # Maintain window size
            if len(self.tick_window[tick.symbol]) > self.max_window:
                self.tick_window[tick.symbol] = self.tick_window[tick.symbol][-self.max_window:]
            
            # Update price history for volatility
            self.price_history.append({
                "timestamp": tick.timestamp,
                "mid": tick.mid,
                "bid": tick.bid,
                "ask": tick.ask,
            })
            
            # Maintain price history size
            if len(self.price_history) > self.max_window * 2:
                self.price_history = self.price_history[-self.max_window * 2:]
            
            # Update latest tick
            self.latest_tick = tick
            self.last_update = time.time()
            self.update_count += 1
            
        except Exception as e:
            logger.error(f"Error updating market data feed: {e}")
    
    def has_data(self) -> bool:
        """Check if we have tick data available."""
        return self.latest_tick is not None
    
    def get_latest(self) -> Optional[Tick]:
        """Get the latest tick."""
        return self.latest_tick
    
    def get_recent(self, n: int = 10) -> list:
        """Get the last n ticks."""
        if not self.latest_tick:
            return []
        
        # Get ticks from window for this symbol
        ticks = self.tick_window.get(self.symbol, [])
        return ticks[-n:] if ticks else []
    
    def get_volatility(self, window: Optional[int] = None) -> float:
        """
        Calculate rolling volatility from price history.
        
        Args:
            window: Number of ticks to use (uses self.vol_window if None)
            
        Returns:
            Volatility as percentage
        """
        w = window or self.vol_window
        if len(self.price_history) < w:
            return 0.0
        
        # Get mid prices
        mids = [p["mid"] for p in self.price_history[-w:]]
        if len(mids) < 2:
            return 0.0
        
        # Calculate returns
        returns = [(mids[i] - mids[i-1]) / mids[i-1] for i in range(1, len(mids))]
        
        if not returns:
            return 0.0
        
        # Calculate standard deviation
        import numpy as np
        returns_array = np.array(returns)
        volatility = float(np.std(returns_array)) * np.sqrt(365 * 24 * 60 * 60) * 100.0
        
        return volatility
    
    def get_spread_history(self) -> list:
        """Get spread history from recent ticks."""
        if not self.latest_tick:
            return []
        
        spreads = []
        for tick in self.tick_window.get(self.symbol, []):
            spreads.append(tick.spread)
        return spreads[-20:]  # Last 20 spreads