//+------------------------------------------------------------------+
//|                  CHAOS ENGINE HFT - MarketData.mqh               |
//|                                     Copyright 2026, CHAOS ENGINE HFT |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Module initialization                                              |
//+------------------------------------------------------------------+
bool Initialize()
  {
   // Initialize market data collection
   // Nothing to initialize at module level
   return true;
  }
//+------------------------------------------------------------------+
//| Module deinitialization                                            |
//+------------------------------------------------------------------+
void Deinit()
  {
   // Cleanup market data resources
  }
//+------------------------------------------------------------------+
//| Update market data from ticks                                      |
//+------------------------------------------------------------------+
bool Update()
  {
   // Update internal market data structures from MT5 ticks
   // This is called on every OnTick()
   
   // Get current Bid/Ask
   double bid = MarketInfo(g_symbol, MODE_BID);
   double ask = MarketInfo(g_symbol, MODE_ASK);
   
   // Store for other modules
   g_bid = bid;
   g_ask = ask;
   g_spread = MarketInfo(g_symbol, MODE_SPREAD);
   
   // Get additional data
   g_points = MarketInfo(g_symbol, MODE_POINT);
   g_trade_tick_size = MarketInfo(g_symbol, TRADE_TICK_SIZE);
   g_trade_tick_value = MarketInfo(g_symbol, TRADE_TICK_VALUE);
   
   // Get volume and lot information
   g_volume_min = MarketInfo(g_symbol, VOLUME_MIN);
   g_volume_max = MarketInfo(g_symbol, VOLUME_MAX);
   g_volume_step = MarketInfo(g_symbol, VOLUME_STEP);
   
   // Get swap rates
   g_swap_long = MarketInfo(g_symbol, SWAP_LONG);
   g_swap_short = MarketInfo(g_symbol, SWAP_SHORT);
   
   // Get execution type
   g_trade_mode = MarketInfo(g_symbol, TRADE_MODE);
   g_stop_level = MarketInfo(g_symbol, STOP_LEVEL);
   g_freeze_level = MarketInfo(g_symbol, FREEZE_LEVEL);
   
   // Get session information
   g_session_start = MarketInfo(g_symbol, SESSION_START_TIME);
   g_session_end = MarketInfo(g_symbol, SESSION_END_TIME);
   
   // Check if symbol is visible/tradable
   g_visible = MarketInfo(g_symbol, MODE_VISIBLE);
   
   return true;
  }
//+------------------------------------------------------------------+
//| Handle book events (if DOM available)                              |
//+------------------------------------------------------------------+
void OnBookEvent(const long event_id)
  {
   // Handle depth of market events
   // Only called if broker supports DOM
   
   // Event types:
   // EVENT_TYPE_ORDER - order added/removed from book
   // EVENT_TYPE_DEPTH - depth change
   
   // Get event type
   long event_type = IntegerParam(PARAM_EVENT_TYPE);
   
   switch(event_type)
     {
      case EVENT_TYPE_ORDER:
         // Handle individual order event
         long order = IntegerParam(PARAM_ORDER);
         double order_price = DoubleParam(PARAM_PRICE);
         long order_volume = IntegerParam(PARAM_VOLUME);
         // Process order
         break;
         
      case EVENT_TYPE_DEPTH:
         // Handle depth update
         // Update internal book representation
         break;
     }
  }
//+------------------------------------------------------------------+
//| Module-specific parameters                                         |
//+------------------------------------------------------------------+
input string g_symbol = "EURUSDm";

double g_bid;
double g_ask;
int g_spread;
double g_points;
double g_trade_tick_size;
double g_trade_tick_value;
double g_volume_min;
double g_volume_max;
double g_volume_step;
double g_swap_long;
double g_swap_short;
int g_trade_mode;
double g_stop_level;
double g_freeze_level;
bool g_visible;
datetime g_session_start;
datetime g_session_end;
//+------------------------------------------------------------------+