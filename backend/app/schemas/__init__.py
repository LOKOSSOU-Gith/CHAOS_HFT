#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - API Schemas Module

Pydantic models for request/response validation and serialization.
Maps to database models and API endpoints.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum

# Enums
class TradingState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"


class Environment(str, Enum):
    DEMO = "demo"
    LIVE = "live"
    PAPER = "paper"


class AccountMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class OrderType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_LIMIT = "SELL_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_STOP = "SELL_STOP"
    BUY_LIMIT_ENTRY = "BUY_LIMIT_ENTRY"
    SELL_LIMIT_ENTRY = "SELL_LIMIT_ENTRY"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    REPLACED = "replaced"


class RegimeType(str, Enum):
    CALM = "CALM"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    CRITICAL = "CRITICAL"


class FillingMode(str, Enum):
    FOK = "FOK"  # Fill or Kill
    IOC = "IOC"  # Immediate or Cancel
    RETURN = "RETURN"  # Return (default MT5)
    BOC = "BOC"  # Best Offer Cancel


# ============================================================
# Health Check
# ============================================================

class HealthCheck(BaseModel):
    """Health check response."""
    status: str = "healthy"
    timestamp: float = Field(default_factory=datetime.now().timestamp)
    uptime_seconds: float = Field(default_factory=lambda: (datetime.now() - datetime(1970, 1, 1)).total_seconds())
    version: str = "0.1.0"


# ============================================================
# Status Endpoints
# ============================================================

class StatusResponse(BaseModel):
    """Robot status response."""
    state: TradingState
    environment: Environment
    account_mode: AccountMode
    symbol: str = "EURUSDm"
    connected: bool = False
    uptime_seconds: float = Field(default_factory=lambda: (datetime.now() - datetime(1970, 1, 1)).total_seconds())


# ============================================================
# Account Endpoints
# ============================================================

class AccountInfo(BaseModel):
    """Account information response."""
    balance: float = Field(default=10000.0, ge=0)
    equity: float = Field(default=10000.0, ge=0)
    margin_used: float = Field(default=0.0, ge=0)
    margin_free: float = Field(default=10000.0, ge=0)
    margin_utilization: float = Field(
        default=0.0, ge=0, le=100, alias="marginUtilization"
    )
    daily_pnl: float = Field(default=0.0, ge=-1000, le=1000)
    daily_return_pct: float = Field(
        default=0.0, ge=-100, le=100, alias="dailyReturnPct"
    )
    max_daily_loss_pct: float = Field(
        default=2.0, ge=0, le=100, alias="maxDailyLossPct"
    )
    max_drawdown_pct: float = Field(
        default=8.0, ge=0, le=100, alias="maxDrawdownPct"
    )


# ============================================================
# Position Endpoints
# ============================================================

class PositionSizing(BaseModel):
    """Position sizing information."""
    symbol: str
    net_volume: float = Field(default=0.0, ge=0)
    long_volume: float = Field(default=0.0, ge=0)
    short_volume: float = Field(default=0.0, ge=0)
    avg_price: float = Field(default=0.0, ge=0)
    margin_used: float = Field(default=0.0, ge=0)
    swaps: float = Field(default=0.0, ge=0)
    commission: float = Field(default=0.0, ge=0)
    profit: float = Field(default=0.0, ge=0)


class PositionInfo(BaseModel):
    """Position information for a symbol."""
    symbol: str
    volume: float = Field(default=0.0, ge=0)
    net_volume: float = Field(default=0.0, ge=0)
    avg_price: float = Field(default=0.0, ge=0)
    swaps: float = Field(default=0.0)
    commission: float = Field(default=0.0)
    profit: float = Field(default=0.0)
    commission_paid: float = Field(default=0.0, ge=0)


# ============================================================
# Order Endpoints
# ============================================================

class OrderRequest(BaseModel):
    """Order placement request."""
    symbol: str = "EURUSDm"
    order_type: OrderType = OrderType.BUY_LIMIT
    volume: float = Field(gt=0, le=100.0, description="Volume in lots")
    price: Optional[float] = Field(
        default=None, 
        ge=0.0001,
        description="Limit price (None for market order)"
    )
    comment: str = "hft_scalper_demo"
    magic: int = 860001
    filling_mode: FillingMode = FillingMode.RETURN
    
    @validator("volume")
    def volume_reasonable(cls, v):
        if v < 0.01:
            raise ValueError("Volume too small - minimum 0.01 lots")
        if v > 50.0:
            raise ValueError("Volume too large - maximum 50 lots")
        return v
    
    @validator("price")
    def price_required_for_limit(cls, v, values):
        order_type = values.data.get("order_type") if hasattr(values, 'data') else None
        # For limit/stop orders, price must be provided
        if order_type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT, 
                          OrderType.BUY_STOP, OrderType.SELL_STOP):
            if v is None:
                raise ValueError(f"Price required for {order_type} order")
        return v


class OrderResponse(BaseModel):
    """Order placement response."""
    ticket: int = Field(default=0, ge=0)
    status: OrderStatus = OrderStatus.PENDING
    symbol: str
    volume: float
    price: float
    comment: str
    magic: int = Field(default=860001)
    request_time: float = Field(default_factory=datetime.now().timestamp)
    execution_time: Optional[float] = Field(default=None)
    filled_price: Optional[float] = Field(default=None)
    filled_volume: float = Field(default=0.0, ge=0)
    partial_fill: bool = Field(default=False)


# ============================================================
# Configuration Endpoints
# ============================================================

class ConfigKeyValue(BaseModel):
    """Configuration key-value pair."""
    key: str
    value: Any
    
    @validator("key")
    def key_must_be_valid(cls, v):
        # Valid config keys
        valid_keys = [
            "environment", "account_mode",
            "trading.allow_buy", "trading.allow_sell",
            "risk.max_daily_loss_percent", "risk.max_drawdown_percent",
            "execution.max_active_orders", "execution.max_positions",
            "chaos.enabled", "chaos.score_min", "chaos.score_max",
            "broker.auto_detect", "broker.require_limit_orders",
        ]
        if v not in valid_keys:
            # Allow any key but warn
            import warnings
            warnings.warn(f"Config key '{v}' not in predefined list")
        return v


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""
    key: str
    value: Any


class ConfigResponse(BaseModel):
    """Configuration response."""
    environment: Environment = Environment.DEMO
    account_mode: AccountMode = AccountMode.AUTO
    trading: Dict[str, Any]
    risk: Dict[str, Any]
    execution: Dict[str, Any]
    chaos: Dict[str, Any]
    broker: Dict[str, Any]


# ============================================================
# Symbol Endpoints
# ============================================================

class SymbolInfo(BaseModel):
    """Symbol information."""
    symbol: str
    description: str = ""
    point_value: float = Field(default=1.0, ge=0)
    tick_size: float = Field(default=0.00001, gt=0)
    trade_mode: str = "both"
    margin_mode: str = "retail_hedging"
    max_lot: float = Field(default=100.0, gt=0)
    min_lot: float = Field(default=0.01, gt=0)
    lot_step: float = Field(default=0.01, gt=0)
    spread_mode: str = "variable"
    filling_mode: FillingMode = FillingMode.RETURN
    volume_min: float = Field(default=0.01, gt=0)
    volume_max: float = Field(default=10.0, gt=0)
    tick_value: float = Field(default=1.0, ge=0)
    swaps_long: float = Field(default=0.0)
    swaps_short: float = Field(default=0.0)
    commission: float = Field(default=0.0, ge=0)


class SymbolsList(BaseModel):
    """List of available symbols."""
    symbols: List[SymbolInfo]
    selected: str = "EURUSDm"


# ============================================================
# Metrics Endpoints
# ============================================================

class MetricsResponse(BaseModel):
    """Performance metrics response."""
    total_trades: int = Field(default=0, ge=0)
    win_rate: float = Field(default=0.0, ge=0, le=100)
    profit_factor: float = Field(default=0.0, ge=0)
    total_return_pct: float = Field(default=0.0, ge=-100, le=100)
    max_drawdown_pct: float = Field(default=0.0, ge=0, le=100)
    sharpe_ratio: float = Field(default=0.0)
    calmar_ratio: float = Field(default=0.0)
    total_cotations: int = Field(default=0, ge=0)
    total_rejections: int = Field(default=0, ge=0)
    acceptances: int = Field(default=0, ge=0)
    slippage_total: float = Field(default=0.0, ge=0)


# ============================================================
# Risk Endpoints
# ============================================================

class RiskLimits(BaseModel):
    """Risk limits configuration."""
    max_daily_loss_pct: float = Field(default=2.0, ge=0, le=100)
    max_drawdown_pct: float = Field(default=8.0, ge=0, le=100)
    max_margin_utilization_pct: float = Field(
        default=20.0, ge=0, le=100
    )
    max_portfolio_risk_pct: float = Field(
        default=1.0, ge=0, le=100
    )
    risk_per_new_exposure_pct: float = Field(
        default=0.25, ge=0, le=100
    )
    max_active_orders: int = Field(default=10, ge=1)
    max_positions: int = Field(default=10, ge=1)


class RiskStatus(BaseModel):
    """Current risk status."""
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_margin_utilization_pct: float
    current_daily_pnl_pct: float = Field(default=0.0)
    current_margin_utilization_pct: float = Field(default=0.0)
    daily_loss_triggered: bool = False
    drawdown_warning_triggered: bool = False
    hard_drawdown_stopped: bool = False
    max_positions_reached: bool = False
    max_orders_reached: bool = False


# ============================================================
# Log Endpoints
# ============================================================

class LogEntry(BaseModel):
    """Single log entry."""
    timestamp: float = Field(default_factory=datetime.now().timestamp)
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    message: str
    component: str = "api"
    metadata: Optional[Dict[str, Any]] = None


class LogsResponse(BaseModel):
    """Logs response."""
    total_returned: int
    logs: List[LogEntry]


# ============================================================
# Utility Functions
# ============================================================

def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """Convert Pydantic model to dictionary."""
    return model.model_dump() if hasattr(model, 'model_dump') else model.dict()


def validate_config_value(key: str, value: Any) -> Any:
    """Validate and convert a configuration value."""
    # Type conversions based on key
    type_converters = {
        "max_daily_loss_pct": float,
        "max_drawdown_pct": float,
        "max_margin_utilization_pct": float,
        "risk_per_new_exposure_pct": float,
        "max_active_orders": int,
        "max_positions": int,
        "score_min": float,
        "score_max": float,
    }
    
    converter = type_converters.get(key)
    if converter:
        try:
            return converter(value)
        except (ValueError, TypeError):
            return value
    
    return value