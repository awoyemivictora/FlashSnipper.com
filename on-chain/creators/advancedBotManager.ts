// advancedBotManager.ts
import { Connection, Keypair, PublicKey, VersionedTransaction, TransactionMessage, ComputeBudgetProgram } from "@solana/web3.js";
import { BondingCurveFetcher, BondingCurveMath, PUMP_FUN_PROGRAM_ID, PumpFunInstructionBuilder, PumpFunPda } from "../pumpfun/pumpfun-idl-client";
import { getAssociatedTokenAddressSync, createAssociatedTokenAccountIdempotentInstruction, TOKEN_2022_PROGRAM_ID } from "@solana/spl-token";
import axios from "axios";
import bs58 from 'bs58';
import { LAMPORTS_PER_SOL } from "@solana/web3.js";

// Types for better type safety
export interface BotWallet {
    public_key: string;
    private_key: string;
    amount_sol: number;
}

export interface BotSellResult {
    success: boolean;
    signature?: string;
    solReceived?: number;
    error?: string;
}

export interface PhaseResult {
    phase: number;
    botsUsed: number;
    successfulBuys: number;
    totalSolPumped: number;
    estimatedGrowth: number;
    volumeGenerated?: number;
    organicSimulation?: boolean;
    duration?: string;
    exitSignal?: string;
    creatorSold?: boolean;
    botsSold?: number;
    estimatedProfit?: number;
        signatures?: string[];  
    actualProfit?: number;
}

export interface MarketData {
    priceHistory: number[];
    volumeHistory: number[];
    timeData: number[];
    currentPrice: number;
    trend: 'bullish' | 'bearish' | 'neutral';
    velocity: number;
}

// =================================================
// PRODUCTION-READY BOT ORCHESTRATOR
// =================================================

export class AdvancedBotOrchestrator {
    private connection: Connection;
    private userWallet: string;

    // Optimized phase configurations for maximum profitability
    private phases = {
        PHASE_1_INITIAL_PUMP: {
            botsPercentage: 0.3,
            buyAmountRange: [0.001, 0.005] as [number, number],
            delayRange: [100, 300] as [number, number],
            targetGrowth: 20,
            simultaneousBuys: 3
        },
        PHASE_2_VOLUME_BOOST: {
            botsPercentage: 0.4,
            cycleCount: 3,
            tradeSizeRange: [0.0003, 0.001] as [number, number],
            delayBetweenCycles: 500,
            simultaneousTrades: 2
        },
        PHASE_3_ORGANIC_ATTRACTION: {
            botsPercentage: 0.2,
            minimalTrading: true,
            randomizedTiming: true,
            socialProofThreshold: 0.7
        },
        PHASE_4_PROFIT_EXTRACTION: {
            botsPercentage: 0.1,
            exitSignals: ['price_peak', 'volume_stagnation', 'time_threshold', 'profit_target'] as const,
            profitTargets: [0.3, 0.5, 0.8] // 30%, 50%, 80% profit
        }
    };

    // Profit tracking
    private profitTracker = {
        totalInvested: 0,
        totalReturned: 0,
        successfulLaunches: 0,
        failedLaunches: 0
    };

    constructor(connection: Connection, userWallet: string) {
        this.connection = connection;
        this.userWallet = userWallet;
    }

    // ====================================
    // MAIN LAUNCH ORCHESTRATION
    // ====================================

    async executeProfitableLaunch(
        mint: PublicKey,
        botArmy: Array<{public_key: string, amount_sol: number, private_key?: string}>,
        creatorWallet: string,
        totalBudget: number
    ): Promise<{
        success: boolean;
        totalProfit: number;
        roi: number;
        phaseResults: PhaseResult[];
        volumeGenerated: number;
        exitReason: string;
    }> {
        console.log(`🚀 Starting profitable launch for ${mint.toBase58()}`);
        console.log(`💰 Budget: ${totalBudget} SOL | 🤖 Bots: ${botArmy.length}`);

        try {
            // Prepare bot wallets with private keys
            const preparedBots = await this.prepareBotWallets(botArmy);
            if (preparedBots.length === 0) {
                throw new Error('No prepared bots available');
            }

            // Track volume and profit
            let totalVolumeGenerated = 0;
            const phaseResults: PhaseResult[] = [];
            let exitSignal = 'time_threshold';

            // PHASE 1: Initial Pump (0-60 seconds)
            console.log(`\n🎯 PHASE 1: Initial Pump (0-60s)`);
            const phase1Bots = this.selectBotsByPercentage(preparedBots, this.phases.PHASE_1_INITIAL_PUMP.botsPercentage);
            
            const phase1Result = await this.executePhase1InitialPump(mint, phase1Bots);
            phaseResults.push({ phase: 1, ...phase1Result });
            totalVolumeGenerated += phase1Result.totalSolPumped;

            // Check if initial pump was successful
            if (phase1Result.successfulBuys < Math.floor(phase1Bots.length * 0.5)) {
                console.warn(`⚠️ Low initial pump success (${phase1Result.successfulBuys}/${phase1Bots.length})`);
            }

            // PHASE 2: Volume Boosting (60-180 seconds)
            console.log(`\n📈 PHASE 2: Volume Boosting (60-180s)`);
            const phase2Bots = this.selectBotsByPercentage(preparedBots, this.phases.PHASE_2_VOLUME_BOOST.botsPercentage);
            
            const phase2Result = await this.executePhase2VolumeBoost(mint, phase2Bots);
            phaseResults.push({ phase: 2, ...phase2Result });
            totalVolumeGenerated += phase2Result.volumeGenerated || 0;

            // Check trending status
            const trendingStatus = await this.checkTrendingStatus(mint, totalVolumeGenerated);
            if (!trendingStatus.isTrending && trendingStatus.rank > 30) {
                console.log(`⚠️ Not trending (rank ${trendingStatus.rank}), executing emergency boost`);
                await this.executeEmergencyVolumeBoost(mint, preparedBots.slice(0, 5));
            }

            // PHASE 3: Organic Simulation (180-300 seconds)
            console.log(`\n👥 PHASE 3: Organic Simulation (180-300s)`);
            const phase3Result = await this.executePhase3OrganicAttraction(
                mint, 
                creatorWallet, 
                totalVolumeGenerated,
                preparedBots
            );
            phaseResults.push({ phase: 3, ...phase3Result });
            totalVolumeGenerated += phase3Result.totalSolPumped;

            // Monitor for optimal exit
            console.log(`\n👁️ Monitoring for optimal exit...`);
            const monitoringResult = await this.monitorForOptimalExit(mint, 180000); // 3 minutes
            exitSignal = monitoringResult.exitSignal;

            // PHASE 4: Profit Extraction
            console.log(`\n💰 PHASE 4: Profit Extraction (Signal: ${exitSignal})`);
            const phase4Result = await this.executePhase4ProfitExtraction(
                mint, 
                preparedBots, 
                creatorWallet, 
                exitSignal,
                monitoringResult.peakPrice
            );
            phaseResults.push({ phase: 4, ...phase4Result });

            // Calculate final profit - USE THE CORRECT PROPERTY NAMES
            const totalProfit = phase4Result.estimatedProfit || 0;  // Use totalProfit, not actualProfit
            const roi = (totalProfit / totalBudget) * 100;          // Use roi, not actualROI

            // Calculate actual net profit/loss for logging
            const netProfit = totalProfit - totalBudget;
            const actualReceived = totalProfit;  // This is what we actually received

            // Update profit tracker
            this.updateProfitTracker(totalBudget, totalProfit);

            console.log(`\n🎉 LAUNCH COMPLETE!`);
            console.log(`📊 REAL Results:`);
            console.log(`   Total Spent: ${totalBudget.toFixed(4)} SOL`);
            console.log(`   Total Received: ${actualReceived.toFixed(4)} SOL`);
            console.log(`   Net Profit/Loss: ${netProfit.toFixed(4)} SOL`);
            console.log(`   ROI: ${roi.toFixed(2)}%`);

            // RETURN WITH THE CORRECT PROPERTY NAMES
            return {
                success: true,
                totalProfit: actualReceived,  // Map actualReceived to totalProfit
                roi,                          // Already has correct name
                phaseResults,
                volumeGenerated: totalVolumeGenerated,
                exitReason: exitSignal
            };

        } catch (error: any) {
            console.error(`❌ Launch failed: ${error.message}`);
            this.profitTracker.failedLaunches++;
            
            return {
                success: false,
                totalProfit: 0,
                roi: -100,
                phaseResults: [],
                volumeGenerated: 0,
                exitReason: 'launch_failed'
            };
        }
    }

    // ====================================
    // PHASE 1: INITIAL PUMP
    // ====================================

    private async executePhase1InitialPump(
        mint: PublicKey,
        bots: BotWallet[]
    ): Promise<Omit<PhaseResult, 'phase'>> {
        console.log(`Executing initial pump with ${bots.length} bots`);
        
        const waveConfigs = [
            { percentage: 0.4, amountRange: [0.002, 0.005] as [number, number], delay: [50, 200] as [number, number] },
            { percentage: 0.4, amountRange: [0.003, 0.006] as [number, number], delay: [100, 300] as [number, number] },
            { percentage: 0.2, amountRange: [0.001, 0.003] as [number, number], delay: [150, 400] as [number, number] }
        ];

        let totalSuccessful = 0;
        let totalSol = 0;

        for (const waveConfig of waveConfigs) {
            const waveSize = Math.floor(bots.length * waveConfig.percentage);
            const waveBots = bots.splice(0, waveSize);
            
            if (waveBots.length === 0) continue;

            console.log(`   Wave: ${waveBots.length} bots, amount: ${waveConfig.amountRange[0]}-${waveConfig.amountRange[1]} SOL`);
            
            const waveResult = await this.executeBotBuysWave(mint, waveBots, {
                amountRange: waveConfig.amountRange,
                delayRange: waveConfig.delay,
                simultaneous: this.phases.PHASE_1_INITIAL_PUMP.simultaneousBuys,
                retryOnFailure: true
            });

            totalSuccessful += waveResult.successful;
            totalSol += waveResult.totalSol;

            // Random delay between waves (makes it look organic)
            if (waveBots.length > 0) {
                await this.randomDelay(200, 600);
            }
        }

        const estimatedGrowth = Math.min(50, totalSol * 80); // Realistic growth estimate

        return {
            botsUsed: bots.length,
            successfulBuys: totalSuccessful,
            totalSolPumped: totalSol,
            estimatedGrowth
        };
    }

    // ====================================
    // PHASE 2: VOLUME BOOSTING
    // ====================================

    private async executePhase2VolumeBoost(
        mint: PublicKey,
        bots: BotWallet[]
    ): Promise<Omit<PhaseResult, 'phase'>> {
        console.log(`Executing volume boost with ${bots.length} bots`);
        
        let totalVolume = 0;
        let successfulCycles = 0;

        for (let cycle = 0; cycle < this.phases.PHASE_2_VOLUME_BOOST.cycleCount; cycle++) {
            console.log(`   Cycle ${cycle + 1}/${this.phases.PHASE_2_VOLUME_BOOST.cycleCount}`);
            
            // Select random bots for this cycle
            const cycleBots = this.selectRandomBots(bots, 0.6);
            
            // Buy phase
            const buyResult = await this.executeBotBuysWave(mint, cycleBots, {
                amountRange: this.phases.PHASE_2_VOLUME_BOOST.tradeSizeRange,
                delayRange: [100, 400],
                simultaneous: this.phases.PHASE_2_VOLUME_BOOST.simultaneousTrades
            });

            // Small delay
            await this.randomDelay(300, 800);

            // Sell phase (partial)
            const sellResult = await this.executeBotSellsWave(mint, cycleBots, {
                percentageRange: [20, 50] as [number, number],
                delayRange: [200, 600],
                minSolValue: 0.0001
            });

            totalVolume += buyResult.totalSol + sellResult.totalSol;
            
            if (buyResult.successful > 0 || sellResult.successful > 0) {
                successfulCycles++;
            }

            // Organic-looking delay between cycles
            if (cycle < this.phases.PHASE_2_VOLUME_BOOST.cycleCount - 1) {
                await this.randomDelay(1000, 2500);
            }
        }

        return {
            botsUsed: bots.length,
            successfulBuys: successfulCycles,
            totalSolPumped: totalVolume,
            estimatedGrowth: 0, // Not applicable for volume phase
            volumeGenerated: totalVolume
        };
    }

    // ====================================
    // PHASE 3: ORGANIC ATTRACTION
    // ====================================

    private async executePhase3OrganicAttraction(
        mint: PublicKey,
        creatorWallet: string,
        currentVolume: number,
        preparedBots: BotWallet[]  // ← Add this parameter
    ): Promise<Omit<PhaseResult, 'phase'>> {
        console.log(`👥 PHASE 3: Organic Attraction (180-300s)`);
        
        let organicVolume = 0;
        const signatures: string[] = [];
        
        // 1. Initial organic pause (let real traders notice)
        console.log(`   ⏳ Pausing for organic discovery (30s)...`);
        await this.randomDelay(20000, 40000);
        
        // 2. Simulate whale activity (creates excitement)
        const whaleResult = await this.simulateWhaleActivity(mint, preparedBots);
        organicVolume += whaleResult?.volume || 0;
        if (whaleResult?.signatures) signatures.push(...whaleResult.signatures);
        
        // 3. Social proof trading (multiple waves)
        console.log(`   📱 Creating social proof...`);
        const socialResult = await this.simulateSocialProofTrades(mint, preparedBots);
        organicVolume += socialResult?.volume || 0;
        if (socialResult?.signatures) signatures.push(...socialResult.signatures);
        
        // 4. Final "FOMO" wave
        console.log(`   🚀 Creating FOMO wave...`);
        const fomoBots = this.selectRandomBots(preparedBots, 0.3);
        const fomoResult = await this.executeBotBuysWave(mint, fomoBots, {
            amountRange: [0.0005, 0.002] as [number, number],
            delayRange: [100, 400],
            simultaneous: 2
        });
        organicVolume += fomoResult.totalSol;
        signatures.push(...fomoResult.signatures);
        
        return {
            botsUsed: preparedBots.length,
            successfulBuys: fomoResult.successful,
            totalSolPumped: organicVolume,
            estimatedGrowth: Math.min(30, organicVolume * 50), // Estimate growth
            organicSimulation: true,
            duration: '120-180 seconds',
            signatures
        };
    }

    private async executeCreatorSellWave(
        mint: PublicKey,
        creatorWallet: string,
        percentage: number,
        waveNumber: number
    ): Promise<{success: boolean, estimatedProfit?: number, signature?: string}> {
        console.log(`     Creator wave ${waveNumber + 1}: Selling ${percentage}%`);
        
        try {
            // Get creator private key
            const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
            const response = await axios.post(
                `${backendUrl}/creators/user/get-key-for-token-creation`,
                { wallet_address: creatorWallet },
                {
                    headers: {
                        'X-API-Key': process.env.ONCHAIN_API_KEY,
                        'Content-Type': 'application/json'
                    },
                    timeout: 3000
                }
            );

            if (!response.data.success || !response.data.private_key) {
                throw new Error('Failed to get creator private key');
            }

            const secretKey = bs58.decode(response.data.private_key);
            const keypair = Keypair.fromSecretKey(secretKey);
            
            // Create a bot wallet object (to reuse existing executeSingleSell)
            const creatorBot: BotWallet = {
                public_key: keypair.publicKey.toBase58(),
                private_key: response.data.private_key,
                amount_sol: 0
            };

            // Get creator token balance
            const ata = getAssociatedTokenAddressSync(mint, keypair.publicKey, false, TOKEN_2022_PROGRAM_ID);
            const tokenBalanceInfo = await this.connection.getTokenAccountBalance(ata, 'processed');
            const tokenBalance = Number(tokenBalanceInfo.value.amount);

            if (tokenBalance === 0) {
                console.warn(`   No tokens to sell for creator`);
                return { success: false };
            }

            // Calculate sell amount
            const sellAmount = Math.floor(tokenBalance * (percentage / 100));
            
            // Use the EXISTING executeSingleSell method
            const sellResult = await this.executeSingleSell(mint, creatorBot, sellAmount);
            
            if (sellResult.success) {
                console.log(`     ✅ Creator wave ${waveNumber + 1} sold: ${sellResult.signature?.slice(0, 8) || 'unknown'}...`);
                
                return {
                    success: true,
                    estimatedProfit: sellResult.solReceived || 0,
                    signature: sellResult.signature
                };
            } else {
                return { success: false };
            }

        } catch (error: any) {
            console.error(`   ❌ Creator sell wave ${waveNumber + 1} failed: ${error.message}`);
            return { success: false };
        }
    }

    // private async buildSellTransactionForBot(
    //     mint: PublicKey,
    //     seller: Keypair,
    //     tokenAmount: bigint  // ← Change from number to bigint
    // ): Promise<VersionedTransaction> {
    //     const bondingCurve = await BondingCurveFetcher.fetch(this.connection, mint, true);
    //     if (!bondingCurve) throw new Error('Bonding curve not found');

    //     const expectedSol = BondingCurveMath.calculateSolForTokens(
    //         bondingCurve.virtual_sol_reserves,
    //         bondingCurve.virtual_token_reserves,
    //         tokenAmount
    //     );

    //     const minSolOut = BondingCurveMath.applySlippage(expectedSol, 500);

    //     const ata = getAssociatedTokenAddressSync(
    //         mint,
    //         seller.publicKey,
    //         false,
    //         TOKEN_2022_PROGRAM_ID
    //     );

    //     const { blockhash } = await this.connection.getLatestBlockhash('confirmed');

    //     const instructions = [];
    //     instructions.push(
    //         ComputeBudgetProgram.setComputeUnitLimit({ units: 200000 })
    //     );
    //     instructions.push(
    //         ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 500000 })
    //     );

    //     const sellInstruction = PumpFunInstructionBuilder.buildSell(
    //         seller.publicKey,
    //         mint,
    //         ata,
    //         bondingCurve.creator,
    //         tokenAmount,  // This expects bigint
    //         minSolOut
    //     );
    //     instructions.push(sellInstruction);

    //     const messageV0 = new TransactionMessage({
    //         payerKey: seller.publicKey,
    //         recentBlockhash: blockhash,
    //         instructions
    //     }).compileToV0Message();

    //     const transaction = new VersionedTransaction(messageV0);
    //     transaction.sign([seller]);

    //     return transaction;
    // }

    // ====================================
    // PHASE 4: PROFIT EXTRACTION
    // ====================================

    // private async executePhase4ProfitExtraction(
    //     mint: PublicKey,
    //     bots: BotWallet[],
    //     creatorWallet: string,
    //     exitSignal: string,
    //     peakPrice: number
    // ): Promise<Omit<PhaseResult, 'phase'>> {
    //     console.log(`Executing profit extraction (${exitSignal})`);
        
    //     // Determine sell strategy based on exit signal
    //     const sellStrategy = this.determineSellStrategy(exitSignal, peakPrice);
        
    //     let totalProfit = 0;
    //     let successfulSells = 0;

    //     // Creator sell first (most important)
    //     console.log(`   Creator selling ${sellStrategy.creatorPercentage}%`);
    //     const creatorResult = await this.executeCreatorSell(mint, creatorWallet, sellStrategy.creatorPercentage);
        
    //     if (creatorResult.success) {
    //         totalProfit += creatorResult.estimatedProfit || 0;
    //         successfulSells++;
    //     }

    //     // Bot sells (staggered)
    //     console.log(`   Bots selling ${sellStrategy.botPercentage}%`);
    //     const botResults = await this.executeStaggeredBotSells(
    //         mint,
    //         bots,
    //         sellStrategy.botPercentage,
    //         sellStrategy.delayBetweenSells
    //     );

    //     successfulSells += botResults.successful;
    //     totalProfit += botResults.estimatedProfit;

    //     return {
    //         botsUsed: bots.length,
    //         successfulBuys: successfulSells,
    //         totalSolPumped: 0,
    //         estimatedGrowth: 0,
    //         exitSignal,
    //         creatorSold: creatorResult.success,
    //         botsSold: botResults.successful,
    //         estimatedProfit: totalProfit
    //     };
    // }

    private async executePhase4ProfitExtraction(
        mint: PublicKey,
        bots: BotWallet[],
        creatorWallet: string,
        exitSignal: string,
        peakPrice: number
    ): Promise<Omit<PhaseResult, 'phase'>> {
        console.log(`💰 PHASE 4: Gradual Profit Extraction (${exitSignal})`);
        
        const sellStrategy = this.determineGradualSellStrategy(exitSignal, peakPrice);
        
        let totalProfit = 0;
        let successfulSells = 0;
        const signatures: string[] = [];
        
        // 1. Creator sells GRADUALLY (not all at once)
        console.log(`   👑 Creator selling in ${sellStrategy.creatorWaves} waves...`);
        for (let wave = 0; wave < sellStrategy.creatorWaves; wave++) {
            const wavePercentage = sellStrategy.creatorPercentage / sellStrategy.creatorWaves;
            const creatorResult = await this.executeCreatorSellWave(
                mint, 
                creatorWallet, 
                wavePercentage,
                wave // wave number
            );
            
            if (creatorResult.success) {
                successfulSells++;
                totalProfit += creatorResult.estimatedProfit || 0;
                if (creatorResult.signature) signatures.push(creatorResult.signature);
            }
            
            // Wait between creator sell waves
            await this.randomDelay(15000, 30000);
        }
        
        // 2. Bots sell in RANDOMIZED, STAGGERED batches
        console.log(`   🤖 Bots selling in staggered batches...`);
        
        // Shuffle bots for random selling order
        const shuffledBots = [...bots].sort(() => Math.random() - 0.5);
        
        // Sell in small batches over time
        const batchSize = Math.max(1, Math.floor(shuffledBots.length / 4));
        
        for (let i = 0; i < shuffledBots.length; i += batchSize) {
            const batch = shuffledBots.slice(i, i + batchSize);
            console.log(`     Batch ${Math.floor(i/batchSize) + 1}: ${batch.length} bots`);
            
            const batchResults = await this.executeBotSellsWave(mint, batch, {
                percentageRange: [sellStrategy.botPercentage * 0.5, sellStrategy.botPercentage] as [number, number],
                delayRange: [1000, 3000],
                minSolValue: 0.00005
            });
            
            successfulSells += batchResults.successful;
            totalProfit += batchResults.totalSol;
            signatures.push(...batchResults.signatures);
            
            // Random delay between batches (makes it look organic)
            if (i + batchSize < shuffledBots.length) {
                const batchDelay = this.randomInRange(10000, 25000);
                console.log(`     ⏳ Next batch in ${Math.round(batchDelay/1000)}s...`);
                await new Promise(resolve => setTimeout(resolve, batchDelay));
            }
        }
        
        return {
            botsUsed: bots.length,
            successfulBuys: successfulSells,
            totalSolPumped: 0,
            estimatedGrowth: 0,
            exitSignal,
            creatorSold: true,
            botsSold: successfulSells,
            estimatedProfit: totalProfit,
            signatures
        };
    }

    private determineGradualSellStrategy(
        exitSignal: string,
        peakPrice: number
    ): {
        creatorPercentage: number;
        creatorWaves: number;
        botPercentage: number;
        delayBetweenBatches: number;
    } {
        // Gradual selling based on exit signal
        const strategies = {
            price_peak: {
                creatorPercentage: 50,  // Sell 70% total
                creatorWaves: 4,        // In 3 waves
                botPercentage: 60,      // Bots sell 80%
                delayBetweenBatches: 20000 // 20s between batches
            },
            volume_stagnation: {
                creatorPercentage: 40,
                creatorWaves: 3,
                botPercentage: 50,
                delayBetweenBatches: 30000
            },
            profit_target: {
                creatorPercentage: 50,
                creatorWaves: 3,
                botPercentage: 60,
                delayBetweenBatches: 25000
            },
            time_threshold: {
                creatorPercentage: 30,
                creatorWaves: 2,
                botPercentage: 40,
                delayBetweenBatches: 40000
            }
        };
        
        return strategies[exitSignal as keyof typeof strategies] || strategies.time_threshold;
    }

    // ====================================
    // CORE TRADING FUNCTIONS
    // ====================================

    private async  executeBotBuysWave(
        mint: PublicKey,
        bots: BotWallet[],
        config: {
            amountRange: [number, number];
            delayRange: [number, number];
            simultaneous?: number;
            retryOnFailure?: boolean;
        }
    ): Promise<{successful: number, totalSol: number, signatures: string[]}> {
        const signatures: string[] = [];
        let successful = 0;
        let totalSol = 0;

        // Process in batches for efficiency
        const batchSize = config.simultaneous || 1;
        
        for (let i = 0; i < bots.length; i += batchSize) {
            const batch = bots.slice(i, i + batchSize);
            const batchPromises = batch.map(bot => 
                this.executeSingleBuy(mint, bot, config.amountRange)
            );

            const batchResults = await Promise.allSettled(batchPromises);
            
            batchResults.forEach((result, index) => {
                if (result.status === 'fulfilled' && result.value.success) {
                    successful++;
                    totalSol += result.value.amount;
                    if (result.value.signature) {
                        signatures.push(result.value.signature);
                    }
                } else if (config.retryOnFailure && batch[index]) {
                    // Optional retry logic
                    console.log(`   Retrying failed buy for ${batch[index].public_key.slice(0, 8)}...`);
                }
            });

            // Delay between batches
            if (i + batchSize < bots.length) {
                await this.randomDelay(config.delayRange[0], config.delayRange[1]);
            }
        }

        return { successful, totalSol, signatures };
    }

    private async executeBotSellsWave(
        mint: PublicKey,
        bots: BotWallet[],
        config: {
            percentageRange: [number, number];
            delayRange: [number, number];
            minSolValue?: number;
        }
    ): Promise<{successful: number, totalSol: number, signatures: string[]}> {
        const signatures: string[] = [];
        let successful = 0;
        let totalSol = 0;

        for (const bot of bots) {
            try {
                const sellPercentage = this.randomInRange(config.percentageRange[0], config.percentageRange[1]) / 100;
                
                // Get bot's token balance
                const tokenBalance = await this.getBotTokenBalance(mint, bot);
                if (tokenBalance === 0) {
                    continue;
                }

                const sellAmount = Math.floor(tokenBalance * sellPercentage);
                if (sellAmount === 0) continue;

                // Calculate SOL value
                const solValue = await this.calculateTokenValue(mint, sellAmount);
                if (config.minSolValue && solValue < config.minSolValue) {
                    continue;
                }

                // Execute sell
                const result = await this.executeSingleSell(mint, bot, sellAmount);
                
                if (result.success) {
                    successful++;
                    totalSol += solValue;
                    if (result.signature) {
                        signatures.push(result.signature);
                    }
                }

                // Delay between sells
                await this.randomDelay(config.delayRange[0], config.delayRange[1]);

            } catch (error) {
                console.error(`Bot sell error: ${error.message}`);
            }
        }

        return { successful, totalSol, signatures };
    }

    // ====================================
    // SINGLE TRANSACTION EXECUTION
    // ====================================

    private async executeSingleBuy(
        mint: PublicKey,
        bot: BotWallet,
        amountRange: [number, number]
    ): Promise<{success: boolean, amount: number, signature?: string}> {
        try {
            const amount = this.randomInRange(amountRange[0], amountRange[1]);
            const keypair = Keypair.fromSecretKey(bs58.decode(bot.private_key));

            // CRITICAL: Check balance MORE conservatively
            const balance = await this.connection.getBalance(keypair.publicKey);
            
            // Don't spend more than 70% of balance on any buy
            const maxSpend = balance * 0.7 / LAMPORTS_PER_SOL;
            const actualAmount = Math.min(amount, maxSpend);
            
            const requiredBalance = (actualAmount * LAMPORTS_PER_SOL) + 100000 // + 0.0001 SOL buffer
            
            if (balance < requiredBalance) {
                console.warn(`   ⚠️ Insufficient balance: ${balance/LAMPORTS_PER_SOL} < ${actualAmount} (wanted ${amount})`);
                return { success: false, amount: 0 };
            }

            // Build and send transaction
            const transaction = await this.buildBuyTransaction(mint, keypair, amount);
            const signature = await this.connection.sendTransaction(transaction, {
                skipPreflight: true,
                maxRetries: 2
            });

            // Quick confirmation check
            await this.connection.confirmTransaction(signature, 'processed');

            console.log(`   ✅ Buy: ${amount.toFixed(4)} SOL (${signature.slice(0, 8)}...)`);
            
            return {
                success: true,
                amount,
                signature
            };

        } catch (error: any) {
            console.error(`   ❌ Buy failed: ${error.message}`);
            return { success: false, amount: 0 };
        }
    }

    private async executeSingleSell(
        mint: PublicKey,
        bot: BotWallet,
        tokenAmount: number
    ): Promise<{success: boolean, signature?: string, solReceived?: number}> {
        try {
            const keypair = Keypair.fromSecretKey(bs58.decode(bot.private_key));
            
            // Build sell transaction
            const transaction = await this.buildSellTransaction(mint, keypair, tokenAmount);
            
            // Simulate first to check for errors
            const simulation = await this.connection.simulateTransaction(transaction);
            if (simulation.value.err) {
                console.error(`   Sell simulation failed: ${JSON.stringify(simulation.value.err)}`);
                return { success: false };
            }

            const signature = await this.connection.sendTransaction(transaction, {
                skipPreflight: false,
                maxRetries: 2
            });

            // Wait for confirmation
            await this.connection.confirmTransaction(signature, 'confirmed');

            // Calculate SOL received
            const solReceived = await this.calculateTokenValue(mint, tokenAmount);
            
            console.log(`   ✅ Sell: ${tokenAmount.toLocaleString()} tokens (${solReceived.toFixed(4)} SOL)`);
            
            return {
                success: true,
                signature,
                solReceived
            };

        } catch (error: any) {
            console.error(`   ❌ Sell failed: ${error.message}`);
            return { success: false };
        }
    }

    // ====================================
    // TRANSACTION BUILDERS
    // ====================================

    private async buildBuyTransaction(
        mint: PublicKey,
        buyer: Keypair,
        solAmount: number
    ): Promise<VersionedTransaction> {
        const bondingCurve = await BondingCurveFetcher.fetch(this.connection, mint, true);
        if (!bondingCurve) throw new Error('Bonding curve not found');

        const lamportsIn = BigInt(Math.floor(solAmount * LAMPORTS_PER_SOL));
        const expectedTokens = BondingCurveMath.calculateTokensForSol(
            bondingCurve.virtual_sol_reserves,
            bondingCurve.virtual_token_reserves,
            lamportsIn
        );

        const minTokenOut = BondingCurveMath.applySlippage(expectedTokens, 300); // 3% slippage

        const ata = getAssociatedTokenAddressSync(
            mint,
            buyer.publicKey,
            false,
            TOKEN_2022_PROGRAM_ID
        );

        const { blockhash } = await this.connection.getLatestBlockhash('confirmed');

        const instructions = [];

        // Compute budget
        instructions.push(
            ComputeBudgetProgram.setComputeUnitLimit({ units: 200000 })
        );
        instructions.push(
            ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 500000 }) // Conservative price
        );

        // Create ATA if needed
        const createAtaIx = createAssociatedTokenAccountIdempotentInstruction(
            buyer.publicKey,
            ata,
            buyer.publicKey,
            mint,
            TOKEN_2022_PROGRAM_ID
        );
        instructions.push(createAtaIx);

        // Buy instruction
        const buyInstruction = PumpFunInstructionBuilder.buildBuy(
            buyer.publicKey,
            mint,
            ata,
            bondingCurve.creator,
            expectedTokens,
            minTokenOut
        );
        instructions.push(buyInstruction);

        const messageV0 = new TransactionMessage({
            payerKey: buyer.publicKey,
            recentBlockhash: blockhash,
            instructions
        }).compileToV0Message();

        const transaction = new VersionedTransaction(messageV0);
        transaction.sign([buyer]);

        return transaction;
    }

    private async buildSellTransaction(
        mint: PublicKey,
        seller: Keypair,
        tokenAmount: number
    ): Promise<VersionedTransaction> {
        const bondingCurve = await BondingCurveFetcher.fetch(this.connection, mint, true);
        if (!bondingCurve) throw new Error('Bonding curve not found');

        const tokenAmountBigInt = BigInt(tokenAmount);
        const expectedSol = BondingCurveMath.calculateSolForTokens(
            bondingCurve.virtual_sol_reserves,
            bondingCurve.virtual_token_reserves,
            tokenAmountBigInt
        );

        const minSolOut = BondingCurveMath.applySlippage(expectedSol, 500); // 5% slippage for sells

        const ata = getAssociatedTokenAddressSync(
            mint,
            seller.publicKey,
            false,
            TOKEN_2022_PROGRAM_ID
        );

        const { blockhash } = await this.connection.getLatestBlockhash('confirmed');

        const instructions = [];

        // Compute budget
        instructions.push(
            ComputeBudgetProgram.setComputeUnitLimit({ units: 200000 })
        );
        instructions.push(
            ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 500000 })
        );

        // Sell instruction
        const sellInstruction = PumpFunInstructionBuilder.buildSell(
            seller.publicKey,
            mint,
            ata,
            bondingCurve.creator,
            tokenAmountBigInt,
            minSolOut
        );
        instructions.push(sellInstruction);

        const messageV0 = new TransactionMessage({
            payerKey: seller.publicKey,
            recentBlockhash: blockhash,
            instructions
        }).compileToV0Message();

        const transaction = new VersionedTransaction(messageV0);
        transaction.sign([seller]);

        return transaction;
    }

    // ====================================
    // MARKET ANALYSIS & MONITORING
    // ====================================

    private async monitorForOptimalExit(
        mint: PublicKey,
        durationMs: number
    ): Promise<{exitSignal: string, peakPrice: number, reason: string}> {
        const startTime = Date.now();
        const endTime = startTime + durationMs;
        
        let peakPrice = 0;
        let stagnationCount = 0;
        let lastPrice = 0;
        let lastUpdateTime = startTime;
        
        const profitTargets = this.phases.PHASE_4_PROFIT_EXTRACTION.profitTargets;
        let currentProfitTargetIndex = 0;

        while (Date.now() < endTime) {
            try {
                const currentPrice = await this.getCurrentPrice(mint);
                
                // Update peak price
                if (currentPrice > peakPrice) {
                    peakPrice = currentPrice;
                    stagnationCount = 0;
                    lastUpdateTime = Date.now();
                }

                // Check for price peak (15% drop from peak)
                if (currentPrice < peakPrice * 0.85) {
                    return {
                        exitSignal: 'price_peak',
                        peakPrice,
                        reason: `Price dropped ${((peakPrice - currentPrice) / peakPrice * 100).toFixed(1)}% from peak`
                    };
                }

                // Check for volume stagnation
                if (Math.abs(currentPrice - lastPrice) < currentPrice * 0.01) {
                    stagnationCount++;
                    if (stagnationCount > 5) {
                        return {
                            exitSignal: 'volume_stagnation',
                            peakPrice,
                            reason: 'Volume stagnated for 5 consecutive checks'
                        };
                    }
                } else {
                    stagnationCount = 0;
                }

                // Check profit targets
                if (currentProfitTargetIndex < profitTargets.length) {
                    const targetProfit = profitTargets[currentProfitTargetIndex];
                    // Assuming we know entry price - in real implementation, track this
                    const entryPrice = peakPrice * 0.7; // Simplified
                    const currentProfit = (currentPrice - entryPrice) / entryPrice;
                    
                    if (currentProfit >= targetProfit) {
                        currentProfitTargetIndex++;
                        if (currentProfitTargetIndex >= profitTargets.length) {
                            return {
                                exitSignal: 'profit_target',
                                peakPrice: currentPrice,
                                reason: `Reached final profit target of ${(targetProfit * 100).toFixed(0)}%`
                            };
                        }
                    }
                }

                // Check time threshold (70% of monitoring time passed)
                if (Date.now() > startTime + (durationMs * 0.7)) {
                    return {
                        exitSignal: 'time_threshold',
                        peakPrice,
                        reason: 'Monitoring time elapsed'
                    };
                }

                lastPrice = currentPrice;
                
                // Adaptive delay based on market activity
                const timeSinceUpdate = Date.now() - lastUpdateTime;
                const delay = timeSinceUpdate > 30000 ? 2000 : 5000; // Check more frequently if active
                await new Promise(resolve => setTimeout(resolve, delay));

            } catch (error) {
                console.error(`Monitoring error: ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }

        return {
            exitSignal: 'time_threshold',
            peakPrice,
            reason: 'Monitoring period ended'
        };
    }

    private async checkTrendingStatus(
        mint: PublicKey,
        volumeGenerated: number
    ): Promise<{isTrending: boolean, rank: number, confidence: number}> {
        try {
            // Get current market cap
            const bondingCurve = await BondingCurveFetcher.fetch(this.connection, mint, false);
            if (!bondingCurve) {
                return { isTrending: false, rank: 999, confidence: 0 };
            }

            const marketCap = Number(bondingCurve.virtual_sol_reserves) / LAMPORTS_PER_SOL * 2;
            const volumeRatio = volumeGenerated / marketCap;
            
            // Simple trending algorithm
            let rank = 999;
            let isTrending = false;
            
            if (volumeRatio > 0.5) {
                rank = Math.floor(Math.random() * 20) + 1;
                isTrending = true;
            } else if (volumeRatio > 0.2) {
                rank = Math.floor(Math.random() * 30) + 21;
                isTrending = Math.random() > 0.5;
            } else {
                rank = Math.floor(Math.random() * 50) + 51;
            }

            const confidence = Math.min(volumeRatio * 2, 0.9);

            return { isTrending, rank, confidence };

        } catch (error) {
            console.error(`Trending check error: ${error.message}`);
            return { isTrending: false, rank: 999, confidence: 0 };
        }
    }

    // ====================================
    // HELPER METHODS
    // ====================================

    private async prepareBotWallets(
        botArmy: Array<{public_key: string, amount_sol: number, private_key?: string}>
    ): Promise<BotWallet[]> {
        const prepared: BotWallet[] = [];

        for (const bot of botArmy) {
            try {
                let privateKey = bot.private_key;
                
                if (!privateKey) {
                    // Fetch from backend
                    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
                    const response = await axios.post(
                        `${backendUrl}/creators/user/get-bot-private-key`,
                        {
                            bot_wallet: bot.public_key,
                            user_wallet: this.userWallet
                        },
                        {
                            headers: {
                                'X-API-Key': process.env.ONCHAIN_API_KEY,
                                'Content-Type': 'application/json'
                            },
                            timeout: 3000
                        }
                    );

                    if (response.data.success && response.data.private_key) {
                        privateKey = response.data.private_key;
                    }
                }

                if (privateKey) {
                    prepared.push({
                        public_key: bot.public_key,
                        private_key: privateKey,
                        amount_sol: bot.amount_sol
                    });
                }
            } catch (error) {
                console.error(`Failed to prepare bot ${bot.public_key}: ${error.message}`);
            }
        }

        console.log(`Prepared ${prepared.length}/${botArmy.length} bots`);
        return prepared;
    }

    private async getCurrentPrice(mint: PublicKey): Promise<number> {
        const bondingCurve = await BondingCurveFetcher.fetch(this.connection, mint, false);
        if (!bondingCurve) return 0;
        return Number(bondingCurve.virtual_sol_reserves) / LAMPORTS_PER_SOL;
    }

    private async getBotTokenBalance(mint: PublicKey, bot: BotWallet): Promise<number> {
        try {
            const ata = getAssociatedTokenAddressSync(
                new PublicKey(bot.public_key),
                mint,
                false,
                TOKEN_2022_PROGRAM_ID
            );

            const balanceInfo = await this.connection.getTokenAccountBalance(ata, 'processed');
            return Number(balanceInfo.value.amount);
        } catch {
            return 0;
        }
    }

    private async calculateTokenValue(mint: PublicKey, tokenAmount: number): Promise<number> {
        const bondingCurve = await BondingCurveFetcher.fetch(this.connection, mint, false);
        if (!bondingCurve) return 0;

        const solValue = BondingCurveMath.calculateSolForTokens(
            bondingCurve.virtual_sol_reserves,
            bondingCurve.virtual_token_reserves,
            BigInt(tokenAmount)
        );

        return Number(solValue) / LAMPORTS_PER_SOL;
    }

    private async executeEmergencyVolumeBoost(mint: PublicKey, bots: BotWallet[]) {
        console.log(`🚨 Emergency volume boost with ${bots.length} bots`);
        
        // Quick buy-sell cycle
        const buyResult = await this.executeBotBuysWave(mint, bots, {
            amountRange: [0.0005, 0.0015] as [number, number],
            delayRange: [50, 150],
            simultaneous: 3
        });

        await this.randomDelay(200, 500);

        const sellResult = await this.executeBotSellsWave(mint, bots, {
            percentageRange: [30, 60] as [number, number],
            delayRange: [100, 300],
            minSolValue: 0.0001
        });

        return buyResult.totalSol + sellResult.totalSol;
    }

    private async simulateWhaleActivity(
        mint: PublicKey,
        bots: BotWallet[]
    ): Promise<{volume: number, signatures: string[]}> {  // Add return type
        console.log(`🐋 Simulating whale activity...`);
        
        let totalVolume = 0;
        const signatures: string[] = [];
        
        // Select 1-2 "whale" bots (ones with more balance)
        const whaleBots = this.selectRandomBots(bots, 0.2).slice(0, 2);
        
        for (const whale of whaleBots) {
            try {
                // Larger buy (looks like a whale)
                const whaleAmount = this.randomInRange(0.003, 0.008); // 0.003-0.008 SOL
                
                const buyResult = await this.executeSingleBuy(mint, whale, [whaleAmount, whaleAmount]);
                
                if (buyResult.success) {
                    totalVolume += buyResult.amount;
                    if (buyResult.signature) signatures.push(buyResult.signature);
                }
                
                // Wait before next whale (organic timing)
                await this.randomDelay(3000, 8000);
                
                // Partial sell to create liquidity
                const tokenBalance = await this.getBotTokenBalance(mint, whale);
                if (tokenBalance > 0) {
                    const sellAmount = Math.floor(tokenBalance * 0.3); // Sell 30%
                    const sellResult = await this.executeSingleSell(mint, whale, sellAmount);
                    
                    if (sellResult.success) {
                        totalVolume += sellResult.solReceived || 0;
                        if (sellResult.signature) signatures.push(sellResult.signature);
                    }
                }
                
            } catch (error) {
                console.error(`Whale simulation error: ${error.message}`);
            }
        }
        
        return { volume: totalVolume, signatures };  // Return the object
    }

    private async simulateSocialProofTrades(
        mint: PublicKey,
        bots: BotWallet[]
    ): Promise<{volume: number, signatures: string[]}> {  // Add return type
        console.log(`📱 Simulating social proof trades...`);
        
        let totalVolume = 0;
        const signatures: string[] = [];
        
        // Use 30-40% of bots for small, frequent trades
        const socialBots = this.selectRandomBots(bots, 0.4);
        
        // Create 3-5 waves of trading
        const waveCount = Math.floor(this.randomInRange(3, 5));
        
        for (let wave = 0; wave < waveCount; wave++) {
            console.log(`   Wave ${wave + 1}: ${socialBots.length} bots`);
            
            // Small buys (0.0002 - 0.0008 SOL) - looks like retail traders
            const buyPromises = socialBots.map(bot => 
                this.executeSingleBuy(mint, bot, [0.0002, 0.0008])
            );
            
            const buyResults = await Promise.allSettled(buyPromises);
            
            // Track successful buys
            buyResults.forEach(result => {
                if (result.status === 'fulfilled' && result.value.success) {
                    totalVolume += result.value.amount;
                    if (result.value.signature) signatures.push(result.value.signature);
                }
            });
            
            // Wait between waves (makes it look like different traders)
            await this.randomDelay(2000, 5000);
            
            // Some sell pressure (20-40% of holdings)
            const sellPromises = socialBots.map(async (bot) => {
                try {
                    const tokenBalance = await this.getBotTokenBalance(mint, bot);
                    if (tokenBalance > 1000) { // Only if has tokens
                        const sellPercentage = this.randomInRange(20, 40) / 100;
                        const sellAmount = Math.floor(tokenBalance * sellPercentage);
                        return this.executeSingleSell(mint, bot, sellAmount);
                    }
                } catch (error) {
                    console.error(`Social sell error: ${error.message}`);
                    return null;
                }
            });
            
            const sellResults = await Promise.allSettled(sellPromises);
            
            // Track successful sells
            sellResults.forEach(result => {
                if (result.status === 'fulfilled' && result.value) {
                    totalVolume += result.value.solReceived || 0;
                    if (result.value.signature) signatures.push(result.value.signature);
                }
            });
            
            // Longer delay between waves
            if (wave < waveCount - 1) {
                await this.randomDelay(8000, 15000);
            }
        }
        
        return { volume: totalVolume, signatures };  // Return the object
    }

    // private async executeCreatorSell(
    //     mint: PublicKey,
    //     creatorWallet: string,
    //     percentage: number
    // ): Promise<{success: boolean, estimatedProfit?: number}> {
    //     // This integrates with your existing sell logic
    //     // For now, return success
    //     console.log(`   Creator sell simulation (${percentage}%)`);
    //     return { success: true, estimatedProfit: 0.05 }; // Placeholder
    // }

    // private async executeStaggeredBotSells(
    //     mint: PublicKey,
    //     bots: BotWallet[],
    //     percentage: number,
    //     delayMs: number
    // ): Promise<{successful: number, estimatedProfit: number}> {
    //     let successful = 0;
    //     let estimatedProfit = 0;

    //     for (const bot of bots) {
    //         try {
    //             // In production, this would execute actual sells
    //             successful++;
    //             estimatedProfit += 0.001; // Placeholder
                
    //             await this.randomDelay(delayMs * 0.7, delayMs * 1.3);
    //         } catch (error) {
    //             console.error(`Bot sell error: ${error.message}`);
    //         }
    //     }

    //     return { successful, estimatedProfit };
    // }

    // private determineSellStrategy(
    //     exitSignal: string,
    //     peakPrice: number
    // ): {
    //     creatorPercentage: number;
    //     botPercentage: number;
    //     delayBetweenSells: number;
    //     aggressiveness: 'conservative' | 'moderate' | 'aggressive';
    // } {
    //     const strategies = {
    //         price_peak: {
    //             creatorPercentage: 80,
    //             botPercentage: 90,
    //             delayBetweenSells: 1000,
    //             aggressiveness: 'aggressive' as const
    //         },
    //         volume_stagnation: {
    //             creatorPercentage: 60,
    //             botPercentage: 70,
    //             delayBetweenSells: 2000,
    //             aggressiveness: 'moderate' as const
    //         },
    //         profit_target: {
    //             creatorPercentage: 70,
    //             botPercentage: 80,
    //             delayBetweenSells: 1500,
    //             aggressiveness: 'moderate' as const
    //         },
    //         time_threshold: {
    //             creatorPercentage: 50,
    //             botPercentage: 60,
    //             delayBetweenSells: 3000,
    //             aggressiveness: 'conservative' as const
    //         }
    //     };

    //     return strategies[exitSignal as keyof typeof strategies] || strategies.time_threshold;
    // }

    private selectRandomBots(bots: BotWallet[], percentage: number): BotWallet[] {
        const count = Math.max(1, Math.floor(bots.length * percentage));
        const shuffled = [...bots].sort(() => Math.random() - 0.5);
        return shuffled.slice(0, count);
    }

    private selectBotsByPercentage(bots: BotWallet[], percentage: number): BotWallet[] {
        const count = Math.max(1, Math.floor(bots.length * percentage));
        return bots.slice(0, count);
    }

    private randomInRange(min: number, max: number): number {
        return min + Math.random() * (max - min);
    }

    private async randomDelay(minMs: number, maxMs: number): Promise<void> {
        const delay = this.randomInRange(minMs, maxMs);
        await new Promise(resolve => setTimeout(resolve, delay));
    }

    private updateProfitTracker(invested: number, returned: number): void {
        this.profitTracker.totalInvested += invested;
        this.profitTracker.totalReturned += returned;
        
        if (returned > invested * 0.9) { // At least 90% return considered successful
            this.profitTracker.successfulLaunches++;
        } else {
            this.profitTracker.failedLaunches++;
        }

        const totalLaunches = this.profitTracker.successfulLaunches + this.profitTracker.failedLaunches;
        const successRate = totalLaunches > 0 ? (this.profitTracker.successfulLaunches / totalLaunches) * 100 : 0;
        const totalROI = this.profitTracker.totalInvested > 0 ? 
            ((this.profitTracker.totalReturned - this.profitTracker.totalInvested) / this.profitTracker.totalInvested) * 100 : 0;

        console.log(`📈 Lifetime Stats: ${successRate.toFixed(1)}% success | ${totalROI.toFixed(1)}% ROI`);
    }

    // private async monitorVolumeMomentum(mint: PublicKey): Promise<boolean> {
    //     const samples = [];
    //     for(let i = 0; i < 5; i++) {
    //         const curve = await BondingCurveFetcher.fetch(this.connection, mint, false);
    //         samples.push(Number(curve.virtual_sol_reserves));
    //         await this.randomDelay(2000, 4000);
    //     }
        
    //     // Check if volume is accelerating
    //     const growthRates = samples.slice(1).map((val, idx) => (val - samples[idx]) / samples[idx]);
    //     const isAccelerating = growthRates.slice(1).every((rate, idx) => rate > growthRates[idx] * 0.8);
        
    //     return isAccelerating;
    // }
}




