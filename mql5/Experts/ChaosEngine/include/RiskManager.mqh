//+------------------------------------------------------------------+
//|                  CHAOS ENGINE HFT - RiskManager.mqh              |
//|                                     Copyright 2026, CHAOS ENGINE HFT |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Global risk configuration                                         |
//+------------------------------------------------------------------+
input double RISK_PER_NEW_EXPOSURE = 0.25;   // 0.25% risk per new exposure
input double MAX_AGGREGATE_OPEN_RISK = 1.0;  // 1% aggregate open risk
input double MAX_DAILY_LOSS = 2.0;           // 2% daily loss limit
input double DRAWDOWN_WARNING = 5.0;         // 5% warning drawdown
input double HARD_DRAWDOWN_STOP = 8.0;       // 8% hard drawdown stop
input double MAX_MARGIN_UTILIZATION = 20.0;  // 20% max margin utilization
input double MAX_DAILY_TRADES = 30.0;        // Max trades per day

//+------------------------------------------------------------------+
//| Module state                                                     |
//+------------------------------------------------------------------+
struct RiskState
  {
   double today_pnl;        // PnL today in % of balance
   double today_trades;     // Trades count today
   double equity_at_start;  // Equity at start of day
   double balance_at_start;   // Balance at start of day
   double max_equity_today; // Max equity reached today
   double min_equity_today; // Min equity reached today
   bool daily_loss_triggered;
   bool drawdown_warning_triggered;
   bool hard_drawdown_stopped;
  };
RiskState g_risk;

//+------------------------------------------------------------------+
//| Module initialization                                              |
//+------------------------------------------------------------------+
bool Initialize()
  {
   // Reset daily state at new day start
   ResetDailyState();
   return true;
  }
//+------------------------------------------------------------------+
//| Module deinitialization                                            |
//+------------------------------------------------------------------+
void Deinit()
  {
   // Cleanup
  }
//+------------------------------------------------------------------+
//| Reset daily risk state                                             |
//+------------------------------------------------------------------+
void ResetDailyState()
  {
   g_risk.today_pnl = 0.0;
   g_risk.today_trades = 0;
   g_risk.equity_at_start = AccountEquity();
   g_risk.balance_at_start = AccountBalance();
   g_risk.max_equity_today = g_risk.equity_at_start;
   g_risk.min_equity_today = g_risk.equity_at_start;
   g_risk.daily_loss_triggered = false;
   g_risk.drawdown_warning_triggered = false;
   g_risk.hard_drawdown_stopped = false;
  }
//+------------------------------------------------------------------+
//| Check before new exposure                                          |
//+------------------------------------------------------------------+
bool CheckNewExposure(double proposed_risk_pct, double position_size_lots, double margin_required)
  {
   // Check per-exposure risk
   if(proposed_risk_pct > RISK_PER_NEW_EXPOSURE)
     {
      // Too risky for this single trade
      return false;
     }
   
   // Check aggregate open risk
   double current_open_risk = GetCurrentOpenRisk();
   if(current_open_risk + proposed_risk_pct > MAX_AGGREGATE_OPEN_RISK)
     {
      // Would exceed aggregate risk limit
      return false;
     }
   
   // Check daily loss limit
   if(g_risk.today_pnl <= -MAX_DAILY_LOSS && !g_risk.daily_loss_triggered)
     {
      // Already at daily loss limit
      return false;
     }
   
   // Check margin utilization
   double margin_pct = margin_required / AccountEquity() * 100.0;
   if(margin_pct > MAX_MARGIN_UTILIZATION)
     {
      // Would exceed margin limit
      return false;
     }
   
   return true;
  }
//+------------------------------------------------------------------+
//| Get current open risk in %                                         |
//+------------------------------------------------------------------+
double GetCurrentOpenRisk()
  {
   // Calculate aggregate risk from all open positions
   double total_risk = 0.0;
   
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS))
        {
         if(OrderSymbol() == _Symbol && OrderMagicNumber() == 860001)
           {
            // Calculate PnP risk per position
            double entry_price = OrderOpenPrice();
            double current_price = OrderType() == ORDER_TYPE_BUY ? Bid : Ask;
            double price_move = MathAbs(current_price - entry_price);
            // Simplified risk calc based on price adverse move
            double risk_pct = price_move / entry_price * 100.0;
            total_risk += risk_pct;
           }
        }
     }
   
   return total_risk;
  }
//+------------------------------------------------------------------+
//| Check daily loss limit                                             |
//+------------------------------------------------------------------+
bool CheckDailyLossLimit()
  {
   if(g_risk.daily_loss_triggered) return false;
   
   double today_pnl_pct = (AccountBalance() - g_risk.balance_at_start) / g_risk.balance_at_start * 100.0;
   
   if(today_pnl_pct <= -MAX_DAILY_LOSS)
     {
      g_risk.daily_loss_triggered = true;
      return false;
     }
   
   return true;
  }
//+------------------------------------------------------------------+
//| Check drawdown warnings                                            |
//+------------------------------------------------------------------+
void CheckDrawdown()
  {
   double current_equity = AccountEquity();
   
   // Update max/min equity
   if(current_equity > g_risk.max_equity_today) g_risk.max_equity_today = current_equity;
   if(current_equity < g_risk.min_equity_today) g_risk.min_equity_today = current_equity;
   
   // Warning drawdown
   double warning_level = (g_risk.equity_at_start - g_risk.max_equity_today) / g_risk.equity_at_start * 100.0;
   if(warning_level >= DRAWDOWN_WARNING && !g_risk.drawdown_warning_triggered)
     {
      g_risk.drawdown_warning_triggered = true;
      // Could post warning here
     }
   
   // Hard drawdown stop
   double hard_level = (g_risk.equity_at_start - g_risk.min_equity_today) / g_risk.equity_at_start * 100.0;
   if(hard_level >= HARD_DRAWDOWN_STOP)
     {
      g_risk.hard_drawdown_stopped = true;
      // Emergency: close positions
     }
  }
//+------------------------------------------------------------------+
//| Check trade count limit                                            |
//+------------------------------------------------------------------+
bool CheckTradeCountLimit()
  {
   if(g_risk.today_trades >= MAX_DAILY_TRADES) return false;
   return true;
  }
//+------------------------------------------------------------------+
//| Increment trade count                                              |
//+------------------------------------------------------------------+
void IncrementTradeCount()
  {
   g_risk.today_trades++;
  }
//+------------------------------------------------------------------+
//| Increment PnL                                                      |
//+------------------------------------------------------------------+
void IncrementPnL(double pnl_pct)
  {
   g_risk.today_pnl += pnl_pct;
  }
//+------------------------------------------------------------------+
//| Write risk status to file                                          |
//+------------------------------------------------------------------+
void WriteRiskStatus(string filename)
  {
   string content = "=== Risk Status ===\n";
   content += "Today PnL %: " + DoubleToString(g_risk.today_pnl, 2) + "\n";
   content += "Today Trades: " + IntegerToString((int)g_risk.today_trades) + "\n";
   content += "Balance start: " + DoubleToString(g_risk.balance_at_start, 2) + "\n";
   content += "Equity start: " + DoubleToString(g_risk.equity_at_start, 2) + "\n";
   content += "Max equity today: " + DoubleToString(g_risk.max_equity_today, 2) + "\n";
   content += "Min equity today: " + DoubleToString(g_risk.min_equity_today, 2) + "\n";
   content += "Daily loss triggered: " + IntegerToString((int)g_risk.daily_loss_triggered) + "\n";
   content += "Drawdown warning triggered: " + IntegerToString((int)g_risk.drawdown_warning_triggered) + "\n";
   content += "Hard drawdown stopped: " + IntegerToString((int)g_risk.hard_drawdown_stopped) + "\n";
   content += "==================\n";
   
   File f;
   if(f.Open(filename, FILE_WRITE | FILE_TXT | FILE_ANSI))
     {
      f.Write(content);
      f.Close();
     }
  }
//+------------------------------------------------------------------+
//| Module-specific parameters                                         |
//+------------------------------------------------------------------+
input double g.RISK_PER_NEW_EXPOSURE = 0.25;
input double g.MAX_AGGREGATE_OPEN_RISK = 1.0;
input double g.MAX_DAILY_LOSS = 2.0;
input double g.DRAWDOWN_WARNING = 5.0;
input double g.HARD_DRAWDOWN_STOP = 8.0;
input double g.MAX_MARGIN_UTILIZATION = 20.0;
input double g.MAX_DAILY_TRADES = 30.0;

// Internal state
struct RiskState
  {
   double today_pnl;
   double today_trades;
   double equity_at_start;
   double balance_at_start;
   double max_equity_today;
   double min_equity_today;
   bool daily_loss_triggered;
   bool drawdown_warning_triggered;
   bool hard_drawdown_stopped;
  };
RiskState g_risk_state;
//+------------------------------------------------------------------+