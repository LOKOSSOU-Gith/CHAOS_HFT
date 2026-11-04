#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Market Making Engine

Implements the Avellaneda-Stoikov market making model and extensions.
Calculates optimal Bid/Ask quotes based on inventory, volatility, spread,
and order flow imbalance. Supports multiple regimes and adaptive behavior.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, Literal
import numpy as np
import logging

logger = logging.getLogger("chaos_engine_hft.market_making")


# Order action types
OrderAction = Literal["BUY", "SELL", "HOLD"]

# Quote action results
class QuoteResult:
    """Result from quote optimization."""
    
    def __init__(
        self,
        action: OrderAction = "HOLD",
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        bid_size: Optional[float] = None,
        ask_size: Optional[float] = None,
        spread: Optional[float] = None,
        edge: Optional[float] = None,
        confidence: float = 0.5,
        regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]] = None,
    ):
        self.action = action
        self.bid_price = bid_price
        self.ask_price = ask_price
        self.bid_size = bid_size
        self.ask_size = ask_size
        self.spread = spread
        self.edge = edge
        self.confidence = confidence
        self.regime = regime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for IPC serialization."""
        return {
            "action": self.action,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "spread": self.spread,
            "edge": self.edge,
            "confidence": self.confidence,
            "regime": self.regime,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuoteResult":
        """Create QuoteResult from dictionary."""
        return cls(
            action=data.get("action", "HOLD"),
            bid_price=data.get("bid_price"),
            ask_price=data.get("ask_price"),
            bid_size=data.get("bid_size"),
            ask_size=data.get("ask_size"),
            spread=data.get("spread"),
            edge=data.get("edge"),
            confidence=data.get("confidence", 0.5),
            regime=data.get("regime"),
        )


# Constants for model parameters
DEFAULT_GAMMA = 0.1       # Risk aversion parameter
DEFAULT_TAU = 1.0         # Time horizon parameter
DEFAULT_K = 100           # Base inventory penalty


class MarketMakingEngine:
    """
    Market Making Engine implementing the Avellaneda-Stoikov model.
    
    Core formula: r = S - q × γ × σ² × τ
    where:
    - S = prix médian (mid price)
    - q = inventaire net
    - γ = aversion au risque
    - σ = volatilité
    - τ = horizon temporel
    
    Extensions include:
    - Order Flow Imbalance adjustment
    - Microprice calculation
    - Hawkes Process for event clustering
    - Adverse Selection detection
    - Spread optimization
    - Regime-aware quoting
    """
    
    def __init__(self, 
                 risk_aversion: float = DEFAULT_GAMMA,
                 time_horizon: float = DEFAULT_TAU,
                 base_inventory_penalty: int = DEFAULT_K,
                 spread_optimizer: bool = True,
                 adverse_selection: bool = True):
        """
        Initialize Market Making Engine.
        
        Args:
            risk_aversion: Risk aversion parameter (γ)
            time_horizon: Time horizon parameter (τ)
            base_inventory_penalty: Base penalty for inventory (k)
            spread_optimizer: Whether to use spread optimizer
            adverse_selection: Whether to use adverse selection detector
        """
        self.risk_aversion = risk_aversion
        self.time_horizon = time_horizon
        self.base_inventory_penalty = base_inventory_penalty
        self.spread_optimizer = spread_optimizer
        self.adverse_selection = adverse_selection
        
        # Internal state
        self.mid_price: float = 0.0
        self.spread: float = 0.0
        self.volatility: float = 0.0
        self.inventory: float = 0.0
        self.order_flow_imbalance: float = 0.0
        self.chaos_score: float = 0.0
        self.regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]] = "NORMAL"
        self.adverse_selection_score: float = 0.0
        
        # Model parameters (can be overridden per-symbol)
        self.gamma: float = risk_aversion
        self.tau: float = time_horizon
        self.k: int = base_inventory_penalty
        
        logger.info("MarketMakingEngine initialized")
    
    def set_market_state(
        self,
        mid: float,
        spread: float,
        volatility: float,
        inventory: float,
        order_flow_imbalance: float = 0.0,
        chaos_score: float = 0.0,
        regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]] = None,
        adverse_selection_score: float = 0.0,
    ) -> None:
        """
        Set the current market state for quote calculation.
        
        Args:
            mid: Mid price (bid + ask) / 2
            spread: Current spread in points
            volatility: Current volatility (%)
            inventory: Net inventory in lots
            order_flow_imbalance: Order flow imbalance [-1, 1]
            chaos_score: Chaos mathematics score
            regime: Current trading regime
            adverse_selection_score: Adverse selection detection score
        """
        self.mid_price = mid
        self.spread = spread
        self.volatility = volatility
        self.inventory = inventory
        self.order_flow_imbalance = order_flow_imbalance
        self.chaos_score = chaos_score
        self.regime = regime
        self.adverse_selection_score = adverse_selection_score
    
    def calculate_quotes(
        self,
        mid: Optional[float] = None,
        inventory: Optional[float] = None,
        volatility: Optional[float] = None,
        regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]] = None,
    ) -> QuoteResult:
        """
        Calculate optimal Bid and Ask quotes using Avellaneda-Stoikov model.
        
        Core formula: r = S - q × γ × σ² × τ
        
        Where:
        - r = reservation price offset from mid
        - S = mid price
        - q = net inventory
        - γ = risk aversion
        - σ² = volatility squared
        - τ = time horizon
        
        Then:
        - Bid = S - r - spread/2
        - Ask = S + r + spread/2
        
        Args:
            mid: Mid price (uses internal state if None)
            inventory: Net inventory (uses internal state if None)
            volatility: Volatility (uses internal state if None)
            regime: Trading regime (uses internal state if None)
            
        Returns:
            QuoteResult with optimal bid/ask prices and sizes
        """
        # Use provided values or internal state
        mid = mid if mid is not None else self.mid_price
        inv = inventory if inventory is not None else self.inventory
        vol = volatility if volatility is not None else self.volatility
        reg = regime if regime is not None else self.regime
        
        if mid <= 0 or vol <= 0:
            return QuoteResult(action="HOLD", confidence=0.0)
        
        # Calculate volatility squared
        vol_sq = vol ** 2
        
        # Calculate reservation price offset (r = S - q × γ × σ² × τ)
        # But we want the offset FROM mid, so:
        r = inv * self.gamma * vol_sq * self.tau
        
        # Apply inventory skew adjustment
        # If long inventory, reduce bid and increase ask (conservative)
        # If short inventory, increase bid and reduce ask (conservative)
        skew_adjustment = inv * self.k / 1000.0  # Scale factor
        
        # Apply order flow imbalance adjustment
        ofi_adjustment = self.order_flow_imbalance * vol * 0.1
        
        # Apply adverse selection adjustment
        as_adjustment = self.adverse_selection_score * vol * 0.05
        
        # Regime-specific adjustments
        regime_adjustment = 0.0
        if reg == "HIGH_ACTIVITY":
            # Tighter spreads, more aggressive quoting
            regime_adjustment = -0.5 * vol  # Tighten by 0.5 vol%
        elif reg == "REDUCED_ACTIVITY":
            # Wider spreads, more conservative
            regime_adjustment = 1.5 * vol  # Widen by 1.5 vol%
        elif reg == "PROTECTION_MODE":
            # Minimal quoting, preserve capital
            regime_adjustment = 3.0 * vol  # Significantly widen
        
        # Total offset
        total_offset = r + skew_adjustment + ofi_adjustment + as_adjustment + regime_adjustment
        
        # Calculate bid and ask offsets from mid
        # spread/2 is the base half-spread
        half_spread = self.spread / 2 if self.spread > 0 else mid * 0.001  # 0.1% default
        
        bid_offset = half_spread + total_offset
        ask_offset = half_spread - total_offset
        
        # Ensure positive offsets
        bid_offset = max(bid_offset, 0.0001)
        ask_offset = max(ask_offset, 0.0001)
        
        # Calculate quote sizes based on confidence and regime
        bid_size, ask_size = self._calculate_sizes(inv, reg, vol)
        
        # Calculate edge estimate
        edge = self._calculate_edge(vol, inventory, order_flow_imbalance)
        
        # Determine action
        action = self._determine_action(bid_offset, ask_offset, edge, reg)
        
        # Calculate confidence
        confidence = self._calculate_confidence(vol, reg, edge)
        
        return QuoteResult(
            action=action,
            bid_price=mid - bid_offset if action in ("BUY", "HOLD") else None,
            ask_price=mid + ask_offset if action in ("SELL", "HOLD") else None,
            bid_size=bid_size,
            ask_size=ask_size,
            spread=bid_offset + ask_offset,
            edge=edge,
            confidence=confidence,
            regime=reg,
        )
    
    def _calculate_sizes(
        self,
        inventory: float,
        regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]],
        volatility: float,
    ) -> tuple:
        """Calculate bid and ask sizes based on regime and state."""
        # Base size decreases with inventory risk
        base_size = max(0.1, 1.0 - abs(inventory) * 0.1)
        
        # Regime adjustments
        if regime == "HIGH_ACTIVITY":
            # Full size, can be aggressive
            multiplier = 1.0
        elif regime == "NORMAL":
            multiplier = 0.9
        elif regime == "REDUCED_ACTIVITY":
            multiplier = 0.5
        elif regime == "PROTECTION_MODE":
            multiplier = 0.1
        else:
            multiplier = 0.8
        
        # Volatility adjustment - higher vol = smaller sizes
        vol_adj = max(0.1, 1.0 - vol / 100.0)
        
        size = base_size * multiplier * vol_adj
        
        return size, size  # Symmetric sizes for simplicity
    
    def _calculate_edge(self, volatility: float, inventory: float, 
                       order_flow_imbalance: float) -> Optional[float]:
        """
        Calculate estimated edge (expected profit per trade).
        
        Returns edge in percentage points, or None if not calculable.
        """
        try:
            # Base edge from spread capture
            spread_edge = self.spread / self.mid_price * 100.0 if self.mid_price > 0 else 0
            
            # Inventory cost carry
            carry_cost = abs(inventory) * volatility / 100.0 * 0.1
            
            # Order flow imbalance effect
            ofi_effect = order_flow_imbalance * volatility * 0.05
            
            # Total edge
            edge = spread_edge - carry_cost + ofi_effect
            
            # Clamp to reasonable range
            edge = max(-10.0, min(10.0, edge))
            
            return round(edge, 4)
            
        except Exception:
            return 0.0
    
    def _determine_action(
        self,
        bid_offset: float,
        ask_offset: float,
        edge: float,
        regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]],
    ) -> OrderAction:
        """
        Determine whether to BUY, SELL, or HOLD.
        
        Logic:
        - If edge > threshold and not inventory-heavy: provide both sides
        - If edge positive but inventory concerns: lean opposite side
        - If edge negative or regime protective: HOLD
        """
        # Edge threshold by regime
        thresholds = {
            "HIGH_ACTIVITY": 0.05,    # 0.05%
            "NORMAL": 0.10,           # 0.10%
            "REDUCED_ACTIVITY": 0.15, # 0.15%
            "PROTECTION_MODE": 0.0,   # No threshold - hold
        }
        
        threshold = thresholds.get(regime, 0.10)
        
        # Check if we have sufficient edge
        has_sufficient_edge = abs(edge) > threshold
        
        # Inventory-based leaning
        inventory_factor = abs(inventory) * 0.02  # 2% lean per lot
        
        # Decision logic
        if has_sufficient_edge and edge > 0 and inventory < 3:
            # Positive edge, not too inventory-heavy -> provide both sides (implicitly BUY+SELL)
            return "HOLD"  # Engine provides both sides, caller decides
        
        elif has_sufficient_edge and edge < 0 and inventory > -3:
            # Negative edge, not too short inventory -> hold
            return "HOLD"
        
        elif edge > 0 and inventory > 0:
            # Positive edge but long inventory -> lean SELL
            return "SELL"
        
        elif edge < 0 and inventory < 0:
            # Negative edge but short inventory -> lean BUY
            return "BUY"
        
        elif edge > 0:
            # Positive edge -> provide both (return HOLD, engine handles both sides)
            return "HOLD"
        
        elif edge < 0:
            # Negative edge -> HOLD, don't quote
            return "HOLD"
        
        else:
            # Indeterminate -> HOLD
            return "HOLD"
    
    def _calculate_confidence(self, volatility: float, regime: Optional[str], 
                             edge: float) -> float:
        """
        Calculate confidence in the quote (0.0 to 1.0).
        
        Higher confidence when:
        - Volatility is well-known (not extreme)
        - Regime is stable
        - Edge estimate is clear and positive
        """
        try:
            # Base confidence
            confidence = 0.5
            
            # Regime stability
            regime_stability = {
                "HIGH_ACTIVITY": 0.8,
                "NORMAL": 0.9,
                "REDUCED_ACTIVITY": 0.7,
                "PROTECTION_MODE": 0.3,
            }
            confidence *= regime_stability.get(regime, 0.7) if regime else 0.7
            
            # Edge clarity - how far from zero
            edge_clarity = min(1.0, abs(edge) * 20)  # 0.05 edge -> 1.0 confidence
            confidence *= (0.5 + 0.5 * edge_clarity)
            
            # Volatility reasonableness - not too high, not too low
            vol_reasonable = max(0.0, 1.0 - abs(volatility - 15.0) / 50.0)  # ~15% is ideal
            confidence *= 0.5 + 0.5 * vol_reasonable
            
            # Clamp
            confidence = max(0.0, min(1.0, confidence))
            
            return round(confidence, 3)
            
        except Exception:
            return 0.5
    
    def optimize_spread(
        self,
        volatility: float,
        inventory: float,
        regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]] = None,
    ) -> float:
        """
        Optimize spread based on current conditions.
        
        Uses a modified Avellaneda-Stoikov spread formula.
        """
        # Base spread components
        vol_component = volatility / 100.0  # Convert % to decimal
        inv_component = abs(inventory) * 0.05  # Inventory penalty
        regime_component = {
            "HIGH_ACTIVITY": 1.0,
            "NORMAL": 1.0,
            "REDUCED_ACTIVITY": 1.5,
            "PROTECTION_MODE": 2.5,
        }.get(regime, 1.0)
        
        # Final spread in percentage
        base_spread_pct = 2 * vol_component * regime_component
        
        # Minimum and maximum spreads
        min_spread_pct = 0.001  # 0.1 basis points
        max_spread_pct = 0.05   # 5 basis points
        
        # Clamp
        final_spread_pct = max(min_spread_pct, min(max_spread_pct, base_spread_pct))
        
        return round(final_spread_pct, 6)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize engine state to dictionary."""
        return {
            "mid_price": self.mid_price,
            "spread": self.spread,
            "volatility": self.volatility,
            "inventory": self.inventory,
            "order_flow_imbalance": self.order_flow_imbalance,
            "chaos_score": self.chaos_score,
            "regime": self.regime,
            "adverse_selection_score": self.adverse_selection_score,
            "gamma": self.gamma,
            "tau": self.tau,
            "k": self.k,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketMakingEngine":
        """Create engine from dictionary state."""
        engine = cls(
            risk_aversion=data.get("gamma", DEFAULT_GAMMA),
            time_horizon=data.get("tau", DEFAULT_TAU),
            base_inventory_penalty=data.get("k", DEFAULT_K),
        )
        engine.mid_price = data.get("mid_price", 0.0)
        engine.spread = data.get("spread", 0.0)
        engine.volatility = data.get("volatility", 0.0)
        engine.inventory = data.get("inventory", 0.0)
        engine.order_flow_imbalance = data.get("order_flow_imbalance", 0.0)
        engine.chaos_score = data.get("chaos_score", 0.0)
        engine.regime = data.get("regime", "NORMAL")
        engine.adverse_selection_score = data.get("adverse_selection_score", 0.0)
        return engine


# Convenience function for quick quote calculation
def quick_quotes(
    mid: float,
    inventory: float,
    volatility: float,
    spread: float = 0.0,
    gamma: float = DEFAULT_GAMMA,
    tau: float = DEFAULT_TAU,
    k: int = DEFAULT_K,
    regime: Optional[Literal["HIGH_ACTIVITY", "NORMAL", "REDUCED", "PROTECTION"]] = None,
) -> QuoteResult:
    """
    Quick quote calculation with specified parameters.
    
    Convenience function for testing and rapid evaluation.
    """
    engine = MarketMakingEngine(
        risk_aversion=gamma,
        time_horizon=tau,
        base_inventory_penalty=k,
    )
    engine.set_market_state(
        mid=mid,
        spread=spread,
        volatility=volatility,
        inventory=inventory,
        regime=regime,
    )
    return engine.calculate_quotes()


if __name__ == "__main__":
    # Quick test
    import numpy as np
    
    result = quick_quotes(
        mid=1.1178,
        inventory=0.5,
        volatility=1.5,
        spread=1.2,
        gamma=0.1,
        tau=1.0,
        k=100,
        regime="NORMAL",
    )
    
    print(f"Quote Result: {result.action}")
    print(f"  Bid Price: {result.bid_price}")
    print(f"  Ask Price: {result.ask_price}")
    print(f"  Spread: {result.spread}")
    print(f"  Edge: {result.edge}")
    print(f"  Confidence: {result.confidence}")