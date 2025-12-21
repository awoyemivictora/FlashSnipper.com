import {
    Connection, PublicKey, TransactionInstruction,
    SystemProgram, SYSVAR_RENT_PUBKEY, Commitment, LAMPORTS_PER_SOL
} from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID, getAssociatedTokenAddressSync } from '@solana/spl-token';
import * as borsh from 'borsh';


// ============================================
// 1. EXACT IDL DEFINITIONS
// ============================================

// From IDL: programId: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
export const PUMP_FUN_PROGRAM_ID = new PublicKey('6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P');
export const PUMP_FUN_GLOBAL = new PublicKey('4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf');
export const FEE_PROGRAM_ID = new PublicKey('pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ');
export const SOL_MINT = new PublicKey('So11111111111111111111111111111111111111112');

export const PROTOCOL_FEE_RECIPIENT = new PublicKey('CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM');

export const TOKEN_2022_PROGRAM_ID = new PublicKey('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb');

// BondingCurve structure from IDL
export class BondingCurve {
    virtual_token_reserves: bigint;
    virtual_sol_reserves: bigint;
    real_token_reserves: bigint;
    real_sol_reserves: bigint;
    token_total_supply: bigint;
    complete: boolean;
    creator: PublicKey;

    constructor(fields: {
        virtual_token_reserves: bigint,
        virtual_sol_reserves: bigint,
        real_token_reserves: bigint,
        real_sol_reserves: bigint,
        token_total_supply: bigint,
        complete: boolean,
        creator: PublicKey,
    }) {
        Object.assign(this, fields);
    }

    static decode(data: Buffer): BondingCurve {
        let offset = 8;  // Skip the 8-byte Anchor discriminator
        
        const virtual_token_reserves = data.readBigUInt64LE(offset);
        offset += 8;
        
        const virtual_sol_reserves = data.readBigUInt64LE(offset);
        offset += 8;
        
        const real_token_reserves = data.readBigUInt64LE(offset);
        offset += 8;
        
        const real_sol_reserves = data.readBigUInt64LE(offset);
        offset += 8;
        
        const token_total_supply = data.readBigUInt64LE(offset);
        offset += 8;
        
        const complete = data.readUInt8(offset) !== 0;
        offset += 1;
        
        const creator = new PublicKey(data.slice(offset, offset + 32));
        
        return new BondingCurve({
            virtual_token_reserves,
            virtual_sol_reserves,
            real_token_reserves,
            real_sol_reserves,
            token_total_supply,
            complete,
            creator
        });
    }
}

// ============================================
// 2. PDA HELPERS (EXACT FROM IDL SEEDS)
// ============================================

export class PumpFunPda {
    // Global PDA: seeds = ["global"]
    static getGlobal(): PublicKey {
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("global")],
            PUMP_FUN_PROGRAM_ID
        );
        return pda;
    }

    // BondingCurve PDA: seeds = ["bonding-curve", mint]
    static getBondingCurve(mint: PublicKey): PublicKey {
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("bonding-curve"), mint.toBuffer()],
            PUMP_FUN_PROGRAM_ID
        );
        return pda;
    }

    // Associated Bonding Curve (Token Account)
    static getAssociatedBondingCurve(
        bondingCurve: PublicKey,
        mint: PublicKey
        ): PublicKey {
        return getAssociatedTokenAddressSync(
            mint,
            bondingCurve,
            true, // allowOwnerOffCurve (PDA)
            TOKEN_2022_PROGRAM_ID
        );
    }

    // Creator Vault: seeds = ["creator-vault", bonding_curve.creator]
    static getCreatorVault(creator: PublicKey): PublicKey {
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("creator-vault"), creator.toBuffer()],
            PUMP_FUN_PROGRAM_ID
        );
        return pda;
    }

    // Event Authority: seeds = ["__event_authority"]
    static getEventAuthority(): PublicKey {
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("__event_authority")],
            PUMP_FUN_PROGRAM_ID
        );
        return pda;
    }

    // Global Volume Accumulator: seeds = ["global_volume_accumulator"]
    static getGlobalVolumeAccumulator(): PublicKey {
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("global_volume_accumulator")],
            PUMP_FUN_PROGRAM_ID
        );
        return pda;
    }

    // User Volume Accumulator: seeds = ["user_volume_accumulator", user]
    static getUserVolumeAccumulator(user: PublicKey): PublicKey {
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("user_volume_accumulator"), user.toBuffer()],
            PUMP_FUN_PROGRAM_ID
        );
        return pda;
    }

    // Fee Config: seeds = ["fee_config", <specific 32-byte array>], program = FEE_PROGRAM_ID
    static getFeeConfig(): PublicKey {
        const FEE_CONFIG_SEED = new Uint8Array([
            1, 86, 224, 246, 147, 102, 90, 207, 68, 219, 21, 104, 191, 23, 91, 170,
            81, 137, 203, 151, 245, 210, 255, 59, 101, 93, 43, 182, 253, 109, 24, 176
        ]);
        
        const [pda] = PublicKey.findProgramAddressSync(
            [Buffer.from("fee_config"), Buffer.from(FEE_CONFIG_SEED)],
            FEE_PROGRAM_ID
        );
        return pda;
    }

}


// ============================================
// 3. INSTRUCTION BUILDERS (EXACT BYTE LAYOUT)
// ============================================

export class PumpFunInstructionBuilder {
    // Discriminators from IDL
    private static readonly BUY_DISCRIMINATOR = Buffer.from([102, 6, 61, 18, 1, 218, 235, 234]);
    private static readonly BUY_EXACT_SOL_IN_DISCRIMINATOR = Buffer.from([56, 252, 116, 8, 158, 223, 205, 95]);
    private static readonly SELL_DISCRIMINATOR = Buffer.from([51, 230, 133, 164, 1, 127, 131, 173]);

    static debugInstruction(instruction: TransactionInstruction): void {
        console.log('🔍 INSTRUCTION DEBUG:');
        console.log(`   Program: ${instruction.programId.toBase58()}`);
        console.log(`   Data length: ${instruction.data.length} bytes`);
        console.log(`   Data (hex): ${Buffer.from(instruction.data).toString('hex')}`);
        console.log(`   Keys: ${instruction.keys.length}`);
        instruction.keys.forEach((key, i) => {
            console.log(`     ${i}: ${key.pubkey.toBase58().slice(0, 8)}... (signer: ${key.isSigner}, writable: ${key.isWritable})`);
        });
    }

    // private static encodeBuy(
    //     solIn: bigint,
    //     minTokensOut: bigint,
    //     trackVolume: boolean
    // ): Buffer {

    //     const args = Buffer.alloc(8 + 8 + 2);
    //     let offset = 0;

    //     // solIn (u64)
    //     args.writeBigUInt64LE(solIn, offset);
    //     offset += 8;

    //     // minTokensOut (u64)
    //     args.writeBigUInt64LE(minTokensOut, offset);
    //     offset += 8;

    //     // Option<bool> track_volume
    //     if (trackVolume) {
    //         args.writeUInt8(1, offset);     // Some
    //         args.writeUInt8(1, offset + 1); // true
    //     } else {
    //         args.writeUInt8(0, offset);     // None
    //         args.writeUInt8(0, offset + 1);
    //     }

    //     return Buffer.concat([
    //         PumpFunInstructionBuilder.BUY_EXACT_SOL_IN_DISCRIMINATOR,
    //         args,
    //     ]);
    // }

    
    private static encodeBuy(
        tokensOut: bigint,      // Amount of tokens to buy
        maxSolCost: bigint      // Maximum SOL to spend
    ): Buffer {
        const args = Buffer.alloc(16);
        let offset = 0;

        // amount (tokensOut) - u64
        args.writeBigUInt64LE(tokensOut, offset);
        offset += 8;

        // max_sol_cost - u64  
        args.writeBigUInt64LE(maxSolCost, offset);

        return Buffer.concat([
            PumpFunInstructionBuilder.BUY_DISCRIMINATOR,
            args,
        ]);
    }

     private static encodeBuyExactSolIn(
        solIn: bigint,
        minTokensOut: bigint
        ): Buffer {
        const args = Buffer.alloc(16 + 1);
        let offset = 0;

        args.writeBigUInt64LE(solIn, offset);
        offset += 8;

        args.writeBigUInt64LE(minTokensOut, offset);
        offset += 8;

        // Option<bool> = None
        args.writeUInt8(0, offset);

        return Buffer.concat([
            PumpFunInstructionBuilder.BUY_EXACT_SOL_IN_DISCRIMINATOR,
            args
        ]);
    }




    /**
     * Build buy_exact_sol_in instruction (Professional sniper method)
     * @param user The buyer's wallet (signer)
     * @param mint Token mint address
     * @param userAta User's associated token account for the mint
     * @param creator Creator address (from bonding curve)
     * @param spendableSolIn Max SOL in lamports to spend
     * @param minTokensOut Minimum tokens to receive (slippage control)
     * @param trackVolume Whether to track volume (should be true for incentives)
     */

    static buildBuyExactSolIn(
    user: PublicKey,
    mint: PublicKey,
    userAta: PublicKey,
    creator: PublicKey,
    solIn: bigint,
    minTokensOut: bigint
): TransactionInstruction {

    console.log(`🔧 Building BUY instruction (using buy instructions format according to pump.fun program IDL!)`);

    // Get all PDAs
    const global = PumpFunPda.getGlobal();
    const bondingCurve = PumpFunPda.getBondingCurve(mint);
    const associatedBondingCurve = PumpFunPda.getAssociatedBondingCurve(bondingCurve, mint);
    const creatorVault = PumpFunPda.getCreatorVault(creator);
    const eventAuthority = PumpFunPda.getEventAuthority();
    const feeConfig = PumpFunPda.getFeeConfig();

    // Volume accumulators - check if they exist
    const globalVolumeAccumulator = PumpFunPda.getGlobalVolumeAccumulator();
    const userVolumeAccumulator = PumpFunPda.getUserVolumeAccumulator(user);

    console.log(`📊 Volume accounts:`);
    console.log(`   Global: ${globalVolumeAccumulator.toBase58().slice(0, 8)}...`);
    console.log(`   User: ${userVolumeAccumulator.toBase58().slice(0, 8)}...`);

    // CRITICAL FIX: SOL ATA uses regular Token Program, NOT Token-2022!
    // const feeRecipient = getAssociatedTokenAddressSync(
    //     SOL_MINT,
    //     feeConfig,
    //     true,
    //     TOKEN_PROGRAM_ID  // SOL is regular SPL token, not Token-2022
    // );

    // EXACT 16 accounts as per IDL
    return new TransactionInstruction({
        programId: PUMP_FUN_PROGRAM_ID,
        keys: [
            // 0: global
            { pubkey: global, isSigner: false, isWritable: false },
            // 1: fee_recipient
            { pubkey: PROTOCOL_FEE_RECIPIENT, isSigner: false, isWritable: true },
            // 2: mint
            { pubkey: mint, isSigner: false, isWritable: false },
            // 3: bonding_curve
            { pubkey: bondingCurve, isSigner: false, isWritable: true },
            // 4: associated_bonding_curve
            { pubkey: associatedBondingCurve, isSigner: false, isWritable: true },
            // 5: associated_user
            { pubkey: userAta, isSigner: false, isWritable: true },
            // 6: user
            { pubkey: user, isSigner: true, isWritable: true },
            // 7: system_program
            { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
            // 8: token_program
            { pubkey: TOKEN_2022_PROGRAM_ID, isSigner: false, isWritable: false },
            // 9: creator_vault
            { pubkey: creatorVault, isSigner: false, isWritable: true },
            // 10: event_authority
            { pubkey: eventAuthority, isSigner: false, isWritable: false },
            // 11: program
            { pubkey: PUMP_FUN_PROGRAM_ID, isSigner: false, isWritable: false },
            // 12: global_volume_accumulator
            { pubkey: globalVolumeAccumulator, isSigner: false, isWritable: true },
            // 13: user_volume_accumulator
            { pubkey: userVolumeAccumulator, isSigner: false, isWritable: true },
            // 14: fee_config
            { pubkey: feeConfig, isSigner: false, isWritable: false },
            // 15: fee_program
            { pubkey: FEE_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        // data: PumpFunInstructionBuilder.encodeBuy(tokensOut, maxSolCost),
        data: PumpFunInstructionBuilder.encodeBuyExactSolIn(solIn, minTokensOut),
    });
}


    /**
     * Build sell instruction
     * @param user The seller's wallet (signer)
     * @param mint Token mint address
     * @param userAta User's associated token account
     * @param creator Creator address
     * @param amount Tokens to sell in lamports
     * @param minSolOutput Minimum SOL to receive (slippage control)
     */
    static buildSell(
        user: PublicKey,
        mint: PublicKey,
        userAta: PublicKey,
        creator: PublicKey,
        amount: bigint,           // tokens to sell (in base units)
        minSolOutput: bigint      // minimum SOL to receive (slippage protection)
    ): TransactionInstruction {

        console.log(`🔧 Building SELL instruction for ${mint.toBase58().slice(0, 8)}...`);

        // PDAs
        const global = PumpFunPda.getGlobal();
        const bondingCurve = PumpFunPda.getBondingCurve(mint);
        const associatedBondingCurve = PumpFunPda.getAssociatedBondingCurve(bondingCurve, mint);
        const creatorVault = PumpFunPda.getCreatorVault(creator);
        const eventAuthority = PumpFunPda.getEventAuthority();
        const feeConfig = PumpFunPda.getFeeConfig();

        // Encode instruction data: discriminator + amount (u64) + min_sol_output (u64)
        const args = Buffer.alloc(16);
        args.writeBigUInt64LE(amount, 0);
        args.writeBigUInt64LE(minSolOutput, 8);

        const data = Buffer.concat([
            this.SELL_DISCRIMINATOR,  // [51, 230, 133, 164, 1, 127, 131, 173]
            args
        ]);

        // EXACT 14 accounts in order from current IDL
        return new TransactionInstruction({
            programId: PUMP_FUN_PROGRAM_ID,
            keys: [
                // 0: global
                { pubkey: global, isSigner: false, isWritable: false },
                // 1: fee_recipient (hardcoded protocol wallet)
                { pubkey: PROTOCOL_FEE_RECIPIENT, isSigner: false, isWritable: true },
                // 2: mint
                { pubkey: mint, isSigner: false, isWritable: false },
                // 3: bonding_curve
                { pubkey: bondingCurve, isSigner: false, isWritable: true },
                // 4: associated_bonding_curve
                { pubkey: associatedBondingCurve, isSigner: false, isWritable: true },
                // 5: associated_user (user's ATA for the token)
                { pubkey: userAta, isSigner: false, isWritable: true },
                // 6: user (signer)
                { pubkey: user, isSigner: true, isWritable: true },
                // 7: system_program
                { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
                // 8: creator_vault
                { pubkey: creatorVault, isSigner: false, isWritable: true },
                // 9: token_program → Regular Token Program (NOT Token-2022!)
                { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
                // 10: event_authority
                { pubkey: eventAuthority, isSigner: false, isWritable: false },
                // 11: program (self-reference)
                { pubkey: PUMP_FUN_PROGRAM_ID, isSigner: false, isWritable: false },
                // 12: fee_config
                { pubkey: feeConfig, isSigner: false, isWritable: false },
                // 13: fee_program
                { pubkey: FEE_PROGRAM_ID, isSigner: false, isWritable: false },
            ],
            data,
        });
    }
}

// ============================================
// 4. BONDING CURVE MATH & STATE MANAGEMENT
// ============================================

export class BondingCurveMath {
    /**
     * Calculate token output for given SOL input (before fees)
     * Using constant product formula: x * y = k
     * where x = virtual_sol_reserves, y = virtual_token_reserves
     */
    static calculateTokensForSol(
        virtualSolReserves: bigint,
        virtualTokenReserves: bigint,
        solInput: bigint
    ): bigint {
        if (virtualSolReserves === 0n || solInput === 0n) return 0n;
        
        // x' = x + Δx
        const newVirtualSol = virtualSolReserves + solInput;
        
        // y' = k / x'
        const k = virtualSolReserves * virtualTokenReserves;
        const newVirtualToken = k / newVirtualSol;
        
        // Δy = y - y'
        const tokensOut = virtualTokenReserves - newVirtualToken;
        
        return tokensOut;
    }

    /**
     * Calculate SOL output for given token input (before fees)
     */
    static calculateSolForTokens(
        virtualSolReserves: bigint,
        virtualTokenReserves: bigint,
        tokenInput: bigint
    ): bigint {
        if (virtualTokenReserves === 0n || tokenInput === 0n) return 0n;
        
        // y' = y + Δy
        const newVirtualToken = virtualTokenReserves + tokenInput;
        
        // x' = k / y'
        const k = virtualSolReserves * virtualTokenReserves;
        const newVirtualSol = k / newVirtualToken;
        
        // Δx = x - x'
        const solOut = virtualSolReserves - newVirtualSol;
        
        return solOut;
    }

    /**
     * Apply fees to amount (protocol + creator fees)
     */
    static applyFees(
        amount: bigint,
        feeBasisPoints: bigint,
        creatorFeeBasisPoints: bigint
    ): { netAmount: bigint, totalFee: bigint } {
        const totalFeeBps = feeBasisPoints + creatorFeeBasisPoints;
        const fee = (amount * totalFeeBps) / 10000n;
        const netAmount = amount - fee;
        
        return { netAmount, totalFee: fee };
    }

    /**
     * Calculate with slippage tolerance
     */
    static applySlippage(amount: bigint, slippageBps: number): bigint {
        const slippageRate = BigInt(slippageBps);
        const minAmount = (amount * (10000n - slippageRate)) / 10000n;
        return minAmount > 0n ? minAmount : 1n;
    }
}

export class BondingCurveFetcher {
    private static cache = new Map<string, { data: BondingCurve, timestamp: number }>();
    private static readonly CACHE_TTL = 2000; // 2 seconds

    /**
     * Fetch and decode bonding curve state (with caching)
     */
    static async fetch(
        connection: Connection,
        mint: PublicKey,
        useCache: boolean = true,
        retryCount: number = 3
    ): Promise<BondingCurve | null> {
        const cacheKey = mint.toBase58();
        
        if (useCache) {
            const cached = this.cache.get(cacheKey);
            if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
                return cached.data;
            }
        }

        for (let attempt = 0; attempt < retryCount; attempt++) {
            try {
                const bondingCurve = PumpFunPda.getBondingCurve(mint);
                console.log(`📊 Fetching bonding curve for ${mint.toBase58().slice(0, 8)}...`);
                
                // const accountInfo = await connection.getAccountInfo(bondingCurve, 'confirmed');
                const accountInfo = await connection.getAccountInfo(bondingCurve, 'processed'); // For faster data visibility
                
                if (!accountInfo) {
                    console.log(`❌ Bonding curve not found for mint: ${mint.toBase58()}`);
                    if (attempt < retryCount - 1) {
                        await new Promise(resolve => setTimeout(resolve, 200 * (attempt + 1)));
                        continue;
                    }
                    return null;
                }

                // Check if account is initialized (has data)
                if (accountInfo.data.length < 65) { // Minimum size for bonding curve
                    console.log(`⚠️ Bonding curve account too small: ${accountInfo.data.length} bytes`);
                    if (attempt < retryCount - 1) {
                        await new Promise(resolve => setTimeout(resolve, 200 * (attempt + 1)));
                        continue;
                    }
                    return null;
                }

                const curveData = BondingCurve.decode(accountInfo.data);
                
                // Update cache
                this.cache.set(cacheKey, {
                    data: curveData,
                    timestamp: Date.now()
                });

                console.log(`✅ Bonding curve found: ${Number(curveData.virtual_sol_reserves) / LAMPORTS_PER_SOL} SOL, ${curveData.virtual_token_reserves} tokens`);
                return curveData;
                
            } catch (error) {
                console.error(`Attempt ${attempt + 1}/${retryCount} failed for ${mint.toBase58()}:`, error);
                if (attempt < retryCount - 1) {
                    await new Promise(resolve => setTimeout(resolve, 200 * (attempt + 1)));
                }
            }
        }
        
        console.error(`❌ Failed to fetch bonding curve for ${mint.toBase58()} after ${retryCount} attempts`);
        return null;
    }

    /**
     * Check if curve is complete (migrated to Raydium)
     */
    static isComplete(curve: BondingCurve): boolean {
        return curve.complete;
    }

    /**
     * Get creator from bonding curve
     */
    static getCreator(curve: BondingCurve): PublicKey {
        return curve.creator;
    }
}