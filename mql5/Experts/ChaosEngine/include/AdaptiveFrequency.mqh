//+------------------------------------------------------------------+
//|                  CHAOS ENGINE HFT - AdaptiveFrequency.mqh         |
//|                                     Copyright 2026, CHAOS ENGINE HFT |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Adaptive trading frequency control                                |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Four trading regimes                                              |
//+------------------------------------------------------------------+
input enum eRegimeMode { 
   REGIME_HIGH_ACTIVITY = 0,    // High activity - aggressive quoting
   REGIME_NORMAL_ACTIVITY = 1,  // Normal activity - balanced quoting
   REGIME_REDUCED_ACTIVITY = 2, // Reduced activity - conservative quoting
   REGIME_PROTECTION_MODE = 3   // Protection mode - defensive quoting
}eCurrentRegime = REGIME_NORMAL_ACTIVITY;

//+------------------------------------------------------------------+
//| Regime thresholds                                                 |
//+------------------------------------------------------------------+
input int MAX_ACTIVE_ORDERS = 10;        // Max active orders per side
input int MAX_POSITIONS = 10;            // Max concurrent positions
input int MAX_MODIFICATIONS_PER_MINUTE = 10; // Max order modifications/min
input int MIN_QUOTE_REFRESH_MS = 250;    // Min quote refresh in ms
input int MAX_QUOTE_REFRESH_MS = 5000;   // Max quote refresh in ms
input int MAX_SPREAD_POINTS = 3;         // Max spread in points to quote
input double MIN_EXPECTED_NET_EDGE = 0.1; // Min expected edge in % to quote
input double MAX_SYMBOL_EXPOSURE = 5.0;  // Max symbol exposure in lots
input double MAX_PORTFOLIO_EXPOSURE = 10.0; // Max portfolio exposure in lots
input int MAX_ORDER_LIFETIME_MS = 300000; // Max order lifetime in ms (5 min)

//+------------------------------------------------------------------+
//| Regime state                                                      |
//+------------------------------------------------------------------+
struct RegimeState
  {
   eRegimeMode current_mode;
   datetime last_regime_change;
   int modifications_this_minute;
   int active_orders;
   int active_positions;
   double last_spread;
   double last_chaos_score;
   double last_volatility;
   double last_order_flow_imbalance;
   bool quote_disabled;
   datetime last_quote_time;
   double total_cotations;
  };
RegimeState g_regime;

//+------------------------------------------------------------------+
//| Initialize regime                                                  |
//+------------------------------------------------------------------+
void InitializeRegime()
  {
   g_regime.current_mode = REGIME_NORMAL_ACTIVITY;
   g_regime.last_regime_change = TimeCurrent();
   g_regime.modifications_this_minute = 0;
   g_regime.active_orders = 0;
   g_regime.active_positions = 0;
   g_regime.last_spread = 0.0;
   g_regime.last_chaos_score = 0.0;
   g_regime.last_volatility = 0.0;
   g_regime.last_order_flow_imbalance = 0.0;
   g_regime.quote_disabled = false;
   g_regime.last_quote_time = 0;
   g_regime.total_cotations = 0;
  }
//+------------------------------------------------------------------+
//| Update regime based on market conditions                          |
//+------------------------------------------------------------------+
void UpdateRegime(double current_spread, double chaos_score, 
                 double volatility, double order_flow_imbalance,
                 double net_exposure, double volatility_adj)
  {
   // Calculate regime indicators
   bool spread_too_wide = current_spread > MAX_SPREAD_POINTS;
   bool high_volatility = volatility > 3.0; // Adjusted threshold
   bool low_edge = chaos_score < MIN_EXPECTED_NET_EDGE;
   bool high_exposure = MathAbs(net_exposure) > MAX_SYMBOL_EXPOSURE;
   
   // Determine new regime
   eRegimeMode new_mode = g_regime.current_mode;
   
   // Protection mode takes priority
   if(spread_too_wide || low_edge || high_exposure)
     {
      new_mode = REGIME_PROTECTION_MODE;
     }
   else if(chaos_score > 0.7 && volatility < 1.5)
     {
      new_mode = REGIME_HIGH_ACTIVITY;
     }
   else if(chaos_score < 0.3 || high_volatility)
     {
      new_mode = REGIME_REDUCED_ACTIVITY;
     }
   else
     {
      new_mode = REGIME_NORMAL_ACTIVITY;
     }
   
   // Change regime if needed
   if(new_mode != g_regime.current_mode)
     {
      RegimeChange(new_mode);
     }
   
   // Update regime state
   g_regime.current_mode = new_mode;
   g_regime.last_spread = current_spread;
   g_regime.last_chaos_score = chaos_score;
   g_regime.last_volatility = volatility;
   g_regime.last_order_flow_imbalance = order_flow_imbalance;
   g_regime.total_cotations++;
  }
//+------------------------------------------------------------------+
//| Handle regime change                                                |
//+------------------------------------------------------------------+
void RegimeChange(eRegimeMode new_mode)
  {
   eRegimeMode old_mode = g_regime.current_mode;
   g_regime.current_mode = new_mode;
   g_regime.last_regime_change = TimeCurrent();
   
   // Reset counters on regime change
   g_regime.modifications_this_minute = 0;
   g_regime.active_orders = 0;
   g_regime.active_positions = 0;
   g_regime.quote_disabled = false;
   
   // Log regime change
   string mode_name;
   switch(new_mode)
     {
      case REGIME_HIGH_ACTIVITY: mode_name = "HIGH_ACTIVITY"; break;
      case REGIME_NORMAL_ACTIVITY: mode_name = "NORMAL_ACTIVITY"; break;
      case REGIME_REDUCED_ACTIVITY: mode_name = "REDUCED_ACTIVITY"; break;
      case REGIME_PROTECTION_MODE: mode_name = "PROTECTION_MODE"; break;
     }
   
   // Write to journal
   Print(">>> Regime change: ", mode_name, " (from ", mode_name_for(old_mode), ")");
  }
//+------------------------------------------------------------------+
//| Get mode name for logging                                         |
//+------------------------------------------------------------------+
string mode_name_for(eRegimeMode mode)
  {
   switch(mode)
     {
      case REGIME_HIGH_ACTIVITY: return "HIGH_ACTIVITY";
      case REGIME_NORMAL_ACTIVITY: return "NORMAL_ACTIVITY";
      case REGIME_REDUCED_ACTIVITY: return "REDUCED_ACTIVITY";
      case REGIME_PROTECTION_MODE: return "PROTECTION_MODE";
     }
   return "UNKNOWN";
  }
//+------------------------------------------------------------------+
//| Apply regime limits to order placement                            |
//+------------------------------------------------------------------+
bool ApplyRegimeLimits(int order_type, double order_size, 
                      double current_spread, double chaos_score,
                      double net_exposure)
  {
   // Check active orders limit
   if(g_regime.active_orders >= MAX_ACTIVE_ORDERS) return false;
   
   // Check positions limit
   if(order_type == ORDER_TYPE_BUY && g_regime.active_positions >= MAX_POSITIONS) return false;
   if(order_type == ORDER_TYPE_SELL && g_regime.active_positions >= MAX_POSITIONS) return false;
   
   // Check spread limit
   if(current_spread > MAX_SPREAD_POINTS) return false;
   
   // Check exposure limit
   if(MathAbs(net_exposure) + order_size > MAX_SYMBOL_EXPOSURE) 
     {
      // Reduce order size to fit within limits
      order_size = MAX_SYMBOL_EXPOSURE - MathAbs(net_exposure);
      if(order_size <= 0) return false;
     }
   
   // Apply mode-specific limits
   switch(g_regime.current_mode)
     {
      case REGIME_HIGH_ACTIVITY:
         // Normal limits, can quote aggressively
         break;
         
      case REGIME_NORMAL_ACTIVITY:
         // Normal quoting limits
         if(g_regime.modifications_this_minute >= MAX_MODIFICATIONS_PER_MINUTE) return false;
         break;
         
      case REGIME_REDUCED_ACTIVITY:
         // Reduced quoting - wider spread filter
         if(current_spread > MAX_SPREAD_POINTS * 1.5) return false;
         // Reduce order sizes
         order_size *= 0.5; // Halve order sizes
         break;
         
      case REGIME_PROTECTION_MODE:
         // Protection - minimize risk
         if(g_regime.active_orders > 0) return false; // No new orders
         if(g_regime.active_positions > 0) 
           {
            // Close positions at market if possible
           }
         return false; // No new orders
         break;
     }
   
   // Update counters
   g_regime.modifications_this_minute++;
   if(order_type == ORDER_TYPE_BUY) g_regime.active_orders++;
   if(order_type == ORDER_TYPE_SELL) g_regime.active_orders++;
   
   return true;
  }
//+------------------------------------------------------------------+
//| Reduce position (for protection mode)                             |
//+------------------------------------------------------------------+
void ReducePositions()
  {
   // Close positions based on risk priority
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS))
        {
         if(OrderSymbol() == _Symbol && OrderMagicNumber() == 860001)
           {
            // Close positions based on PnL and risk
            if(OrderProfitLoss() < 0) // Losing positions first
              {
               // Close this position
              }
           }
        }
     }
  }
//+------------------------------------------------------------------+
//| Get current regime                                                 |
//+------------------------------------------------------------------+
eRegimeMode GetCurrentRegime()
  {
   return g_regime.current_mode;
  }
//+------------------------------------------------------------------+
//| Get regime state                                                   |
//+------------------------------------------------------------------+
RegimeState GetRegimeState()
  {
   return g_regime;
  }
//+------------------------------------------------------------------+
//| Module-specific parameters                                         |
//+------------------------------------------------------------------+
input int g.MAX_ACTIVE_ORDERS = 10;
input int g.MAX_POSITIONS = 10;
input int g.MAX_MODIFICATIONS_PER_MINUTE = 10;
input int g.MIN_QUOTE_REFRESH_MS = 250;
input int g.MAX_QUOTE_REFRESH_MS = 5000;
input int g.MAX_SPREAD_POINTS = 3;
input double g.MIN_EXPECTED_NET_EDGE = 0.1;
input double g.MAX_SYMBOL_EXPOSURE = 5.0;
input double g.MAX_PORTFOLIO_EXPOSURE = 10.0;
input int g.MAX_ORDER_LIFETIME_MS = 300000;

// Internal state
struct RegimeState { /* as above */ };
RegimeState g_regime_state;
//+------------------------------------------------------------------+