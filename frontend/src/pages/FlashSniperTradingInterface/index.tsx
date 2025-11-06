import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getOrCreateWallet } from '@/utils/wallet.js';
import { Connection, clusterApiUrl } from '@solana/web3.js';
import bs58 from 'bs58';
import { executeTrade } from '@/services/trade';
import { useTradeMonitor } from '@/hooks/useTradeMonitor';



interface TransactionItem {
  id: string;
  type: 'traded' | 'exchanged' | 'sold' | 'completed' | 'liquidated';
  amount: string;
  token: string;
  date: string;
  time: string;
}

interface BuyFormData {
  amount: string;
  priorityFee: string;
  slippage: string;
}

interface SellFormData {
  takeProfit: string;
  stopLoss: string;
  slippage: string;
  timeout: string;
  priorityFee: string;
  trailingStopLoss: boolean;
  useOwnRPC: boolean;
}

const FlashSniperTradingInterface: React.FC = () => {
  // UI State
  const [activeTab, setActiveTab] = useState<'logs' | 'transactions'>('transactions');
  const [activeWalletTab, setActiveWalletTab] = useState<'wallet' | 'buySell'>('buySell');
  const [copied, setCopied] = useState(false);
  
  // Form State
  const [buyForm, setBuyForm] = useState<BuyFormData>({
    amount: '0.12000',
    priorityFee: '0.12000',
    slippage: '30%'
  });
  
  const [sellForm, setSellForm] = useState<SellFormData>({
    takeProfit: '40%',
    stopLoss: '20%',
    slippage: '40%',
    timeout: '60 seconds',
    priorityFee: '0.1000',
    trailingStopLoss: false,
    useOwnRPC: false
  });

  // Wallet and Trading State
  const [walletKeypair, setWalletKeypair] = useState<import('@solana/web3.js').Keypair | null>(null);
  const [walletAddress, setWalletAddress] = useState('');
  const [privateKeyString, setPrivateKeyString] = useState('');
  const [balance, setBalance] = useState(0);
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken') || null);
  const [isRegistered, setIsRegistered] = useState(!!localStorage.getItem('authToken'));
  const [tradeLogs, setTradeLogs] = useState<string[]>([]);
  const [isBotRunning, setIsBotRunning] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [showCopyMessage, setShowCopyMessage] = useState<'address' | 'key' | null>(null);
  const [showBalance, setShowBalance] = useState<boolean>(false); // Controls balance visibility
  const [hasCheckedBalance, setHasCheckedBalance] = useState(false);
  
  // Bot Settings
  const [botSettings, setBotSettings] = useState({
    buy_amount_sol: 0.05,
    buy_priority_fee_lamports: 1_000_000,
    buy_slippage_bps: 500,
    sell_take_profit_pct: 50.0,
    sell_stop_loss_pct: 10.0,
    sell_timeout_seconds: 300,
    sell_priority_fee_lamports: 1_000_000,
    sell_slippage_bps: 500,
    enable_trailing_stop_loss: false,
    trailing_stop_loss_pct: null,
    filter_socials_added: true,
    filter_liquidity_burnt: true,
    filter_immutable_metadata: true,
    filter_mint_authority_renounced: true,
    filter_freeze_authority_revoked: true,
    filter_pump_fun_migrated: true,
    filter_check_pool_size_min_sol: 0.5,
    filter_top_holders_max_pct: null,
    filter_bundled_max: null,
    filter_max_same_block_buys: null,
    filter_safety_check_period_seconds: null,
    bot_check_interval_seconds: 30,
    is_premium: false,
  });

  // Refs
  const tradeLogsRef = useRef<HTMLPreElement>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const connection = new Connection(clusterApiUrl('mainnet-beta'), 'confirmed');

  // Transaction History (mocked for now)
  const [transactions, setTransactions] = useState<TransactionItem[]>([
    {
      id: '1',
      type: 'traded',
      amount: '0.001',
      token: 'DRAGON',
      date: '15th August 2025',
      time: '3:45pm'
    },
    {
      id: '2',
      type: 'exchanged',
      amount: '0.001',
      token: 'PHOENIX',
      date: '5th September 2023',
      time: '9:00am'
    },
    {
      id: '3',
      type: 'sold',
      amount: '0.001',
      token: 'TIGER',
      date: '1st January 2026',
      time: '12:30pm'
    },
    {
      id: '4',
      type: 'completed',
      amount: '0.001',
      token: 'EAGLE',
      date: '10th October 2024',
      time: '4:15pm'
    },
    {
      id: '5',
      type: 'liquidated',
      amount: '0.001',
      token: 'WOLF',
      date: '30th November 2023',
      time: '8:00am'
    }
  ]);

  // Logging function
  interface LogToUI {
    (message: string): void;
  }

  interface NewTransaction extends TransactionItem {}

  const logToUI: LogToUI = useCallback((message: string) => {
    setTradeLogs((prevLogs: string[]) => [
      ...prevLogs,
      `[${new Date().toLocaleTimeString()}] ${message}`,
    ]);
    // Add to transactions if it's a trade message
    if (
      message.includes('Traded') ||
      message.includes('Sold') ||
      message.includes('Exchanged')
    ) {
      const newTransaction: NewTransaction = {
        id: Date.now().toString(),
        type: message.includes('Traded')
          ? 'traded'
          : message.includes('Sold')
          ? 'sold'
          : 'exchanged',
        amount: '0.001', // Extract from message in real implementation
        token: 'TOKEN', // Extract from message in real implementation
        date: new Date().toLocaleDateString('en-US', {
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        }),
        time: new Date().toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      };
      setTransactions((prev: TransactionItem[]) => [newTransaction, ...prev]);
    }
  }, []);

  // Initialize trade monitor
  useTradeMonitor(walletKeypair, walletAddress, authToken, logToUI);

  // Auto-scroll when new logs are added
  useEffect(() => {
    if (tradeLogsRef.current) {
      tradeLogsRef.current.scrollTop = tradeLogsRef.current.scrollHeight;
    }
  }, [tradeLogs]);

  // Fetch balance function
  interface FetchBalance {
    (publicKey: import('@solana/web3.js').PublicKey): Promise<void>;
  }

  const fetchBalance: FetchBalance = useCallback(
    async (publicKey: import('@solana/web3.js').PublicKey): Promise<void> => {
      try {
        const lamports: number = await connection.getBalance(publicKey);
        const solBalance: number = lamports / 1_000_000_000;
        setBalance(solBalance);
        logToUI(`Balance updated: ${solBalance.toFixed(4)} SOL`);
      } catch (error: any) {
        console.error("Error fetching balance:", error);
        setBalance(0);
        logToUI(`Error fetching balance: ${error.message}`);
      }
    },
    [connection, logToUI]
  );

  // Register wallet with backend
  interface RegisterWalletResponse {
    access_token: string;
    [key: string]: any;
  }

  interface RegisterWalletError {
    detail?: string;
    [key: string]: any;
  }

  interface RegisterWalletWithBackend {
    (keypair: import('@solana/web3.js').Keypair): Promise<void>;
  }

  const registerWalletWithBackend: RegisterWalletWithBackend = useCallback(
    async (keypair: import('@solana/web3.js').Keypair): Promise<void> => {
      const pubKey: string = keypair.publicKey.toBase58();
      const privateKeyBytes: Uint8Array = keypair.secretKey;
      const privateKeyBase64: string = btoa(JSON.stringify(Array.from(privateKeyBytes)));

      try {
        const response: Response = await fetch('https://api-v1.flashsnipper.com/auth/register-or-login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            wallet_address: pubKey,
            encrypted_private_key_bundle: privateKeyBase64,
          }),
        });

        if (!response.ok) {
          const errorData: RegisterWalletError = await response.json();
          throw new Error(errorData.detail || 'Failed to register/login wallet with backend.');
        }

        const data: RegisterWalletResponse = await response.json();
        localStorage.setItem('authToken', data.access_token);
        setAuthToken(data.access_token);
        setIsRegistered(true);
        logToUI("Wallet successfully registered/logged in with backend.");
      } catch (error: any) {
        logToUI(`Error registering/logging in wallet with backend: ${error.message}`);
        console.error("Error registering/logging in wallet with backend:", error);
      }
    },
    [logToUI]
  );

  // Fetch user settings
  useEffect(() => {
    const fetchUserSettings = async () => {
      if (authToken && walletAddress) {
        try {
          const response = await fetch(`https://api-v1.flashsnipper.com/user/settings/${walletAddress}`, {
            headers: {
              'Authorization': `Bearer ${authToken}`
            }
          });
          if (!response.ok) {
            throw new Error('Failed to fetch user settings');
          }
          const settingsData = await response.json();
          setBotSettings(prevSettings => ({
            ...prevSettings,
            ...settingsData,
            filter_top_holders_max_pct: settingsData.filter_top_holders_max_pct || null,
            trailing_stop_loss_pct: settingsData.trailing_stop_loss_pct || null,
            is_premium: settingsData.is_premium || false,
          }));
          logToUI("User bot settings loaded.");
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error);
          logToUI(`Error loading user settings: ${errorMsg}`);
          console.error("Error loading user settings:", error);
        }
      }
    };

    fetchUserSettings();
  }, [authToken, walletAddress, logToUI]);

  // Initialize wallet
  useEffect(() => {
    const keypair = getOrCreateWallet();
    setWalletKeypair(keypair);
    const address = keypair.publicKey.toBase58();
    setWalletAddress(address);

    try {
      const storedKeyBase64 = localStorage.getItem('solana_bot_pk_base64');
      if (!storedKeyBase64) throw new Error("No key in storage");

      const privateKeyBytes = new Uint8Array(JSON.parse(atob(storedKeyBase64)));
      const base58PrivateKey = bs58.encode(privateKeyBytes);
      setPrivateKeyString(base58PrivateKey);
    } catch (e) {
      console.error("Error displaying private key:", e);
      setPrivateKeyString("Error: Could not display private key.");
    }

    fetchBalance(keypair.publicKey);

    if (!isRegistered && keypair) {
      registerWalletWithBackend(keypair);
    }
  }, [fetchBalance, isRegistered, registerWalletWithBackend]);

  // WebSocket connection for real-time logs
  // useEffect(() => {
  //   if (walletAddress && authToken && !websocketRef.current) {
  //     const wsUrl = `ws://api-v1.flashsnipper.com/ws/connect/${walletAddress}?token=${authToken}`;
  //     websocketRef.current = new WebSocket(wsUrl);

  //     websocketRef.current.onopen = () => {
  //       logToUI("WebSocket connection established.");
  //     };

  //     websocketRef.current.onmessage = (event) => {
  //       const message = JSON.parse(event.data);
  //       logToUI(`WS Message: ${JSON.stringify(message)}`);

  //       if (message.type === "trade_instruction" && walletKeypair) {
  //         logToUI(`Received trade instruction from backend: ${message.message}`);
  //         executeTrade(walletKeypair, walletAddress, authToken, {
  //           mint_address: message.mint_address,
  //           amount_sol: message.amount_sol,
  //           trade_type: message.trade_type,
  //           token_symbol: message.token_symbol || "UNKNOWN",
  //           slippage_bps: botSettings.buy_slippage_bps,
  //           priority_fee_lamports: botSettings.buy_priority_fee_lamports
  //         });
  //       } else if (message.type === "log") {
  //         logToUI(`Bot Log: ${message.message}`);
  //       } else if (message.type === "bot_status") {
  //         setIsBotRunning(message.status === "running");
  //         logToUI(`Bot Status: ${message.status}`);
  //       } else if (message.type === "trade_update") {
  //         logToUI(`Trade Update for ${message.mint_address}: ${message.status} (TX: ${message.tx_hash || 'N/A'})`);
  //       }
  //     };

  //     websocketRef.current.onerror = (error) => {
  //       const err = error as any;
  //       logToUI(`WebSocket Error: ${err?.message || "Unknown error"}`);
  //       console.error("WebSocket Error:", error);
  //     };

  //     websocketRef.current.onclose = () => {
  //       logToUI("WebSocket connection closed. Attempting to reconnect in 5 seconds...");
  //       websocketRef.current = null;
  //       setTimeout(() => {
  //         if (walletAddress && authToken && !websocketRef.current) {
  //           const wsUrl = `ws://api-v1.flashsnipper.com/ws/connect/${walletAddress}?token=${authToken}`;
  //           websocketRef.current = new WebSocket(wsUrl);
  //           websocketRef.current.onopen = () => logToUI("WebSocket connection re-established.");
  //           websocketRef.current.onmessage = (event) => { /* ... */ };
  //           websocketRef.current.onerror = (error) => { /* ... */ };
  //           websocketRef.current.onclose = () => { /* ... */ };
  //         }
  //       }, 5000);
  //     };

  //     return () => {
  //       if (websocketRef.current) {
  //         websocketRef.current.close();
  //       }
  //     };
  //   }
  // }, [walletAddress, authToken, walletKeypair, logToUI, botSettings]);


  // UI Helpers
  const getTransactionText = (transaction: TransactionItem): string => {
    switch (transaction.type) {
      case 'traded':
        return `Traded ${transaction.amount} SOL of ${transaction.token}.`;
      case 'exchanged':
        return `Exchanged ${transaction.amount} SOL of ${transaction.token}.`;
      case 'sold':
        return `Sold ${transaction.amount} SOL of ${transaction.token}.`;
      case 'completed':
        return `Completed a sale of ${transaction.amount} SOL of ${transaction.token}.`;
      case 'liquidated':
        return `Liquidated ${transaction.amount} SOL of ${transaction.token}.`;
      default:
        return '';
    }
  };

  const handleBuyFormChange = (field: keyof BuyFormData, value: string) => {
    setBuyForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSellFormChange = (field: keyof SellFormData, value: string | boolean) => {
    setSellForm(prev => ({ ...prev, [field]: value }));
  };

  
  const handleCopyAddress = async () => {
    try {
      await navigator.clipboard.writeText(walletAddress);
      setShowCopyMessage('address');
      setTimeout(() => setShowCopyMessage(null), 2000);
    } catch (err) {
      console.error('Failed to copy address:', err);
    }
  };

  const handleCopyPrivateKey = async () => {
    try {
      await navigator.clipboard.writeText(privateKeyString);
      setShowCopyMessage('key');
      setTimeout(() => setShowCopyMessage(null), 2000);
    } catch (err) {
      console.error('Failed to copy private key:', err);
    }
  };

  const handleCheckSolDeposit = () => {
    if (walletKeypair) {
      fetchBalance(walletKeypair.publicKey);
    }
  };

  const handleRunBot = async () => {
    if (!authToken || !walletAddress) {
      alert("Please ensure wallet is registered and you have an auth token.");
      return;
    }
    logToUI("Sending request to backend to start bot/monitoring...");
    try {
      const response = await fetch('https://api-v1.flashsnipper.com/bot/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({ wallet_address: walletAddress })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to start bot.');
      }
      logToUI(`Bot start request: ${data.status}`);
      setIsBotRunning(true);
    } catch (error) {
      logToUI(`Error starting bot: ${error instanceof Error ? error.message : String(error)}`);
      console.error("Error starting bot:", error);
    }
  };

  const handleStopBot = async () => {
    if (!authToken || !walletAddress) {
      alert("Wallet not authenticated.");
      return;
    }
    logToUI("Sending request to backend to stop bot...");
    try {
      const response = await fetch('https://api-v1.flashsnipper.com/bot/stop', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({ wallet_address: walletAddress })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to stop bot.');
      }
      logToUI(`Bot stop request: ${data.status}`);
      setIsBotRunning(false);
    } catch (error) {
      logToUI(`Error stopping bot: ${error instanceof Error ? error.message : String(error)}`);
      console.error("Error stopping bot:", error);
    }
  };

  const handleManualBuy = async () => {
    if (!walletKeypair || !authToken || !walletAddress) {
      alert("Wallet not loaded or not authenticated.");
      return;
    }
    logToUI("Attempting manual BUY trade...");
    const result = await executeTrade(walletKeypair, walletAddress, authToken, {
      mint_address: "EPjFWdd5AufqSSqeM2qN1xzybapTVG4itwqZNfwpPJ",
      amount_sol: parseFloat(buyForm.amount),
      trade_type: "buy",
      token_symbol: "USDC",
      slippage_bps: parseInt(buyForm.slippage.replace('%', '')) * 100,
      priority_fee_lamports: parseFloat(buyForm.priorityFee) * 1_000_000_000
    });
    if (result.success) {
      logToUI("Manual BUY trade initiated successfully!");
    } else {
      logToUI(`Manual BUY trade failed: ${result.error}`);
    }
  };

  const handleManualSell = async () => {
    if (!walletKeypair || !authToken || !walletAddress) {
      alert("Wallet not loaded or not authenticated.");
      return;
    }
    logToUI("Attempting manual SELL trade...");
    const result = await executeTrade(walletKeypair, walletAddress, authToken, {
      mint_address: "EPjFWdd5AufqSSqeM2qN1xzybapTVG4itwqZNfwpPJ",
      amount_sol: 1,
      trade_type: "sell",
      token_symbol: "USDC",
      previousBuyPrice: 1,
      slippage_bps: parseInt(sellForm.slippage.replace('%', '')) * 100,
      priority_fee_lamports: parseFloat(sellForm.priorityFee) * 1_000_000_000
    });
    if (result.success) {
      logToUI("Manual SELL trade initiated successfully!");
    } else {
      logToUI(`Manual SELL trade failed: ${result.error}`);
    }
  };

  interface SaveBotSettingsEvent extends React.FormEvent<HTMLFormElement> {}

  interface SaveBotSettingsResponse {
    [key: string]: any;
  }

  interface SaveBotSettingsError {
    detail?: string;
    [key: string]: any;
  }

  const handleSaveBotSettings = async (event: SaveBotSettingsEvent): Promise<void> => {
    event.preventDefault();
    if (!authToken || !walletAddress) {
      alert("Please ensure wallet is registered and you have an auth token.");
      return;
    }
    logToUI("Saving bot settings...");
    try {
      const response: Response = await fetch(`https://api-v1.flashsnipper.com/user/settings/${walletAddress}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(botSettings)
      });

      const data: SaveBotSettingsResponse = await response.json();
      if (!response.ok) {
        const errorData: SaveBotSettingsError = data;
        throw new Error(errorData.detail || 'Failed to save bot settings.');
      }
      logToUI("Bot settings saved successfully!");
    } catch (error: any) {
      logToUI(`Error saving bot settings: ${error.message}`);
      console.error("Error saving bot settings:", error);
    }
  };

  const handleFundWallet = () => {
    alert(`Please send SOL to: ${walletAddress}`);
    logToUI(`Wallet address copied to clipboard: ${walletAddress}`);
    navigator.clipboard.writeText(walletAddress);
  };

  if (!walletKeypair) return <div className="text-white text-center py-8">Loading wallet...</div>;

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-[#10b98166] to-secondary relative">
      {/* Background Image */}
      <div 
        className="absolute inset-0 bg-cover bg-center opacity-20"
        style={{ backgroundImage: 'url(/images/img_grid_layers_v2.png)' }}
      />
      
      <div className="relative z-10">
        {/* Header */}
        <header className="bg-primary border-b border-[#ffffff21] h-16 flex items-center justify-between px-8">
          <div className="flex items-center gap-4">
            <img src="/images/img_frame_1171277880.svg" alt="Logo" className="w-3 h-3" />
            <div className="text-white text-sm font-black font-inter">
              <span className="text-white">FLASH </span>
              <span className="text-success">SNIPER</span>
            </div>
          </div>
          <div className="flex items-center gap-8">
            <span className="text-white text-sm font-medium">Documentation</span>
            <span className="text-white text-sm font-medium">Frequently Asked Questions</span>
          </div>
        </header>

        {/* Hero Section */}
        <div className="flex flex-col items-center justify-center py-16 px-8">
          <h1 className="text-white text-lg font-black text-center mb-6">Welcome to</h1>
          <div className="flex items-center gap-4 mb-8">
            <img src="/images/img_frame_1171277880.svg" alt="Logo" className="w-8 h-8" />
            <div className="text-white text-4xl font-black font-inter">
              <span className="text-white">FLASH </span>
              <span className="text-success">SNIPER</span>
            </div>
          </div>
          <p className="text-white text-sm font-medium text-center max-w-2xl mb-8 leading-relaxed">
            Velocity. Security. Accuracy. Take control of the Solana market with the quickest and most reliable sniper tool available. Your advantage in the Solana market begins now. Are you prepared to snipe with assurance?
          </p>
          <div className="text-center">
            <p className="text-white text-sm font-medium mb-2">Scroll down to snipe</p>
            <div className="w-px h-4 bg-white mx-auto"></div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex">
          {/* Left Panel - Transaction Logs */}
          <div className="w-[823px] bg-secondary border-r border-[#ffffff21]">
            {/* Tab Navigation */}
            <div className="bg-primary border-t border-b border-[#ffffff1e] h-12 flex">
              <button
                onClick={() => setActiveTab('logs')}
                className={`flex items-center gap-3 px-6 h-full border-b-2 ${
                  activeTab === 'logs' ? 'text-success border-success' : 'text-white border-transparent'
                }`}
              >
                <img 
                  src="/images/img_license_white_a700.svg" 
                  alt="Logs" 
                  className={`w-4 h-4 ${activeTab === 'logs' ? '' : 'opacity-70'}`}
                />
                <span className="text-sm font-medium">Logs</span>
              </button>
              <button
                onClick={() => setActiveTab('transactions')}
                className={`flex items-center gap-3 px-6 h-full border-b-2 ${
                  activeTab === 'transactions' ? 'text-success border-success' : 'text-white border-transparent'
                }`}
              >
                <img 
                  src="/images/img_transactionhistory_teal_400.svg" 
                  alt="Transactions" 
                  className={`w-4 h-4 ${activeTab === 'transactions' ? '' : 'opacity-70'}`}
                />
                <span className="text-sm font-medium">Transactions</span>
              </button>
            </div>

            {/* Stats Bar */}
            <div className="bg-secondary border-b border-[#ffffff1e] h-11 flex items-center justify-between px-4">
              <span className="text-white text-sm font-medium">Token snipped: 3</span>
              <span className="text-white text-sm font-medium">Total profit: {balance.toFixed(4)} SOL</span>
            </div>

            {/* Content based on active tab */}
            {activeTab === 'logs' ? (
              <div className="bg-secondary h-[600px] overflow-y-auto p-4">
                <pre className="text-white text-sm font-mono" ref={tradeLogsRef}>
                  {/* {tradeLogs.join('\n')} */}
                </pre>
              </div>
            ) : (
              <div className="bg-secondary h-[600px] overflow-y-auto">
                {transactions.map((transaction) => (
                  <div key={transaction.id} className="flex items-start gap-4 p-4 border-b border-[#ffffff1e] last:border-b-0">
                    <div className="w-6 h-6 bg-error-light rounded-full flex-shrink-0 mt-0.5"></div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white text-sm font-medium">
                          {getTransactionText(transaction)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-white text-sm font-medium">View on:</span>
                          <img src="/images/img_image_2.png" alt="View" className="w-6 h-6" />
                        </div>
                      </div>
                      <span className="text-secondary text-xs font-medium">
                        {transaction.date} at {transaction.time}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Panel - Trading Interface */}
            {/* Right Panel - Trading Interface */}
            <div className="flex-1 bg-overlay">
              {/* Wallet Tab Navigation */}
              <div className="bg-primary border-t border-b border-[#ffffff1e] h-12 flex">
                <button
                  onClick={() => setActiveWalletTab('wallet')}
                  className={`flex items-center gap-3 px-6 h-full border-b-2 ${
                    activeWalletTab === 'wallet' ? 'text-success border-success' : 'text-white border-transparent'
                  }`}
                >
                  <img 
                    src="/images/img_wallet01_white_a700.svg" 
                    alt="Wallet" 
                    className="w-4 h-4" 
                  />
                  <span className="text-sm font-medium">Wallet</span>
                </button>
                <button
                  onClick={() => setActiveWalletTab('buySell')}
                  className={`flex items-center gap-3 px-6 h-full border-b-2 ${
                    activeWalletTab === 'buySell' ? 'text-success border-success' : 'text-white border-transparent'
                  }`}
                >
                  <img 
                    src="/images/img_exchange01_teal_400.svg" 
                    alt="Buy/Sell" 
                    className="w-4 h-4" 
                  />
                  <span className="text-sm font-medium">Buy/Sell</span>
                </button>
              </div>

              <div className="p-4 space-y-4">
                {activeWalletTab === 'wallet' ? (
                  <div className="p-4 space-y-4">
                    {/* Wallet Card */}
                    <div className="bg-dark-2 rounded-lg border border-[#262944] shadow-lg">
                      <div className="flex items-center gap-3 p-4 border-b border-[#000010] shadow-sm">
                        <img
                          src="/images/img_wallet01_white_a700.svg"
                          alt="Wallet"
                          className="w-[18px] h-[18px]"
                        />
                        <span className="text-light font-satoshi font-medium text-[13px] leading-[18px]">
                          Your Wallet
                        </span>
                      </div>

                      <div className="p-3 space-y-3">
                        {/* Wallet Address */}
                        <div className="relative">
                          <input
                            type="text"
                            value={walletAddress}
                            readOnly
                            className="w-full bg-primary border border-[#20233a] rounded-lg px-3 py-3 text-white font-satoshi font-medium text-[13px] leading-[18px] shadow-sm"
                          />
                          {showCopyMessage === 'address' && (
                            <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-success text-white px-2 py-1 rounded text-xs">
                              Copied!
                            </div>
                          )}
                        </div>

                        {/* Action Buttons */}
                        <div className="flex gap-2">
                          <button
                            onClick={handleCopyAddress}
                            className="flex-1 bg-accent border-t border-[#22253e] rounded-lg px-3 py-3 text-success font-satoshi font-medium text-[13px] leading-[18px] hover:bg-opacity-80 transition-colors shadow-sm"
                          >
                            Copy address
                          </button>
                          <button
                            onClick={handleCopyPrivateKey}
                            className="flex-1 bg-accent border-t border-[#22253e] rounded-lg px-3 py-3 text-success font-satoshi font-medium text-[13px] leading-[18px] hover:bg-opacity-80 transition-colors shadow-sm relative"
                          >
                            Copy private key
                            {showCopyMessage === 'key' && (
                              <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-success text-white px-2 py-1 rounded text-xs">
                                Copied!
                              </div>
                            )}
                          </button>
                        </div>

                        {/* Current Balance - Always shown after first check */}
                        {/* <div className="relative">
                          <input
                            type="text"
                            value={`${balance.toFixed(4)} SOL`}
                            readOnly
                            className="w-full bg-primary border border-[#20233a] rounded-lg px-3 py-3 text-white font-satoshi font-medium text-[13px] leading-[18px] shadow-sm"
                          />
                        </div> */}

                        {/* Thumbs Up Button for Balance Check - Only shown if balance hasn't been checked yet */}
                        {(balance < 0.0 || !hasCheckedBalance) && (
                          <div className="flex items-center justify-center pt-2">
                            <button
                              onClick={() => {
                                handleCheckSolDeposit();
                                setHasCheckedBalance(true);
                              }}
                              className="flex items-center justify-center w-12 h-12 bg-success rounded-full shadow-lg hover:bg-opacity-90 transition-colors"
                              title="Check SOL Balance"
                            >
                              <span className="text-2xl">👍</span>
                            </button>
                            <span className="ml-3 text-white-transparent font-satoshi font-medium text-[11px] leading-[10px]">
                              Click to check your SOL balance
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Warning Message - Only shown if balance is less than 0.2 SOL */}
                    {balance < 0.2 && (
                      <div className="bg-warning-light border border-[#e7a13a4c] rounded-lg px-4 py-3 shadow-sm">
                        <span className="text-warning font-satoshi font-medium text-[13px] leading-[18px]">
                          Please send a minimum of 0.2 sol to this wallet to get started
                        </span>
                      </div>
                    )}

                    {/* Run Bot Button */}
                    <button
                      onClick={isBotRunning ? handleStopBot : handleRunBot}
                      className={`w-full rounded-lg px-4 py-3 font-satoshi font-medium text-[13px] leading-[18px] border transition-all duration-200 shadow-sm ${
                        isBotRunning
                          ? 'bg-red-600 border-red-600 text-white hover:bg-red-700'
                          : 'bg-success border-white text-white hover:bg-opacity-90'
                      }`}
                      disabled={balance < 0.2} // Disable if balance is less than 0.2 SOL
                    >
                      {isBotRunning ? 'Stop Bot' : 'Run Bot'}
                    </button>

                    {/* Disclaimer */}
                    <p className="text-white-transparent font-satoshi font-medium text-[11px] leading-[15px] text-center">
                      Start or stop anytime. 1% fee per trade. Starting means you accept our disclaimer
                    </p>
                  </div>

                ) : (
                  <>
                    {/* Buy Section */}
                    <div className="bg-dark-1 rounded-lg shadow-lg">
                      <div className="flex items-center gap-3 p-4 border-b border-[#000010]">
                        <img src="/images/img_bitcoinshopping.svg" alt="Buy" className="w-5 h-5" />
                        <span className="text-light text-base font-medium">Buy</span>
                      </div>

                      <div className="p-4 space-y-4">
                        {/* Fund Wallet Alert */}
                        {balance <= 0 && (
                          <button
                            onClick={handleFundWallet}
                            className="w-full p-3 bg-warning-light border border-[#e7a13a4c] rounded-lg text-warning text-sm font-medium"
                          >
                            Fund your wallet to use the bot
                          </button>
                        )}

                        {/* Amount and Priority Fee */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-muted text-sm font-medium mb-2">Amount</label>
                            <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                              <input
                                type="text"
                                value={buyForm.amount}
                                onChange={(e) => handleBuyFormChange('amount', e.target.value)}
                                className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                              />
                              <span className="text-muted text-sm">SOL</span>
                            </div>
                          </div>
                          <div>
                            <label className="block text-muted text-sm font-medium mb-2">Priority fee</label>
                            <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                              <input
                                type="text"
                                value={buyForm.priorityFee}
                                onChange={(e) => handleBuyFormChange('priorityFee', e.target.value)}
                                className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                              />
                              <span className="text-muted text-sm">SOL</span>
                            </div>
                          </div>
                        </div>

                        {/* Slippage */}
                        <div>
                          <label className="block text-muted text-sm font-medium mb-2">Slippage</label>
                          <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                            <input
                              type="text"
                              value={buyForm.slippage}
                              onChange={(e) => handleBuyFormChange('slippage', e.target.value)}
                              className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                            />
                          </div>
                        </div>

                        {/* Manual Buy Button */}
                        <button
                          onClick={handleManualBuy}
                          className="w-full bg-primary text-white text-sm font-medium py-3 rounded-lg border border-primary-dark shadow-sm hover:bg-opacity-90 transition-colors"
                          disabled={balance <= 0}
                        >
                          Manual Buy
                        </button>
                      </div>
                    </div>

                    {/* Sell Section */}
                    <div className="bg-dark-2 rounded-lg shadow-lg">
                      <div className="flex items-center gap-3 p-4 border-b border-[#000010]">
                        <img src="/images/img_bitcoin03.svg" alt="Sell" className="w-5 h-5" />
                        <span className="text-light text-base font-medium">Sell</span>
                      </div>

                      <div className="p-4 space-y-4 border-b border-[#000010]">
                        {/* Take Profit and Stop Loss */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-muted text-sm font-medium mb-2">Take profit</label>
                            <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                              <input
                                type="text"
                                value={sellForm.takeProfit}
                                onChange={(e) => handleSellFormChange('takeProfit', e.target.value)}
                                className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-muted text-sm font-medium mb-2">Stop loss</label>
                            <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                              <input
                                type="text"
                                value={sellForm.stopLoss}
                                onChange={(e) => handleSellFormChange('stopLoss', e.target.value)}
                                className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                              />
                            </div>
                          </div>
                        </div>

                        {/* Slippage and Timeout */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-muted text-sm font-medium mb-2">Slippage</label>
                            <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                              <input
                                type="text"
                                value={sellForm.slippage}
                                onChange={(e) => handleSellFormChange('slippage', e.target.value)}
                                className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-muted text-sm font-medium mb-2">Timeout</label>
                            <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center justify-between">
                              <input
                                type="text"
                                value={sellForm.timeout}
                                onChange={(e) => handleSellFormChange('timeout', e.target.value)}
                                className="bg-transparent text-muted text-sm font-medium outline-none flex-1"
                              />
                            </div>
                          </div>
                        </div>

                        {/* Priority Fee */}
                        <div>
                          <label className="block text-muted text-sm font-medium mb-2">Priority fee</label>
                          <input
                            type="text"
                            value={sellForm.priorityFee}
                            onChange={(e) => handleSellFormChange('priorityFee', e.target.value)}
                            className="w-full bg-accent border-t border-[#22253e] rounded-lg p-3 text-muted text-sm font-medium outline-none"
                            placeholder="0.1000"
                          />
                        </div>

                        {/* Trailing Stop Loss */}
                        <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={sellForm.trailingStopLoss}
                            onChange={(e) => handleSellFormChange('trailingStopLoss', e.target.checked)}
                            className="w-6 h-6"
                          />
                          <span className="text-muted text-sm font-medium">Trailing stop loss</span>
                        </div>
                      </div>

                      {/* Use Own RPC */}
                      <div className="p-4">
                        <div className="bg-accent border-t border-[#22253e] rounded-lg p-3 flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={sellForm.useOwnRPC}
                            onChange={(e) => handleSellFormChange('useOwnRPC', e.target.checked)}
                            className="w-6 h-6"
                          />
                          <span className="text-muted text-sm font-medium">Use your own RPC?</span>
                        </div>
                      </div>
                    </div>

                    {/* Manual Sell Button */}
                    <button
                      onClick={handleManualSell}
                      className="w-full bg-error text-white text-sm font-medium py-3 rounded-lg border border-error-dark shadow-sm hover:bg-opacity-90 transition-colors"
                      disabled={balance <= 0}
                    >
                      Manual Sell
                    </button>

                    {/* Run/Stop Bot Button */}
                    {!isBotRunning ? (
                      <button
                        onClick={handleRunBot}
                        className="w-full bg-success text-white text-sm font-medium py-3 rounded-lg border border-white shadow-sm hover:bg-opacity-90 transition-colors"
                        disabled={balance <= 0}
                      >
                        Run Bot
                      </button>
                    ) : (
                      <button
                        onClick={handleStopBot}
                        className="w-full bg-error text-white text-sm font-medium py-3 rounded-lg border border-white shadow-sm hover:bg-opacity-90 transition-colors"
                      >
                        Stop Bot
                      </button>
                    )}

                    {/* Disclaimer */}
                    <p className="text-white-transparent text-xs font-medium text-center leading-relaxed">
                      Start or stop anytime. 1% fee per trade. Starting means you accept our disclaimer
                    </p>
                  </>
                )}
              </div>
            </div>


          
        </div>

        {/* Footer */}
        <footer className="bg-secondary border-t border-[#ffffff21] h-12 flex items-center justify-between px-8">
          <span className="text-white text-sm font-medium">© 2025 | FlashSniper.com | Disclaimer</span>
          <div className="flex items-center gap-10">
            <img src="/images/img_newtwitter.svg" alt="Twitter" className="w-4 h-4" />
            <img src="/images/img_telegram.svg" alt="Telegram" className="w-4 h-4" />
            <img src="/images/img_discord.svg" alt="Discord" className="w-4 h-4" />
          </div>
        </footer>
      </div>
    </div>
  );
};

export default FlashSniperTradingInterface;