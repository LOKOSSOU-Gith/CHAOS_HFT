#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Market Regime Classifier

Classifies market conditions into regimes using statistical models
including Hidden Markov Models (HMM) and technical filters.
Determines which quoting policy should be active.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, Literal
import numpy as np
import logging
from collections import deque

logger = logging.getLogger("chaos_engine_hft.regime")


# Regime types
RegimeType = Literal["CALM", "HIGH_VOLATILITY", "TRENDING", "RANGING", "CRITICAL"]

# Regime transition probabilities (for HMM)
TRANSITION_PROBS = {
    "CALM": {"CALM": 0.7, "HIGH_VOLATILITY": 0.15, "TRENDING": 0.1, "RANGING": 0.05},
    "HIGH_VOLATILITY": {"CALM": 0.2, "HIGH_VOLATILITY": 0.5, "TRENDING": 0.2, "RANGING": 0.1},
    "TRENDING": {"CALM": 0.1, "HIGH_VOLATILITY": 0.1, "TRENDING": 0.7, "RANGING": 0.1},
    "RANGING": {"CALM": 0.3, "HIGH_VOLATILITY": 0.2, "TRENDING": 0.1, "RANGING": 0.4},
    "CRITICAL": {"CALM": 0.5, "HIGH_VOLATILITY": 0.3, "TRENDING": 0.1, "RANGING": 0.1},
}


class RegimeClassifier:
    """
    Market regime classifier for CHAOS ENGINE HFT.
    
    Determines current market conditions using multiple indicators:
    1. Volatility analysis
    2. Trend detection (ADX-like)
    3. Persistence (Hurst exponent)
    4. Order flow imbalance
    5. Chaos/Lyapunov score
    
    The classifier uses a weighted scoring system and optional HMM
    to determine the current regime.
    """
    
    def __init__(self, 
                 volatility_window: int = 50,
                 trend_window: int = 20,
                 hurst_window: int = 100):
        """
        Initialize regime classifier.
        
        Args:
            volatility_window: Window for volatility calculation
            trend_window: Window for trend indicator
            hurst_window: Window for Hurst exponent
        """
        self.volatility_window = volatility_window
        self.trend_window = trend_window
        self.hurst_window = hurst_window
        
        # History buffers
        self.price_history: deque = deque(maxlen=max(volatility_window, hurst_window))
        self.vol_history: deque = deque(maxlen=volatility_window)
        self.trend_history: deque = deque(maxlen=trend_window)
        
        # Current regime
        self._current_regime: RegimeType = "RANGING"
        self._regime_confidence: float = 0.5
        self._regime_since: float = 0.0
        
        # Indicator thresholds
        self.vol_thresholds = {
            "low": 5.0,      # % vol - calm
            "moderate": 15.0, # % vol - normal
            "high": 30.0,    # % vol - high
            "extreme": 50.0, # % vol - extreme
        }
        
        self.trend_threshold = 25.0  # ADX-like threshold for trending
        
        logger.info("RegimeClassifier initialized")
    
    def update(self, tick: Any) -> None:
        """
        Update classifier with new tick data.
        
        Args:
            tick: Tick object or dict with bid/ask/mid/volume
        """
        try:
            # Extract price data
            if hasattr(tick, 'mid'):
                mid = tick.mid
                bid = tick.bid
                ask = tick.ask
            elif isinstance(tick, dict):
                mid = tick.get("mid", tick.get("close", 0))
                bid = tick.get("bid", 0)
                ask = tick.get("ask", 0)
            else:
                return
            
            # Add to history
            self.price_history.append(mid)
            self.vol_history.append(tick.spread if hasattr(tick, 'spread') else 0)
            self.trend_history.append({"mid": mid, "timestamp": tick.timestamp})
            
            # Recalculate regime
            self._recale_regime()
            
        except Exception as e:
            logger.error(f"Error updating regime classifier: {e}")
    
    def _recale_regime(self) -> None:
        """Recalculate current regime based on all indicators."""
        try:
            # Get volatility
            volatility = self._calculate_volatility()
            
            # Get trend strength
            trend_strength = self._calculate_trend_strength()
            
            # Get Hurst exponent
            hurst = self._calculate_hurst()
            
            # Get order flow imbalance (simplified)
            oi = self._calculate_order_flow_imbalance()
            
            # Get chaos score
            chaos_score = self._calculate_chaos_score()
            
            # Score each regime
            regime_scores = self._score_regimes(
                volatility, trend_strength, hurst, oi, chaos_score
            )
            
            # Select highest scoring regime
            if regime_scores:
                new_regime = max(regime_scores, key=regime_scores.get)
                new_confidence = regime_scores[new_regime] / max(sum(regime_scores.values()), 1)
                
                # Only change if confidence is significant enough
                if new_confidence > 0.55 or self._current_regime != new_regime:
                    self._current_regime = new_regime
                    self._regime_confidence = new_confidence
                    self._regime_since = np.datetime64().item().timestamp()
                    logger.debug(f"Regime changed to: {new_regime} (confidence: {new_confidence:.2f})")
            
        except Exception as e:
            logger.error(f"Error recalculating regime: {e}")
    
    def _calculate_volatility(self) -> float:
        """Calculate current volatility percentage."""
        if len(self.price_history) < 2:
            return 0.0
        
        prices = np.array(self.price_history)
        if len(prices) < 2:
            return 0.0
        
        # Calculate log returns
        returns = np.diff(np.log(prices))
        
        if len(returns) == 0:
            return 0.0
        
        # Annualized volatility percentage
        vol_pct = float(np.std(returns)) * np.sqrt(365 * 24 * 60 * 60) * 100.0
        
        return vol_pct
    
    def _calculate_trend_strength(self) -> float:
        """
        Calculate trend strength using ADX-like approach.
        
        Returns value approximately 0-100 where:
        - < 25: Weak/no trend (ranging)
        - 25-50: Moderate trend
        - 50-75: Strong trend
        - > 75: Very strong trend
        """
        if len(self.trend_history) < 3:
            return 0.0
        
        try:
            # Get recent prices
            recent = np.array([entry["mid"] for entry in list(self.trend_history)[-10:]])
            if len(recent) < 3:
                return 0.0
            
            # Calculate linear regression slope
            x = np.arange(len(recent))
            slope, _ = np.polyfit(x, recent, 1)
            
            # Calculate percent change over window
            if len(recent) > 1:
                pct_change = (recent[-1] - recent[0]) / recent[0] * 100.0
            else:
                pct_change = 0.0
            
            # ADX approximation: combine slope magnitude and volatility
            if len(self.price_history) > 1:
                recent_prices = np.array(list(self.price_history)[-10:])
                if len(recent_prices) > 1:
                    avg_vol = np.std(np.diff(recent_prices)) * np.sqrt(365 * 24 * 60 * 60) * 100.0
                else:
                    avg_vol = 0.0
            else:
                avg_vol = 0.0
            
            # Trend strength: combine direction and consistency
            # Simple: use absolute % change scaled
            trend_val = min(100.0, abs(pct_change) * 10)
            
            # Adjust based on volatility consistency
            if avg_vol > 0:
                # Higher volatility with consistent direction = stronger trend
                direction_consistency = 1.0  # simplified
                trend_val *= (1.0 + min(1.0, avg_vol / 50.0))  # boost up to 2x
            
            return max(0.0, trend_val)
            
        except Exception:
            return 0.0
    
    def _calculate_hurst(self) -> float:
        """Calculate Hurst exponent for persistence analysis."""
        if len(self.price_history) < 20:
            return 0.5
        
        try:
            prices = np.array(list(self.price_history)[-50:])  # use last 50
            if len(prices) < 20:
                return 0.5
            
            # Rescaled Range analysis with multiple scales
            n = len(prices)
            scales = [max(5, n // 4), max(5, n // 2), max(5, n - 1)]
            
            rs_ratios = []
            for scale in scales:
                if scale < 3 or scale > n:
                    continue
                
                n_segments = n // scale
                if n_segments < 2:
                    continue
                
                rs_values = []
                for seg in range(n_segments):
                    start = seg * scale
                    end = min(start + scale, n)
                    segment = prices[start:end]
                    
                    if len(segment) < 3:
                        continue
                    
                    # Mean of segment
                    mean_seg = np.mean(segment)
                    
                    # Cumulative deviation
                    cumdev = np.cumsum(segment - mean_seg)
                    
                    # Range R
                    r = np.max(cumdev) - np.min(cumdev)
                    
                    # Standard deviation S
                    s = np.std(segment) if len(segment) > 1 else 0
                    
                    if s > 0:
                        rs_values.append(r / s)
                    else:
                        rs_values.append(1.0)
                
                if rs_values:
                    rs_ratios.append(np.mean(rs_values))
            
            if len(rs_ratios) >= 2:
                # Linear regression on log-log
                log_scales = np.log([s for s in scales if s >= 3 and s < n])
                log_rs = np.log([rs for rs in rs_ratios if rs > 0])
                
                if len(log_scales) >= 2 and len(log_rs) >= 2:
                    coeffs = np.polyfit(log_scales, log_rs, 1)
                    hurst = float(coeffs[0])
                    return max(0.0, min(1.0, hurst))
            
            return 0.5
            
        except Exception:
            return 0.5
    
    def _calculate_order_flow_imbalance(self) -> float:
        """
        Calculate order flow imbalance.
        
        Simplified: compares bid vs ask pressure.
        Positive = buy pressure, Negative = sell pressure
        """
        # In a real implementation, this would use Level 2 data
        # For now, use spread and price movement
        if len(self.price_history) < 2:
            return 0.0
        
        try:
            recent_prices = np.array(list(self.price_history)[-20:])
            if len(recent_prices) < 2:
                return 0.0
            
            # Calculate price changes direction
            changes = np.diff(recent_prices)
            
            # imbalance = (up ticks - down ticks) / total ticks
            if len(changes) > 0:
                up = np.sum(changes > 0)
                down = np.sum(changes < 0)
                total = len(changes)
                imbalance = (up - down) / total if total > 0 else 0.0
            else:
                imbalance = 0.0
            
            return float(imbalance)
            
        except Exception:
            return 0.0
    
    def _calculate_chaos_score(self) -> float:
        """Get chaos score from the chaos analyzer (placeholder)."""
        # This would integrate with the chaos engine
        # For now, return a placeholder
        return 0.5
    
    def _score_regimes(self, 
                       volatility: float, 
                       trend_strength: float, 
                       hurst: float, 
                       oi: float, 
                       chaos_score: float) -> Dict[RegimeType, float]:
        """
        Score each regime type based on indicators.
        
        Returns dict mapping RegimeType -> score (higher = better match)
        """
        scores: Dict[RegimeType, float] = {}
        
        # CALM: low volatility, low trend, Hurst near 0.5 (or either extreme), low chaos
        vol_low = volatility < self.vol_thresholds["low"]
        trend_weak = trend_strength < self.trend_threshold
        hurst_neutral = 0.4 <= hurst <= 0.6
        chaos_low = chaos_score < 0.4
        
        calm_score = 0.0
        if vol_low and trend_weak and hurst_neutral and chaos_low:
            calm_score = 1.0
        elif vol_low and trend_weak:
            calm_score = 0.5
        scores["CALM"] = calm_score
        
        # HIGH_VOLATILITY: high volatility, moderate/strong trend, higher chaos
        vol_high = self.vol_thresholds["high"] <= volatility < self.vol_thresholds["extreme"]
        chaos_high = chaos_score >= 0.6
        
        hv_score = 0.0
        if vol_high and chaos_high:
            hv_score = 1.0
        elif vol_high:
            hv_score = 0.7
        scores["HIGH_VOLATILITY"] = hv_score
        
        # TRENDING: strong trend, Hurst > 0.5 (persistent), moderate chaos
        trend_strong = trend_strength >= 50.0
        hurst_persistent = hurst > 0.6
        chaos_mod = 0.3 <= chaos_score < 0.6
        
        trending_score = 0.0
        if trend_strong and hurst_persistent and chaos_mod:
            trending_score = 1.0
        elif trend_strong and hurst_persistent:
            trending_score = 0.8
        scores["TRENDING"] = trending_score
        
        # RANGING: low-moderate volatility, low trend, Hurst near 0.5, low chaos
        vol_mod = self.vol_thresholds["low"] <= volatility < self.vol_thresholds["high"]
        trend_weak2 = trend_strength < 30.0
        hurst_mixed = not (0.4 <= hurst <= 0.6)  # outside neutral range
        chaos_low2 = chaos_score < 0.5
        
        ranging_score = 0.0
        if vol_mod and trend_weak2 and chaos_low2:
            # Hurst can be outside neutral for ranging too
            ranging_score = 1.0 if hurst_mixed else 0.7
        scores["RANGING"] = ranging_score
        
        # CRITICAL: very high volatility + high chaos + extreme conditions
        vol_extreme = volatility >= self.vol_thresholds["extreme"]
        chaos_extreme = chaos_score >= 0.8
        
        critical_score = 0.0
        if vol_extreme and chaos_extreme:
            critical_score = 1.0
        elif vol_extreme or chaos_extreme:
            critical_score = 0.5
        scores["CRITICAL"] = critical_score
        
        return scores
    
    def classify(self, tick: Any, chaos_score: Optional[float] = None) -> RegimeType:
        """
        Classify the current market regime.
        
        Args:
            tick: Tick data
            chaos_score: Optional chaos score (calculated if not provided)
            
        Returns:
            RegimeType label
        """
        self.update(tick)
        
        return self._current_regime
    
    def get_current_regime(self) -> Dict[str, Any]:
        """Get current regime information."""
        return {
            "regime": self._current_regime,
            "confidence": self._regime_confidence,
            "since": self._regime_since,
        }
    
    def get_indicators(self) -> Dict[str, float]:
        """Get current indicator values."""
        volatility = self._calculate_volatility()
        trend = self._calculate_trend_strength()
        hurst = self._calculate_hurst()
        
        return {
            "volatility": volatility,
            "trend_strength": trend,
            "hurst": hurst,
        }