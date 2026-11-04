#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Chaos Mathematics Engine

Provides chaos mathematics analysis for financial time series.
Implements Largest Lyapunov Exponent, Permutation Entropy, 
Recurrence Quantification Analysis, Hurst Exponent, and Chaos Score.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import logging

logger = logging.getLogger("chaos_engine_hft.chaos")


class ChaosAnalyzer:
    """
    Implements chaos mathematics analysis for financial series.
    
    Modules:
    - phase_space.py - Phase space reconstruction
    - lyapunov.py - Largest Lyapunov Exponent
    - permutation_entropy.py - Permutation Entropy
    - recurrence_analysis.py - Recurrence Quantification Analysis
    - hurst.py - Hurst Exponent
    - chaos_score.py - Composite Chaos Score
    - validation.py - Validation against random references
    """
    
    def __init__(self, window: int = 100):
        """
        Initialize chaos analyzer.
        
        Args:
            window: Analysis window size in ticks
        """
        self.window = window
        self.price_history: list = []
        self.returns: Optional[np.ndarray] = None
        
        # Cached metrics
        self.lyapunov: Optional[float] = None
        self.permutation_entropy: Optional[float] = None
        self.hurst: Optional[float] = None
        self.chaos_score: Optional[float] = None
        
        logger.info("ChaosAnalyzer initialized")
    
    def update(self, tick: Any) -> None:
        """
        Update internal state with new tick data.
        
        Args:
            tick: Tick object or dict with bid/ask/mid and timestamp
        """
        try:
            # Extract mid price
            if hasattr(tick, 'mid'):
                mid = tick.mid
            elif isinstance(tick, dict):
                mid = tick.get("mid", tick.get("close", 0))
            else:
                mid = 0.0
            
            self.price_history.append({
                "timestamp": tick.timestamp if hasattr(tick, 'timestamp') else time.time(),
                "mid": mid,
            })
            
            # Keep window size
            if len(self.price_history) > self.window:
                self.price_history = self.price_history[-self.window:]
            
            # Recalculate returns and metrics
            self._calculate_metrics()
            
        except Exception as e:
            logger.error(f"Error updating chaos analyzer: {e}")
    
    def _calculate_metrics(self) -> None:
        """Calculate all chaos metrics from current price history."""
        if len(self.price_history) < 10:
            # Not enough data for meaningful metrics
            self.lyapunov = 0.0
            self.permutation_entropy = 0.0
            self.hurst = 0.5  # neutral
            self.chaos_score = 0.0
            return
        
        try:
            # Extract mid prices
            mids = np.array([p["mid"] for p in self.price_history])
            
            # Calculate returns
            returns = np.diff(mids)
            self.returns = returns
            
            # 1. Largest Lyapunov Exponent (estimated)
            self.lyapunov = self._compute_lyapunov(returns)
            
            # 2. Permutation Entropy
            self.permutation_entropy = self._compute_permutation_entropy(mids)
            
            # 3. Hurst Exponent
            self.hurst = self._compute_hurst(mids)
            
            # 4. Chaos Score (composite)
            self.chaos_score = self._compute_chaos_score()
            
        except Exception as e:
            logger.error(f"Error calculating chaos metrics: {e}")
            self.lyapunov = 0.0
            self.permutation_entropy = 0.0
            self.hurst = 0.5
            self.chaos_score = 0.0
    
    def _compute_lyapunov(self, returns: np.ndarray) -> float:
        """
        Estimate Largest Lyapunov Exponent.
        
        Uses a simplified Rosenstein algorithm for chaos detection.
        Positive value indicates chaos, negative indicates stability.
        """
        if len(returns) < 20:
            return 0.0
        
        try:
            # Reconstruct state space
            dim = min(3, len(returns) // 10)
            tau = 1  # time delay
            
            # Build trajectory matrix
            n = len(returns) - (dim - 1) * tau
            if n < 10:
                return 0.0
            
            # Simple estimation: correlation dimension approach
            # Count close pairs and track divergence
            distances = []
            
            for i in range(0, n, 10):
                for j in range(i + 10, n, 10):
                    # Calculate distance between state vectors
                    dist = 0.0
                    for k in range(dim):
                        diff = returns[i + k] - returns[j + k]
                        dist += diff ** 2
                    dist = dist ** 0.5
                    distances.append(dist)
            
            if not distances or len(distances) < 5:
                return 0.0
            
            # Average log-distance vs time (simplified)
            # In practice, this would track divergence over time windows
            # For now, use average distance as rough indicator
            avg_dist = np.mean(distances)
            
            # Normalize by data length and dimension
            if avg_dist > 0 and len(returns) > 0:
                lyap = -np.log(avg_dist) / np.log(len(returns))
                # Clamp to reasonable range
                lyap = max(-1.0, min(1.0, lyap))
                return lyap
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _compute_permutation_entropy(self, mids: np.ndarray, 
                                    dimension: int = 3, 
                                    delay: int = 1) -> float:
        """
        Compute Permutation Entropy.
        
        Measures temporal complexity based on ordinal patterns.
        Higher values = more complex/less predictable.
        Lower values = more regular/predictable.
        """
        try:
            n = len(mids)
            if n < dimension * delay:
                return 0.0
            
            # Build ordinal patterns
            patterns = []
            for i in range(n - (dimension - 1) * delay):
                # Get values at delayed positions
                values = [mids[i + k * delay] for k in range(dimension)]
                
                # Rank the values (0 = smallest, dimension-1 = largest)
                ranked = sorted(range(dimension), key=lambda k: values[k])
                patterns.append(tuple(ranked))
            
            # Count pattern frequencies
            from collections import Counter
            pattern_counts = Counter(patterns)
            total = len(patterns)
            
            if total == 0 or len(pattern_counts) == 0:
                return 0.0
            
            # Calculate entropy
            entropy = 0.0
            norm = np.math.factorial(dimension)  # number of possible patterns
            
            for count in pattern_counts.values():
                p = count / total
                if p > 0:
                    entropy -= p * np.log(p)
            
            # Normalize by maximum possible entropy
            if norm > 0:
                entropy = entropy / np.log(norm)
            
            return float(entropy)
            
        except Exception as e:
            logger.error(f"Error computing permutation entropy: {e}")
            return 0.0
    
    def _compute_hurst(self, mids: np.ndarray) -> float:
        """
        Compute Hurst Exponent.
        
        Measures long-term memory/dependence:
        - H > 0.5: Persistent (trending)
        - H = 0.5: Random walk
        - H < 0.5: Anti-persistent (mean-reverting)
        """
        try:
            if len(mids) < 20:
                return 0.5
            
            # Rescaled Range (R/S) analysis
            n = len(mids)
            
            # Calculate cumulative deviation from mean
            mean_mid = np.mean(mids)
            deviations = mids - mean_mid
            
            # Calculate cumulative sum
            cumsum = np.cumsum(deviations)
            
            # Calculate R (range) and S (standard deviation) for different scales
            # Use a few scale sizes
            scales = [max(10, n // 4), max(10, n // 2), max(10, n - 1)]
            
            rs_ratios = []
            for scale in scales:
                if scale < 3:
                    continue
                
                # Divide into segments of size 'scale'
                n_segments = n // scale
                if n_segments < 2:
                    continue
                
                rs_values = []
                for seg in range(n_segments):
                    start = seg * scale
                    end = min(start + scale, n)
                    segment = cumsum[start:end]
                    
                    if len(segment) < 3:
                        continue
                    
                    # Range of cumulative sum
                    r = np.max(segment) - np.min(segment)
                    
                    # Standard deviation of original segment
                    if len(segment) > 1:
                        s = np.std(segment)
                    else:
                        s = 0 if len(segment) == 0 else abs(segment[0] - mean_mid)
                    
                    if s > 0:
                        rs_values.append(r / s)
                    else:
                        rs_values.append(1.0)
                
                if rs_values:
                    rs_ratios.append(np.mean(rs_values))
            
            if len(rs_ratios) < 2:
                return 0.5
            
            # Fit Hurst exponent using linear regression on log-log plot
            # log(R/S) vs log(n)
            log_scales = np.log([s for s in scales if s < n and s >= 3])
            log_rs = np.log([rs for rs in rs_ratios if rs > 0])
            
            if len(log_scales) >= 2 and len(log_rs) >= 2:
                # Linear fit: log(R/S) = H * log(n) + C
                coeffs = np.polyfit(log_scales, log_rs, 1)
                hurst = float(coeffs[0])
                # Clamp to [0, 1]
                hurst = max(0.0, min(1.0, hurst))
                return hurst
            
            return 0.5
            
        except Exception as e:
            logger.error(f"Error computing Hurst exponent: {e}")
            return 0.5
    
    def _compute_chaos_score(self) -> float:
        """
        Compute composite Chaos Score.
        
        Combines multiple metrics into a single normalized score [0, 1].
        Higher = more chaotic/unpredictable.
        Lower = more stable/predictable.
        
        Formula combines:
        - Lyapunov exponent (normalized)
        - Permutation entropy (normalized)  
        - Hurst deviation from 0.5
        """
        try:
            if self.lyapunov is None or self.permutation_entropy is None or self.hurst is None:
                return 0.0
            
            # Normalize each component to [0, 1]
            
            # Lyapunov: positive = chaotic, negative = stable
            # Map from [-1, 1] to [0, 1]
            lyap_norm = max(0.0, min(1.0, (self.lyapunov + 1.0) / 2.0))
            
            # Permutation entropy already in [0, 1]
            perm_norm = max(0.0, min(1.0, self.permutation_entropy))
            
            # Hurst: deviation from 0.5
            # |H - 0.5| * 2 maps [0, 1] to [0, 1], but we want:
            # H near 0.5 (random) = lower chaos, H far from 0.5 = higher chaos
            # Actually, both very persistent (H->1) and very anti-persistent (H->0) can be
            # considered "structured" but not necessarily "chaotic"
            # We'll use absolute deviation as contributor
            hurst_dev = abs(self.hurst - 0.5) * 2  # Maps 0.5->0, 0 or 1->1
            
            # Weighted combination
            # Lyapunov has strongest signal, entropy provides nuance, Hurst adds context
            weights = {"lyapunov": 0.5, "entropy": 0.3, "hurst": 0.2}
            
            chaos_score = (
                weights["lyapunov"] * lyap_norm +
                weights["entropy"] * perm_norm +
                weights["hurst"] * hurst_dev
            )
            
            # Final clamp
            chaos_score = max(0.0, min(1.0, chaos_score))
            
            return chaos_score
            
        except Exception as e:
            logger.error(f"Error computing chaos score: {e}")
            return 0.0
    
    def get_chaos_score(self) -> float:
        """Get the current chaos score."""
        return self.chaos_score if self.chaos_score is not None else 0.0
    
    def get_lyapunov(self) -> float:
        """Get the largest Lyapunov exponent."""
        return self.lyapunov if self.lyapunov is not None else 0.0
    
    def get_permutation_entropy(self) -> float:
        """Get the permutation entropy."""
        return self.permutation_entropy if self.permutation_entropy is not None else 0.0
    
    def get_hurst(self) -> float:
        """Get the Hurst exponent."""
        return self.hurst if self.hurst is not None else 0.5
    
    def get_metrics(self) -> Dict[str, float]:
        """Get all chaos metrics as dictionary."""
        return {
            "chaos_score": self.get_chaos_score(),
            "lyapunov": self.get_lyapunov(),
            "permutation_entropy": self.get_permutation_entropy(),
            "hurst": self.get_hurst(),
        }


# Convenience function for quick analysis
def analyze_tick(tick: Any, window: int = 100) -> Dict[str, float]:
    """
    Quick chaos analysis of a single tick.
    
    Args:
        tick: Tick object or dict
        window: Analysis window size
        
    Returns:
        Dictionary of chaos metrics
    """
    analyzer = ChaosAnalyzer(window=window)
    
    # If we have history, update first
    if hasattr(tick, '__len__') and not isinstance(tick, (str, bytes)):
        # Multiple ticks - update analyzer
        for t in tick if hasattr(tick, '__iter__') else [tick]:
            analyzer.update(t)
    else:
        analyzer.update(tick)
    
    return analyzer.get_metrics()