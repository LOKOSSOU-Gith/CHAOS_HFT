#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Backend Core Module

Core business logic for the FastAPI backend.
Handles authentication, permission checks, state management,
and integration with other system components.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("chaos_engine_hft.core")


# Security utilities
def verify_api_key(api_key: str) -> bool:
    """Verify API key for endpoint access."""
    # Placeholder - in production would validate against stored keys
    return api_key == "chaos_engine_hft_key_2026"


def check_permission(user_role: str, required_role: str) -> bool:
    """Check if user has required permission role."""
    # Role hierarchy
    hierarchy = {"admin": ["admin", "trader", "viewer"],
                 "trader": ["trader", "viewer"],
                 "viewer": ["viewer"]}
    
    return user_role in hierarchy.get(required_role, [])


# State management
class SystemState:
    """Singleton-like system state manager."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.trading_state = TradingState.STOPPED
            self.environment = Environment.DEMO
            self.account_mode = AccountMode.AUTO
            self.symbol = "EURUSDm"
            self.uptime_start = None
            self._initialized = True
    
    def update_from_config(self):
        """Update state from current configuration."""
        from config import get_config
        config = get_config()
        
        env = config.get("environment", "demo")
        mode = config.get("account_mode", "AUTO")
        
        self.environment = Environment(env) if env in Environment.__members__ else Environment.DEMO
        self.account_mode = AccountMode(mode) if mode in AccountMode.__members__ else AccountMode.AUTO
        
        self.symbol = config.get("broker.symbol", "EURUSDm")
    
    def can_trade(self) -> bool:
        """Check if trading is allowed."""
        if self.environment == Environment.LIVE:
            # Live trading requires explicit authorization
            return False  # Would check auth config
        return self.trading_state in (TradingState.RUNNING, TradingState.STARTING)
    
    def can_start_trading(self) -> bool:
        """Check if trading can be started."""
        return (self.environment in (Environment.DEMO, Environment.PAPER) and 
                self.trading_state == TradingState.STOPPED)


# Trading state enum
from enum import Enum

class TradingState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"


# Environment enum
from enum import Enum

class Environment(str, Enum):
    DEMO = "demo"
    LIVE = "live"
    PAPER = "paper"


# Account mode enum
from enum import Enum

class AccountMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# Database models (placeholders - actual SQLAlchemy models in database module)
class BotInstance(BaseModel):
    """Bot instance model."""
    id: str
    name: str
    status: TradingState = TradingState.STOPPED
    environment: Environment = Environment.DEMO
    symbol: str = "EURUSDm"
    created_at: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    config: Dict[str, Any] = {}


# Service interfaces
class IBotService:
    """Interface for bot services."""
    
    async def start_bot(self, instance_id: str) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def stop_bot(self, instance_id: str) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def get_status(self, instance_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class IAccountService:
    """Interface for account services."""
    
    async def get_account_info(self) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def get_positions(self) -> Dict[str, Any]:
        raise NotImplementedError


# Export commonly used types
__all__ = [
    "verify_api_key",
    "check_permission", 
    "SystemState",
    "TradingState",
    "Environment",
    "AccountMode",
    "BotInstance",
    "IBotService",
    "IAccountService",
]