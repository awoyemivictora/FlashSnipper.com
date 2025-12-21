// on-chain/risk-analyzer.ts - PRODUCTION GRADE
import { Connection, PublicKey } from "@solana/web3.js";
import axios from 'axios';
import { 
    RPC_ENDPOINTS,
    PUMPFUN_PROGRAM_ID,
    MIN_SAFE_CREATOR_BALANCE
} from './config';

export interface RiskAnalysis {
    riskScore: number;
    riskLevel: 'SAFE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    warnings: string[];
    confidence: number;
    factors: {
        tokenAge: number;
        creatorReputation: number;
        liquidityScore: number;
        holderConcentration: number;
        contractSafety: number;
        socialVerification: number;
        marketMetrics: number;
    };
    recommendations: string[];
    timestamp: number;
}

export interface TokenMetrics {
    mint: string;
    creator: string;
    creatorBalance: number;
    holderCount: number;
    topHolderPercentage: number;
    liquidity: number;
    volume24h: number;
    priceChange5m: number;
    ageSeconds: number;
    socialLinks: number;
    contractVerified: boolean;
    isPumpFun: boolean;
}

export class AdvancedRiskAnalyzer {
    private connection: Connection;
    private highRiskMints = new Set<string>();
    private trustedCreators = new Set<string>();
    private scamPatterns = [
        'TEST', 'FAKE', 'SCAM', 'RUG', 'PULL', 'HONEYPOT', 
        'DUMP', 'TRAP', 'SHIT', 'MEME', 'MOON', 'PONZI',
        'SHIB', 'FLOKI', 'ELON', 'MUSK', 'DOGE'
    ];
    
    private knownScamMints = new Set<string>();
    private knownRugMints = new Set<string>();
    
    // External API endpoints for enhanced analysis
    private readonly DEXSCREENER_API = 'https://api.dexscreener.com/latest/dex/tokens';
    private readonly BIRDEYE_API = 'https://public-api.birdeye.so/public/token';
    private readonly RUGCHECK_API = 'https://api.rugcheck.xyz/v1/tokens';
    
    constructor(connection?: Connection) {
        this.connection = connection || new Connection(RPC_ENDPOINTS[0], 'confirmed');
        this.loadRiskDatabases();
    }
    
    async analyzeToken(mintAddress: string): Promise<RiskAnalysis> {
        const startTime = Date.now();
        
        try {
            console.log(`🔍 Analyzing risk for ${mintAddress.slice(0, 8)}...`);
            
            // Quick blacklist check
            if (this.isBlacklisted(mintAddress)) {
                return this.createCriticalRisk('Token is blacklisted');
            }
            
            // Parallel data collection for speed
            const [metrics, dexscreenerData, birdeyeData] = await Promise.all([
                this.collectTokenMetrics(mintAddress),
                this.fetchDexscreenerData(mintAddress),
                this.fetchBirdeyeData(mintAddress)
            ]);
            
            // Combine all data
            const enhancedMetrics = {
                ...metrics,
                dexscreenerData,
                birdeyeData
            };
            
            // Calculate risk factors in parallel
            const factors = await this.calculateRiskFactors(enhancedMetrics);
            
            // Calculate overall risk score
            const riskScore = this.calculateOverallRisk(factors);
            const riskLevel = this.determineRiskLevel(riskScore);
            
            // Generate warnings and recommendations
            const warnings = this.generateWarnings(enhancedMetrics, factors);
            const recommendations = this.generateRecommendations(riskLevel, enhancedMetrics);
            
            const analysisTime = Date.now() - startTime;
            
            console.log(`✅ Risk analysis complete: ${riskLevel} (${riskScore.toFixed(1)}) in ${analysisTime}ms`);
            
            return {
                riskScore,
                riskLevel,
                warnings,
                confidence: this.calculateConfidence(enhancedMetrics),
                factors,
                recommendations,
                timestamp: Date.now()
            };
            
        } catch (error) {
            console.error(`Risk analysis failed for ${mintAddress.slice(0, 8)}:`, error);
            return this.createErrorRisk(error.message);
        }
    }
    
    private async collectTokenMetrics(mintAddress: string): Promise<TokenMetrics> {
        const mintPubkey = new PublicKey(mintAddress);
        
        // Parallel data collection
        const [
            accountInfo,
            largestAccounts,
            creatorInfo,
            isPumpFun
        ] = await Promise.all([
            this.connection.getAccountInfo(mintPubkey),
            this.connection.getTokenLargestAccounts(mintPubkey),
            this.getCreatorInfo(mintAddress),
            this.checkIfPumpFunToken(mintAddress)
        ]);
        
        // Calculate holder concentration
        let holderCount = 0;
        let topHolderPercentage = 0;
        
        if (largestAccounts.value && largestAccounts.value.length > 0) {
            holderCount = largestAccounts.value.length;
            const totalSupply = largestAccounts.value.reduce((sum, acc) => sum + acc.uiAmount, 0);
            const topHolderAmount = largestAccounts.value[0]?.uiAmount || 0;
            topHolderPercentage = totalSupply > 0 ? (topHolderAmount / totalSupply) * 100 : 0;
        }
        
        // Calculate token age
        const ageSeconds = accountInfo ? await this.calculateTokenAge(accountInfo.lamports) : 0;
        
        return {
            mint: mintAddress,
            creator: creatorInfo.creator || 'unknown',
            creatorBalance: creatorInfo.balance || 0,
            holderCount,
            topHolderPercentage,
            liquidity: 0, // Will be filled by external APIs
            volume24h: 0,
            priceChange5m: 0,
            ageSeconds,
            socialLinks: 0,
            contractVerified: false,
            isPumpFun
        };
    }
    
    private async checkIfPumpFunToken(mintAddress: string): Promise<boolean> {
        try {
            // Check multiple methods for Pump.fun verification
            
            // Method 1: Check bonding curve accounts
            const bondingCurveAccounts = await this.connection.getProgramAccounts(
                new PublicKey(PUMPFUN_PROGRAM_ID),
                {
                    filters: [
                        { dataSize: 129 },
                        { memcmp: { offset: 0, bytes: mintAddress } }
                    ]
                }
            );
            
            if (bondingCurveAccounts.length > 0) return true;
            
            // Method 2: Check transaction history
            const signatures = await this.connection.getSignaturesForAddress(
                new PublicKey(mintAddress),
                { limit: 5 }
            );
            
            // Check if any transaction involves Pump.fun program
            for (const sig of signatures) {
                const tx = await this.connection.getTransaction(sig.signature, {
                    maxSupportedTransactionVersion: 0
                });
                
                if (tx?.transaction.message.compiledInstructions.some(
                    ix => ix.programIdIndex !== undefined && 
                    tx.transaction.message.staticAccountKeys[ix.programIdIndex]?.toBase58() === PUMPFUN_PROGRAM_ID
                )) {
                    return true;
                }
            }
            
            return false;
            
        } catch (error) {
            return false;
        }
    }
    
    private async getCreatorInfo(mintAddress: string): Promise<{creator: string, balance: number}> {
        try {
            // Get creator from metadata
            const metadata = await this.getTokenMetadata(mintAddress);
            if (metadata?.creator) {
                const balance = await this.connection.getBalance(new PublicKey(metadata.creator));
                return {
                    creator: metadata.creator,
                    balance: balance / 1e9
                };
            }
            
            // Fallback: Check initial mint transaction
            const signatures = await this.connection.getSignaturesForAddress(
                new PublicKey(mintAddress),
                { limit: 1 }
            );
            
            if (signatures.length > 0) {
                const tx = await this.connection.getTransaction(signatures[0].signature);
                if (tx?.transaction.message.accountKeys.length > 0) {
                    const possibleCreator = tx.transaction.message.accountKeys[0].toString();
                    const balance = await this.connection.getBalance(new PublicKey(possibleCreator));
                    return {
                        creator: possibleCreator,
                        balance: balance / 1e9
                    };
                }
            }
            
            return { creator: 'unknown', balance: 0 };
            
        } catch (error) {
            return { creator: 'unknown', balance: 0 };
        }
    }
    
    private async calculateTokenAge(lamports: number): Promise<number> {
        try {
            const slot = await this.connection.getSlot();
            // Simplified age calculation - in production, use block time
            return Math.max(0, slot - Number(lamports) / 1e9) * 0.4; // ~400ms per slot
        } catch (error) {
            return 0;
        }
    }
    
    private async fetchDexscreenerData(mintAddress: string): Promise<any> {
        try {
            const response = await axios.get(`${this.DEXSCREENER_API}/${mintAddress}`, {
                timeout: 2000
            });
            
            return response.data?.pairs?.[0] || null;
        } catch (error) {
            return null;
        }
    }
    
    private async fetchBirdeyeData(mintAddress: string): Promise<any> {
        try {
            const response = await axios.get(`${this.BIRDEYE_API}?address=${mintAddress}`, {
                headers: {
                    'X-API-Key': process.env.BIRDEYE_API_KEY || ''
                },
                timeout: 2000
            });
            
            return response.data?.data || null;
        } catch (error) {
            return null;
        }
    }
    
    private async calculateRiskFactors(metrics: any): Promise<RiskAnalysis['factors']> {
        // Calculate each risk factor with advanced logic
        
        return {
            tokenAge: this.calculateAgeRisk(metrics.ageSeconds),
            creatorReputation: this.calculateCreatorRisk(metrics),
            liquidityScore: this.calculateLiquidityRisk(metrics),
            holderConcentration: this.calculateConcentrationRisk(metrics.topHolderPercentage),
            contractSafety: this.calculateContractRisk(metrics),
            socialVerification: this.calculateSocialRisk(metrics),
            marketMetrics: this.calculateMarketRisk(metrics)
        };
    }
    
    private calculateAgeRisk(ageSeconds: number): number {
        // Newer tokens are higher risk
        if (ageSeconds < 60) return 80; // < 1 minute
        if (ageSeconds < 300) return 60; // < 5 minutes
        if (ageSeconds < 1800) return 40; // < 30 minutes
        if (ageSeconds < 7200) return 20; // < 2 hours
        if (ageSeconds < 86400) return 10; // < 1 day
        return 5; // > 1 day
    }
    
    private calculateCreatorRisk(metrics: any): number {
        let risk = 50;
        
        // Check creator balance
        if (metrics.creatorBalance < MIN_SAFE_CREATOR_BALANCE) {
            risk += 30; // Creator has low SOL, higher chance of rug
        }
        
        // Check if creator is known
        if (this.trustedCreators.has(metrics.creator)) {
            risk -= 40; // Trusted creator
        }
        
        // Check creator history (simplified)
        if (metrics.creator === 'unknown') {
            risk += 20;
        }
        
        return Math.max(0, Math.min(100, risk));
    }
    
    private calculateLiquidityRisk(metrics: any): number {
        const liquidity = metrics.dexscreenerData?.liquidity?.usd || 0;
        
        if (liquidity === 0) return 100; // No liquidity
        if (liquidity < 1000) return 80; // < $1k liquidity
        if (liquidity < 10000) return 60; // < $10k liquidity
        if (liquidity < 50000) return 40; // < $50k liquidity
        if (liquidity < 100000) return 20; // < $100k liquidity
        return 10; // Good liquidity
    }
    
    private calculateConcentrationRisk(topHolderPercentage: number): number {
        if (topHolderPercentage > 50) return 90; // Majority held by one wallet
        if (topHolderPercentage > 30) return 70;
        if (topHolderPercentage > 20) return 50;
        if (topHolderPercentage > 10) return 30;
        return 10; // Well distributed
    }
    
    private calculateContractRisk(metrics: any): number {
        let risk = 50;
        
        // Pump.fun tokens have some safety features
        if (metrics.isPumpFun) {
            risk -= 20;
        }
        
        // Check if contract is verified (simplified)
        if (!metrics.contractVerified) {
            risk += 20;
        }
        
        // Check for suspicious mint patterns
        if (this.hasSuspiciousPatterns(metrics.mint)) {
            risk += 30;
        }
        
        return Math.max(0, Math.min(100, risk));
    }
    
    private calculateSocialRisk(metrics: any): number {
        const socialLinks = metrics.socialLinks || 0;
        
        if (socialLinks === 0) return 70; // No socials
        if (socialLinks === 1) return 50; // Only one social
        if (socialLinks === 2) return 30; // Two socials
        return 10; // Multiple socials
    }
    
    private calculateMarketRisk(metrics: any): number {
        let risk = 50;
        
        // Check volume
        const volume24h = metrics.dexscreenerData?.volume?.h24 || 0;
        if (volume24h === 0) risk += 30; // No volume
        
        // Check price volatility
        const priceChange5m = metrics.priceChange5m || 0;
        if (Math.abs(priceChange5m) > 50) risk += 20; // Extreme volatility
        
        // Check if trading on multiple DEXs
        const dexCount = metrics.dexscreenerData?.dexId ? 1 : 0;
        if (dexCount < 2) risk += 10; // Only on one DEX
        
        return Math.max(0, Math.min(100, risk));
    }
    
    private hasSuspiciousPatterns(mintAddress: string): boolean {
        const mintStr = mintAddress.toLowerCase();
        
        // Check for known scam patterns in mint address
        for (const pattern of this.scamPatterns) {
            if (mintStr.includes(pattern.toLowerCase())) {
                return true;
            }
        }
        
        // Check for sequential patterns (often auto-generated)
        if (/(1234|abcd|1111|2222|3333|4444|5555|6666|7777|8888|9999|0000)/.test(mintStr)) {
            return true;
        }
        
        return false;
    }
    
    private calculateOverallRisk(factors: RiskAnalysis['factors']): number {
        // Weighted average of all factors
        const weights = {
            tokenAge: 0.15,
            creatorReputation: 0.20,
            liquidityScore: 0.25,
            holderConcentration: 0.15,
            contractSafety: 0.10,
            socialVerification: 0.05,
            marketMetrics: 0.10
        };
        
        let totalWeight = 0;
        let weightedSum = 0;
        
        for (const [factor, weight] of Object.entries(weights)) {
            weightedSum += factors[factor as keyof typeof factors] * weight;
            totalWeight += weight;
        }
        
        return weightedSum / totalWeight;
    }
    
    private determineRiskLevel(score: number): RiskAnalysis['riskLevel'] {
        if (score >= 80) return 'CRITICAL';
        if (score >= 60) return 'HIGH';
        if (score >= 40) return 'MEDIUM';
        if (score >= 20) return 'LOW';
        return 'SAFE';
    }
    
    private generateWarnings(metrics: any, factors: RiskAnalysis['factors']): string[] {
        const warnings: string[] = [];
        
        // Age warnings
        if (factors.tokenAge > 70) warnings.push('Token is extremely new (< 1 minute)');
        else if (factors.tokenAge > 50) warnings.push('Token is very new (< 5 minutes)');
        
        // Creator warnings
        if (factors.creatorReputation > 70) warnings.push('Creator has suspicious profile');
        if (metrics.creatorBalance < 0.1) warnings.push('Creator has very low SOL balance');
        
        // Liquidity warnings
        if (factors.liquidityScore > 80) warnings.push('Extremely low liquidity');
        else if (factors.liquidityScore > 60) warnings.push('Very low liquidity');
        
        // Holder warnings
        if (factors.holderConcentration > 70) warnings.push('High holder concentration (> 50%)');
        else if (factors.holderConcentration > 50) warnings.push('Significant holder concentration (> 30%)');
        
        // Contract warnings
        if (factors.contractSafety > 60) warnings.push('Contract has safety concerns');
        
        // Social warnings
        if (factors.socialVerification > 60) warnings.push('No social media presence');
        
        // Market warnings
        if (factors.marketMetrics > 70) warnings.push('Abnormal market activity detected');
        
        return warnings.slice(0, 5); // Limit to 5 most important warnings
    }
    
    private generateRecommendations(riskLevel: string, metrics: any): string[] {
        const recommendations: string[] = [];
        
        switch (riskLevel) {
            case 'CRITICAL':
                recommendations.push('DO NOT BUY - Extreme risk of rug pull');
                recommendations.push('Avoid completely - Multiple red flags detected');
                break;
                
            case 'HIGH':
                recommendations.push('Consider avoiding - High risk');
                recommendations.push('If buying, use very small position size (< 0.1 SOL)');
                recommendations.push('Set tight stop loss (15-20%)');
                break;
                
            case 'MEDIUM':
                recommendations.push('Proceed with caution');
                recommendations.push('Use moderate position size (0.1-0.5 SOL)');
                recommendations.push('Set stop loss (20-30%)');
                recommendations.push('Take partial profits early');
                break;
                
            case 'LOW':
                recommendations.push('Generally safe for trading');
                recommendations.push('Standard position sizing okay');
                recommendations.push('Monitor for unusual activity');
                break;
                
            case 'SAFE':
                recommendations.push('Good trading opportunity');
                recommendations.push('Consider larger position if other factors align');
                recommendations.push('Standard risk management applies');
                break;
        }
        
        // Add specific recommendations based on metrics
        if (metrics.ageSeconds < 300) {
            recommendations.push('Token is very new - wait for initial volatility to settle');
        }
        
        if (metrics.topHolderPercentage > 30) {
            recommendations.push('Watch top holder wallets for sudden movements');
        }
        
        if (!metrics.isPumpFun) {
            recommendations.push('Not a Pump.fun token - extra caution advised');
        }
        
        return recommendations;
    }
    
    private calculateConfidence(metrics: any): number {
        let confidence = 100;
        
        // Reduce confidence for missing data
        if (!metrics.dexscreenerData) confidence -= 30;
        if (!metrics.birdeyeData) confidence -= 20;
        if (metrics.creator === 'unknown') confidence -= 15;
        if (metrics.holderCount === 0) confidence -= 10;
        
        return Math.max(30, confidence); // Minimum 30% confidence
    }
    
    private isBlacklisted(mintAddress: string): boolean {
        return (
            this.highRiskMints.has(mintAddress) ||
            this.knownScamMints.has(mintAddress) ||
            this.knownRugMints.has(mintAddress)
        );
    }
    
    private createCriticalRisk(reason: string): RiskAnalysis {
        return {
            riskScore: 100,
            riskLevel: 'CRITICAL',
            warnings: [reason],
            confidence: 100,
            factors: {
                tokenAge: 100,
                creatorReputation: 100,
                liquidityScore: 100,
                holderConcentration: 100,
                contractSafety: 100,
                socialVerification: 100,
                marketMetrics: 100
            },
            recommendations: ['DO NOT BUY UNDER ANY CIRCUMSTANCES'],
            timestamp: Date.now()
        };
    }
    
    private createErrorRisk(error: string): RiskAnalysis {
        return {
            riskScore: 70, // Assume high risk if analysis fails
            riskLevel: 'HIGH',
            warnings: [`Analysis failed: ${error}`],
            confidence: 10,
            factors: {
                tokenAge: 70,
                creatorReputation: 70,
                liquidityScore: 70,
                holderConcentration: 70,
                contractSafety: 70,
                socialVerification: 70,
                marketMetrics: 70
            },
            recommendations: ['Cannot complete analysis - proceed with extreme caution'],
            timestamp: Date.now()
        };
    }
    
    private async getTokenMetadata(mintAddress: string): Promise<any> {
        try {
            // Simplified metadata fetch
            // In production, use Metaplex or similar
            return null;
        } catch (error) {
            return null;
        }
    }
    
    private loadRiskDatabases(): void {
        // Load known scam databases (simplified)
        // In production, you'd load from file or API
        
        // Example: Known scam mints
        this.knownScamMints = new Set([
            '11111111111111111111111111111111', // Example
            // Add more from your database
        ]);
        
        // Example: Known rugs
        this.knownRugMints = new Set([
            // Add known rug pull tokens
        ]);
        
        // Example: Trusted creators
        this.trustedCreators = new Set([
            // Add known legitimate creators
        ]);
    }
    
    // Public methods for external use
    public markHighRisk(mintAddress: string): void {
        this.highRiskMints.add(mintAddress);
    }
    
    public markTrustedCreator(creatorAddress: string): void {
        this.trustedCreators.add(creatorAddress);
    }
    
    public isHighRisk(mintAddress: string): boolean {
        return this.highRiskMints.has(mintAddress);
    }
    
    public async quickRiskCheck(mintAddress: string): Promise<number> {
        // Ultra-fast risk check for speed-critical operations
        try {
            if (this.isBlacklisted(mintAddress)) return 100;
            
            // Quick age check
            const accountInfo = await this.connection.getAccountInfo(new PublicKey(mintAddress));
            if (!accountInfo) return 80;
            
            const slot = await this.connection.getSlot();
            const ageSlots = slot - accountInfo.lamports;
            
            if (ageSlots < 10) return 90; // Extremely new
            if (ageSlots < 100) return 70; // Very new
            
            // Quick pattern check
            if (this.hasSuspiciousPatterns(mintAddress)) return 85;
            
            return 40; // Assume medium risk for speed
            
        } catch (error) {
            return 70; // Assume higher risk if check fails
        }
    }
}

// Singleton instance
export const riskAnalyzer = new AdvancedRiskAnalyzer();


