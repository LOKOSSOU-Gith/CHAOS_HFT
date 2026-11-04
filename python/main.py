#!/usr/bin/env python3
"""
CHAOS ENGINE HFT - Python Quant Engine Main Entry Point

Entry point for the Python side of the CHAOS ENGINE HFT system.
Handles market data processing, strategy calculations, and IPC communication
with the MQL5 Expert Advisor.

This module does NOT make synchronous trading decisions per tick.
It provides quantitative recommendations that MQL5 validates before execution.
"""

import sys
import os
import time
import json
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bridge.ipc import IPCBridge
from market_data.feed import MarketDataFeed
from market_making.engine import MarketMakingEngine
from chaos.analyzer import ChaosAnalyzer
from regime.classifier import RegimeClassifier
from portfolio.manager import PortfolioManager
from monitoring.logger import MonitoringLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / "logs" / "python_engine.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("chaos_engine_hft")

class PythonQuantEngine:
    """
    Main Python Quant Engine class.
    
    Responsibilities:
    1. Receive market data from MQL5 via IPC
    2. Calculate quantitative indicators
    3. Detect market regimes
    4. Optimize quotes
    5. Produce bounded recommendations
    6. Calculate statistics
    7. Communicate with MQL5
    8. Record results
    """
    
    def __init__(self):
        self.project_root = project_root
        self.running = False
        self.last_tick_time = 0
        self.tick_counter = 0
        
        # Initialize components
        self.ipc = IPCBridge()
        self.market_data = MarketDataFeed()
        self.mm_engine = MarketMakingEngine()
        self.chaos_analyzer = ChaosAnalyzer()
        self.regime_classifier = RegimeClassifier()
        self.portfolio_manager = PortfolioManager()
        self.monitor = MonitoringLogger()
        
        # Configuration
        self.config = self._load_config()
        self.regime_mode = "NORMAL"
        
        # Statistics
        self.stats = {
            "total_cotations": 0,
            "total_trades": 0,
            "start_time": time.time(),
            "regime_changes": 0,
            "rejections": 0,
            "accepted": 0
        }
        
        logger.info("Python Quant Engine initialized")
    
    def _load_config(self):
        """Load configuration from YAML or JSON."""
        config_path = self.project_root / "config" / "default.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        return self._default_config()
    
    def _default_config(self):
        """Default configuration."""
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
    
    def start(self):
        """Start the Python Quant Engine."""
        logger.info("Starting Python Quant Engine...")
        self.running = True
        
        # Initialize IPC connection to MQL5
        if not self.ipc.connect():
            logger.error("Failed to connect to MQL5 IPC bridge")
            return False
        
        # Initialize market data feed
        self.market_data.start()
        
        # Initialize monitoring directory
        self.monitor.start()
        
        logger.info("Python Quant Engine started - waiting for MQL5 data...")
        
        # Main loop
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down...")
        finally:
            self.stop()
        
        return True
    
    def _main_loop(self):
        """Main processing loop."""
        loop_count = 0
        
        while self.running:
            loop_count += 1
            
            # Get latest tick data from MQL5
            tick = self.ipc.receive_tick()
            
            if tick:
                self._process_tick(tick)
            
            # Regime classification every 10 ticks
            if loop_count % 10 == 0:
                self._classify_regime()
            
            # Full market making optimization every 50 ticks
            if loop_count % 50 == 0:
                self._optimize_quotes()
            
            # Statistics and monitoring every 100 ticks
            if loop_count % 100 == 0:
                self._report_stats()
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.01)
    
    def _process_tick(self, tick):
        """Process a single tick from MQL5."""
        self.tick_counter += 1
        current_time = time.time()
        
        # Update market data feed
        self.market_data.update(tick)
        
        # Calculate chaos score
        chaos_score = self.chaos_analyzer.calculate(tick)
        
        # Classify market regime
        regime = self.regime_classifier.classify(tick, chaos_score)
        
        # Update regime if changed
        if regime != self.regime_mode:
            self.regime_mode = regime
            self.stats["regime_changes"] += 1
            logger.info(f"Regime changed to: {regime}")
        
        # Market making engine evaluation
        if self.config["trading"]["market_making_enabled"]:
            mm_result = self.mm_engine.evaluate(tick, chaos_score, regime)
            
            if mm_result["action"] != "HOLD":
                # Portfolio risk check
                risk_check = self.portfolio_manager.check_risk(mm_result, tick)
                
                if risk_check["allowed"]:
                    # Send recommendation to MQL5 via IPC
                    self.ipc.send_recommendation(mm_result, risk_check)
                    self.stats["accepted"] += 1
                else:
                    self.stats["rejections"] += 1
        
        # Record metrics
        self.monitor.record(tick, chaos_score, self.regime_mode)
    
    def _classify_regime(self):
        """Classify current market regime."""
        if not self.market_data.has_data():
            return
        
        tick = self.market_data.get_latest()
        chaos_score = self.chaos_analyzer.calculate(tick)
        regime = self.regime_classifier.classify(tick, chaos_score)
        
        # Regime-specific adjustments
        if regime == "HIGH_VOLATILITY":
            self.mm_engine.reduce_activity()
        elif regime == "TRENDING":
            self.mm_engine.adjust_for_trend()
        elif regime == "RANGING":
            self.mm_engine.adjust_for_ranging()
        elif regime == "CRITICAL":
            self.mm_engine.protection_mode()
    
    def _optimize_quotes(self):
        """Optimize quote parameters based on current conditions."""
        if not self.market_data.has_data():
            return
        
        tick = self.market_data.get_latest()
        chaos_score = self.chaos_analyzer.calculate(tick)
        
        # Calculate optimal spread
        optimal_spread = self.mm_engine.calculate_optimal_spread(
            tick, chaos_score, self.regime_mode
        )
        
        # Calculate optimal position sizes
        position_sizes = self.portfolio_manager.calculate_position_sizes(
            tick, chaos_score, self.regime_mode
        )
        
        # Send optimized parameters to MQL5
        self.ipc.send_quote_optimization(optimal_spread, position_sizes)
    
    def _report_stats(self):
        """Report statistics and health check."""
        uptime = time.time() - self.stats["start_time"]
        
        stats = {
            "uptime_seconds": uptime,
            "tick_counter": self.tick_counter,
            "regime": self.regime_mode,
            "total_cotations": self.stats["total_cotations"],
            "total_trades": self.stats["total_trades"],
            "rejections": self.stats["rejections"],
            "accepted": self.stats["accepted"],
            "rejection_rate": self.stats["rejections"] / max(self.tick_counter, 1) * 100,
        }
        
        logger.info(f"Stats: {json.dumps(stats, indent=2)}")
        
        # Write stats to file
        stats_path = self.project_root / "logs" / "engine_stats.json"
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
    
    def stop(self):
        """Stop the Python Quant Engine."""
        logger.info("Stopping Python Quant Engine...")
        self.running = False
        
        # Stop components
        self.market_data.stop()
        self.ipc.disconnect()
        self.monitor.stop()
        
        # Final statistics
        final_stats = {
            "total_runtime": time.time() - self.stats["start_time"],
            "total_ticks": self.tick_counter,
            "final_regime": self.regime_mode,
            "total_accepted": self.stats["accepted"],
            "total_rejected": self.stats["rejections"],
        }
        logger.info(f"Final stats: {json.dumps(final_stats, indent=2)}")


def main():
    """Main entry point."""
    engine = PythonQuantEngine()
    
    try:
        if not engine.start():
            sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()