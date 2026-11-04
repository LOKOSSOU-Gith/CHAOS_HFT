//+------------------------------------------------------------------+
//|                  CHAOS ENGINE HFT - InventoryManager.mqh         |
//|                                     Copyright 2026, CHAOS ENGINE HFT |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Inventory management for hedging and netting accounts             |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Global inventory state                                            |
//+------------------------------------------------------------------+
struct InventoryState
  {
   // Net position by symbol
   double net_position[256];      // Array indexed by symbol index
   double raw_long[256];          // Total long volume
   double raw_short[256];         // Total short volume
   
   // Exposure limits per symbol
   double max_net_exposure[256];  // Max net lots per symbol
   double max_long_lots[256];     // Max long lots per symbol
   double max_short_lots[256];    // Max short lots per symbol
   
   // Portfolio-level limits
   double max_portfolio_exposure; // Max total portfolio exposure
   double max_margin_utilization; // Max margin utilization %
   
   // Tracking
   double total_pnl;              // Total PnL from inventory management
   int    trade_count;            // Trade count
   
   // Symbol count
   int symbol_count;
  };
InventoryState g_inventory;

//+------------------------------------------------------------------+
//| Module initialization                                               |
//+------------------------------------------------------------------+
bool Initialize()
  {
   // Initialize inventory state
   ResetInventory();
   return true;
  }
//+------------------------------------------------------------------+
//| Module deinitialization                                             |
//+------------------------------------------------------------------+
void Deinit()
  {
   // Cleanup inventory state
  }
//+------------------------------------------------------------------+
//| Reset inventory state                                               |
//+------------------------------------------------------------------+
void ResetInventory()
  {
   // Reset all symbol exposures
   for(int i = 0; i < 256; i++)
     {
      g_inventory.net_position[i] = 0.0;
      g_inventory.raw_long[i] = 0.0;
      g_inventory.raw_short[i] = 0.0;
      g_inventory.max_net_exposure[i] = 20.0;
      g_inventory.max_long_lots[i] = 50.0;
      g_inventory.max_short_lots[i] = 50.0;
     }
   
   g_inventory.total_pnl = 0.0;
   g_inventory.trade_count = 0;
   g_inventory.symbol_count = 0;
   g_inventory.max_portfolio_exposure = 100.0;
   g_inventory.max_margin_utilization = 20.0;
  }
//+------------------------------------------------------------------+
//| Update inventory from an order execution                          |
//+------------------------------------------------------------------+
void UpdateInventory(int order_type, double volume, string symbol_name)
  {
   // Find symbol index
   int sym_index = SymbolIndexByName(symbol_name);
   if(sym_index < 0) return;
   
   // Update raw exposure
   if(order_type == ORDER_TYPE_BUY)
     {
      g_inventory.raw_long[sym_index] += volume;
     }
   else if(order_type == ORDER_TYPE_SELL)
     {
      g_inventory.raw_short[sym_index] += volume;
     }
   
   // Update net position
   if(order_type == ORDER_TYPE_BUY)
     {
      g_inventory.net_position[sym_index] += volume;
     }
   else if(order_type == ORDER_TYPE_SELL)
     {
      g_inventory.net_position[sym_index] -= volume;
     }
   
   // Track PnL impact (simplified)
   g_inventory.total_pnl += volume * 0.001;  // placeholder
   g_inventory.trade_count++;
  }
//+------------------------------------------------------------------+
//| Check if symbol has net exposure                                    |
//+------------------------------------------------------------------+
bool HasNetExposure(string symbol_name)
  {
   int idx = SymbolIndexByName(symbol_name);
   if(idx < 0) return false;
   
   return MathAbs(g_inventory.net_position[idx]) > 0.01;
  }
//+------------------------------------------------------------------+
//| Get net position for symbol                                         |
//+------------------------------------------------------------------+
double GetNetPosition(string symbol_name)
  {
   int idx = SymbolIndexByName(symbol_name);
   if(idx < 0) return 0.0;
   
   return g_inventory.net_position[idx];
  }
//+------------------------------------------------------------------+
//| Get raw long exposure                                               |
//+------------------------------------------------------------------+
double GetRawLong(string symbol_name)
  {
   int idx = SymbolIndexByName(symbol_name);
   if(idx < 0) return 0.0;
   
   return g_inventory.raw_long[idx];
  }
//+------------------------------------------------------------------+
//| Get raw short exposure                                              |
//+------------------------------------------------------------------+
double GetRawShort(string symbol_name)
  {
   int idx = SymbolIndexByName(symbol_name);
   if(idx < 0) return 0.0;
   
   return g_inventory.raw_short[idx];
  }
//+------------------------------------------------------------------+
//| Check portfolio exposure limits                                     |
//+------------------------------------------------------------------+
bool CheckPortfolioLimits(double total_exposure)
  {
   if(total_exposure > g_inventory.max_portfolio_exposure)
     {
      return false;
     }
   
   // Check margin utilization
   double margin_pct = AccountMarginTotal() / AccountEquity() * 100.0;
   if(margin_pct > g_inventory.max_margin_utilization)
     {
      return false;
     }
   
   return true;
  }
//+------------------------------------------------------------------+
//| Reduce exposure for a symbol                                        |
//+------------------------------------------------------------------+
void ReduceExposure(string symbol_name, double target_net)
  {
   int idx = SymbolIndexByName(symbol_name);
   if(idx < 0) return;
   
   double current_net = g_inventory.net_position[idx];
   double diff = current_net - target_net;
   
   // Close positions to reach target net
   if(MathAbs(diff) > 0.01)
     {
      // Select opposing orders to close
      for(int i = OrdersTotal() - 1; i >= 0; i--)
        {
         if(OrderSelect(i, SELECT_BY_POS))
           {
            if(OrderSymbol() == symbol_name && OrderMagicNumber() == 860001)
              {
               // Close if it reduces the net exposure difference
               bool reduces_diff = false;
               
               if(diff > 0 && OrderType() == ORDER_TYPE_SELL)
                 {
                  reduces_diff = true;  // Selling reduces positive net
                 }
               else if(diff < 0 && OrderType() == ORDER_TYPE_BUY)
                 {
                  reduces_diff = true;  // Buying reduces negative net
                 }
               
               if(reduces_diff)
                 {
                  // Close partial or full position
                  double close_volume = MathMin(MathAbs(diff), OrderLot());
                  if(close_volume > 0)
                    {
                     OrderClose(OrderTicket(), close_volume, OrderOpenPrice(), 0, clrNONE);
                    }
                  break;
                 }
              }
           }
        }
     }
  }
//+------------------------------------------------------------------+
//| Get total portfolio exposure                                        |
//+------------------------------------------------------------------+
double GetTotalExposure()
  {
   double total = 0.0;
   
   for(int i = 0; i < g_inventory.symbol_count; i++)
     {
      total += MathAbs(g_inventory.net_position[i]);
     }
   
   return total;
  }
//+------------------------------------------------------------------+
//| Synchronize symbol count                                              |
//+------------------------------------------------------------------+
void SynchronizeSymbolCount()
  {
   g_inventory.symbol_count = 0;
   for(int i = 0; i < 256; i++)
     {
      // Count symbols that have been initialized
      if(StringLen(SymbolName(i)) > 0)
        {
         g_inventory.symbol_count = i + 1;
        }
     }
  }
//+------------------------------------------------------------------+
//| Module-specific parameters                                             |
//+------------------------------------------------------------------+
input double g.max_portfolio_exposure = 100.0;  // Max portfolio exposure in lots
input double g.max_margin_utilization = 20.0;   // Max margin %
input double g.skew_penalty_factor = 0.1;       // Inventory skew penalty factor

// Internal state
struct InventoryState { /* as above */ };
InventoryState g_inventory_state;
//+------------------------------------------------------------------+