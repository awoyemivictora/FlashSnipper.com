// // on-chain/sniper-engine.ts
// import {
//     Connection,
//     Keypair,
//     PublicKey,
//     VersionedTransaction,
//     TransactionMessage,
//     ComputeBudgetProgram,
//     SystemProgram,
//     LAMPORTS_PER_SOL,
//     Commitment,
//     TransactionInstruction
// } from "@solana/web3.js";
// import {
//     getOrCreateAssociatedTokenAccount,
//     createAssociatedTokenAccountInstruction,
//     TOKEN_PROGRAM_ID,
//     ASSOCIATED_TOKEN_PROGRAM_ID,
//     getAssociatedTokenAddressSync
// } from '@solana/spl-token';
// import axios from 'axios';
// import bs58 from 'bs58';
// import WebSocket from 'ws';

// // Import our IDL-based client
// import {
//     PUMP_FUN_PROGRAM_ID,
//     PumpFunInstructionBuilder,
//     BondingCurveMath,
//     BondingCurveFetcher,
//     BondingCurve,
//     PumpFunPda
// } from './pumpfun-idl-client';
// import { jitoBundleSender, JitoBundleSender } from "./jito-integration";

// // ============================================
// // CONFIGURATION
// // ============================================
// const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
// const RPC_URL = process.env.RPC_URL || 'https://api.mainnet-beta.solana.com';
// const ONCHAIN_API_KEY = process.env.ONCHAIN_API_KEY;
// const JITO_TIP_AMOUNT = 100000; // 0.0001 SOL

// // Ultra-fast RPC connection
// const connection = new Connection(RPC_URL, {
//     commitment: 'confirmed' as Commitment,
//     wsEndpoint: RPC_URL.replace('https://', 'wss://'),
//     confirmTransactionInitialTimeout: 10000,
//     disableRetryOnRateLimit: false,
//     httpHeaders: {
//         'Content-Type': 'application/json'
//     }
// });

// // ============================================
// // INTERFACES
// // ============================================
// interface UserConfig {
//     wallet_address: string;
//     buy_amount_sol: number;
//     buy_slippage_bps: number;
//     is_premium: boolean;
//     encrypted_private_key: string;
//     sol_balance: number;
//     partial_sell_pct: number;
//     trailing_sl_pct: number;
//     rug_liquidity_drop_pct: number;
//     bot_check_interval_seconds: number;
//     filter_socials_added?: boolean;
//     filter_liquidity_burnt?: boolean;
//     filter_check_pool_size_min_sol?: number;
//     filter_top_holders_max_pct?: number;
//     filter_safety_check_period_seconds?: number;
//     has_ws_connection: boolean;
//     has_bot_state: boolean;
//     has_active_task: boolean;
// }

// interface TokenData {
//     Name: string;
//     Symbol: string;
//     Mint: string;
//     Bonding_Curve: string;
//     Creator: string;
//     signature: string;
//     timestamp: string;
//     VirtualTokenReserves: string;
//     VirtualSolReserves: string;
//     RealTokenReserves: string;
//     TokenTotalSupply: string;
// }

// interface SnipeResult {
//     success: boolean;
//     token: string;
//     users: string[];
//     bundleId?: string;
//     error?: string;
//     timestamp: number;
// }

// interface GlobalData {
//     fee_basis_points: bigint;
//     creator_fee_basis_points: bigint;
//     fee_recipient: PublicKey;
//     initialized: boolean;
// }

// // ============================================
// // PRODUCTION SNIPER ENGINE
// // ============================================
// export class ProductionSniperEngine {
//     private activeUsers: Map<string, UserConfig> = new Map();
//     private userKeypairs: Map<string, Keypair> = new Map();
//     private lastFetchTime = 0;
//     private readonly USER_REFRESH_INTERVAL = 2000;
    
//     private recentSnipedTokens = new Map<string, number>();
//     private readonly RECENT_SNIPE_TTL = 30000;
    
//     private stats = {
//         totalSnipes: 0,
//         successfulSnipes: 0,
//         failedSnipes: 0,
//         totalUsersSnipped: 0,
//         totalVolume: 0,
//         lastSnipeTime: 0
//     };

//     private activationWebSocket: WebSocket | null = null;
//     private readonly ACTIVATION_WS_URL = process.env.BACKEND_WS_URL || 'ws://localhost:8000';
    
//     private globalData: GlobalData = {
//         fee_basis_points: 100n,    // 1% protocol fee
//         creator_fee_basis_points: 50n, // 0.5% creator fee
//         fee_recipient: new PublicKey('CebN5WGQ4jvTDQU9EPre3g1RrnGMx3agP1JyiH4g58M'),
//         initialized: true
//     };

//     // Performance tracking
//     private performanceMetrics = {
//         detectionToSnipe: [] as number[],
//         transactionBuildTime: [] as number[],
//         jitoLatency: [] as number[]
//     };

//     constructor() {
//         this.initialize();
//     }

//     private jitoSenderInitialized = false;

//     private buySuccessTracker = new Map<string, {
//         user: string;
//         mint: string;
//         amountSol: number;
//         timestamp: number;
//     }>();

//     private async initialize(): Promise<void> {
//         console.log('🚀 ULTRA-FAST PUMP.FUN SNIPER ENGINE v2.0');

//         // Initialize Jito
//         try {
//             await jitoBundleSender.initialize();
//             this.jitoSenderInitialized = true;
//             console.log('✅ Jito Bundle Sender initialized');
//         } catch (error) {
//             console.error('⚠️ Jito initilization failed, will use RPC fallback:', error);
//         }

//         // Start services
//         this.startUserRefreshLoop();
//         this.connectToActivationWebSocket();
//         this.startHealthMonitor();
//         this.cleanupRecentSnipes();

//         console.log('✅ Engine Initialized - READY FOR PRODUCTION');
//     }

//     // ============================================
//     // MAIN SNIPING LOGIC
//     // ============================================
    
//     public async immediateTokenSnipping(tokenData: TokenData): Promise<SnipeResult> {
//         const startTime = performance.now();
//         console.log(`\n⚡⚡⚡ IMMEDIATE SNIPE TRIGGERED: ${tokenData.Name} (${tokenData.Symbol})`);

//         // Ultra-fast duplicate check
//         if (this.recentSnipedTokens.has(tokenData.Mint)) {
//             const lastSnipeTime = this.recentSnipedTokens.get(tokenData.Mint)!;
//             if (Date.now() - lastSnipeTime < this.RECENT_SNIPE_TTL) {
//                 console.log(`⏭️ Skipping - sniped ${Math.floor((Date.now() - lastSnipeTime)/1000)}s ago`);
//                 return {
//                     success: false,
//                     token: tokenData.Mint,
//                     users: [],
//                     error: 'Already sniped recently',
//                     timestamp: Date.now()
//                 };
//             }
//         }

//         try {
//             // Mark as sniping immediately
//             this.recentSnipedTokens.set(tokenData.Mint, Date.now());

//             // 1. Get eligible users (parallel)
//             const eligibleUsers = await this.getEligibleUsersForToken(tokenData);
//             if (eligibleUsers.length === 0) {
//                 throw new Error('No eligible users for snipe');
//             }

//             console.log(`👥 Sniping for ${eligibleUsers.length} users`);

//             // 2. Prepare and execute bundle
//             const bundleResult = await this.executeUltraFastBundle(eligibleUsers, tokenData);
            
//             if (!bundleResult.success) {
//                 throw new Error('Bundle execution failed');
//             }

//             if (bundleResult.success) {
//                 // Track successful buys for later selling
//                 for (const user of eligibleUsers) {
//                     this.buySuccessTracker.set(`${user.wallet_address}_${tokenData.Mint}`, {
//                         user: user.wallet_address,
//                         mint: tokenData.Mint,
//                         amountSol: user.buy_amount_sol,
//                         timestamp: Date.now()
//                     });
//                 }

//                 // Start monitoring for sell opportunities
//                 this.monitorForSellOpportunities(tokenData.Mint).catch(console.error);
//             }

//             // 3. Update stats
//             this.stats.totalSnipes++;
//             this.stats.successfulSnipes++;
//             this.stats.totalUsersSnipped += eligibleUsers.length;
//             this.stats.totalVolume += eligibleUsers.reduce((sum, user) => sum + user.buy_amount_sol, 0);
//             this.stats.lastSnipeTime = Date.now();

//             // 4. Async logging
//             this.logSnipeToBackend(eligibleUsers, tokenData, bundleResult).catch(console.error);

//             const executionTime = performance.now() - startTime;
//             this.performanceMetrics.detectionToSnipe.push(executionTime);
            
//             console.log(`✅✅✅ SNIPE COMPLETED in ${executionTime.toFixed(0)}ms`);
//             console.log(`📊 Avg execution: ${this.getAverage(this.performanceMetrics.detectionToSnipe).toFixed(0)}ms`);

//             return {
//                 success: true,
//                 token: tokenData.Mint,
//                 users: eligibleUsers.map(u => u.wallet_address),
//                 bundleId: bundleResult.bundleId,
//                 timestamp: Date.now()
//             };

//         } catch (error: any) {
//             console.error(`❌ SNIPE FAILED:`, error.message);
//             this.stats.failedSnipes++;
//             this.recentSnipedTokens.delete(tokenData.Mint);

//             return {
//                 success: false,
//                 token: tokenData.Mint,
//                 users: [],
//                 error: error.message,
//                 timestamp: Date.now()
//             };
//         }
//     }

//     // ============================================
//     // BUNDLE EXECUTION (ULTRA-FAST)
//     // ============================================
    
//     private async executeUltraFastBundle(
//         users: UserConfig[],
//         tokenData: TokenData
//     ): Promise<{ bundleId: string; success: boolean }> {
//         const startTime = performance.now();
//         console.log(`📦 Building bundle for ${users.length} users...`);

//         // Pre-fetch bonding curve data once
//         const mint = new PublicKey(tokenData.Mint);
//         const bondingCurve = await BondingCurveFetcher.fetch(connection, mint, false);
        
//         if (!bondingCurve) {
//             throw new Error('Failed to fetch bonding curve');
//         }
        
//         if (BondingCurveFetcher.isComplete(bondingCurve)) {
//             throw new Error('Bonding curve already migrated to Raydium');
//         }

//         const creator = BondingCurveFetcher.getCreator(bondingCurve);

//         // Prepare all transactions in parallel
//         const transactionPromises = users.map(async (user) => {
//             try {
//                 const keypair = this.userKeypairs.get(user.wallet_address);
//                 if (!keypair) return [];

//                 return await this.prepareUserTransactions(
//                     keypair,
//                     user,
//                     mint,
//                     creator,
//                     bondingCurve
//                 );
//             } catch (error) {
//                 console.error(`Transaction prep failed:`, error);
//                 return [];
//             }
//         });

//         const results = await Promise.allSettled(transactionPromises);
//         const allTransactions: VersionedTransaction[] = [];

//         results.forEach((result) => {
//             if (result.status === 'fulfilled' && result.value) {
//                 allTransactions.push(...result.value);
//             }
//         });

//         if (allTransactions.length === 0) {
//             throw new Error('No transactions prepared');
//         }

//         const buildTime = performance.now() - startTime;
//         this.performanceMetrics.transactionBuildTime.push(buildTime);
//         console.log(`✅ Built ${allTransactions.length} transactions in ${buildTime.toFixed(0)}ms`);

//         // Execute with Jito
//         try {
//             return await this.sendToJito(allTransactions);
//         } catch (jitoError) {
//             console.error('Jito failed, falling back to RPC:', jitoError);
//             return await this.fallbackRpcExecution(allTransactions);
//         }
//     }

//     // private async prepareUserTransactions(
//     //     keypair: Keypair,
//     //     user: UserConfig,
//     //     mint: PublicKey,
//     //     creator: PublicKey,
//     //     bondingCurve: BondingCurve
//     // ): Promise<VersionedTransaction[]> {
//     //     const transactions: VersionedTransaction[] = [];
//     //     const userPubkey = keypair.publicKey;
        
//     //     // Get user ATA
//     //     const userAta = getAssociatedTokenAddressSync(mint, userPubkey);
        
//     //     // 1. BUY transaction
//     //     const buyTx = await this.createBuyTransaction(
//     //         keypair,
//     //         mint,
//     //         userAta,
//     //         creator,
//     //         user.buy_amount_sol,
//     //         user.buy_slippage_bps,
//     //         bondingCurve
//     //     );
//     //     if (buyTx) transactions.push(buyTx);

//     //     // Calculate expected tokens
//     //     const solInputLamports = BigInt(Math.floor(user.buy_amount_sol * LAMPORTS_PER_SOL));
//     //     const expectedTokens = BondingCurveMath.calculateTokensForSol(
//     //         bondingCurve.virtual_sol_reserves,
//     //         bondingCurve.virtual_token_reserves,
//     //         solInputLamports
//     //     );

//     //     if (expectedTokens > 0n) {
//     //         // Apply fees to get net tokens
//     //         const { netAmount: netTokens } = BondingCurveMath.applyFees(
//     //             expectedTokens,
//     //             this.globalData.fee_basis_points,
//     //             this.globalData.creator_fee_basis_points
//     //         );

//     //         // 2. SELL 50%
//     //         const sell50Amount = netTokens / 2n;
//     //         const sell50Tx = await this.createSellTransaction(
//     //             keypair,
//     //             mint,
//     //             userAta,
//     //             creator,
//     //             sell50Amount,
//     //             user.buy_slippage_bps * 2,
//     //             bondingCurve
//     //         );
//     //         if (sell50Tx) transactions.push(sell50Tx);

//     //         // 3. SELL remaining
//     //         const sellRemainingTx = await this.createSellTransaction(
//     //             keypair,
//     //             mint,
//     //             userAta,
//     //             creator,
//     //             sell50Amount,
//     //             user.buy_slippage_bps * 2,
//     //             bondingCurve
//     //         );
//     //         if (sellRemainingTx) transactions.push(sellRemainingTx);
//     //     }

//     //     return transactions;
//     // }

//     // In prepareUserTransactions, ONLY DO BUY for now:
    
//     private async prepareUserTransactions(
//         keypair: Keypair,
//         user: UserConfig,
//         mint: PublicKey,
//         creator: PublicKey,
//         bondingCurve: BondingCurve
//     ): Promise<VersionedTransaction[]> {
//         const transactions: VersionedTransaction[] = [];
//         const userPubkey = keypair.publicKey;
        
//         // Get user ATA
//         const userAta = getAssociatedTokenAddressSync(mint, userPubkey);
        
//         try {
//             // 1. BUY transaction ONLY - no sells
//             const buyTx = await this.createBuyTransaction(
//                 keypair,
//                 mint,
//                 userAta,
//                 creator,
//                 user.buy_amount_sol,
//                 user.buy_slippage_bps,
//                 bondingCurve
//             );
            
//             if (buyTx) {
//                 transactions.push(buyTx);
//                 console.log(`✅ Prepared BUY for ${userPubkey.toBase58().slice(0, 8)}`);
                
//                 // IMPORTANT: Do NOT add sell transactions here
//                 // They fail because tokens haven't been bought yet
//                 // You need a separate monitoring system for selling
//             }

//         } catch (error) {
//             console.error(`Failed to prepare transactions for ${userPubkey.toBase58().slice(0, 8)}:`, error);
//         }

//         return transactions;
//     }

//     // ============================================
//     // TRANSACTION BUILDERS (IDL-EXACT)
//     // ============================================
    
//     private async createBuyTransaction(
//         keypair: Keypair,
//         mint: PublicKey,
//         userAta: PublicKey,
//         creator: PublicKey,
//         amountSol: number,
//         slippageBps: number,
//         bondingCurve: BondingCurve
//     ): Promise<VersionedTransaction | null> {
//         const startTime = performance.now();
        
//         try {
//             // Calculate amounts
//             const spendableSolIn = BigInt(Math.floor(amountSol * LAMPORTS_PER_SOL));
            
//             // Calculate expected tokens (after fees) - USE CACHED DATA
//             const { netAmount: expectedTokens } = BondingCurveMath.applyFees(
//                 BondingCurveMath.calculateTokensForSol(
//                     bondingCurve.virtual_sol_reserves,
//                     bondingCurve.virtual_token_reserves,
//                     spendableSolIn
//                 ),
//                 this.globalData.fee_basis_points,
//                 this.globalData.creator_fee_basis_points
//             );

//             if (expectedTokens <= 0n) {
//                 console.error(`❌ Invalid token amount: ${expectedTokens}`);
//                 return null;
//             }

//             // Apply slippage
//             const minTokensOut = BondingCurveMath.applySlippage(expectedTokens, slippageBps);

//             // Get blockhash in parallel while building instruction
//             const [blockhash] = await Promise.all([
//                 connection.getLatestBlockhash('confirmed')
//             ]);

//             // Build instruction (non-async)
//             const buyInstruction = PumpFunInstructionBuilder.buildBuyExactSolIn(
//                 keypair.publicKey,
//                 mint,
//                 userAta,
//                 creator,
//                 spendableSolIn,
//                 minTokensOut,
//                 true
//             );

//             // Add priority fee
//             const priorityInstruction = ComputeBudgetProgram.setComputeUnitPrice({
//                 microLamports: 500000 // Increase for faster execution
//             });

//             // Check ATA in parallel
//             const ataCheckPromise = connection.getAccountInfo(userAta, 'confirmed');
//             const instructions = [priorityInstruction, buyInstruction];

//             // Add ATA creation only if needed
//             try {
//                 const ataInfo = await ataCheckPromise;
//                 if (!ataInfo) {
//                     instructions.splice(1, 0, createAssociatedTokenAccountInstruction(
//                         keypair.publicKey,
//                         userAta,
//                         keypair.publicKey,
//                         mint
//                     ));
//                 }
//             } catch (error) {
//                 console.error('ATA check failed, continuing without:', error);
//             }

//             // Build transaction
//             const messageV0 = new TransactionMessage({
//                 payerKey: keypair.publicKey,
//                 recentBlockhash: blockhash.blockhash,
//                 instructions
//             }).compileToV0Message();

//             const transaction = new VersionedTransaction(messageV0);
//             transaction.sign([keypair]);

//             const buildTime = performance.now() - startTime;
//             console.log(`⚡ Buy TX built in ${buildTime.toFixed(0)}ms`);

//             return transaction;
//         } catch (error) {
//             console.error('Failed to create buy transaction:', error);
//             return null;
//         }
//     }

//     private async createSellTransaction(
//         keypair: Keypair,
//         mint: PublicKey,
//         userAta: PublicKey,
//         creator: PublicKey,
//         tokenAmount: bigint,
//         slippageBps: number,
//         bondingCurve: BondingCurve
//     ): Promise<VersionedTransaction> {
//         // Calculate expected SOL output
//         const expectedSol = BondingCurveMath.calculateSolForTokens(
//             bondingCurve.virtual_sol_reserves,
//             bondingCurve.virtual_token_reserves,
//             tokenAmount
//         );

//         // Apply fees
//         const { netAmount: netSol } = BondingCurveMath.applyFees(
//             expectedSol,
//             this.globalData.fee_basis_points,
//             this.globalData.creator_fee_basis_points
//         );

//         // Apply slippage
//         const minSolOutput = BondingCurveMath.applySlippage(netSol, slippageBps);

//         // Build instruction
//         const sellInstruction = PumpFunInstructionBuilder.buildSell(
//             keypair.publicKey,
//             mint,
//             userAta,
//             creator,
//             tokenAmount,
//             minSolOutput
//         );

//         // Add priority fee
//         const priorityInstruction = ComputeBudgetProgram.setComputeUnitPrice({
//             microLamports: 250000
//         });

//         // Build transaction
//         const { blockhash } = await connection.getLatestBlockhash('confirmed');
//         const instructions = [priorityInstruction, sellInstruction];

//         const messageV0 = new TransactionMessage({
//             payerKey: keypair.publicKey,
//             recentBlockhash: blockhash,
//             instructions
//         }).compileToV0Message();

//         const transaction = new VersionedTransaction(messageV0);
//         transaction.sign([keypair]);

//         return transaction;
//     }

//     private async monitorForSellOpportunities(mint: string): Promise<void> {
//         // Check after 5 seconds if tokens are bought
//         setTimeout(async () => {
//             const mintPubkey = new PublicKey(mint);

//             // Get all users who bought this token
//             const buys = Array.from(this.buySuccessTracker.entries())
//                 .filter(([key]) => key.endsWith(`_${mint}`));

//                 for (const [key, buyInfo] of buys) {
//                     try {
//                         // Check if user actually received tokens
//                         const userPubkey = new PublicKey(buyInfo.user);
//                         const ata = getAssociatedTokenAddressSync(mintPubkey, userPubkey);
//                         const tokenAccount = await connection.getTokenAccountBalance(ata, 'confirmed');

//                         if (tokenAccount.value.uiAmount > 0) {
//                             console.log(`💰 User ${buyInfo.user.slice(0, 8)} got ${tokenAccount.value.uiAmount} tokens, ready to sell`);
//                             // Schedule sell transaction here:

//                         }
//                     } catch (error) {
//                         console.error('Failed to check token balance:', error);
//                     }
//                 }
//         }, 5000);
//     }

//     private async createAtaIfNeeded(
//         user: PublicKey,
//         mint: PublicKey,
//         ata: PublicKey
//     ): Promise<TransactionInstruction | null> {
//         try {
//             const ataInfo = await connection.getAccountInfo(ata);
//             if (ataInfo) return null;

//             return createAssociatedTokenAccountInstruction(
//                 user,
//                 ata,
//                 user,
//                 mint
//             );
//         } catch {
//             return null;
//         }
//     }

//     // ============================================
//     // JITO BUNDLE EXECUTION USING JITO SDK
//     // ============================================
    
//     private async sendToJito(transactions: VersionedTransaction[]): Promise<{ bundleId: string; success: boolean }> {
//         const startTime = performance.now();
        
//         try {
//             const result = await jitoBundleSender.sendBundle(transactions, connection);

//             if (!result.success) {
//                 throw new Error(result.error || 'Jito bundle submission failed');
//             }

//             console.log(`📤 Jito bundle sent: ${result.bundleId}`);
//             return { bundleId: result.bundleId, success: true };

//         } catch (error: any) {
//             console.error('Jito error:', error.message);
//             throw error;
//         }
//     }

//     private async fallbackRpcExecution(transactions: VersionedTransaction[]): Promise<{ bundleId: string; success: boolean }> {
//         console.log('🔄 Falling back to RPC execution...');
        
//         const sendPromises = transactions.map(tx => 
//             connection.sendTransaction(tx, { skipPreflight: true, maxRetries: 0 })
//                 .catch(e => null)
//         );

//         await Promise.all(sendPromises);
//         return { bundleId: 'rpc_fallback', success: true };
//     }

//     // ============================================
//     // USER MANAGEMENT
//     // ============================================
    
//     private async getEligibleUsersForToken(tokenData: TokenData): Promise<UserConfig[]> {
//         const eligibleUsers: UserConfig[] = [];
        
//         for (const [wallet, user] of this.activeUsers) {
//             try {
//                 const keypair = this.userKeypairs.get(wallet);
//                 if (!keypair) continue;

//                 // Check balance
//                 const balance = await this.getUserBalance(wallet);
//                 const required = user.buy_amount_sol * 3 + 0.1; // Account for 3 txs + buffer
                
//                 if (balance < required) continue;

//                 // Check premium filters
//                 if (user.is_premium) {
//                     const passes = await this.applyPremiumFilters(user, tokenData);
//                     if (!passes) continue;
//                 }

//                 // Check bonding curve state
//                 const mint = new PublicKey(tokenData.Mint);
//                 const curve = await BondingCurveFetcher.fetch(connection, mint, true);
//                 if (!curve || BondingCurveFetcher.isComplete(curve)) continue;

//                 eligibleUsers.push(user);

//             } catch (error) {
//                 console.error(`User eligibility check failed:`, error);
//             }
//         }

//         return eligibleUsers;
//     }

//     private async applyPremiumFilters(user: UserConfig, tokenData: TokenData): Promise<boolean> {
//         // Safety period
//         if (user.filter_safety_check_period_seconds) {
//             const tokenAge = Date.now() - new Date(tokenData.timestamp).getTime();
//             if (tokenAge < user.filter_safety_check_period_seconds * 1000) {
//                 return false;
//             }
//         }

//         // Socials check (simplified)
//         if (user.filter_socials_added) {
//             // In production, check token metadata for socials
//         }

//         return true;
//     }

//     private async getUserBalance(wallet: string): Promise<number> {
//         try {
//             const balance = await connection.getBalance(new PublicKey(wallet), 'confirmed');
//             return balance / LAMPORTS_PER_SOL;
//         } catch {
//             return 0;
//         }
//     }

//     // ============================================
//     // USER REFRESH LOOP
//     // ============================================
    
//     private async startUserRefreshLoop(): Promise<void> {
//         while (true) {
//             try {
//                 await this.refreshActiveUsers();
//                 await this.refreshKeypairs();
//                 await new Promise(resolve => setTimeout(resolve, this.USER_REFRESH_INTERVAL));
//             } catch (error) {
//                 console.error('User refresh error:', error);
//                 await new Promise(resolve => setTimeout(resolve, 5000));
//             }
//         }
//     }

//     private async refreshActiveUsers(): Promise<void> {
//         try {
//             const response = await axios.get(`${BACKEND_URL}/user/active-users`, {
//                 params: { api_key: ONCHAIN_API_KEY },
//                 headers: { 'X-Request-Type': 'sniper-engine' },
//                 timeout: 1500
//             });

//             const newUsers = new Map<string, UserConfig>();
//             if (response.data?.users) {
//                 for (const user of response.data.users) {
//                     if (this.isUserEligibleForSniping(user)) {
//                         newUsers.set(user.wallet_address, user);
//                     }
//                 }
//             }

//             this.activeUsers = newUsers;
//             this.lastFetchTime = Date.now();

//             if (newUsers.size > 0) {
//                 console.log(`👤 Active users: ${newUsers.size}`);
//             }

//         } catch (error: any) {
//             console.error('User refresh failed:', error.message);
//         }
//     }

//     private isUserEligibleForSniping(user: UserConfig): boolean {
//         if (!user.encrypted_private_key || user.encrypted_private_key.length < 20) {
//             return false;
//         }

//         const minBalance = (user.buy_amount_sol || 0.1) + 0.05;
//         if (user.sol_balance < minBalance) {
//             return false;
//         }

//         return true;
//     }

//     private async refreshKeypairs(): Promise<void> {
//         const startTime = Date.now();
//         let decrypted = 0;

//         for (const [wallet, user] of this.activeUsers) {
//             if (this.userKeypairs.has(wallet)) continue;

//             try {
//                 const keypair = await this.decryptUserKeypair(user);
//                 if (keypair) {
//                     this.userKeypairs.set(wallet, keypair);
//                     decrypted++;
//                 }
//             } catch (error) {
//                 console.error(`Failed to decrypt keypair for ${wallet.slice(0, 8)}`);
//                 this.activeUsers.delete(wallet);
//             }
//         }

//         if (decrypted > 0) {
//             console.log(`🔑 Decrypted ${decrypted} keypairs in ${Date.now() - startTime}ms`);
//         }
//     }

//     private async decryptUserKeypair(user: UserConfig): Promise<Keypair | null> {
//         try {
//             const decoded = bs58.decode(user.encrypted_private_key);
//             if (decoded.length === 64) {
//                 return Keypair.fromSecretKey(decoded);
//             }
//         } catch (error) {
//             console.error('Keypair decryption error:', error);
//         }
//         return null;
//     }

//     // ============================================
//     // WEB SOCKET & HEALTH
//     // ============================================
    
//     private async connectToActivationWebSocket(): Promise<void> {
//         try {
//             this.activationWebSocket = new WebSocket(`${this.ACTIVATION_WS_URL}/ws/sniper-activations`);
            
//             this.activationWebSocket.on('open', () => {
//                 console.log('📡 Connected to activation WebSocket');
//             });
            
//             this.activationWebSocket.on('message', async (data: WebSocket.Data) => {
//                 try {
//                     const message = typeof data === 'string' ? data : data.toString();
//                     const parsed = JSON.parse(message);
                    
//                     if (parsed.type === 'user_activated') {
//                         await this.refreshActiveUsers();
//                     }
//                 } catch (error) {
//                     console.error('WebSocket message error:', error);
//                 }
//             });
            
//             this.activationWebSocket.on('error', (error: Error) => {
//                 console.error('WebSocket error:', error);
//             });
            
//             this.activationWebSocket.on('close', () => {
//                 console.log('WebSocket closed, reconnecting...');
//                 setTimeout(() => this.connectToActivationWebSocket(), 3000);
//             });
            
//         } catch (error) {
//             console.error('WebSocket connection failed:', error);
//             setTimeout(() => this.connectToActivationWebSocket(), 3000);
//         }
//     }

//     private startHealthMonitor(): void {
//         setInterval(() => {
//             const health = this.getHealthStatus();
//             if (health.healthScore < 85) {
//                 console.warn(`⚠️ Health score low: ${health.healthScore}%`);
//             }
//         }, 30000);
//     }

//     private cleanupRecentSnipes(): void {
//         setInterval(() => {
//             const now = Date.now();
//             for (const [mint, timestamp] of this.recentSnipedTokens.entries()) {
//                 if (now - timestamp > this.RECENT_SNIPE_TTL) {
//                     this.recentSnipedTokens.delete(mint);
//                 }
//             }
//         }, 30000);
//     }

//     // ============================================
//     // UTILITIES
//     // ============================================
    
//     private async logSnipeToBackend(
//         users: UserConfig[],
//         tokenData: TokenData,
//         bundleResult: { bundleId: string; success: boolean }
//     ): Promise<void> {
//         try {
//             await axios.post(`${BACKEND_URL}/trade/immediate-snipe`, {
//                 trades: users.map(user => ({
//                     user_wallet_address: user.wallet_address,
//                     mint_address: tokenData.Mint,
//                     token_symbol: tokenData.Symbol,
//                     token_name: tokenData.Name,
//                     trade_type: 'immediate_snipe',
//                     amount_sol: user.buy_amount_sol,
//                     bundle_id: bundleResult.bundleId,
//                     timestamp: new Date().toISOString()
//                 })),
//                 token_data: tokenData,
//                 bundle_id: bundleResult.bundleId
//             }, {
//                 headers: { 'X-API-Key': ONCHAIN_API_KEY },
//                 timeout: 2000
//             });
//         } catch (error) {
//             console.error('Failed to log snipe:', error);
//         }
//     }

//     private getAverage(numbers: number[]): number {
//         if (numbers.length === 0) return 0;
//         const sum = numbers.reduce((a, b) => a + b, 0);
//         return sum / numbers.length;
//     }

//     public getHealthStatus(): {
//         healthScore: number;
//         activeUsers: number;
//         cachedKeypairs: number;
//         stats: typeof this.stats;
//         performance: typeof this.performanceMetrics;
//     } {
//         const healthScore = this.calculateHealthScore();
        
//         return {
//             healthScore,
//             activeUsers: this.activeUsers.size,
//             cachedKeypairs: this.userKeypairs.size,
//             stats: { ...this.stats },
//             performance: { ...this.performanceMetrics }
//         };
//     }

//     private calculateHealthScore(): number {
//         let score = 100;
        
//         if (this.activeUsers.size === 0) score -= 40;
//         if (this.userKeypairs.size === 0) score -= 40;
        
//         const successRate = this.stats.totalSnipes > 0 
//             ? (this.stats.successfulSnipes / this.stats.totalSnipes) * 100 
//             : 100;
        
//         if (successRate < 60) score -= 30;
        
//         const avgSnipeTime = this.getAverage(this.performanceMetrics.detectionToSnipe);
//         if (avgSnipeTime > 200) score -= 20;
//         if (avgSnipeTime < 100) score += 10;
        
//         return Math.max(0, Math.min(100, score));
//     }

//     public async emergencyStop(): Promise<void> {
//         console.log('🛑 EMERGENCY STOP INITIATED');
        
//         this.activeUsers.clear();
//         this.userKeypairs.clear();
//         this.recentSnipedTokens.clear();
        
//         try {
//             await axios.post(`${BACKEND_URL}/sniper/emergency-stop`, {}, {
//                 headers: { 'X-API-Key': ONCHAIN_API_KEY },
//                 timeout: 2000
//             });
//         } catch (error) {
//             console.error('Emergency stop notification failed:', error);
//         }
        
//         console.log('✅ Emergency stop complete');
//     }
// }

// // ============================================
// // EXPORTS
// // ============================================
// export const sniperEngine = new ProductionSniperEngine();
// export const immediateTokenSniping = sniperEngine.immediateTokenSnipping.bind(sniperEngine);









// on-chain/sniper-engine.ts
import {
    Connection,
    Keypair,
    PublicKey,
    VersionedTransaction,
    TransactionMessage,
    ComputeBudgetProgram,
    SystemProgram,
    LAMPORTS_PER_SOL,
    Commitment,
    TransactionInstruction,
    Transaction
} from "@solana/web3.js";
import {
    getOrCreateAssociatedTokenAccount,
    createAssociatedTokenAccountInstruction,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
    getAssociatedTokenAddressSync
} from '@solana/spl-token';
import axios from 'axios';
import bs58 from 'bs58';
import WebSocket from 'ws';

// Import our IDL-based client
import {
    PUMP_FUN_PROGRAM_ID,
    PumpFunInstructionBuilder,
    BondingCurveMath,
    BondingCurveFetcher,
    BondingCurve,
    PumpFunPda
} from './pumpfun-idl-client';
import { jitoBundleSender, JitoBundleSender } from "./jito-integration";

// ============================================
// CONFIGURATION
// ============================================
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const RPC_URL = process.env.RPC_URL || 'https://api.mainnet-beta.solana.com';
const ONCHAIN_API_KEY = process.env.ONCHAIN_API_KEY;

// Ultra-fast RPC connection with multiple endpoints for failover
const RPC_ENDPOINTS = [
    'https://api.mainnet-beta.solana.com',
    'https://solana-mainnet.g.alchemy.com/v2/demo',
    'https://rpc.ankr.com/solana',
    'https://solana-api.projectserum.com'
];

class MultiRpcConnection {
    private connections: Connection[] = [];
    private currentIndex = 0;
    
    constructor(endpoints: string[]) {
        this.connections = endpoints.map(endpoint => new Connection(endpoint, {
            commitment: 'confirmed' as Commitment,
            wsEndpoint: endpoint.replace('https://', 'wss://'),
            confirmTransactionInitialTimeout: 8000,
            disableRetryOnRateLimit: false,
            httpHeaders: {
                'Content-Type': 'application/json'
            }
        }));
    }
    
    getCurrent(): Connection {
        return this.connections[this.currentIndex];
    }
    
    rotate(): void {
        this.currentIndex = (this.currentIndex + 1) % this.connections.length;
        console.log(`🔄 Rotated to RPC endpoint ${this.currentIndex + 1}/${this.connections.length}`);
    }
    
    async getBest(): Promise<Connection> {
        const promises = this.connections.map(async (conn, index) => {
            try {
                const start = performance.now();
                await conn.getSlot({ commitment: 'processed' });
                const latency = performance.now() - start;
                return { conn, latency, index };
            } catch {
                return null;
            }
        });
        
        const results = await Promise.all(promises);
        const valid = results.filter(r => r !== null) as Array<{conn: Connection, latency: number, index: number}>;
        
        if (valid.length === 0) {
            return this.connections[0];
        }
        
        // Pick the fastest
        valid.sort((a, b) => a.latency - b.latency);
        this.currentIndex = valid[0].index;
        return valid[0].conn;
    }
}

const rpcManager = new MultiRpcConnection(RPC_ENDPOINTS);
const connection = rpcManager.getCurrent();

// ============================================
// INTERFACES
// ============================================
interface UserConfig {
    wallet_address: string;
    buy_amount_sol: number;
    buy_slippage_bps: number;
    is_premium: boolean;
    encrypted_private_key: string;
    sol_balance: number;
    partial_sell_pct: number;
    trailing_sl_pct: number;
    rug_liquidity_drop_pct: number;
    bot_check_interval_seconds: number;
    filter_socials_added?: boolean;
    filter_liquidity_burnt?: boolean;
    filter_check_pool_size_min_sol?: number;
    filter_top_holders_max_pct?: number;
    filter_safety_check_period_seconds?: number;
    has_ws_connection: boolean;
    has_bot_state: boolean;
    has_active_task: boolean;
}

interface TokenData {
    Name: string;
    Symbol: string;
    Mint: string;
    Bonding_Curve: string;
    Creator: string;
    signature: string;
    timestamp: string;
    VirtualTokenReserves: string;
    VirtualSolReserves: string;
    RealTokenReserves: string;
    TokenTotalSupply: string;
}

interface SnipeResult {
    success: boolean;
    token: string;
    users: string[];
    bundleId?: string;
    error?: string;
    timestamp: number;
    estimatedProfit?: number;
}

interface GlobalData {
    fee_basis_points: bigint;
    creator_fee_basis_points: bigint;
    fee_recipient: PublicKey;
    initialized: boolean;
}

interface ProfitStrategy {
    name: string;
    buyMultiplier: number;
    sellTargets: number[]; // Percentages to sell at
    stopLoss: number; // Percentage to stop loss
    reEntryMultiplier?: number;
    minVolume?: number;
}

// ============================================
// ADVANCED PROFIT STRATEGIES
// ============================================
const PROFIT_STRATEGIES: ProfitStrategy[] = [
    {
        name: "AGGRESSIVE_SNIPE",
        buyMultiplier: 1.0,
        sellTargets: [30, 60, 100], // Sell 33% at 30%, 33% at 60%, 34% at 100%
        stopLoss: -15,
        minVolume: 0.5
    },
    {
        name: "CONSERVATIVE_FLIP",
        buyMultiplier: 0.5,
        sellTargets: [20, 40, 80],
        stopLoss: -10,
        reEntryMultiplier: 1.5
    },
    {
        name: "ULTRA_FAST_SCALP",
        buyMultiplier: 0.3,
        sellTargets: [10, 15, 20], // Quick scalps
        stopLoss: -5
    }
];

// ============================================
// PRODUCTION SNIPER ENGINE
// ============================================
export class ProductionSniperEngine {
    private activeUsers: Map<string, UserConfig> = new Map();
    private userKeypairs: Map<string, Keypair> = new Map();
    private lastFetchTime = 0;
    private readonly USER_REFRESH_INTERVAL = 1500; // Faster refresh
    
    private recentSnipedTokens = new Map<string, number>();
    private readonly RECENT_SNIPE_TTL = 15000; // 15 seconds for same token
    
    private stats = {
        totalSnipes: 0,
        successfulSnipes: 0,
        failedSnipes: 0,
        totalUsersSnipped: 0,
        totalVolume: 0,
        totalProfit: 0,
        lastSnipeTime: 0
    };

    private activationWebSocket: WebSocket | null = null;
    private readonly ACTIVATION_WS_URL = process.env.BACKEND_WS_URL || 'ws://localhost:8000';
    
    private globalData: GlobalData = {
        fee_basis_points: 100n,    // 1% protocol fee
        creator_fee_basis_points: 50n, // 0.5% creator fee
        fee_recipient: new PublicKey('CebN5WGQ4jvTDQU9EPre3g1RrnGMx3agP1JyiH4g58M'),
        initialized: true
    };

    // Performance tracking
    private performanceMetrics = {
        detectionToSnipe: [] as number[],
        transactionBuildTime: [] as number[],
        jitoLatency: [] as number[],
        profitPerSnipe: [] as number[]
    };

    // Token tracking for advanced strategies
    private tokenTrackers = new Map<string, {
        initialPrice: number;
        currentPrice: number;
        volume24h: number;
        holders: number;
        lastUpdate: number;
        buys: number;
        sells: number;
        priceHistory: Array<{price: number, timestamp: number}>;
    }>();

    // Active profit strategies per token/user
    private activeStrategies = new Map<string, {
        user: string;
        token: string;
        strategy: ProfitStrategy;
        buyAmount: number;
        tokensBought: number;
        entryPrice: number;
        sellLevels: Array<{target: number, sold: boolean}>;
        stopLossTriggered: boolean;
        lastCheck: number;
    }>();

    constructor() {
        this.initialize();
    }

    private jitoSenderInitialized = false;
    private strategyRotationIndex = 0;

    private async initialize(): Promise<void> {
        console.log('🚀 ULTRA-FAST PUMP.FUN SNIPER ENGINE');
        await jitoBundleSender.initialize();
        this.startUserRefreshLoop();
        this.connectToActivationWebSocket();
        this.startHealthMonitor();
        this.cleanupRecentSnipes();
        console.log('✅ Engine Initialized - READY FOR PRODUCTION');
    }

    // ============================================
    // MAIN SNIPING LOGIC WITH PROFIT OPTIMIZATION
    // ============================================
    
    public async immediateTokenSnipping(tokenData: TokenData): Promise<SnipeResult> {
        const startTime = performance.now();
        console.log(`\n⚡ IMMEDIATE SNIPE TRIGGERED: ${tokenData.Name} (${tokenData.Symbol})`);

        if (this.recentSnipedTokens.has(tokenData.Mint)) {
            const lastSnipeTime = this.recentSnipedTokens.get(tokenData.Mint)!;
            if (Date.now() - lastSnipeTime < this.RECENT_SNIPE_TTL) {
                console.log(`⏭️ Skipping - sniped ${Math.floor((Date.now() - lastSnipeTime)/1000)}s ago`);
                return {
                    success: false,
                    token: tokenData.Mint,
                    users: [],
                    error: 'Already sniped recently',
                    timestamp: Date.now()
                };
            }
        }

        try {
            this.recentSnipedTokens.set(tokenData.Mint, Date.now());
            const eligibleUsers = await this.getEligibleUsersForToken(tokenData);
            if (eligibleUsers.length === 0) {
                throw new Error('No eligible users for snipe');
            }

            console.log(`👥 Sniping for ${eligibleUsers.length} users`);
            const bundleResult = await this.executeUltraFastBundle(eligibleUsers, tokenData);
            
            if (!bundleResult.success) {
                throw new Error('Bundle execution failed');
            }

            this.stats.totalSnipes++;
            this.stats.successfulSnipes++;
            this.stats.totalUsersSnipped += eligibleUsers.length;
            this.stats.totalVolume += eligibleUsers.reduce((sum, user) => sum + user.buy_amount_sol, 0);
            this.stats.lastSnipeTime = Date.now();

            this.logSnipeToBackend(eligibleUsers, tokenData, bundleResult).catch(console.error);

            const executionTime = performance.now() - startTime;
            this.performanceMetrics.detectionToSnipe.push(executionTime);
            
            console.log(`✅ SNIPE COMPLETED in ${executionTime.toFixed(0)}ms`);

            return {
                success: true,
                token: tokenData.Mint,
                users: eligibleUsers.map(u => u.wallet_address),
                bundleId: bundleResult.bundleId,
                timestamp: Date.now()
            };

        } catch (error: any) {
            console.error(`❌ SNIPE FAILED:`, error.message);
            this.stats.failedSnipes++;
            this.recentSnipedTokens.delete(tokenData.Mint);

            return {
                success: false,
                token: tokenData.Mint,
                users: [],
                error: error.message,
                timestamp: Date.now()
            };
        }
    }

    // ============================================
    // ADVANCED PROFIT BUNDLE EXECUTION
    // ============================================
    
    private async executeUltraFastBundle(
        users: UserConfig[],
        tokenData: TokenData
    ): Promise<{ bundleId: string; success: boolean }> {
        const startTime = performance.now();
        console.log(`📦 Building bundle for ${users.length} users...`);

        const mint = new PublicKey(tokenData.Mint);

        // Try to get bonding curve with retry
        let bondingCurve = null;
        let retries = 0;
        while (retries < 3 && !bondingCurve) {
            try {
                bondingCurve = await BondingCurveFetcher.fetch(connection, mint, false);
            } catch (error) {
                retries++;
                if (retries >= 3) throw new Error('Failed to fetch bonding curve after 3 attempts');
                await new Promise(resolve => setTimeout(resolve, 500 * retries));
            }
        }
        
        if (!bondingCurve) {
            throw new Error('Failed to fetch bonding curve');
        }
        
        if (BondingCurveFetcher.isComplete(bondingCurve)) {
            throw new Error('Bonding curve already migrated to Raydium');
        }

        const creator = BondingCurveFetcher.getCreator(bondingCurve);
        
        // Limit number of users per bundle to avoid rate limits
        const maxUsersPerBundle = 3;
        const limitedUsers = users.slice(0, maxUsersPerBundle);
        
        const transactionPromises = limitedUsers.map(async (user) => {
            try {
                const keypair = this.userKeypairs.get(user.wallet_address);
                if (!keypair) return [];

                return await this.prepareUserTransactions(
                    keypair,
                    user,
                    mint,
                    creator,
                    bondingCurve
                );
            } catch (error) {
                console.error(`Transaction prep failed for ${user.wallet_address.slice(0, 8)}:`, error);
                return [];
            }
        });

        const results = await Promise.allSettled(transactionPromises);
        const allTransactions: VersionedTransaction[] = [];

        results.forEach((result) => {
            if (result.status === 'fulfilled' && result.value) {
                allTransactions.push(...result.value);
            }
        });

        if (allTransactions.length === 0) {
            throw new Error('No transactions prepared');
        }

        const buildTime = performance.now() - startTime;
        this.performanceMetrics.transactionBuildTime.push(buildTime);
        console.log(`✅ Built ${allTransactions.length} transactions in ${buildTime.toFixed(0)}ms`);

        try {
            return await this.sendToJito(allTransactions);
        } catch (jitoError) {
            console.error('Jito failed, falling back to RPC:', jitoError);
            return await this.fallbackRpcExecution(allTransactions);
        }
    }



    // ============================================
    // OPTIMIZED TRANSACTION BUILDERS
    // ============================================
    
    private async prepareUserTransactions(
        keypair: Keypair,
        user: UserConfig,
        mint: PublicKey,
        creator: PublicKey,
        bondingCurve: BondingCurve
    ): Promise<VersionedTransaction[]> {
        const transactions: VersionedTransaction[] = [];
        const userPubkey = keypair.publicKey;
        const userAta = getAssociatedTokenAddressSync(mint, userPubkey);
        
        try {
            const buyTx = await this.createBuyTransaction(
                keypair,
                mint,
                userAta,
                creator,
                user.buy_amount_sol,
                user.buy_slippage_bps,
                bondingCurve
            );
            
            if (buyTx) {
                transactions.push(buyTx);
                console.log(`✅ Prepared BUY for ${userPubkey.toBase58().slice(0, 8)}`);
            }

        } catch (error) {
            console.error(`Failed to prepare transactions for ${userPubkey.toBase58().slice(0, 8)}:`, error);
        }

        return transactions;
    }

    private async createBuyTransaction(
        keypair: Keypair,
        mint: PublicKey,
        userAta: PublicKey,
        creator: PublicKey,
        amountSol: number,
        slippageBps: number,
        bondingCurve: BondingCurve
    ): Promise<VersionedTransaction | null> {
        const startTime = performance.now();
        
        try {
            const spendableSolIn = BigInt(Math.floor(amountSol * LAMPORTS_PER_SOL));
            
            const { netAmount: expectedTokens } = BondingCurveMath.applyFees(
                BondingCurveMath.calculateTokensForSol(
                    bondingCurve.virtual_sol_reserves,
                    bondingCurve.virtual_token_reserves,
                    spendableSolIn
                ),
                this.globalData.fee_basis_points,
                this.globalData.creator_fee_basis_points
            );

            if (expectedTokens <= 0n) {
                console.error(`❌ Invalid token amount: ${expectedTokens}`);
                return null;
            }

            const minTokensOut = BondingCurveMath.applySlippage(expectedTokens, slippageBps);
            const { blockhash } = await connection.getLatestBlockhash('confirmed');
            
            // FIXED: Use correct ATA creation method
            const userPubkey = keypair.publicKey;
            const ataInfo = await connection.getAccountInfo(userAta, 'confirmed').catch(() => null);

            const instructions: TransactionInstruction[] = [];

            // Add priority fee instruction
            instructions.push(ComputeBudgetProgram.setComputeUnitPrice({
                microLamports: 500000
            }));

            // FIXED: Create ATA instruction using the correct method
            if (!ataInfo) {
                instructions.push(
                    createAssociatedTokenAccountInstruction(
                        userPubkey,           // payer
                        userAta,              // ata
                        userPubkey,           // owner
                        mint,                 // mint
                        TOKEN_PROGRAM_ID,     // token program (IMPORTANT!)
                        ASSOCIATED_TOKEN_PROGRAM_ID // associated token program
                    )
                );
            }

            // Add buy instruction
            const buyInstruction = PumpFunInstructionBuilder.buildBuyExactSolIn(
                userPubkey,
                mint,
                userAta,
                creator,
                spendableSolIn,
                minTokensOut,
                true
            );
            instructions.push(buyInstruction);

            // Build transaction
            const messageV0 = new TransactionMessage({
                payerKey: userPubkey,
                recentBlockhash: blockhash,
                instructions
            }).compileToV0Message();

            const transaction = new VersionedTransaction(messageV0);
            transaction.sign([keypair]);

            const buildTime = performance.now() - startTime;
            console.log(`⚡ Buy TX built in ${buildTime.toFixed(0)}ms`);

            return transaction;
        } catch (error) {
            console.error('Failed to create buy transaction:', error);
            return null;
        }
    }


    // ============================================
    // PROFIT STRATEGY MANAGEMENT
    // ============================================
    
    // private async monitorAndExecuteSells(): Promise<void> {
    //     const now = Date.now();
        
    //     for (const [key, strategy] of this.activeStrategies.entries()) {
    //         // Skip if recently checked
    //         if (now - strategy.lastCheck < 2000) continue;
            
    //         try {
    //             const mint = new PublicKey(strategy.token);
    //             const userPubkey = new PublicKey(strategy.user);
    //             const ata = getAssociatedTokenAddressSync(mint, userPubkey);
                
    //             // Check token balance
    //             const tokenBalance = await connection.getTokenAccountBalance(ata, 'confirmed');
    //             const currentTokens = tokenBalance.value.uiAmount || 0;
                
    //             if (currentTokens > 0 && !strategy.stopLossTriggered) {
    //                 // Get current price
    //                 const bondingCurve = await BondingCurveFetcher.fetch(connection, mint, true);
    //                 if (!bondingCurve) continue;
                    
    //                 const currentPrice = this.calculateCurrentTokenPrice(bondingCurve);
    //                 const priceChangePercent = ((currentPrice - strategy.entryPrice) / strategy.entryPrice) * 100;
                    
    //                 // Check stop loss
    //                 if (priceChangePercent < strategy.strategy.stopLoss) {
    //                     console.log(`🛑 Stop loss triggered for ${strategy.user.slice(0, 8)}: ${priceChangePercent.toFixed(2)}%`);
    //                     strategy.stopLossTriggered = true;
                        
    //                     // Execute stop loss sell
    //                     await this.executeSell(strategy.user, strategy.token, currentTokens, priceChangePercent);
    //                     this.activeStrategies.delete(key);
    //                     continue;
    //                 }
                    
    //                 // Check sell targets
    //                 for (let i = 0; i < strategy.sellLevels.length; i++) {
    //                     const level = strategy.sellLevels[i];
    //                     if (!level.sold && priceChangePercent >= level.target) {
    //                         console.log(`🎯 Target ${level.target}% hit for ${strategy.user.slice(0, 8)}`);
                            
    //                         // Calculate amount to sell (progressive selling)
    //                         const sellPercentage = 1 / (strategy.sellLevels.length - i);
    //                         const tokensToSell = currentTokens * sellPercentage;
                            
    //                         await this.executeSell(strategy.user, strategy.token, tokensToSell, priceChangePercent);
    //                         level.sold = true;
                            
    //                         // If all levels sold, remove strategy
    //                         if (strategy.sellLevels.every(l => l.sold)) {
    //                             this.activeStrategies.delete(key);
    //                             console.log(`✅ All profit targets achieved for ${strategy.user.slice(0, 8)}`);
    //                         }
    //                         break;
    //                     }
    //                 }
    //             }
                
    //             strategy.lastCheck = now;
                
    //         } catch (error) {
    //             console.error(`Strategy monitor failed for ${strategy.user.slice(0, 8)}:`, error);
    //         }
    //     }
    // }
    


    // ============================================
    // ADVANCED STRATEGY SELECTION
    // ============================================
    
    // private selectOptimalStrategy(tokenData: TokenData, quality: {score: number, confidence: number}): ProfitStrategy {
    //     // Rotate strategies to avoid pattern detection
    //     this.strategyRotationIndex = (this.strategyRotationIndex + 1) % PROFIT_STRATEGIES.length;
        
    //     // Base selection on token quality
    //     if (quality.score >= 80) {
    //         return PROFIT_STRATEGIES[0]; // AGGRESSIVE_SNIPE for high quality
    //     } else if (quality.score >= 60) {
    //         return PROFIT_STRATEGIES[1]; // CONSERVATIVE_FLIP for medium quality
    //     } else {
    //         return PROFIT_STRATEGIES[2]; // ULTRA_FAST_SCALP for lower quality
    //     }
    // }
    
    // private async assessTokenQuality(tokenData: TokenData): Promise<{score: number, confidence: number}> {
    //     let score = 50; // Base score
        
    //     // 1. Check creator reputation (simplified)
    //     const creator = new PublicKey(tokenData.Creator);
    //     const creatorBalance = await connection.getBalance(creator).catch(() => 0);
    //     if (creatorBalance > 0.1 * LAMPORTS_PER_SOL) score += 10;
        
    //     // 2. Check initial liquidity
    //     const initialLiquidity = parseFloat(tokenData.VirtualSolReserves) / LAMPORTS_PER_SOL;
    //     if (initialLiquidity > 0.1) score += 15;
    //     if (initialLiquidity > 0.5) score += 10;
        
    //     // 3. Check token supply distribution
    //     const tokenSupply = parseFloat(tokenData.TokenTotalSupply);
    //     const virtualReserves = parseFloat(tokenData.VirtualTokenReserves);
    //     const concentration = virtualReserves / tokenSupply;
        
    //     if (concentration > 0.7) score -= 20; // Too concentrated
    //     if (concentration < 0.3) score += 10; // Good distribution
        
    //     // 4. Check time since creation
    //     const tokenAge = Date.now() - new Date(tokenData.timestamp).getTime();
    //     if (tokenAge < 30000) score += 15; // Very fresh
    //     else if (tokenAge < 120000) score += 5; // Still fresh
        
    //     // Cap score between 0-100
    //     score = Math.max(0, Math.min(100, score));
        
    //     // Confidence based on data completeness
    //     const confidence = tokenData.VirtualSolReserves && tokenData.VirtualTokenReserves ? 85 : 60;
        
    //     return { score, confidence };
    // }
    
    // private calculateInitialTokenPrice(tokenData: TokenData): number {
    //     const solReserves = parseFloat(tokenData.VirtualSolReserves);
    //     const tokenReserves = parseFloat(tokenData.VirtualTokenReserves);
        
    //     // Add validation
    //     if (isNaN(solReserves) || isNaN(tokenReserves) || tokenReserves === 0) {
    //         console.warn(`⚠️ Invalid token reserves: SOL=${solReserves}, TOKEN=${tokenReserves}`);
    //         return 0;
    //     }
        
    //     const price = solReserves / tokenReserves;
        
    //     // Additional safety check
    //     if (isNaN(price) || !isFinite(price)) {
    //         console.warn(`⚠️ Invalid price calculation: ${solReserves} / ${tokenReserves}`);
    //         return 0;
    //     }
        
    //     return price;
    // }
    
    private calculateCurrentTokenPrice(bondingCurve: BondingCurve): number {
        const solReserves = Number(bondingCurve.virtual_sol_reserves);
        const tokenReserves = Number(bondingCurve.virtual_token_reserves);
        
        if (tokenReserves === 0) return 0;
        return solReserves / tokenReserves;
    }
    
    // private calculateEstimatedProfit(users: UserConfig[], tokenData: TokenData, strategy: ProfitStrategy): number {
    //     let totalProfit = 0;
        
    //     for (const user of users) {
    //         const buyAmount = user.buy_amount_sol * strategy.buyMultiplier;
            
    //         // Estimate average profit based on strategy targets
    //         const avgTarget = strategy.sellTargets.reduce((a, b) => a + b, 0) / strategy.sellTargets.length;
    //         const estimatedProfitPercent = avgTarget * 0.7; // 70% of target on average
            
    //         totalProfit += buyAmount * (estimatedProfitPercent / 100);
    //     }
        
    //     return totalProfit;
    // }
    
    // private calculateDynamicSlippage(bondingCurve: BondingCurve, baseSlippage: number): number {
    //     // Increase slippage for low liquidity pools
    //     const liquidity = Number(bondingCurve.virtual_sol_reserves) / LAMPORTS_PER_SOL;
        
    //     if (liquidity < 0.1) return baseSlippage * 3;
    //     if (liquidity < 0.5) return baseSlippage * 2;
    //     return baseSlippage;
    // }
    
    // private calculateDynamicPriorityFee(buyAmount: number): number {
    //     // Scale priority fee with buy amount
    //     if (buyAmount > 1) return 1000000; // 1 SOL+ = high priority
    //     if (buyAmount > 0.1) return 500000; // 0.1-1 SOL = medium priority
    //     return 250000; // Small buys = lower priority
    // }

    // ============================================
    // OPTIMIZED JITO BUNDLE EXECUTION
    // ============================================
    
    private async sendToJito(transactions: VersionedTransaction[]): Promise<{ bundleId: string; success: boolean }> {
        const startTime = performance.now();
        
        try {
            const result = await jitoBundleSender.sendBundle(transactions, connection);

            if (!result.success) {
                throw new Error(result.error || 'Jito bundle submission failed');
            }

            console.log(`📤 Jito bundle sent: ${result.bundleId}`);
            return { bundleId: result.bundleId, success: true };

        } catch (error: any) {
            console.error('Jito error:', error.message);
            throw error;
        }
    }

    private async fallbackRpcExecution(transactions: VersionedTransaction[]): Promise<{ bundleId: string; success: boolean }> {
        console.log('🔄 Falling back to RPC execution...');
        
        const sendPromises = transactions.map(tx => 
            connection.sendTransaction(tx, { skipPreflight: true, maxRetries: 0 })
                .catch(e => null)
        );

        await Promise.all(sendPromises);
        return { bundleId: 'rpc_fallback', success: true };
    }

    // ============================================
    // OPTIMIZED USER MANAGEMENT
    // ============================================
    
    private async getEligibleUsersForToken(tokenData: TokenData): Promise<UserConfig[]> {
        const eligibleUsers: UserConfig[] = [];
        
        for (const [wallet, user] of this.activeUsers) {
            try {
                const keypair = this.userKeypairs.get(wallet);
                if (!keypair) continue;

                const balance = await this.getUserBalance(wallet);
                const required = user.buy_amount_sol + 0.1;
                
                if (balance < required) continue;

                if (user.is_premium) {
                    const passes = await this.applyPremiumFilters(user, tokenData);
                    if (!passes) continue;
                }

                const mint = new PublicKey(tokenData.Mint);
                const curve = await BondingCurveFetcher.fetch(connection, mint, true);
                if (!curve || BondingCurveFetcher.isComplete(curve)) continue;

                eligibleUsers.push(user);

            } catch (error) {
                console.error(`User eligibility check failed:`, error);
            }
        }

        return eligibleUsers;
    }

    private async getCachedUserBalance(wallet: string): Promise<number> {
        // Implement simple in-memory cache
        const cacheKey = `balance_${wallet}`;
        const cached = this.userBalanceCache.get(cacheKey);
        
        if (cached && Date.now() - cached.timestamp < 5000) {
            return cached.balance;
        }
        
        try {
            const balance = await connection.getBalance(new PublicKey(wallet), 'confirmed');
            const solBalance = balance / LAMPORTS_PER_SOL;
            
            this.userBalanceCache.set(cacheKey, {
                balance: solBalance,
                timestamp: Date.now()
            });
            
            return solBalance;
        } catch {
            return 0;
        }
    }

    private userBalanceCache = new Map<string, {balance: number, timestamp: number}>();

    private async applyPremiumFilters(user: UserConfig, tokenData: TokenData): Promise<boolean> {
        if (user.filter_safety_check_period_seconds) {
            const tokenAge = Date.now() - new Date(tokenData.timestamp).getTime();
            if (tokenAge < user.filter_safety_check_period_seconds * 1000) {
                return false;
            }
        }

        return true;
    }

    private async getUserBalance(wallet: string): Promise<number> {
        try {
            const balance = await connection.getBalance(new PublicKey(wallet), 'confirmed');
            return balance / LAMPORTS_PER_SOL;
        } catch {
            return 0;
        }
    }

    // ============================================
    // USER REFRESH LOOP
    // ============================================
    
    private async startUserRefreshLoop(): Promise<void> {
        while (true) {
            try {
                await this.refreshActiveUsers();
                await this.refreshKeypairs();
                await new Promise(resolve => setTimeout(resolve, this.USER_REFRESH_INTERVAL));
            } catch (error) {
                console.error('User refresh error:', error);
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }
    }

    private async refreshActiveUsers(): Promise<void> {
        // Add delay between requests
        const timeSinceLastFetch = Date.now() - this.lastFetchTime;
        if (timeSinceLastFetch < 1000) {    // Minimum 1 second between fetches
            await new Promise(resolve => setTimeout(resolve, 1000 - timeSinceLastFetch));
        }

        try {
            const response = await axios.get(`${BACKEND_URL}/user/active-users`, {
                params: { api_key: ONCHAIN_API_KEY },
                headers: { 'X-Request-Type': 'sniper-engine' },
                timeout: 5000 // Increased from 1000ms
            });

            const newUsers = new Map<string, UserConfig>();
            if (response.data?.users) {
                for (const user of response.data.users) {
                    if (this.isUserEligibleForSniping(user)) {
                        newUsers.set(user.wallet_address, user);
                    }
                }
            }

            this.activeUsers = newUsers;
            this.lastFetchTime = Date.now();

            if (newUsers.size > 0) {
                console.log(`👤 Active users: ${newUsers.size}`);
            }

        } catch (error: any) {
            // if (error.response?.status === 429) {
            //     console.error('⚠️ Backend rate limited, increasing delay...');
            //     this.USER_REFRESH_INTERVAL = Math.min(this.USER_REFRESH_INTERVAL * 2, 10000);   // Max 10 seconds
            // }
            // Don't spam logs for timeouts
            if (error.code !== 'ECONNABORTED') {
                console.error('User refresh failed:', error.message);
            }
        }
    }

    private isUserEligibleForSniping(user: UserConfig): boolean {
        if (!user.encrypted_private_key || user.encrypted_private_key.length < 20) {
            return false;
        }

        const minBalance = (user.buy_amount_sol || 0.1) + 0.02; // Reduced buffer
        if (user.sol_balance < minBalance) {
            return false;
        }

        return true;
    }

    private async refreshKeypairs(): Promise<void> {
        const startTime = Date.now();
        let decrypted = 0;
        let newUsers = 0;

        for (const [wallet, user] of this.activeUsers) {
            if (this.userKeypairs.has(wallet)) continue;

            try {
                const keypair = await this.decryptUserKeypair(user);
                if (keypair) {
                    this.userKeypairs.set(wallet, keypair);
                    decrypted++;
                    newUsers++;
                }
            } catch (error) {
                console.error(`Failed to decrypt keypair for ${wallet.slice(0, 8)}`);
                this.activeUsers.delete(wallet);
            }
        }

        if (decrypted > 0) {
            console.log(`🔑 Decrypted ${decrypted} keypairs in ${Date.now() - startTime}ms`);
            if (newUsers > 0) {
                console.log(`🚀 Auto-initializing Jito for ${newUsers} new users`);
            }
        }
    }

    private async decryptUserKeypair(user: UserConfig): Promise<Keypair | null> {
        try {
            const decoded = bs58.decode(user.encrypted_private_key);
            if (decoded.length === 64) {
                return Keypair.fromSecretKey(decoded);
            }
        } catch (error) {
            console.error('Keypair decryption error:', error);
        }
        return null;
    }

    // ============================================
    // MONITORING SERVICES
    // ============================================
    
    private async connectToActivationWebSocket(): Promise<void> {
        try {
            this.activationWebSocket = new WebSocket(`${this.ACTIVATION_WS_URL}/ws/sniper-activations`);
            
            this.activationWebSocket.on('open', () => {
                console.log('📡 Connected to activation WebSocket');
            });
            
            this.activationWebSocket.on('message', async (data: WebSocket.Data) => {
                try {
                    const message = typeof data === 'string' ? data : data.toString();
                    const parsed = JSON.parse(message);
                    
                    if (parsed.type === 'user_activated') {
                        await this.refreshActiveUsers();
                    }
                } catch (error) {
                    console.error('WebSocket message error:', error);
                }
            });
            
            this.activationWebSocket.on('error', (error: Error) => {
                console.error('WebSocket error:', error);
            });
            
            this.activationWebSocket.on('close', () => {
                console.log('WebSocket closed, reconnecting...');
                setTimeout(() => this.connectToActivationWebSocket(), 2000);
            });
            
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            setTimeout(() => this.connectToActivationWebSocket(), 2000);
        }
    }

    private startHealthMonitor(): void {
        setInterval(() => {
            const health = this.getHealthStatus();
            if (health.healthScore < 80) {
                console.warn(`⚠️ Health score low: ${health.healthScore}%`);
            }
        }, 30000);
    }

    // private startStrategyMonitor(): void {
    //     setInterval(() => {
    //         this.monitorAndExecuteSells().catch(console.error);
    //     }, 3000); // Check every 3 seconds
    // }

    private startTokenTracker(): void {
        setInterval(() => {
            this.updateTokenPrices().catch(console.error);
        }, 5000);
    }

    private async updateTokenPrices(): Promise<void> {
        // Update prices for tracked tokens
        for (const [mint, tracker] of this.tokenTrackers.entries()) {
            try {
                const bondingCurve = await BondingCurveFetcher.fetch(
                    connection, 
                    new PublicKey(mint), 
                    true
                );
                
                if (bondingCurve) {
                    const currentPrice = this.calculateCurrentTokenPrice(bondingCurve);
                    tracker.currentPrice = currentPrice;
                    tracker.priceHistory.push({
                        price: currentPrice,
                        timestamp: Date.now()
                    });
                    
                    // Keep only last 100 price points
                    if (tracker.priceHistory.length > 100) {
                        tracker.priceHistory.shift();
                    }
                }
            } catch (error) {
                // Silent error
            }
        }
    }

    private updateTokenTracker(mint: string, initialPrice: number): void {
        this.tokenTrackers.set(mint, {
            initialPrice,
            currentPrice: initialPrice,
            volume24h: 0,
            holders: 0,
            lastUpdate: Date.now(),
            buys: 0,
            sells: 0,
            priceHistory: [{ price: initialPrice, timestamp: Date.now() }]
        });
    }

    private cleanupRecentSnipes(): void {
        setInterval(() => {
            const now = Date.now();
            for (const [mint, timestamp] of this.recentSnipedTokens.entries()) {
                if (now - timestamp > this.RECENT_SNIPE_TTL) {
                    this.recentSnipedTokens.delete(mint);
                }
            }
        }, 30000);
    }

    // ============================================
    // PROFIT LOGGING
    // ============================================
    
    private async logProfitSnipeToBackend(
        users: UserConfig[],
        tokenData: TokenData,
        bundleResult: { bundleId: string; success: boolean },
        strategy: ProfitStrategy,
        estimatedProfit: number
    ): Promise<void> {
        try {
            await axios.post(`${BACKEND_URL}/trade/profit-snipe`, {
                trades: users.map(user => ({
                    user_wallet_address: user.wallet_address,
                    mint_address: tokenData.Mint,
                    token_symbol: tokenData.Symbol,
                    token_name: tokenData.Name,
                    trade_type: 'profit_snipe',
                    strategy: strategy.name,
                    amount_sol: user.buy_amount_sol * strategy.buyMultiplier,
                    estimated_profit: estimatedProfit / users.length,
                    bundle_id: bundleResult.bundleId,
                    timestamp: new Date().toISOString()
                })),
                token_data: tokenData,
                bundle_id: bundleResult.bundleId,
                total_users: users.length,
                total_volume: users.reduce((sum, user) => sum + (user.buy_amount_sol * strategy.buyMultiplier), 0),
                estimated_total_profit: estimatedProfit,
                strategy_used: strategy.name
            }, {
                headers: { 'X-API-Key': ONCHAIN_API_KEY },
                timeout: 2000
            });
        } catch (error) {
            console.error('Failed to log profit snipe:', error);
        }
    }

    // ============================================
    // UTILITIES
    // ============================================
    private async logSnipeToBackend(
        users: UserConfig[],
        tokenData: TokenData,
        bundleResult: { bundleId: string; success: boolean }
    ): Promise<void> {
        try {
            await axios.post(`${BACKEND_URL}/trade/immediate-snipe`, {
                trades: users.map(user => ({
                    user_wallet_address: user.wallet_address,
                    mint_address: tokenData.Mint,
                    token_symbol: tokenData.Symbol,
                    token_name: tokenData.Name,
                    trade_type: 'immediate_snipe',
                    amount_sol: user.buy_amount_sol,
                    bundle_id: bundleResult.bundleId,
                    timestamp: new Date().toISOString()
                })),
                token_data: tokenData,
                bundle_id: bundleResult.bundleId
            }, {
                headers: { 'X-API-Key': ONCHAIN_API_KEY },
                timeout: 2000
            });
        } catch (error) {
            console.error('Failed to log snipe:', error);
        }
    }
    
    private getAverage(numbers: number[]): number {
        if (numbers.length === 0) return 0;
        const sum = numbers.reduce((a, b) => a + b, 0);
        return sum / numbers.length;
    }

    public getHealthStatus(): {
        healthScore: number;
        activeUsers: number;
        cachedKeypairs: number;
        activeStrategies: number;
        stats: typeof this.stats;
        performance: typeof this.performanceMetrics;
    } {
        const healthScore = this.calculateHealthScore();
        
        return {
            healthScore,
            activeUsers: this.activeUsers.size,
            cachedKeypairs: this.userKeypairs.size,
            activeStrategies: this.activeStrategies.size,
            stats: { ...this.stats },
            performance: { ...this.performanceMetrics }
        };
    }

    private calculateHealthScore(): number {
        let score = 100;
        
        if (this.activeUsers.size === 0) score -= 40;
        if (this.userKeypairs.size === 0) score -= 40;
        
        const successRate = this.stats.totalSnipes > 0 
            ? (this.stats.successfulSnipes / this.stats.totalSnipes) * 100 
            : 100;
        
        if (successRate < 60) score -= 30;
        if (successRate > 80) score += 10;
        
        const avgSnipeTime = this.getAverage(this.performanceMetrics.detectionToSnipe);
        if (avgSnipeTime > 150) score -= 20;
        if (avgSnipeTime < 80) score += 15;
        
        // Bonus for profitability
        if (this.stats.totalProfit > 0) score += 10;
        
        return Math.max(0, Math.min(100, score));
    }

    public async emergencyStop(): Promise<void> {
        console.log('🛑 EMERGENCY STOP INITIATED');
        
        this.activeUsers.clear();
        this.userKeypairs.clear();
        this.recentSnipedTokens.clear();
        this.activeStrategies.clear();
        
        try {
            await axios.post(`${BACKEND_URL}/sniper/emergency-stop`, {}, {
                headers: { 'X-API-Key': ONCHAIN_API_KEY },
                timeout: 2000
            });
        } catch (error) {
            console.error('Emergency stop notification failed:', error);
        }
        
        console.log('✅ Emergency stop complete');
    }
}

// ============================================
// EXPORTS
// ============================================
export const sniperEngine = new ProductionSniperEngine();
export const immediateTokenSniping = sniperEngine.immediateTokenSnipping.bind(sniperEngine);










