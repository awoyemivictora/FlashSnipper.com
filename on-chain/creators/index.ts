import express, { Request, Response } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { Connection, Keypair, PublicKey, VersionedTransaction } from '@solana/web3.js';
import dotenv from 'dotenv';
import winston from 'winston';
import morgan from 'morgan';

// Import services
// import { createToken } from './tokenCreation';
// Update your imports to use the new functions
import { executeBuy, executeBotBuy } from './buyExecution';
import { executeSell, executeBotSell } from './sellExecution';
import { createCompleteLaunchBundle, executeAtomicLaunch, executeBotBuys, fundBots } from './botManager';
import { estimateCost } from './costEstimator';
import { CreateTokenRequest, BuyRequest, SellRequest, FundBotsRequest, EstimateCostRequest, AtomicLaunchRequest, ExecuteBotBuysRequest, BotSellRequest } from '../types/api';
import { validateRequest } from '../types/validation';
import axios from 'axios';
import bs58  from 'bs58';
import { createJitoBundleSender } from '../jito_bundles/jito-integration';
import { createToken } from './tokenCreation';
import { createCompleteLaunchWithAutoSell, executeSmartSells } from './sellManager';

dotenv.config();

interface DecryptedKeyResponse {
  wallet_address: string;
  decrypted_private_key: string;
  cached: boolean;
  timestamp: string;
}

// Initialize logger
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'onchain-service.log' })
  ]
});

// Initialize connection
const RPC_URL = process.env.RPC_URL || 'https://api.mainnet-beta.solana.com';
const connection = new Connection(RPC_URL, 'confirmed');

// Express app
const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(helmet());
app.use(cors({
  origin: process.env.BACKEND_URL || 'http://localhost:8000',
  credentials: true
}));
app.use(express.json({ limit: '10mb' }));
app.use(morgan('combined', { stream: { write: (message) => logger.info(message.trim()) } }));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP'
});
app.use('/api/onchain/', limiter);

// Health check endpoint
app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    service: 'on-chain-service',
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version || '1.0.0',
    rpc_connected: true
  });
});

// API key middleware
const apiKeyMiddleware = (req: Request, res: Response, next: Function) => {
  const apiKey = req.headers['x-api-key'];
  const expectedKey = process.env.ONCHAIN_API_KEY;
  
  if (!apiKey || apiKey !== expectedKey) {
    logger.warn(`Unauthorized API access attempt from ${req.ip}`);
    return res.status(401).json({ 
      success: false, 
      error: 'Unauthorized: Invalid API key' 
    });
  }
  next();
};

// Apply API key middleware to all on-chain endpoints
app.use('/api/onchain/', apiKeyMiddleware);

// Atomic create and buy endpoint (token creation + all buys in one bundle)
app.post('/api/onchain/atomic-create-and-buy', async (req: Request, res: Response) => {
  try {
    logger.info('Received atomic create and buy request');
    
    const {
      user_wallet,
      metadata,
      creator_buy_amount,
      bot_wallets = [],
      use_jito = true,
      sell_strategy
    } = req.body;
    
    // 1. Create token first
    const tokenResult = await createToken(connection, {
      metadata,
      user_wallet,
      use_jito: false, // We'll bundle everything
      creator_override: undefined
    });
    
    if (!tokenResult.success || !tokenResult.mint_address) {
      throw new Error(`Token creation failed: ${tokenResult.error}`);
    }
    
    const mintAddress = tokenResult.mint_address;
    logger.info(`✅ Token created: ${mintAddress}`);
    
    // 2. Prepare all buy transactions
    const allTransactions: VersionedTransaction[] = [];
    
    // Add creator buy
    const creatorBuyResult = await executeBuy(connection, {
      action: 'buy',
      mint_address: mintAddress,
      user_wallet,
      amount_sol: creator_buy_amount,
      use_jito: false, // Bundle with others
      slippage_bps: 500
    });
    
    if (creatorBuyResult.transaction) {
      allTransactions.push(creatorBuyResult.transaction);
    }
    
    // Add bot buys
    for (const bot of bot_wallets) {
      const botBuyResult = await executeBotBuys(connection, {
        action: 'execute_bot_buys',
        mint_address: mintAddress,
        user_wallet,
        bot_wallets: [bot], // Single bot at a time
        use_jito: false, // Bundle with others
        slippage_bps: 500
      });
      
      if (botBuyResult.transaction) {
        allTransactions.push(botBuyResult.transaction);
      }
    }
    
    logger.info(`✅ Prepared ${allTransactions.length} transactions for atomic bundle`);
    
    // 3. Send as Jito bundle
    let bundleResult;
    if (use_jito && allTransactions.length > 0) {
      try {
        logger.info(`🚀 Sending atomic bundle via Jito...`);
        // Create Jito sender instance
        const jitoSender = createJitoBundleSender(connection);
        bundleResult = await jitoSender.sendBundle(allTransactions);
      } catch (jitoError) {
        logger.error('Jito atomic bundle failed:', jitoError);
        bundleResult = { success: false };
      }
    }

    // 4. Calculate estimated results
    const totalCost = creator_buy_amount + 
                     bot_wallets.reduce((sum: number, bot: any) => sum + bot.buy_amount, 0);
    
    // Estimate profit (simplified - you'd need actual price data)
    const estimatedProfit = totalCost * 0.2; // 20% estimate
    const estimatedROI = (estimatedProfit / totalCost) * 100;
    
    res.json({
      success: true,
      mint_address: mintAddress,
      creator_signature: creatorBuyResult.signatures?.[0],
      bundle_id: bundleResult?.bundleId,
      signatures: allTransactions.map(tx => bs58.encode(tx.signatures[0])),
      estimated_cost: totalCost,
      estimated_profit: estimatedProfit,
      estimated_roi: estimatedROI,
      transaction_count: allTransactions.length,
      bot_count: bot_wallets.length,
      timestamp: new Date().toISOString()
    });
    
    logger.info(`Atomic create+buy completed: success`);
    
  } catch (error: any) {
    logger.error(`Atomic create+buy error: ${error.message}`, { stack: error.stack });
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Token creation endpoint
// app.post('/api/onchain/create-token', async (req: Request, res: Response) => {
//   try {
//     logger.info('Received token creation request');
    
//     const validation = validateRequest<CreateTokenRequest>(req.body, 'create_token');
//     if (!validation.valid) {
//       return res.status(400).json({
//         success: false,
//         error: validation.errors?.join(', ')
//       });
//     }
    
//     const result = await createToken(connection, req.body);
    
//     res.json({
//       success: result.success,
//       signature: result.signature,
//       mint_address: result.mint_address,
//       error: result.error,
//       timestamp: new Date().toISOString()
//     });
    
//     logger.info(`Token creation completed: ${result.success ? 'success' : 'failed'}`);
    
//   } catch (error: any) {
//     logger.error(`Token creation error: ${error.message}`, { stack: error.stack });
//     res.status(500).json({
//       success: false,
//       error: error.message,
//       timestamp: new Date().toISOString()
//     });
//   }
// });

// index.ts - Update the create-token endpoint
app.post('/api/onchain/create-token', async (req: Request, res: Response) => {
  try {
    logger.info('Received token creation request');
    
    // ✅ Simplified validation
    const { name, symbol, uri } = req.body.metadata || {};
    
    if (!name || !symbol || !uri) {
      return res.status(400).json({
        success: false,
        error: 'Metadata must include name, symbol, and uri'
      });
    }
    
    // Call token creation with simplified data
    const result = await createToken(connection, {
      ...req.body,
      metadata: { name, symbol, uri } // ✅ Only send name, symbol, uri
    });
    
    res.json({
      success: result.success,
      signature: result.signature,
      mint_address: result.mint_address,
      error: result.error,
      timestamp: new Date().toISOString()
    });
    
  } catch (error: any) {
    logger.error(`Token creation error: ${error.message}`);
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Buy execution endpoint
// app.post('/api/onchain/buy', async (req: Request, res: Response) => {
//   try {
//     logger.info('Received buy execution request');
    
//     const validation = validateRequest<BuyRequest>(req.body, 'buy');
//     if (!validation.valid) {
//       return res.status(400).json({
//         success: false,
//         error: validation.errors?.join(', ')
//       });
//     }
    
//     const result = await executeBuy(connection, req.body);
    
//     res.json({
//       success: result.success,
//       bundle_id: result.bundle_id,
//       signatures: result.signatures,
//       error: result.error,
//       estimated_cost: result.estimated_cost,
//       timestamp: new Date().toISOString()
//     });
    
//     logger.info(`Buy execution completed: ${result.success ? 'success' : 'failed'}`);
    
//   } catch (error: any) {
//     logger.error(`Buy execution error: ${error.message}`, { stack: error.stack });
//     res.status(500).json({
//       success: false,
//       error: error.message,
//       timestamp: new Date().toISOString()
//     });
//   }
// });

// // Sell execution endpoint
// app.post('/api/onchain/sell', async (req: Request, res: Response) => {
//   try {
//     logger.info('Received sell execution request');
    
//     const validation = validateRequest<SellRequest>(req.body, 'sell');
//     if (!validation.valid) {
//       return res.status(400).json({
//         success: false,
//         error: validation.errors?.join(', ')
//       });
//     }
    
//     const result = await executeSell(connection, req.body);
    
//     res.json({
//       success: result.success,
//       bundle_id: result.bundle_id,
//       signatures: result.signatures,
//       error: result.error,
//       estimated_cost: result.estimated_cost,
//       timestamp: new Date().toISOString()
//     });
    
//     logger.info(`Sell execution completed: ${result.success ? 'success' : 'failed'}`);
    
//   } catch (error: any) {
//     logger.error(`Sell execution error: ${error.message}`, { stack: error.stack });
//     res.status(500).json({
//       success: false,
//       error: error.message,
//       timestamp: new Date().toISOString()
//     });
//   }
// });

// Fund bots endpoint
app.post('/api/onchain/fund-bots', async (req: Request, res: Response) => {
  try {
    logger.info('Received fund bots request');
    
    const validation = validateRequest<FundBotsRequest>(req.body, 'fund_bots');
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.errors?.join(', ')
      });
    }
    
    const result = await fundBots(connection, req.body);
    
    res.json({
      success: result.success,
      bundle_id: result.bundle_id,
      signatures: result.signatures,
      error: result.error,
      estimated_cost: result.estimated_cost,
      timestamp: new Date().toISOString()
    });
    
    logger.info(`Fund bots completed: ${result.success ? 'success' : 'failed'}`);
    
  } catch (error: any) {
    logger.error(`Fund bots error: ${error.message}`, { stack: error.stack });
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

app.post('/api/onchain/execute-bot-buys', async (req: Request, res: Response) => {
  try {
    logger.info('Received execute bot buys request');

    // Validate request
    const validation = validateRequest<ExecuteBotBuysRequest>(req.body, 'execute_bot_buys');
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.errors?.join(', ')
      });
    }

    const result = await executeBotBuys(connection, req.body);

    res.json({
      success: result.success,
      bundle_id: result.bundle_id,
      signatures: result.signatures,
      mint_address: req.body.mint_address,
      error: result.error,
      estimated_cost: result.estimated_cost,
      stats: result.stats, // ✅ Now this will work
      timestamp: new Date().toISOString()
    });

    logger.info(`Execute bot buys completed: ${result.success ? 'success' : 'failed'}`);

  } catch (error: any) {
    logger.error(`Execute bot buys error: ${error.message}`, { stack: error.stack });
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});








app.post('/api/onchain/atomic-launch', async (req: Request, res: Response) => {
  try {
    logger.info('📨 Received atomic launch request');
    
    // ✅ DEBUG: Log the entire request body
    logger.info('📋 Request body:', JSON.stringify(req.body, null, 2));
    
    // ✅ ALWAYS USE AUTO-SELL - NO CHECK NEEDED
    logger.info('🚀 Processing ATOMIC LAUNCH WITH AUTO-SELL...');
    
    // ✅ CRITICAL FIX: Check for BOTH "bot_buys" and "bot_wallets"
    let botBuys = [];
    
    // Check for bot_buys (what the backend sends)
    if (req.body.bot_buys && Array.isArray(req.body.bot_buys)) {
      botBuys = req.body.bot_buys;
      logger.info(`✅ Found bot_buys: ${botBuys.length} bots`);
    } 
    // Check for bot_wallets (legacy field)
    else if (req.body.bot_wallets && Array.isArray(req.body.bot_wallets)) {
      botBuys = req.body.bot_wallets;
      logger.info(`✅ Found bot_wallets: ${botBuys.length} bots`);
    }
    // Check for botBuys (camelCase)
    else if (req.body.botBuys && Array.isArray(req.body.botBuys)) {
      botBuys = req.body.botBuys;
      logger.info(`✅ Found botBuys: ${botBuys.length} bots`);
    }
    else {
      logger.warn('⚠️ No bot arrays found in request');
      logger.warn('Available keys:', Object.keys(req.body));
    }
    
    // ✅ DEBUG: Log metadata structure
    if (req.body.metadata) {
      logger.info('📄 Metadata structure:');
      logger.info(`   Type: ${typeof req.body.metadata}`);
      logger.info(`   Keys: ${Object.keys(req.body.metadata).join(', ')}`);
      logger.info(`   Has name: ${!!req.body.metadata.name}`);
      logger.info(`   Has symbol: ${!!req.body.metadata.symbol}`);
      logger.info(`   Has uri: ${!!req.body.metadata.uri}`);
      
      if (req.body.metadata.uri) {
        logger.info(`🔗 URI value: ${req.body.metadata.uri}`);
      }
    }
    
    // ✅ DEBUG: Check if metadata is being passed correctly
    if (!req.body.metadata) {
      logger.error('❌ No metadata in request');
      return res.status(400).json({
        success: false,
        error: 'No metadata provided'
      });
    }
    
    const { name, symbol, uri } = req.body.metadata;
    // Extract launch_id from request
    const launch_id = req.body.launch_id;
    
    // ✅ CRITICAL: Validate we have the minimal required fields
    if (!name || !symbol || !uri) {
      logger.error('❌ Missing required metadata fields:');
      logger.error(`   Name: ${name || 'MISSING'}`);
      logger.error(`   Symbol: ${symbol || 'MISSING'}`);
      logger.error(`   URI: ${uri || 'MISSING'}`);
      
      return res.status(400).json({
        success: false,
        error: 'Metadata must include name, symbol, and uri'
      });
    }
    
    // Map bot wallets properly - handle different field names
    const mappedBotBuys = botBuys.map((bot: any) => {
      return {
        public_key: bot.public_key || bot.publicKey,
        amount_sol: bot.amount_sol || bot.buy_amount || bot.amount || 0.0001
      };
    });

    // ✅ ALWAYS USE AUTO-SELL STRATEGY
    // Parse sell strategy from request or use defaults
    const sellStrategy = req.body.sell_strategy || {
      minProfitPercentage: req.body.min_profit_percentage || 30,
      maxHoldTimeSeconds: req.body.max_hold_time || 60,
      stopLossPercentage: req.body.stop_loss_percentage || 15,
      staggeredSellDelayMs: req.body.staggered_sell_delay || 2000,
      partialSellPercentages: req.body.partial_sell_percentages || [50, 50]
    };
    
    logger.info('💰 Auto-sell strategy:', JSON.stringify(sellStrategy, null, 2));
    
    // ✅ DEBUG: Log what we're sending to createCompleteLaunchWithAutoSell
    logger.info('🚀 Calling createCompleteLaunchWithAutoSell with:');
    logger.info(`   User wallet: ${req.body.user_wallet}`);
    logger.info(`   Name: ${name}`);
    logger.info(`   Symbol: ${symbol}`);
    logger.info(`   URI: ${uri}`);
    logger.info(`   Creator buy amount: ${req.body.creator_buy_amount || 0.01}`);
    logger.info(`   Bot count: ${mappedBotBuys.length}`);
    logger.info(`   Use Jito: ${req.body.use_jito !== false}`);
    logger.info(`   Slippage: ${req.body.slippage_bps || 500} bps`);
    logger.info(`   Sell strategy: ${JSON.stringify(sellStrategy, null, 2)}`);
    
    // ✅ ALWAYS CALL createCompleteLaunchWithAutoSell
    const result = await createCompleteLaunchWithAutoSell(connection, {
      user_wallet: req.body.user_wallet,
      metadata: {
        name,
        symbol,
        uri
      },
      creator_buy_amount: req.body.creator_buy_amount || 0.01,
      bot_buys: mappedBotBuys,
      sell_strategy: sellStrategy,
      use_jito: req.body.use_jito !== false,
      slippage_bps: req.body.slippage_bps || 500,
      launch_id: launch_id
    });
    
    // ✅ DEBUG: Log the result
    logger.info('📊 Launch result:');
    logger.info(`   Success: ${result.success}`);
    logger.info(`   Mint address: ${result.mint_address || 'NONE'}`);
    logger.info(`   Error: ${result.error || 'NONE'}`);
    logger.info(`   Signature count: ${result.signatures?.length || 0}`);
    logger.info(`   Estimated cost: ${result.estimated_cost || 0} SOL`);
    logger.info(`   Total SOL received: ${result.total_sol_received || 0} SOL`);
    
    if (result.signatures && result.signatures.length > 0) {
      result.signatures.forEach((sig: string, i: number) => {
        logger.info(`   Signature ${i}: ${sig.slice(0, 16)}...`);
      });
    }
    
    // Return response with sell stats
    const response = {
      success: result.success,
      bundle_id: result.bundle_id,
      signatures: result.signatures,
      mint_address: result.mint_address,
      error: result.error,
      estimated_cost: result.estimated_cost,
      sell_stats: result.sell_stats,
      total_sol_received: result.total_sol_received,
      auto_sell: true, // Always true now
      timestamp: new Date().toISOString()
    };

    res.json(response);
    
    // Calculate profit/loss if possible
    if (result.estimated_cost && result.total_sol_received) {
      const profit = result.total_sol_received - result.estimated_cost;
      const roi = (profit / result.estimated_cost) * 100;
      logger.info(`💰 Profit/Loss Summary:`);
      logger.info(`   Total spent: ${result.estimated_cost.toFixed(6)} SOL`);
      logger.info(`   Total received: ${result.total_sol_received.toFixed(6)} SOL`);
      logger.info(`   Net: ${profit >= 0 ? '+' : ''}${profit.toFixed(6)} SOL`);
      logger.info(`   ROI: ${roi.toFixed(2)}%`);
    }
    
    logger.info(`✅ Atomic launch with auto-sell completed: ${result.success ? 'SUCCESS' : 'FAILED'}`);

  } catch (error: any) {
    logger.error(`❌ Atomic launch error:`, {
      message: error.message,
      stack: error.stack,
      body: JSON.stringify(req.body, null, 2)
    });
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Keep the separate endpoint for selling existing tokens if needed
app.post('/api/onchain/execute-smart-sells', async (req: Request, res: Response) => {
  try {
    logger.info('📨 Received smart sell request for existing token');
    
    const request: BotSellRequest = {
      mint_address: req.body.mint_address,
      user_wallet: req.body.user_wallet,
      creator_wallet: req.body.creator_wallet,
      bot_wallets: req.body.bot_wallets || [],
      sell_strategy: req.body.sell_strategy || {
        minProfitPercentage: 30,
        maxHoldTimeSeconds: 60,
        stopLossPercentage: 15,
        staggeredSellDelayMs: 2000,
        partialSellPercentages: [50, 50]
      },
      use_jito: req.body.use_jito !== false
    };
    
    logger.info('💰 Smart sell request:', JSON.stringify(request, null, 2));
    
    const result = await executeSmartSells(connection, request);
    
    res.json({
      success: result.success,
      signatures: result.signatures,
      total_sol_received: result.total_sol_received,
      error: result.error,
      stats: result.stats,
      timestamp: new Date().toISOString()
    });
    
    logger.info(`✅ Smart sells completed: ${result.success ? 'SUCCESS' : 'FAILED'}`);
    
  } catch (error: any) {
    logger.error(`❌ Smart sell error:`, error.message);
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});










app.post('/api/onchain/estimate-cost', async (req: Request, res: Response) => {
  try {
    logger.info('Received cost estimation request');
    
    const validation = validateRequest<EstimateCostRequest>(req.body, 'estimate_cost');
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.errors?.join(', ')
      });
    }
    
    const result = await estimateCost(connection, req.body);
    
    res.json({
      success: result.success,
      estimated_cost: result.estimated_cost,
      cost_breakdown: result.cost_breakdown,
      error: result.error,
      timestamp: new Date().toISOString()
    });
    
  } catch (error: any) {
    logger.error(`Cost estimation error: ${error.message}`, { stack: error.stack });
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Get token price endpoint
app.get('/api/onchain/token-price/:mintAddress', async (req: Request, res: Response) => {
  try {
    const { mintAddress } = req.params;

    const { BondingCurveFetcher } = require('../pumpfun/pumpfun-idl-client');
    const mint = new PublicKey(mintAddress);
    const bondingCurve = await BondingCurveFetcher.fetch(connection, mint, true);

    if (!bondingCurve) {
      return res.status(404).json({
        success: false,
        error: 'Token not found or not on pump.fun'
      });
    }

    // Calculate price per token (in lamports)
    const pricePerToken = bondingCurve.virtual_sol_reserves * 1000000n / bondingCurve.virtual_token_reserves;

    res.json({
      success: true,
      mint_address: mintAddress,
      price_sol: Number(pricePerToken) / 1e9,
      virtual_sol_reserves: Number(bondingCurve.virtual_sol_reserves) / 1e9,
      virtual_token_reserves: Number(bondingCurve.virtual_token_reserves) / 1e6,
      creator: bondingCurve.creator.toBase58(),
      complete: bondingCurve.complete,
      timestamp: new Date().toISOString()
    });
  } catch (error: any) {
    logger.error(`Token price error: ${error.message}`);
    res.status(500).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Create token with creator buy endpoint
app.post('/api/onchain/create-token-with-buy', async (req: Request, res: Response) => {
    try {
        logger.info('Received create token with buy request');
        
        const { createTokenWithCreatorBuy } = require('./tokenCreation');
        const result = await createTokenWithCreatorBuy(connection, req.body);
        
        res.json({
            success: result.success,
            signature: result.signature,
            mint_address: result.mint_address,
            buy_signature: result.buy_signature,
            error: result.error,
            timestamp: new Date().toISOString()
        });
        
        logger.info(`Create token with buy completed: ${result.success ? 'success' : 'failed'}`);
        
    } catch (error: any) {
        logger.error(`Create token with buy error: ${error.message}`, { stack: error.stack });
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Start server
app.listen(PORT, () => {
  logger.info(`🚀 On-chain service running on port ${PORT}`);
  logger.info(`📡 RPC: ${RPC_URL}`);
  logger.info(`🔐 API key protection: ${!!process.env.ONCHAIN_API_KEY}`);
});


