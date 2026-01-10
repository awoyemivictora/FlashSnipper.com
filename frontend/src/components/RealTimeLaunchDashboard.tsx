// components/RealTimeLaunchDashboard.tsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { apiService } from '@/services/api';
import { launchWebSocket } from '@/services/websocket';
import { 
  ActivityFeedItem, 
  TransactionStatus, 
  BotActivity,
  RealTimeLaunchStats,
  TokenInfo
} from '@/types/realtime';


interface RealTimeLaunchDashboardProps {
  launchId: string;
  onClose?: () => void;
}

const RealTimeLaunchDashboard: React.FC<RealTimeLaunchDashboardProps> = ({ 
  launchId, 
  onClose 
}) => {
  const [activityFeed, setActivityFeed] = useState<ActivityFeedItem[]>([]);
  const [liveStats, setLiveStats] = useState<RealTimeLaunchStats>({
    totalTransactions: 0,
    successfulTransactions: 0,
    failedTransactions: 0,
    totalVolume: 0,
    totalBots: 0,
    activeBots: 0,
    currentPhase: 'setup',
    estimatedTimeRemaining: 0
  });
  
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [botActivities, setBotActivities] = useState<BotActivity[]>([]);
  const [transactions, setTransactions] = useState<TransactionStatus[]>([]);
  const [showDetails, setShowDetails] = useState<boolean>(true);
  const [selectedTab, setSelectedTab] = useState<'overview' | 'bots' | 'transactions' | 'performance'>('overview');

  // Add activity to feed with auto-scroll
  const addActivity = useCallback((item: ActivityFeedItem) => {
    setActivityFeed(prev => [item, ...prev.slice(0, 49)]); // Keep last 50 items
  }, []);

  // Initialize WebSocket connection
  useEffect(() => {
    if (!launchId) return;

    launchWebSocket.connect(launchId);

    // Token creation events
    launchWebSocket.on('token_created', (data: any) => {
      addActivity({
        type: 'token_creation',
        message: `Token ${data.name} (${data.symbol}) created`,
        timestamp: new Date().toISOString(),
        data: {
          mintAddress: data.mint_address,
          signature: data.signature,
          explorerUrl: `https://solscan.io/tx/${data.signature}`,
          pumpFunUrl: `https://pump.fun/coin/${data.mint_address}`
        }
      });

      setTokenInfo({
        mintAddress: data.mint_address,
        name: data.name,
        symbol: data.symbol,
        created: new Date().toISOString(),
        explorerUrl: `https://solscan.io/tx/${data.signature}`,
        pumpFunUrl: `https://pump.fun/coin/${data.mint_address}`
      });
    });

    // Bot funding events
    launchWebSocket.on('bot_funding_start', (data: any) => {
      addActivity({
        type: 'bot_funding',
        message: `Funding ${data.bot_count} bots with ${data.total_amount.toFixed(4)} SOL`,
        timestamp: new Date().toISOString(),
        data
      });
    });

    launchWebSocket.on('bot_funded', (data: any) => {
      const botActivity: BotActivity = {
        botId: data.bot_id,
        publicKey: data.public_key,
        action: 'funded',
        amount: data.amount,
        timestamp: new Date().toISOString(),
        status: 'success',
        signature: data.signature
      };

      setBotActivities(prev => [botActivity, ...prev.slice(0, 99)]);
      addActivity({
        type: 'bot_funded',
        message: `Bot ${data.public_key.slice(0, 8)}... funded with ${data.amount.toFixed(4)} SOL`,
        timestamp: new Date().toISOString(),
        data: botActivity
      });
    });

    // Bot buy events
    launchWebSocket.on('bot_buy_start', (data: any) => {
      addActivity({
        type: 'bot_buy',
        message: `Bot ${data.bot_id} buying ${data.amount.toFixed(4)} SOL worth of tokens`,
        timestamp: new Date().toISOString(),
        data
      });
    });

    launchWebSocket.on('bot_buy_complete', (data: any) => {
      const txStatus: TransactionStatus = {
        signature: data.signature,
        type: 'buy',
        status: 'confirmed',
        amount: data.amount,
        tokenAmount: data.token_amount,
        timestamp: new Date().toISOString(),
        explorerUrl: `https://solscan.io/tx/${data.signature}`
      };

      setTransactions(prev => [txStatus, ...prev.slice(0, 99)]);
      
      const botActivity: BotActivity = {
        botId: data.bot_id,
        publicKey: data.public_key,
        action: 'buy',
        amount: data.amount,
        tokenAmount: data.token_amount,
        timestamp: new Date().toISOString(),
        status: 'success',
        signature: data.signature
      };

      setBotActivities(prev => [botActivity, ...prev.slice(0, 99)]);
      
      addActivity({
        type: 'bot_buy_success',
        message: `✅ Bot ${data.bot_id} bought ${data.token_amount.toLocaleString()} tokens`,
        timestamp: new Date().toISOString(),
        data: botActivity
      });
    });

    // Sell events
    launchWebSocket.on('sell_start', (data: any) => {
      addActivity({
        type: 'sell_start',
        message: `Starting sell phase: ${data.strategy_type}`,
        timestamp: new Date().toISOString(),
        data
      });
    });

    launchWebSocket.on('sell_complete', (data: any) => {
      const txStatus: TransactionStatus = {
        signature: data.signature,
        type: 'sell',
        status: 'confirmed',
        amount: data.amount,
        profit: data.profit,
        timestamp: new Date().toISOString(),
        explorerUrl: `https://solscan.io/tx/${data.signature}`
      };

      setTransactions(prev => [txStatus, ...prev.slice(0, 99)]);
      
      addActivity({
        type: 'sell_success',
        message: `💰 Sold ${data.token_amount.toLocaleString()} tokens for ${data.amount.toFixed(4)} SOL (Profit: ${data.profit?.toFixed(4)} SOL)`,
        timestamp: new Date().toISOString(),
        data: txStatus
      });
    });

    // Phase updates
    launchWebSocket.on('phase_update', (data: any) => {
    setLiveStats((prev: RealTimeLaunchStats) => ({
      ...prev,
      currentPhase: data.phase as RealTimeLaunchStats['currentPhase'],
      estimatedTimeRemaining: data.estimated_time_remaining as number
    }));

      addActivity({
        type: 'phase_update',
        message: `Entering ${data.phase} phase`,
        timestamp: new Date().toISOString(),
        data
      });
    });

    // Launch complete
    launchWebSocket.on('launch_complete', (data: any) => {
      addActivity({
        type: 'launch_complete',
        message: `🎉 Launch completed! Total profit: ${data.total_profit?.toFixed(4)} SOL (ROI: ${data.roi?.toFixed(2)}%)`,
        timestamp: new Date().toISOString(),
        data
      });

    setLiveStats((prev: RealTimeLaunchStats) => ({
      ...prev,
      currentPhase: 'complete'
    }));
    });

    return () => {
      launchWebSocket.disconnect();
    };
  }, [launchId, addActivity]);

  // Calculate live stats
  useEffect(() => {
    const successfulTxs = transactions.filter(tx => tx.status === 'confirmed').length;
    const failedTxs = transactions.filter(tx => tx.status === 'failed').length;
    const totalVolume = transactions.reduce((sum, tx) => sum + (tx.amount || 0), 0);
    const activeBots = botActivities.filter(bot => 
      bot.timestamp > new Date(Date.now() - 30000).toISOString()
    ).length;

    setLiveStats((prev: RealTimeLaunchStats) => ({
      ...prev,
      totalTransactions: transactions.length,
      successfulTransactions: successfulTxs,
      failedTransactions: failedTxs,
      totalVolume: totalVolume,
      totalBots: botActivities.length,
      activeBots: activeBots
    }));
  }, [transactions, botActivities]);

  // Stats cards
  const StatCard = ({ title, value, change, icon, color }: any) => (
    <div className="bg-dark-2 rounded-xl p-4 border border-gray-800/50">
      <div className="flex items-center justify-between mb-2">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          {icon}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-white">{value}</div>
          {change && (
            <div className={`text-xs ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {change >= 0 ? '↑' : '↓'} {Math.abs(change)}%
            </div>
          )}
        </div>
      </div>
      <div className="text-sm text-gray-400">{title}</div>
    </div>
  );

  // Activity item component
  const ActivityItem = ({ item }: { item: ActivityFeedItem }) => {
    const getIcon = () => {
      switch (item.type) {
        case 'token_creation': return '🏗️';
        case 'bot_funding': return '💰';
        case 'bot_buy': return '🛒';
        case 'bot_buy_success': return '✅';
        case 'sell_success': return '💰';
        case 'phase_update': return '🔄';
        case 'launch_complete': return '🎉';
        default: return '📝';
      }
    };

    const getColor = () => {
      switch (item.type) {
        case 'token_creation': return 'text-blue-400';
        case 'bot_buy_success': return 'text-emerald-400';
        case 'sell_success': return 'text-yellow-400';
        case 'launch_complete': return 'text-purple-400';
        default: return 'text-gray-300';
      }
    };

    return (
      <div className="flex items-start gap-3 p-3 hover:bg-gray-900/30 rounded-lg transition-colors">
        <div className="text-xl mt-0.5">{getIcon()}</div>
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-medium ${getColor()}`}>
            {item.message}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {new Date(item.timestamp).toLocaleTimeString()}
          </div>
          {item.data?.signature && (
            <a
              href={item.data.explorerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 mt-1"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              View Transaction
            </a>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Background overlay */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      
      {/* Dashboard panel */}
      <div className="absolute inset-4 md:inset-20 bg-gradient-to-br from-gray-900 via-dark-1 to-dark-2 rounded-2xl border border-gray-800/50 shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800/50">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">Live Launch Dashboard</h2>
              <div className="flex items-center gap-3 text-sm text-gray-400">
                <span className="font-mono">{launchId.slice(0, 16)}...</span>
                {tokenInfo && (
                  <a
                    href={tokenInfo.pumpFunUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    View on pump.fun
                  </a>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="p-2 hover:bg-gray-800/50 rounded-lg text-gray-400 hover:text-white transition-colors"
            >
              {showDetails ? 'Hide Details' : 'Show Details'}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-800/50 rounded-lg text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-3 gap-6 p-6">
          {/* Left column - Stats and token info */}
          <div className="lg:col-span-2 space-y-6 overflow-y-auto">
            {/* Stats grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                title="Total Transactions"
                value={liveStats.totalTransactions}
                icon={<span>📊</span>}
                color="bg-blue-500/20"
              />
              <StatCard
                title="Successful"
                value={liveStats.successfulTransactions}
                change={(liveStats.successfulTransactions / liveStats.totalTransactions) * 100}
                icon={<span>✅</span>}
                color="bg-emerald-500/20"
              />
              <StatCard
                title="Total Volume"
                value={`${liveStats.totalVolume.toFixed(2)} SOL`}
                icon={<span>💰</span>}
                color="bg-yellow-500/20"
              />
              <StatCard
                title="Active Bots"
                value={liveStats.activeBots}
                change={(liveStats.activeBots / liveStats.totalBots) * 100}
                icon={<span>🤖</span>}
                color="bg-purple-500/20"
              />
            </div>

            {/* Current phase */}
            <div className="bg-dark-2 rounded-xl p-4 border border-gray-800/50">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-bold text-lg">Current Phase</h3>
                <div className="px-3 py-1 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-full border border-cyan-500/30">
                  <span className="text-sm font-medium text-cyan-400 capitalize">
                    {liveStats.currentPhase}
                  </span>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">Time Remaining</span>
                  <span className="text-white font-medium">
                    {liveStats.estimatedTimeRemaining > 0 
                      ? `${Math.floor(liveStats.estimatedTimeRemaining / 60)}m ${liveStats.estimatedTimeRemaining % 60}s`
                      : 'Complete'}
                  </span>
                </div>
                {tokenInfo && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Token Address</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">{tokenInfo.mintAddress.slice(0, 16)}...</span>
                      <button
                        onClick={() => navigator.clipboard.writeText(tokenInfo.mintAddress)}
                        className="text-blue-400 hover:text-blue-300"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Bot activity chart */}
            <div className="bg-dark-2 rounded-xl p-4 border border-gray-800/50">
              <h3 className="text-white font-bold text-lg mb-4">Bot Activity Timeline</h3>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {botActivities.slice(0, 20).map((bot, index) => (
                  <div key={index} className="flex items-center gap-3 p-2 hover:bg-gray-900/30 rounded-lg">
                    <div className={`w-2 h-2 rounded-full ${
                      bot.status === 'success' ? 'bg-emerald-500' : 'bg-red-500'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white">
                        Bot {bot.publicKey.slice(0, 8)}... {bot.action}
                        {bot.amount && ` ${bot.amount.toFixed(4)} SOL`}
                        {bot.tokenAmount && ` (${bot.tokenAmount.toLocaleString()} tokens)`}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(bot.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                    {bot.signature && (
                      <a
                        href={`https://solscan.io/tx/${bot.signature}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right column - Activity feed */}
          <div className="space-y-6 overflow-hidden">
            <div className="bg-dark-2 rounded-xl p-4 border border-gray-800/50 h-full flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-bold text-lg">Live Activity Feed</h3>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                  <span className="text-xs text-emerald-400">Live</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto space-y-1">
                {activityFeed.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-800/50 flex items-center justify-center">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <p>Waiting for launch activity...</p>
                  </div>
                ) : (
                  activityFeed.map((item, index) => (
                    <ActivityItem key={index} item={item} />
                  ))
                )}
              </div>
            </div>

            {/* Quick actions */}
            <div className="bg-dark-2 rounded-xl p-4 border border-gray-800/50">
              <h3 className="text-white font-bold text-lg mb-4">Quick Actions</h3>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => navigator.clipboard.writeText(launchId)}
                  className="py-2 px-3 bg-gray-800/50 hover:bg-gray-700/50 text-gray-300 hover:text-white rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy ID
                </button>
                {tokenInfo && (
                  <a
                    href={tokenInfo.pumpFunUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="py-2 px-3 bg-gradient-to-r from-blue-500/20 to-cyan-500/20 hover:from-blue-500/30 hover:to-cyan-500/30 text-blue-400 hover:text-blue-300 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 border border-blue-500/30"
                  >
                    <span>🚀</span>
                    pump.fun
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer with progress bar */}
        <div className="p-4 border-t border-gray-800/50 bg-dark-1">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                liveStats.currentPhase === 'complete' ? 'bg-emerald-500' :
                liveStats.currentPhase === 'failed' ? 'bg-red-500' : 
                'bg-cyan-500 animate-pulse'
              }`} />
              <span className="text-gray-300">
                {liveStats.currentPhase === 'complete' ? 'Launch Complete' :
                 liveStats.currentPhase === 'failed' ? 'Launch Failed' :
                 'Launch in Progress'}
              </span>
            </div>
            <div className="text-gray-400">
              {liveStats.totalTransactions} transactions • {liveStats.totalVolume.toFixed(2)} SOL volume
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RealTimeLaunchDashboard;




























// // src/components/RealTimeLaunchDashboard.tsx
// import React, { useState, useEffect, useMemo } from 'react';
// import { launchWebSocket } from '@/services/websocket';
// import PerformanceMetrics from './PerformanceMetrics';
// import AutoSellProgress from './AutoSellProgress';
// import MiniStatusIndicator from './MiniStatusIndicator';

// interface RealTimeLaunchDashboardProps {
//   launchId: string;
//   onClose: () => void;
// }

// const RealTimeLaunchDashboard: React.FC<RealTimeLaunchDashboardProps> = ({
//   launchId,
//   onClose
// }) => {
//   const [activeTab, setActiveTab] = useState<'overview' | 'bots' | 'transactions' | 'analytics'>('overview');
//   const [realTimeData, setRealTimeData] = useState<any>({
//     status: 'monitoring',
//     progress: 60,
//     message: 'Monitoring token performance...',
//     transactions: [],
//     botActivities: [],
//     sellProgress: 0,
//     totalTokens: 0,
//     soldTokens: 0,
//     estimatedProfit: 0,
//     sellStrategy: { type: 'volume_based' },
//     performanceMetrics: {
//       totalVolume: 0,
//       successRate: 0,
//       activeBots: 0,
//       averageBuySize: 0
//     }
//   });

//   // Setup WebSocket listeners
//   useEffect(() => {
//     if (!launchId) return;

//     launchWebSocket.connect(launchId);

//     // Listen for status updates
//     launchWebSocket.on('status_update', (data: any) => {
//       console.log('Status update received:', data);
//       setRealTimeData(prev => ({
//         ...prev,
//         status: data.status || prev.status,
//         progress: data.progress || prev.progress,
//         message: data.message || prev.message
//       }));
//     });

//     // Listen for token created event
//     launchWebSocket.on('token_created', (data: any) => {
//       console.log('Token created event:', data);
//       setRealTimeData(prev => ({
//         ...prev,
//         tokenAddress: data.mint_address,
//         tokenName: data.name,
//         tokenSymbol: data.symbol
//       }));
//     });

//     // Listen for transaction events
//     launchWebSocket.on('transaction', (data: any) => {
//       console.log('Transaction event:', data);
//       setRealTimeData(prev => ({
//         ...prev,
//         transactions: [...prev.transactions, {
//           id: data.signature,
//           type: data.type || 'unknown',
//           amount: data.amount,
//           status: data.status || 'pending',
//           timestamp: new Date().toISOString(),
//           signature: data.signature
//         }].slice(-50) // Keep last 50 transactions
//       }));
//     });

//     // Listen for bot activity
//     launchWebSocket.on('bot_activity', (data: any) => {
//       console.log('Bot activity:', data);
//       setRealTimeData(prev => ({
//         ...prev,
//         botActivities: [...prev.botActivities, {
//           botId: data.bot_id,
//           publicKey: data.public_key,
//           action: data.action,
//           amount: data.amount,
//           profit: data.profit,
//           timestamp: new Date().toISOString()
//         }].slice(-100) // Keep last 100 activities
//       }));
//     });

//     // Listen for sell progress
//     launchWebSocket.on('sell_progress', (data: any) => {
//       setRealTimeData(prev => ({
//         ...prev,
//         sellProgress: data.progress || prev.sellProgress,
//         totalTokens: data.totalTokens || prev.totalTokens,
//         soldTokens: data.soldTokens || prev.soldTokens,
//         estimatedProfit: data.estimatedProfit || prev.estimatedProfit
//       }));
//     });

//     // Listen for launch complete
//     launchWebSocket.on('launch_completed', (data: any) => {
//       console.log('Launch completed:', data);
//       setRealTimeData(prev => ({
//         ...prev,
//         status: 'complete',
//         progress: 100,
//         message: 'Launch completed successfully!',
//         results: data.results
//       }));
//     });

//     // Listen for launch failed
//     launchWebSocket.on('launch_failed', (data: any) => {
//       console.log('Launch failed:', data);
//       setRealTimeData(prev => ({
//         ...prev,
//         status: 'failed',
//         progress: 0,
//         message: data.error || 'Launch failed',
//         error: data.error
//       }));
//     });

//     return () => {
//       launchWebSocket.disconnect();
//       launchWebSocket.off('status_update');
//       launchWebSocket.off('token_created');
//       launchWebSocket.off('transaction');
//       launchWebSocket.off('bot_activity');
//       launchWebSocket.off('sell_progress');
//       launchWebSocket.off('launch_completed');
//       launchWebSocket.off('launch_failed');
//     };
//   }, [launchId]);

//   // Calculate performance metrics from data
//   const performanceMetrics = useMemo(() => {
//     const transactions = realTimeData.transactions || [];
//     const botActivities = realTimeData.botActivities || [];
    
//     const totalVolume = transactions.reduce((sum: number, tx: any) => sum + (tx.amount || 0), 0);
//     const successfulTransactions = transactions.filter((tx: any) => tx.status === 'confirmed').length;
//     const successRate = transactions.length > 0 ? (successfulTransactions / transactions.length) * 100 : 0;
    
//     const uniqueBots = new Set(botActivities.map((b: any) => b.botId)).size;
    
//     const buyTransactions = transactions.filter((tx: any) => tx.type === 'buy');
//     const averageBuySize = buyTransactions.length > 0 
//       ? buyTransactions.reduce((sum: number, tx: any) => sum + (tx.amount || 0), 0) / buyTransactions.length
//       : 0;

//     return {
//       totalVolume,
//       successRate,
//       activeBots: uniqueBots,
//       averageBuySize
//     };
//   }, [realTimeData.transactions, realTimeData.botActivities]);

//   const getStatusColor = (status: string) => {
//     switch (status.toLowerCase()) {
//       case 'complete':
//         return 'bg-emerald-500';
//       case 'failed':
//         return 'bg-red-500';
//       case 'monitoring':
//         return 'bg-amber-500';
//       case 'selling':
//         return 'bg-blue-500';
//       default:
//         return 'bg-gray-500';
//     }
//   };

//   const getStatusIcon = (status: string) => {
//     switch (status.toLowerCase()) {
//       case 'complete':
//         return '✅';
//       case 'failed':
//         return '❌';
//       case 'monitoring':
//         return '📊';
//       case 'selling':
//         return '📈';
//       default:
//         return '⏳';
//     }
//   };

//   if (!launchId) return null;

//   return (
//     <div className="fixed inset-0 z-50 overflow-hidden">
//       {/* Backdrop */}
//       <div 
//         className="absolute inset-0 bg-black/70 backdrop-blur-sm"
//         onClick={onClose}
//       />
      
//       {/* Dashboard */}
//       <div className="absolute inset-4 md:inset-20 bg-dark-2 rounded-2xl border border-gray-800/50 shadow-2xl overflow-hidden">
//         {/* Header */}
//         <div className="flex items-center justify-between p-6 border-b border-gray-800/50 bg-dark-2">
//           <div className="flex items-center gap-4">
//             <div className={`w-3 h-3 rounded-full ${getStatusColor(realTimeData.status)} animate-pulse`} />
//             <div>
//               <h2 className="text-white text-2xl font-bold">
//                 Live Launch Dashboard
//               </h2>
//               <p className="text-gray-400 text-sm">
//                 Launch ID: <span className="font-mono text-emerald-400">{launchId.slice(0, 12)}...</span>
//               </p>
//             </div>
//           </div>
          
//           <div className="flex items-center gap-4">
//             <div className="hidden md:flex items-center gap-2 bg-gray-900/50 px-3 py-2 rounded-lg">
//               <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
//               <span className="text-sm text-emerald-400">LIVE</span>
//             </div>
            
//             <button
//               onClick={onClose}
//               className="p-2 hover:bg-gray-800/50 rounded-lg transition-colors"
//             >
//               <svg className="w-6 h-6 text-gray-400 hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
//               </svg>
//             </button>
//           </div>
//         </div>
        
//         {/* Main Content */}
//         <div className="flex flex-col h-[calc(100vh-10rem)] md:h-[calc(100vh-12rem)]">
//           {/* Tabs */}
//           <div className="flex border-b border-gray-800/50">
//             {[
//               { id: 'overview', label: '📊 Overview', icon: '📊' },
//               { id: 'bots', label: '🤖 Bot Army', icon: '🤖' },
//               { id: 'transactions', label: '💸 Transactions', icon: '💸' },
//               { id: 'analytics', label: '📈 Analytics', icon: '📈' }
//             ].map((tab) => (
//               <button
//                 key={tab.id}
//                 onClick={() => setActiveTab(tab.id as any)}
//                 className={`flex-1 py-4 text-sm font-medium transition-colors ${
//                   activeTab === tab.id
//                     ? 'text-white border-b-2 border-emerald-500 bg-emerald-500/10'
//                     : 'text-gray-400 hover:text-white hover:bg-gray-800/30'
//                 }`}
//               >
//                 <div className="flex items-center justify-center gap-2">
//                   <span>{tab.icon}</span>
//                   <span className="hidden sm:inline">{tab.label}</span>
//                 </div>
//               </button>
//             ))}
//           </div>
          
//           {/* Content Area */}
//           <div className="flex-1 overflow-y-auto p-4 md:p-6">
//             {activeTab === 'overview' && (
//               <div className="space-y-6">
//                 {/* Status Card */}
//                 <div className="bg-gray-900/30 rounded-xl p-6 border border-gray-800/50">
//                   <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
//                     <div className="flex items-center gap-4">
//                       <div className="text-3xl">{getStatusIcon(realTimeData.status)}</div>
//                       <div>
//                         <h3 className="text-white text-xl font-bold">{realTimeData.message}</h3>
//                         <p className="text-gray-400">Current phase: {realTimeData.status}</p>
//                       </div>
//                     </div>
                    
//                     <div className="flex items-center gap-6">
//                       <div className="text-center">
//                         <div className="text-2xl font-bold text-white">
//                           {realTimeData.progress}%
//                         </div>
//                         <div className="text-sm text-gray-400">Progress</div>
//                       </div>
                      
//                       <div className="w-32 h-2 bg-gray-800 rounded-full overflow-hidden">
//                         <div
//                           className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-500"
//                           style={{ width: `${realTimeData.progress}%` }}
//                         />
//                       </div>
//                     </div>
//                   </div>
//                 </div>
                
//                 {/* Token Info */}
//                 {realTimeData.tokenAddress && (
//                   <div className="bg-gray-900/30 rounded-xl p-6 border border-gray-800/50">
//                     <h3 className="text-white font-bold text-xl mb-4">Token Information</h3>
//                     <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
//                       <div>
//                         <div className="text-gray-400 text-sm mb-1">Token Address</div>
//                         <div className="font-mono text-sm text-emerald-400 break-all">
//                           {realTimeData.tokenAddress}
//                         </div>
//                       </div>
//                       <div>
//                         <div className="text-gray-400 text-sm mb-1">Token Name</div>
//                         <div className="text-white font-medium">
//                           {realTimeData.tokenName || 'Loading...'}
//                         </div>
//                       </div>
//                       <div>
//                         <div className="text-gray-400 text-sm mb-1">Token Symbol</div>
//                         <div className="text-white font-medium">
//                           {realTimeData.tokenSymbol || 'Loading...'}
//                         </div>
//                       </div>
//                     </div>
//                   </div>
//                 )}
                
//                 {/* Performance Metrics */}
//                 <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
//                   <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-xl p-4 border border-blue-500/30">
//                     <div className="text-sm text-gray-400 mb-1">Total Volume</div>
//                     <div className="text-2xl font-bold text-white">
//                       {performanceMetrics.totalVolume.toFixed(2)} SOL
//                     </div>
//                   </div>
                  
//                   <div className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-xl p-4 border border-emerald-500/30">
//                     <div className="text-sm text-gray-400 mb-1">Success Rate</div>
//                     <div className="text-2xl font-bold text-white">
//                       {performanceMetrics.successRate.toFixed(1)}%
//                     </div>
//                   </div>
                  
//                   <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-xl p-4 border border-purple-500/30">
//                     <div className="text-sm text-gray-400 mb-1">Active Bots</div>
//                     <div className="text-2xl font-bold text-white">
//                       {performanceMetrics.activeBots}
//                     </div>
//                   </div>
                  
//                   <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 rounded-xl p-4 border border-amber-500/30">
//                     <div className="text-sm text-gray-400 mb-1">Avg Buy Size</div>
//                     <div className="text-2xl font-bold text-white">
//                       {performanceMetrics.averageBuySize.toFixed(4)} SOL
//                     </div>
//                   </div>
//                 </div>
                
//                 {/* Auto Sell Progress */}
//                 <AutoSellProgress
//                   sellStrategy={realTimeData.sellStrategy}
//                   currentProgress={realTimeData.sellProgress}
//                   totalTokens={realTimeData.totalTokens}
//                   soldTokens={realTimeData.soldTokens}
//                   estimatedProfit={realTimeData.estimatedProfit}
//                 />
//               </div>
//             )}
            
//             {activeTab === 'bots' && (
//               <div className="space-y-6">
//                 <div className="bg-gray-900/30 rounded-xl p-6 border border-gray-800/50">
//                   <h3 className="text-white font-bold text-xl mb-6">Bot Army Activity</h3>
                  
//                   <div className="overflow-x-auto">
//                     <table className="w-full">
//                       <thead>
//                         <tr className="border-b border-gray-800/50">
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Bot ID</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Action</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Amount</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Profit</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Time</th>
//                         </tr>
//                       </thead>
//                       <tbody>
//                         {realTimeData.botActivities.slice().reverse().map((bot: any, index: number) => (
//                           <tr key={index} className="border-b border-gray-800/30 hover:bg-gray-800/20">
//                             <td className="py-3">
//                               <div className="font-mono text-sm text-gray-300">
//                                 {bot.botId || bot.publicKey?.slice(0, 8)}...
//                               </div>
//                             </td>
//                             <td className="py-3">
//                               <span className={`px-2 py-1 rounded-full text-xs font-medium ${
//                                 bot.action === 'buy' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
//                                 bot.action === 'sell' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
//                                 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
//                               }`}>
//                                 {bot.action || 'unknown'}
//                               </span>
//                             </td>
//                             <td className="py-3 text-white font-medium">
//                               {bot.amount ? `${bot.amount.toFixed(4)} SOL` : '-'}
//                             </td>
//                             <td className="py-3">
//                               <span className={`font-medium ${
//                                 bot.profit > 0 ? 'text-emerald-400' :
//                                 bot.profit < 0 ? 'text-red-400' : 'text-gray-400'
//                               }`}>
//                                 {bot.profit ? `${bot.profit.toFixed(4)} SOL` : '-'}
//                               </span>
//                             </td>
//                             <td className="py-3 text-sm text-gray-400">
//                               {new Date(bot.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
//                             </td>
//                           </tr>
//                         ))}
//                       </tbody>
//                     </table>
//                   </div>
                  
//                   {realTimeData.botActivities.length === 0 && (
//                     <div className="text-center py-12 text-gray-500">
//                       No bot activity yet. Activity will appear here as bots execute trades.
//                     </div>
//                   )}
//                 </div>
//               </div>
//             )}
            
//             {activeTab === 'transactions' && (
//               <div className="space-y-6">
//                 <div className="bg-gray-900/30 rounded-xl p-6 border border-gray-800/50">
//                   <h3 className="text-white font-bold text-xl mb-6">Recent Transactions</h3>
                  
//                   <div className="overflow-x-auto">
//                     <table className="w-full">
//                       <thead>
//                         <tr className="border-b border-gray-800/50">
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Type</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Amount</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Status</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Signature</th>
//                           <th className="py-3 text-left text-gray-400 text-sm font-medium">Time</th>
//                         </tr>
//                       </thead>
//                       <tbody>
//                         {realTimeData.transactions.slice().reverse().map((tx: any, index: number) => (
//                           <tr key={index} className="border-b border-gray-800/30 hover:bg-gray-800/20">
//                             <td className="py-3">
//                               <span className={`px-2 py-1 rounded-full text-xs font-medium ${
//                                 tx.type === 'buy' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
//                                 tx.type === 'sell' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
//                                 tx.type === 'create' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
//                                 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
//                               }`}>
//                                 {tx.type || 'unknown'}
//                               </span>
//                             </td>
//                             <td className="py-3 text-white font-medium">
//                               {tx.amount ? `${tx.amount.toFixed(4)} SOL` : '-'}
//                             </td>
//                             <td className="py-3">
//                               <span className={`px-2 py-1 rounded-full text-xs font-medium ${
//                                 tx.status === 'confirmed' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
//                                 tx.status === 'failed' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
//                                 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
//                               }`}>
//                                 {tx.status || 'pending'}
//                               </span>
//                             </td>
//                             <td className="py-3">
//                               <div className="font-mono text-xs text-gray-400 truncate max-w-[120px]">
//                                 {tx.signature?.slice(0, 16)}...
//                               </div>
//                             </td>
//                             <td className="py-3 text-sm text-gray-400">
//                               {new Date(tx.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
//                             </td>
//                           </tr>
//                         ))}
//                       </tbody>
//                     </table>
//                   </div>
                  
//                   {realTimeData.transactions.length === 0 && (
//                     <div className="text-center py-12 text-gray-500">
//                       No transactions yet. Transactions will appear here as they occur.
//                     </div>
//                   )}
//                 </div>
//               </div>
//             )}
            
//             {activeTab === 'analytics' && (
//               <div className="space-y-6">
//                 <PerformanceMetrics
//                   transactions={realTimeData.transactions}
//                   botActivities={realTimeData.botActivities}
//                 />
//               </div>
//             )}
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// };

// export default RealTimeLaunchDashboard;

