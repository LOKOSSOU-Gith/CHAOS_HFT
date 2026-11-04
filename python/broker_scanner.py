"""Broker Compatibility Scanner for MetaTrader 5.

Scanne automatiquement les capacités du broker MT5 connecté et
génère des rapports CSV et JSON classant chaque instrument :
- COMPATIBLE
- PARTIAL
- INCOMPATIBLE

Ne considère pas automatiquement l'absence de DOM ou de BOC comme une incompatibilité.
Ne doit envoyer aucun ordre.

Usage:
    python broker_scanner.py
"""

import csv
import json
import sys
import os

# Add hft_bot to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5


def get_margin_mode_name(mode):
    """Convert margin mode integer to name."""
    mode_map = {
        0: "ACCOUNT_MARGIN_MODE_UNKNOWN",
        1: "ACCOUNT_MARGIN_MODE_EXCHANGE",
        2: "ACCOUNT_MARGIN_MODE_RETAIL_NETTING",
        3: "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING"
    }
    return mode_map.get(mode, "UNKNOWN")


def scan_broker_capabilities():
    """Scanner complet des capacités du broker MT5."""
    
    results = {
        "broker_name": None,
        "server": None,
        "account_mode": None,
        "margin_mode_name": None,
        "currency": None,
        "leverage": None,
        "instruments": [],
        "classification": {},
        "summary": {
            "total_instruments": 0,
            "compatible": 0,
            "partial": 0,
            "incompatible": 0
        }
    }
    
    # Basic account info
    account = mt5.account_info()
    if account:
        results["server"] = account.server
        results["currency"] = account.currency
        results["leverage"] = account.leverage
        results["account_mode"] = account.margin_mode
        results["margin_mode_name"] = get_margin_mode_name(account.margin_mode)
    
    # Get all symbols
    symbols = mt5.symbols_get()
    if symbols is None:
        print("Impossible de récupérer les symboles")
        return results
    
    results["symbols_total"] = len(symbols)
    
    for symbol_obj in symbols:
        name = symbol_obj.name
        
        # Skip symbols we don't trade
        if not symbol_obj.visible:
            continue
        
        symbol_info = mt5.symbol_info(name)
        if symbol_info is None:
            continue
        
        # Classification for this symbol
        classification = {
            "name": name,
            "compatible": True,
            "reasons": [],
            "limitations": []
        }
        
        # Check if trading is allowed (visible = available for trading)
        if not symbol_info.visible:
            classification["compatible"] = False
            classification["reasons"].append("Symbol not visible in market watch")
            classification["limitations"].append("Cannot place orders - not in market watch")
        
        # Check volume limits
        volume_min = symbol_info.volume_min
        volume_max = symbol_info.volume_max
        volume_step = symbol_info.volume_step
        
        if volume_min >= 0:
            classification["volume_min"] = volume_min
            classification["volume_max"] = volume_max
            classification["volume_step"] = volume_step
            
            # Check for reasonable volume range
            if volume_min > 1.0 or volume_max < 0.01:
                classification["limitations"].append(f"Volume range: {volume_min} - {volume_max} lots")
        
        # Check tick size
        tick_size = symbol_info.trade_tick_size
        if tick_size > 0:
            classification["tick_size"] = tick_size
        
        # Check tick value
        tick_value = symbol_info.trade_tick_value
        if tick_value > 0:
            classification["tick_value"] = tick_value
        
        # Check spread
        spread = symbol_info.spread
        classification["spread"] = spread
        
        # Check stop level
        stop_level = symbol_info.trade_stops_level
        if stop_level > 0:
            classification["stop_level"] = stop_level
            classification["limitations"].append(f"Stop level: {stop_level} points")
        
        # Check execution type via trade mode
        trade_mode = symbol_info.trade_mode
        if trade_mode > 0:
            classification["trade_mode"] = trade_mode
        
        # Check freeze level
        freeze_level = symbol_info.trade_freeze_level
        if freeze_level > 0:
            classification["freeze_level"] = freeze_level
            classification["limitations"].append(f"Freeze level: {freeze_level} points")
        
        # Check swap rates
        swap_long = symbol_info.swap_long
        swap_short = symbol_info.swap_short
        if swap_long != 0:
            classification["swap_long"] = swap_long
        if swap_short != 0:
            classification["swap_short"] = swap_short
        
        # Check filling mode
        filling_mode = symbol_info.filling_mode
        classification["filling_mode"] = filling_mode
        
        # Map filling mode to names
        filling_mode_names = {
            0: "Return",
            1: "FOK", 
            2: "IOC",
            3: "BOC"
        }
        classification["filling_mode_name"] = filling_mode_names.get(filling_mode, f"Mode {filling_mode}")
        
        # Check hedging allowed (for netting mode detection)
        # In MT5, hedging is allowed by default on most accounts
        hedging_allowed = getattr(symbol_info, 'hedging_allowed', True)
        classification["hedging_allowed"] = hedging_allowed
        
        # Check margin hedged
        margin_hedged = symbol_info.margin_hedged
        if margin_hedged >= 0:
            classification["margin_hedged"] = margin_hedged
        
        # Check order mode
        order_mode = symbol_info.order_mode
        if order_mode > 0:
            classification["order_mode"] = order_mode
        
        # Determine if this symbol supports limit orders
        # Most MT5 symbols support limit orders, but check
        classification["support_limit_orders"] = True  # default assumption for MT5
        
        # Check if symbol has reasonable conditions for market making
        # Minimum criteria: visible, reasonable spread, reasonable volume
        min_conditions_met = True
        if not symbol_info.visible:
            min_conditions_met = False
        if spread > 100:  # very wide spread
            min_conditions_met = False
            classification["reasons"].append(f"Spread too wide: {spread} points")
        if volume_min <= 0:
            min_conditions_met = False
            classification["reasons"].append("Invalid volume minimum")
        
        # Determine overall classification
        if not classification["compatible"]:
            classification["status"] = "INCOMPATIBLE"
        elif not min_conditions_met:
            classification["status"] = "INCOMPATIBLE"
        elif classification["limitations"]:
            classification["status"] = "PARTIAL"
        else:
            classification["status"] = "COMPATIBLE"
        
        results["instruments"].append(classification)
        results["classification"][name] = classification["status"]
        
        # Count
        if classification["status"] == "COMPATIBLE":
            results["summary"]["compatible"] += 1
        elif classification["status"] == "PARTIAL":
            results["summary"]["partial"] += 1
        elif classification["status"] == "INCOMPATIBLE":
            results["summary"]["incompatible"] += 1
        
        # Add detailed reasons for incompatible/partial
        if classification["status"] != "COMPATIBLE":
            if not symbol_info.visible:
                classification["reasons"].append("Symbol not visible")
            if spread > 100:
                classification["reasons"].append(f"Spread excessive: {spread} points")
        
    results["summary"]["total_instruments"] = len(results["instruments"])
    
    return results


def generate_reports(results):
    """Générer les rapports CSV et JSON."""
    
    # JSON report
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "broker_compatibility_report.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Rapport JSON généré: broker_compatibility_report.json")
    
    # CSV report
    with open(os.path.join(report_dir, "broker_compatibility_report.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Symbole", "Statut", "Raisons", "Limitations", 
            "Volume Min", "Volume Max", "Tick Size", "Spread", "Stop Level"
        ])
        
        for inst in results["instruments"]:
            reasons = "; ".join(inst["reasons"]) if inst["reasons"] else "Aucune"
            limitations = "; ".join(inst["limitations"]) if inst["limitations"] else "Aucune"
            writer.writerow([
                inst["name"],
                inst["status"],
                reasons,
                limitations,
                inst.get("volume_min", ""),
                inst.get("volume_max", ""),
                inst.get("tick_size", ""),
                inst.get("spread", ""),
                inst.get("stop_level", "")
            ])
    
    print("Rapport CSV généré: broker_compatibility_report.csv")


def main():
    """Point d'entrée principal."""
    print("=" * 60)
    print("SCANNER DE CAPABILITÉS COURTIER MT5 - CHAOS ENGINE HFT")
    print("=" * 60)
    
    # Initialize MT5
    if not mt5.initialize():
        print("Erreur d'initialisation de MetaTrader 5")
        print(mt5.last_error())
        sys.exit(1)
    
    try:
        results = scan_broker_capabilities()
        
        print(f"\nInformations du compte:")
        print(f"  Courtier: {results['broker_name'] or results['server'] or 'Unknown'}")
        print(f"  Serveur: {results['server'] or 'Unknown'}")
        print(f"  Mode marge: {results['margin_mode_name']}")
        print(f"  Devise: {results['currency']}")
        print(f"  Levier: {results['leverage']}")
        print(f"  Total instruments: {results['symbols_total']}")
        
        print(f"\nClassification des instruments:")
        print(f"  COMPATIBLE: {results['summary']['compatible']}")
        print(f"  PARTIAL: {results['summary']['partial']}")
        print(f"  INCOMPATIBLE: {results['summary']['incompatible']}")
        
        # Display detailed info for first few instruments
        print(f"\nPremiers instruments analysés:")
        for i, inst in enumerate(results["instruments"][:10]):
            print(f"  {inst['name']}: {inst['status']}")
            if inst["limitations"]:
                for lim in inst["limitations"][:3]:
                    print(f"    - {lim}")
            if inst["reasons"]:
                for r in inst["reasons"][:2]:
                    print(f"    * {r}")
        
        # Generate reports
        generate_reports(results)
        
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()