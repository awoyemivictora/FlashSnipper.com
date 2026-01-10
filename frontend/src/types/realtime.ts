// types/realtime.ts
export interface ActivityFeedItem {
  type: 'token_creation' | 'bot_funding' | 'bot_funded' | 'bot_buy' | 'bot_buy_success' | 
        'sell_start' | 'sell_success' | 'phase_update' | 'launch_complete' | 'error';
  message: string;
  timestamp: string;
  data?: any;
}

export interface TransactionStatus {
  signature: string;
  type: 'create' | 'buy' | 'sell' | 'fund';
  status: 'pending' | 'confirmed' | 'failed';
  amount?: number;
  tokenAmount?: number;
  profit?: number;
  timestamp: string;
  explorerUrl: string;
}

export interface BotActivity {
  botId: string;
  publicKey: string;
  action: 'funded' | 'buy' | 'sell';
  amount?: number;
  tokenAmount?: number;
  timestamp: string;
  status: 'success' | 'failed';
  signature?: string;
}

export interface RealTimeLaunchStats {
  totalTransactions: number;
  successfulTransactions: number;
  failedTransactions: number;
  totalVolume: number;
  totalBots: number;
  activeBots: number;
  currentPhase: string;
  estimatedTimeRemaining: number;
}

export interface TokenInfo {
  mintAddress: string;
  name: string;
  symbol: string;
  created: string;
  explorerUrl: string;
  pumpFunUrl: string;
}
