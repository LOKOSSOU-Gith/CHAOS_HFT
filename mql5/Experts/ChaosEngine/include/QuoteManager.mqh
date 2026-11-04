//+------------------------------------------------------------------+
//|                  CHAOS ENGINE HFT - QuoteManager.mqh             |
//|                                     Copyright 2026, CHAOS ENGINE HFT |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Module initialization                                              |
//+------------------------------------------------------------------+
bool Initialize()
  {
   // Initialize quote management
   // Set up quote tracking, caching, and optimization structures
   return true;
  }
//+------------------------------------------------------------------+
//| Module deinitialization                                            |
//+------------------------------------------------------------------+
void Deinit()
  {
   // Cleanup quote management resources
  }
//+------------------------------------------------------------------+
//| Update quotes from market data module                              |
//+------------------------------------------------------------------+
bool Update()
  {
   // Update quote structures from MarketData module
   // This calculates mid-price, spread analysis, etc.
   
   // Calculate mid-price
   if(g_bid > 0 && g_ask > 0)
     {
      g_mid = (g_bid + g_ask) / 2.0;
     }
   
   // Calculate spread in points
   g_spread_points = g_spread;  // Already in points from MarketData
   
   // Calculate normalized spread
   if(g_mid > 0)
     {
      g_normalized_spread = g_spread_points / (g_mid * MathPow(10, -g_points));
     }
   
   // Calculate quote quality metrics
   g.quote_quality = CalculateQuoteQuality();
   
   return true;
  }
//+------------------------------------------------------------------+
//| Calculate quote quality metric                                     |
//+------------------------------------------------------------------+
double CalculateQuoteQuality()
  {
   // Calculate a quality score for the current quote
   // Based on spread tightness, volatility, liquidity, etc.
   
   double quality = 100.0;
   
   // Penalize wide spreads
   if(g_spread_points > 0)
     {
      // Normalized spread penalty
      double spread_penalty = g_spread_points / 10.0;  // 10 points = 1% penalty
      quality -= MathMin(spread_penalty, 50.0);
     }
   
   // Check for valid prices
   if(g_bid <= 0 || g_ask <= 0 || g_bid >= g_ask)
     {
      quality = 0.0;
     }
   
   return MathMax(quality, 0.0);
  }
//+------------------------------------------------------------------+
//| Get current mid price                                              |
//+------------------------------------------------------------------+
double GetMid()
  {
   return g_mid;
  }
//+------------------------------------------------------------------+
//| Get current bid price                                              |
//+------------------------------------------------------------------+
double GetBid()
  {
   return g_bid;
  }
//+------------------------------------------------------------------+
//| Get current ask price                                              |
//+------------------------------------------------------------------+
double GetAsk()
  {
   return g_ask;
  }
//+------------------------------------------------------------------+
//| Get current spread in points                                       |
//+------------------------------------------------------------------+
int GetSpreadPoints()
  {
   return g_spread_points;
  }
//+------------------------------------------------------------------+
//| Get normalized spread                                              |
//+------------------------------------------------------------------+
double GetNormalizedSpread()
  {
   return g_normalized_spread;
  }
//+------------------------------------------------------------------+
//| Quote quality                                                      |
//+------------------------------------------------------------------+
double g_quote_quality;

//+------------------------------------------------------------------+
//| Module-specific parameters                                         |
//+------------------------------------------------------------------+
input int g_quote_refresh_ms = 1000;  // How often to refresh quotes

// Internal state
double g_mid;
double g_bid;
double g_ask;
int g_spread_points;
double g_normalized_spread;
double g.quote_quality;
//+------------------------------------------------------------------+