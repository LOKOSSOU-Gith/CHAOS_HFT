//+------------------------------------------------------------------+
//|                                                  ChaosEngineHFT.mq5|
//|                                     Copyright 2026, CHAOS ENGINE HFT |
//|                        https://www.codebuff.com | freebuff.com   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, CHAOS ENGINE HFT"
#property link      "https://www.codebuff.com"
#property version   "1.00"
#property strict
#property strict

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Initialize modules
   if(!MarketDataInitialize())    { Print("Failed to initialize MarketData"); return(INIT_FAILED); }
   if(!QuoteManagerInitialize())  { Print("Failed to initialize QuoteManager"); return(INIT_FAILED); }
   if(!OrderManagerInitialize())  { Print("Failed to initialize OrderManager"); return(INIT_FAILED); }
   if(!PositionManagerInitialize()){ Print("Failed to initialize PositionManager"); return(INIT_FAILED); }
   if(!HedgingManagerInitialize()){ Print("Failed to initialize HedgingManager"); return(INIT_FAILED); }
   if(!NettingManagerInitialize()){ Print("Failed to initialize NettingManager"); return(INIT_FAILED); }
   if(!InventoryManagerInitialize()){ Print("Failed to initialize InventoryManager"); return(INIT_FAILED); }
   if(!RiskManagerInitialize())   { Print("Failed to initialize RiskManager"); return(INIT_FAILED); }
   if(!AdaptiveFrequencyInitialize()){ Print("Failed to initialize AdaptiveFrequency"); return(INIT_FAILED); }
   if(!BrokerAdapterInitialize()) { Print("Failed to initialize BrokerAdapter"); return(INIT_FAILED); }
   if(!PythonBridgeInitialize())  { Print("Failed to initialize PythonBridge"); return(INIT_FAILED); }
   if(!ExecutionGuardInitialize()){ Print("Failed to initialize ExecutionGuard"); return(INIT_FAILED); }
   if(!EmergencyManagerInitialize()){ Print("Failed to initialize EmergencyManager"); return(INIT_FAILED); }
   if(!LoggerInitialize())        { Print("Failed to initialize Logger"); return(INIT_FAILED); }
   
   // Initialize broker compatibility
   if(!BrokerAdapterCheckCompatibility()) { Print("Broker compatibility check failed"); return(INIT_FAILED); }
   
   // Log initialization
   LoggerWrite("CHAOS ENGINE HFT initialisé avec succès");
   
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   // Cleanup modules
   EmergencyManagerDeinit();
   ExecutionGuardDeinit();
   PythonBridgeDeinit();
   BrokerAdapterDeinit();
   AdaptiveFrequencyDeinit();
   RiskManagerDeinit();
   InventoryManagerDeinit();
   NettingManagerDeinit();
   HedgingManagerDeinit();
   PositionManagerDeinit();
   OrderManagerDeinit();
   QuoteManagerDeinit();
   MarketDataDeinit();
   
   LoggerWrite("CHAOS ENGINE HFT déinitialisé (raison: %d)", reason);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Update market data
   if(!MarketDataUpdate()) return;
   
   // Check emergency conditions
   if(EmergencyManagerCheck()) 
     {
      // Emergency mode - only protect existing positions
      EmergencyManagerProtect();
      return;
     }
   
   // Update adaptive frequency
   AdaptiveFrequencyOnTick();
   
   // Get market analysis from Python
   if(!PythonBridgeUpdate()) return;
   
   // Check risk limits
   if(!RiskManagerCheck()) return;
   
   // Execute trading logic
   OrderManagerOnTick();
   PositionManagerOnTick();
   
   // Emergency check after trading
   EmergencyManagerPostTick();
   
   // Heartbeat/Logging
   static int last_heartbeat = 0;
   if(::GetTickCount() - last_heartbeat > 60000)
     {
      last_heartbeat = ::GetTickCount();
      LoggerWrite("Tick %d: balance=%.2f, equity=%.2f, exposure=%.2f lots", 
                  ::CountTicks(), AccountBalance(), AccountEquity(), 
                  PositionGetDouble(POSITION_POSITION) / 100000);
     }
  }
//+------------------------------------------------------------------+
//| Expert timer function (called every second)                      |
//+------------------------------------------------------------------+
void OnTimer()
  {
   // Periodic checks
   BrokerAdapterOnTimer();
   AdaptiveFrequencyOnTimer();
   LoggerOnTimer();
  }
//+------------------------------------------------------------------+
//| Expert trade transaction function                                |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MQLTradeTransaction& transaction,
                      const MQLTradeRequest& request)
  {
   // Handle trade transactions
   ExecutionGuardOnTradeTransaction(transaction, request);
   EmergencyManagerOnTradeTransaction(transaction, request);
   LoggerWriteTransaction(transaction, request);
  }
//+------------------------------------------------------------------+
//| Expert book event function (if DOM available)                    |
//+------------------------------------------------------------------+
void OnBookEvent(const long event_id)
  {
   if(!BrokerAdapterIsDOMAvailable()) return;
   MarketDataOnBookEvent(event_id);
   OrderManagerOnBookEvent(event_id);
   LoggerWriteBookEvent(event_id);
  }
//+------------------------------------------------------------------+
//| cnstance functions for module access                               |
//+------------------------------------------------------------------+
bool MarketDataInitialize()      { return MarketData::Initialize(); }
void MarketDataDeinit()          { MarketData::Deinit(); }
bool MarketDataUpdate()          { return MarketData::Update(); }
void MarketDataOnBookEvent(long event_id) { MarketData::OnBookEvent(event_id); }

bool QuoteManagerInitialize()    { return QuoteManager::Initialize(); }
void QuoteManagerDeinit()        { QuoteManager::Deinit(); }
bool QuoteManagerUpdate()        { return QuoteManager::Update(); }

bool OrderManagerInitialize()    { return OrderManager::Initialize(); }
void OrderManagerDeinit()        { OrderManager::Deinit(); }
void OrderManagerOnTick()        { OrderManager::OnTick(); }
void OrderManagerOnBookEvent(long event_id) { OrderManager::OnBookEvent(event_id); }

bool PositionManagerInitialize() { return PositionManager::Initialize(); }
void PositionManagerDeinit()     { PositionManager::Deinit(); }
void PositionManagerOnTick()     { PositionManager::OnTick(); }
void PositionManagerPostTick()   { PositionManager::PostTick(); }

bool HedgingManagerInitialize()  { return HedgingManager::Initialize(); }
void HedgingManagerDeinit()      { HedgingManager::Deinit(); }

bool NettingManagerInitialize()  { return NettingManager::Initialize(); }
void NettingManagerDeinit()      { NettingManager::Deinit(); }

bool InventoryManagerInitialize(){ return InventoryManager::Initialize(); }
void InventoryManagerDeinit()    { InventoryManager::Deinit(); }

bool RiskManagerInitialize()     { return RiskManager::Initialize(); }
void RiskManagerDeinit()         { RiskManager::Deinit(); }
bool RiskManagerCheck()          { return RiskManager::Check(); }

bool AdaptiveFrequencyInitialize(){ return AdaptiveFrequency::Initialize(); }
void AdaptiveFrequencyDeinit()    { AdaptiveFrequency::Deinit(); }
void AdaptiveFrequencyOnTick()   { AdaptiveFrequency::OnTick(); }
void AdaptiveFrequencyOnTimer()  { AdaptiveFrequency::OnTimer(); }

bool BrokerAdapterInitialize()   { return BrokerAdapter::Initialize(); }
void BrokerAdapterDeinit()       { BrokerAdapter::Deinit(); }
bool BrokerAdapterCheckCompatibility() { return BrokerAdapter::CheckCompatibility(); }
void BrokerAdapterOnTick()       { BrokerAdapter::OnTick(); }
void BrokerAdapterOnTimer()      { BrokerAdapter::OnTimer(); }
bool BrokerAdapterIsDOMAvailable() { return BrokerAdapter::IsDOMAvailable(); }

bool PythonBridgeInitialize()    { return PythonBridge::Initialize(); }
void PythonBridgeDeinit()        { PythonBridge::Deinit(); }
bool PythonBridgeUpdate()        { return PythonBridge::Update(); }

bool ExecutionGuardInitialize()  { return ExecutionGuard::Initialize(); }
void ExecutionGuardDeinit()      { ExecutionGuard::Deinit(); }
void ExecutionGuardOnTradeTransaction(const MQLTradeTransaction& transaction, const MQLTradeRequest& request) { ExecutionGuard::OnTradeTransaction(transaction, request); }

bool EmergencyManagerInitialize(){ return EmergencyManager::Initialize(); }
void EmergencyManagerDeinit()    { EmergencyManager::Deinit(); }
bool EmergencyManagerCheck()     { return EmergencyManager::Check(); }
void EmergencyManagerProtect()   { EmergencyManager::Protect(); }
void EmergencyManagerPostTick()  { EmergencyManager::PostTick(); }
void EmergencyManagerOnTradeTransaction(const MQLTradeTransaction& transaction, const MQLTradeRequest& request) { EmergencyManager::OnTradeTransaction(transaction, request); }

bool LoggerInitialize()          { return Logger::Initialize(); }
void LoggerDeinit()              { Logger::Deinit(); }
void LoggerWrite(const string text) { Logger::Write(text); }
void LoggerWriteTransaction(const MQLTradeTransaction& transaction, const MQLTradeRequest& request) { Logger::WriteTransaction(transaction, request); }
void LoggerOnTimer()             { Logger::OnTimer(); }

// Configuration access
input string g_symbol = "EURUSDm";
input double g_lot_size = 0.1;
input int g_max_spread_points = 3;
input bool g_use_hedging = true;
input bool g_adaptive_frequency = true;

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
  {
   // Called when expert is added to chart or settings changed
   OnInit();
  }
//+------------------------------------------------------------------+