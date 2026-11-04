#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Configuration Module

Central configuration manager for the Python Quant Engine.
Loads and validates configuration from YAML files with defaults.
Provides access to all engine settings by module.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """
    Central configuration class for CHAOS ENGINE HFT.
    
    Loads configuration from:
    1. config/default.yaml (primary)
    2. config/risk.yaml (risk-specific overrides)
    3. config/symbols.yaml (symbol-specific overrides)
    4. Environment variables (highest priority)
    5. Command-line arguments (highest priority)
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_dir: Path to configuration directory. 
                       Defaults to project root / config
        """
        if config_dir is None:
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(config_dir)
        
        self.config_dir = self.project_root / "config"
        self._config: Dict[str, Any] = {}
        self._loaded = False
        
        # Load in priority order
        self._load_base_config()
        self._load_environment_overrides()
        self._validate_config()
    
    def _load_base_config(self):
        """Load base configuration from YAML files."""
        # Load default.yaml
        default_path = self.config_dir / "default.yaml"
        if default_path.exists():
            with open(default_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"Loaded base config from {default_path}")
        else:
            # Create default config if none exists
            self._config = self._get_default_dict()
            logger.warning(f"No {default_path} found, using defaults")
        
        # Load risk.yaml if exists
        risk_path = self.config_dir / "risk.yaml"
        if risk_path.exists():
            with open(risk_path, 'r', encoding='utf-8') as f:
                risk_config = yaml.safe_load(f) or {}
            self._deep_merge(self._config, risk_config)
            logger.info(f"Loaded risk config from {risk_path}")
        
        # Load symbols.yaml if exists
        symbols_path = self.config_dir / "symbols.yaml"
        if symbols_path.exists():
            with open(symbols_path, 'r', encoding='utf-8') as f:
                symbols_config = yaml.safe_load(f) or {}
            self._deep_merge(self._config, symbols_config)
            logger.info(f"Loaded symbols config from {symbols_path}")
    
    def _get_default_dict(self) -> Dict[str, Any]:
        """Return default configuration dictionary."""
        return {
            "environment": "demo",
            "account_mode": "AUTO",
            "trading": {
                "allow_buy": True,
                "allow_sell": True,
                "frequency_mode": "ADAPTIVE",
                "market_making_enabled": True,
                "martingale_enabled": False
            },
            "risk": {
                "max_daily_loss_percent": 2,
                "max_drawdown_percent": 8,
                "max_portfolio_risk_percent": 1,
                "max_margin_utilization_percent": 20
            },
            "execution": {
                "max_active_orders": 10,
                "max_positions": 10,
                "min_quote_refresh_ms": 250,
                "max_quote_refresh_ms": 5000
            },
            "chaos": {
                "enabled": True,
                "score_min": 0,
                "score_max": 1
            },
            "broker": {
                "auto_detect": True,
                "require_limit_orders": True,
                "dom_optional": True,
                "boc_optional": True
            }
        }
    
    def _deep_merge(self, base: Dict, override: Dict):
        """Deep merge override into base dictionary."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _load_environment_overrides(self):
        """Load environment variable overrides."""
        # Map environment variable names to config keys
        env_mapping = {
            "CHAOS_ENGINE_ENV": "environment",
            "CHAOS_ENGINE_ACCOUNT_MODE": "account_mode",
            "CHAOS_ENGINE_MM_ENABLED": "trading.market_making_enabled",
            "CHAOS_ENGINE_MAX_DAILY_LOSS": "risk.max_daily_loss_percent",
            "CHAOS_ENGINE_MAX_DRAWDOWN": "risk.max_drawdown_percent",
            "CHAOS_ENGINE_MAX_MARGIN": "risk.max_margin_utilization_percent",
            "CHAOS_ENGINE_MAX_ORDERS": "execution.max_active_orders",
            "CHAOS_ENGINE_MAX_POSITIONS": "execution.max_positions",
        }
        
        for env_var, config_key in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Convert to appropriate type
                try:
                    if config_key.endswith("_percent") or config_key.endswith("_min") or config_key.endswith("_max"):
                        value = float(value)
                    else:
                        value = str(value)
                    
                    # Set nested value
                    self._set_nested(self._config, config_key, value)
                    logger.info(f"Environment override: {env_var} = {value}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse env var {env_var}: {e}")
    
    def _set_nested(self, d: Dict, key: str, value: Any):
        """Set a nested dictionary value using dot notation."""
        keys = key.split(".")
        current = d
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    
    def _validate_config(self):
        """Validate configuration values are within acceptable ranges."""
        errors = []
        
        # Validate environment
        env = self.get("environment", "demo")
        if env not in ("demo", "live", "paper"):
            errors.append(f"Invalid environment: {env}")
        
        # Validate trading settings
        trading = self.get("trading", {})
        if not isinstance(trading.get("allow_buy"), bool):
            errors.append("trading.allow_buy must be boolean")
        if not isinstance(trading.get("allow_sell"), bool):
            errors.append("trading.allow_sell must be boolean")
        
        # Validate risk settings
        risk = self.get("risk", {})
        max_daily = risk.get("max_daily_loss_percent", 2)
        if not (0 < max_daily <= 100):
            errors.append(f"risk.max_daily_loss_percent must be > 0 and <= 100, got {max_daily}")
        
        max_dd = risk.get("max_drawdown_percent", 8)
        if not (0 < max_dd <= 100):
            errors.append(f"risk.max_drawdown_percent must be > 0 and <= 100, got {max_dd}")
        
        max_margin = risk.get("max_margin_utilization_percent", 20)
        if not (0 < max_margin <= 100):
            errors.append(f"risk.max_margin_utilization_percent must be > 0 and <= 100, got {max_margin}")
        
        # Validate execution settings
        execution = self.get("execution", {})
        max_orders = execution.get("max_active_orders", 10)
        if not isinstance(max_orders, int) or max_orders < 1:
            errors.append(f"execution.max_active_orders must be positive integer, got {max_orders}")
        
        max_pos = execution.get("max_positions", 10)
        if not isinstance(max_pos, int) or max_pos < 1:
            errors.append(f"execution.max_positions must be positive integer, got {max_pos}")
        
        min_refresh = execution.get("min_quote_refresh_ms", 250)
        if not isinstance(min_refresh, int) or min_refresh < 1:
            errors.append(f"execution.min_quote_refresh_ms must be positive integer, got {min_refresh}")
        
        max_refresh = execution.get("max_quote_refresh_ms", 5000)
        if not isinstance(max_refresh, int) or max_refresh < min_refresh:
            errors.append(f"execution.max_quote_refresh_ms must be >= min_quote_refresh_ms, got {max_refresh}")
        
        # Validate chaos settings
        chaos = self.get("chaos", {})
        if not isinstance(chaos.get("enabled"), bool):
            errors.append("chaos.enabled must be boolean")
        
        # Validate broker settings
        broker = self.get("broker", {})
        if not isinstance(broker.get("auto_detect"), bool):
            errors.append("broker.auto_detect must be boolean")
        
        if errors:
            raise ValueError(f"Configuration validation errors: {'; '.join(errors)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation (e.g., "trading.allow_buy")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        current = self._config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y")
        return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_config(self) -> Dict[str, Any]:
        """Return full configuration dictionary."""
        return self._config.copy()


# Global config instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def init_config(config_dir: Optional[str] = None) -> Config:
    """Initialize the global configuration."""
    global _global_config
    _global_config = Config(config_dir)
    return _global_config


if __name__ == "__main__":
    # Test config loading
    cfg = init_config()
    print("Configuration loaded:")
    print(f"  Environment: {cfg.get('environment')}")
    print(f"  Allow buy: {cfg.get_bool('trading.allow_buy')}")
    print(f"  Allow sell: {cfg.get_bool('trading.allow_sell')}")
    print(f"  Max daily loss: {cfg.get('risk.max_daily_loss_percent')}%")
    print(f"  Max drawdown: {cfg.get('risk.max_drawdown_percent')}%")
    print(f"  Max active orders: {cfg.get_int('execution.max_active_orders')}")
    print(f"  Frequency mode: {cfg.get('trading.frequency_mode')}")