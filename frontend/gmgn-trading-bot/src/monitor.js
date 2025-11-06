import { VersionedTransaction, Connection } from '@solana/web3.js';
import fetch from 'node-fetch';
import client from '../db/index.js';
import { getWallet } from './wallet.js';
import { sleep, sendTelegramMessage } from './utils.js';
import dotenv from 'dotenv';
import logger from './logger.js';
import { getTokenPrice, getReceivedSolAmount } from './token_logics.js';

dotenv.config();

const outputToken = 'So11111111111111111111111111111111111111112';
// const amount = '10000000';               // Base units for token
const slippageBps = 50;  



const RPC_ENDPOINT = 'https://api.mainnet-beta.solana.com'; // Or your preferred RPC
const slippage = 1; // 1% slippage



dotenv.config();

const API_HOST = process.env.API_HOST;
const connection = new Connection('https://api.mainnet-beta.solana.com');



async function monitorPositions() {
    try {
        // IMPORTANT: Add an 'is_sold' flag to your database to prevent re-monitoring/re-selling sold tokens
        // You'll need to run: ALTER TABLE token_metadata ADD COLUMN is_sold BOOLEAN DEFAULT FALSE;
        const result = await client.query("SELECT * FROM token_metadata WHERE is_bought = true AND is_sold = false");
        const tokens = result.rows;

        logger.info(`🔄 Checking for stop loss and take profit triggers...`);
        logger.info(`📝 Found ${tokens.length} monitoring tokens.`);

        for (const token of tokens) {
            // Destructure relevant fields from the database
            const { mint_address, entry_price, stop_loss, take_profit, token_amounts_purchased, token_name } = token;
            // Note: 'buy_price' is likely the same as 'entry_price' based on your trader.js,
            // so using 'entry_price' from the DB is clearer for cost basis.
            // 'price_usd' was in your original snippet, but if it's just a snapshot, current price is better.

            // Basic validation: Ensure we have purchase amount to calculate total value
            if (!token_amounts_purchased || token_amounts_purchased <= 0) {
                logger.error(`❌ Missing or invalid 'token_amounts_purchased' for ${mint_address}. Skipping this token.`);
                continue;
            }

            try {
                // 1. Fetch the current price per unit of the token
                const currentTokenPricePerUnit = await getTokenPrice(mint_address);
                if (isNaN(currentTokenPricePerUnit) || currentTokenPricePerUnit === null) {
                    logger.error(`❌ Could not fetch a valid current price for token ${mint_address}. Skipping monitoring for this token.`);
                    continue;
                }

                // 2. Calculate the current TOTAL USD value of your holdings for this token
                const currentTotalHoldingValue = currentTokenPricePerUnit * token_amounts_purchased;

                // Log for clarity and debugging
                logger.info(`🔍 Monitoring ${token_name} (${mint_address}):`);
                logger.info(`    - Current Price (Per Unit): $${currentTokenPricePerUnit.toFixed(9)}`);
                logger.info(`    - Current Total Holding Value: $${currentTotalHoldingValue.toFixed(6)}`);
                logger.info(`    - Original Buy Total (Entry): $${entry_price.toFixed(6)}`);
                logger.info(`    - Target Stop Loss (Total): $${stop_loss.toFixed(6)}`);
                logger.info(`    - Target Take Profit (Total): $${take_profit.toFixed(6)}`);


                // 3. Check for take profit (comparing total holding value to total take profit target)
                if (currentTotalHoldingValue >= take_profit) {
                    logger.info(`💰 Token ${token_name} (${mint_address}) reached TAKE PROFIT at total value $${currentTotalHoldingValue.toFixed(6)}! Initiating sell.`);
                    // Call sellToken function
                    // Pass the current price per unit, original total buy price, total tokens held, and sell reason
                    await sellToken(mint_address, currentTokenPricePerUnit, entry_price, token_amounts_purchased, "Take Profit");

                    // Mark the position as sold in the database
                    await client.query(
                        `UPDATE token_metadata 
                         SET is_sold = true, 
                             sell_timestamp = NOW(), 
                             sell_price = $1, 
                             sell_reason = $2 
                         WHERE mint_address = $3`,
                        [currentTotalHoldingValue, "Take Profit", mint_address] // Use currentTotalHoldingValue as sell_price
                    );
                } 
                // 4. Check for stop loss (comparing total holding value to total stop loss target)
                else if (currentTotalHoldingValue <= stop_loss) {
                    logger.info(`🔻 Token ${token_name} (${mint_address}) hit STOP LOSS at total value $${currentTotalHoldingValue.toFixed(6)}! Initiating sell.`);
                    // Call sellToken function
                    // Fix the typo 'currencurrentTokenPricetPrice' from your original code
                    await sellToken(mint_address, currentTokenPricePerUnit, entry_price, token_amounts_purchased, "Stop Loss");

                    // Mark the position as sold in the database
                    await client.query(
                        `UPDATE token_metadata 
                         SET is_sold = true, 
                             sell_timestamp = NOW(), 
                             sell_price = $1, 
                             sell_reason = $2 
                         WHERE mint_address = $3`,
                        [currentTotalHoldingValue, "Stop Loss", mint_address] // Use currentTotalHoldingValue as sell_price
                    );
                }
                else {
                    logger.info(`⏳ ${token_name}: Haven't reached TAKE PROFIT OR STOP-LOSS YET!`);
                }
            } catch (error) {
                logger.error(`❌ Error monitoring token ${mint_address}: ${error.message}`);
            }
        }
    } catch (error) {
        logger.error("❌ Error in monitoring positions:", error);
    }
}

export default monitorPositions;















// We'll route the selling logic to 3 different providers: Jupiter, OKX and DFlow
async function sellToken(mintAddress, sellPrice, buy_price, token_amounts_purchased, reason) {
    let signature;
    let swapResponse;
    let quoteResponse;
    let providerUsed = 'none';
    
    try {
        const wallet = getWallet();
        const connection = new Connection(RPC_ENDPOINT, {
            commitment: 'confirmed',
            disableRetryOnRateLimit: false
        });

        // 2. Try multiple swap providers in sequence
        const providers = [
            { name: 'DFlow', trySwap: tryDFlowSwap },
            { name: 'Jupiter', trySwap: tryJupiterSwap },
            { name: 'OKX', trySwap: tryOKXSwap },
        ];

        let lastError;
        for (const provider of providers) {
            try {
                logger.info(`Attempting swap with ${provider.name}`);
                const result = await provider.trySwap(mintAddress, token_amounts_purchased, wallet, connection);
                signature = result.signature;
                swapResponse = result.swapResponse;
                quoteResponse = result.quoteResponse;
                providerUsed = provider.name;
                break; // Success, exit the loop
            } catch (error) {
                lastError = error;
                logger.warn(`Swap with ${provider.name} failed: ${error.message}`);
                if (provider.name !== 'DFlow') {
                    await new Promise(resolve => setTimeout(resolve, 1000)); // Short delay between providers
                }
            }
        }

        if (!signature) {
            throw lastError || new Error('All swap providers failed');
        }

        logger.info(`Transaction sent with ${providerUsed}: ${signature}`);

        // 3. Wait for confirmation with detailed monitoring
        const confirmation = await connection.confirmTransaction({
            signature,
            lastValidBlockHeight: swapResponse.lastValidBlockHeight,
            blockhash: swapResponse.blockhash || (swapResponse.swapTransaction ? 
                VersionedTransaction.deserialize(Buffer.from(swapResponse.swapTransaction, 'base64')).message.recentBlockhash : undefined)
        }, 'confirmed');

        if (confirmation.value.err) {
            const txUrl = `https://solscan.io/tx/${signature}`;
            logger.error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}\n${txUrl}`);
            throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
        }

        logger.info(`Transaction confirmed: https://solscan.io/tx/${signature}`);


        // Calculate actual received amount
        const receivedSOLAmount = await getReceivedSolAmount(signature);
        // We get the current price of solana and also for the token
        const currentSOLPrice = await getTokenPrice(outputToken)
        const currentTokenPrice = await getTokenPrice(mintAddress)
        // Now, we get the amount of USD we received after selling the token
        const receiveUSDAmount = currentSOLPrice * receivedSOLAmount

        // So since we used 10000000 lamport of sol to buy the token initially in trader.js
        // and we got the price_usd == amountUSD of the token from the quote response we sent to gmgn
        // Now, to calculate the profit, we have to first get the amount of sol of we received back when 
        // we swap it on either Jupiter, Dflow or OKX
        // then once we've gotten the amount of SOL gotten, then we can multiply it by the current price of SOL
        // which we can get from the getTokenPrice(), 
        // after that, we can now minus it from our buy_price we have stored in the database coming from the monitor function
        // that'll give us our profit for the token
        const profit = receiveUSDAmount - buy_price;

        // Update database
        await client.query(
            `UPDATE token_metadata 
             SET is_bought = false, 
                 sell_price = $1, 
                 sol_amounts_received = $2,
                 sell_timestamp = NOW(), 
                 profit_usd = $3, 
                 sell_tx_hash = $4,
                 sell_attempts = 0,
                 status = 'sold',
                 swap_provider = $5
             WHERE mint_address = $6`,
            [currentTokenPrice, receivedSOLAmount, profit, signature, providerUsed, mintAddress]
        );

        // Success message
        const message = `💸 *Token Sold Successfully!*
            🗓 *Date:* ${new Date().toLocaleString()}
            🪙 *Token:* \`${mintAddress}\`
            💰 *Received:* $${receivedSOLAmount.toFixed(6)}
            📉 *Entry Price:* $${token.buy_price.toFixed(6)}
            🚀 *Profit:* $${profit.toFixed(6)}
            🔄 *Provider:* ${providerUsed}
            🔗 *Tx:* [Solscan](https://solscan.io/tx/${signature})`;
                    
        await sendTelegramMessage(message);
        return { success: true, signature, receivedSOLAmount, providerUsed };

    } catch (error) {
        logger.error(`❌ Error selling token ${mintAddress}:`, {
            error: error.message,
            stack: error.stack,
            quoteResponse,
            swapResponse,
            signature,
            providerUsed
        });
        
        // Update database with failure
        await client.query(
            `UPDATE token_metadata 
             SET sell_attempts = COALESCE(sell_attempts, 0) + 1,
                 last_sell_attempt = NOW(),
                 status = CASE WHEN COALESCE(sell_attempts, 0) + 1 >= 3 THEN 'failed' ELSE 'pending_sell' END,
                 last_error = $2,
                 swap_provider = $3
             WHERE mint_address = $1`,
            [mintAddress, error.message, providerUsed]
        );
        
        // Send detailed error notification
        const attempts = await getSellAttempts(mintAddress);
        if (attempts <= 1) {
            await sendTelegramMessage(
                `⚠️ *Failed to sell token*: \`${mintAddress}\`\n` +
                `📛 *Error:* ${error.message}\n` +
                `🔄 *Provider:* ${providerUsed}\n` +
                `🔗 *Tx:* ${signature ? `https://solscan.io/tx/${signature}` : 'N/A'}\n` +
                `💾 *Value:* $${tokenValue?.toFixed(6) || 'N/A'}\n` +
                `🔄 *Attempt:* ${attempts + 1}/3`
            );
        }

        return { 
            success: false, 
            error: error.message, 
            signature,
            quoteResponse,
            swapResponse,
            providerUsed
        };
    }
}





// Jupiter Swap Implementation
async function tryJupiterSwap(mintAddress, token_amounts_purchased, wallet, connection) {
    // 1. Get Quote
    const quoteUrl = `https://lite-api.jup.ag/swap/v1/quote?inputMint=${mintAddress}&outputMint=${outputToken}&amount=${token_amounts_purchased}&slippageBps=${Math.floor(slippage * 100)}&dynamicSlippage=true`;
    
    logger.debug(`Fetching Jupiter quote from: ${quoteUrl}`);
    const quoteRes = await fetch(quoteUrl);
    
    if (!quoteRes.ok) {
        const errorText = await quoteRes.text();
        logger.error(`Jupiter quote failed (${quoteRes.status}): ${errorText}`);
        throw new Error(`Jupiter quote failed: ${errorText}`);
    }

    const quoteResponse = await quoteRes.json();
    logger.debug(`Jupiter quote response: ${JSON.stringify(quoteResponse, null, 2)}`);

    if (!quoteResponse?.inAmount || quoteResponse.inAmount === "0") {
        logger.error('No valid Jupiter route found', { quoteResponse });
        throw new Error('No valid Jupiter route found');
    }

    // 2. Build Swap Transaction
    const swapPayload = {
        quoteResponse,
        userPublicKey: wallet.publicKey.toString(),
        wrapAndUnwrapSol: true,
        dynamicComputeUnitLimit: true,
        dynamicSlippage: true,
        prioritizationFeeLamports: {
            priorityLevelWithMaxLamports: {
                priorityLevel: "veryHigh",
                maxLamports: 2_000_000,
                global: false
            }
        },
    };

    logger.debug(`Jupiter swap payload: ${JSON.stringify(swapPayload, null, 2)}`);
    
    const swapRes = await fetch('https://lite-api.jup.ag/swap/v1/swap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(swapPayload)
    });
    
    if (!swapRes.ok) {
        const errorText = await swapRes.text();
        logger.error(`Jupiter swap build failed (${swapRes.status}): ${errorText}`);
        throw new Error(`Jupiter swap build failed: ${errorText}`);
    }

    const swapResponse = await swapRes.json();
    logger.debug(`Jupiter swap response: ${JSON.stringify(swapResponse, null, 2)}`);

    if (swapResponse.simulationError) {
        logger.error('Jupiter simulation error:', swapResponse.simulationError);
        throw new Error(`Jupiter simulation failed: ${swapResponse.simulationError}`);
    }

    // 3. Sign and Send Transaction
    const transaction = VersionedTransaction.deserialize(
        Buffer.from(swapResponse.swapTransaction, 'base64')
    );
    transaction.sign([wallet.payer]);

    const rawTransaction = transaction.serialize();
    
    let sendAttempts = 0;
    let lastError;
    
    while (sendAttempts < 3) {
        try {
            const signature = await connection.sendRawTransaction(rawTransaction, {
                maxRetries: 3,
                skipPreflight: sendAttempts > 0,
                preflightCommitment: 'confirmed'
            });
            return { signature, swapResponse, quoteResponse };
        } catch (error) {
            sendAttempts++;
            lastError = error;
            logger.warn(`Jupiter send attempt ${sendAttempts} failed: ${error.message}`);
            await new Promise(resolve => setTimeout(resolve, 1000 * sendAttempts));
        }
    }

    throw lastError || new Error('Failed to send Jupiter transaction after 3 attempts');
}

// DFlow Swap Implementation
async function tryDFlowSwap(mintAddress, token_amounts_purchased, wallet, connection) {
    try {
        // 1. Get Quote
        const quoteUrl = `https://quote-api.dflow.net/quote?inputMint=${mintAddress}&outputMint=${outputToken}&amount=${token_amounts_purchased}&slippageBps=${Math.floor(slippage * 100)}`;
        
        logger.debug(`Fetching DFlow quote from: ${quoteUrl}`);
        const quoteRes = await fetch(quoteUrl);
        
        if (!quoteRes.ok) {
            const errorText = await quoteRes.text();
            logger.error(`DFlow quote failed (${quoteRes.status}): ${errorText}`);
            throw new Error(`DFlow quote failed: ${errorText}`);
        }

        const quoteResponse = await quoteRes.json();
        logger.debug(`DFlow quote response: ${JSON.stringify(quoteResponse, null, 2)}`);

        if (!quoteResponse?.inAmount || quoteResponse.inAmount === "0") {
            logger.error('No valid DFlow route found', { quoteResponse });
            throw new Error('No valid DFlow route found');
        }

        // 2. Build Swap Transaction
        const swapPayload = {
            quoteResponse,
            userPublicKey: wallet.publicKey.toString(),
            wrapAndUnwrapSol: true,
            dynamicComputeUnitLimit: true,
            prioritizationFeeLamports: {
                autoMultiplier: 1 // Adjust based on network conditions
            }
        };

        logger.debug(`DFlow swap payload: ${JSON.stringify(swapPayload, null, 2)}`);
        
        const swapRes = await fetch('https://quote-api.dflow.net/swap', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(swapPayload)
        });
        
        if (!swapRes.ok) {
            const errorText = await swapRes.text();
            logger.error(`DFlow swap build failed (${swapRes.status}): ${errorText}`);
            throw new Error(`DFlow swap build failed: ${errorText}`);
        }

        const swapResponse = await swapRes.json();
        logger.debug(`DFlow swap response: ${JSON.stringify(swapResponse, null, 2)}`);

        // 3. Sign and Send Transaction
        const transaction = VersionedTransaction.deserialize(
            Buffer.from(swapResponse.swapTransaction, 'base64')
        );
        transaction.sign([wallet.payer]);

        const rawTransaction = transaction.serialize();
        
        let sendAttempts = 0;
        let lastError;
        
        while (sendAttempts < 3) {
            try {
                const signature = await connection.sendRawTransaction(rawTransaction, {
                    maxRetries: 3,
                    skipPreflight: sendAttempts > 0,
                    preflightCommitment: 'confirmed'
                });
                return { signature, swapResponse, quoteResponse };
            } catch (error) {
                sendAttempts++;
                lastError = error;
                logger.warn(`DFlow send attempt ${sendAttempts} failed: ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, 1000 * sendAttempts));
            }
        }

        throw lastError || new Error('Failed to send DFlow transaction after 3 attempts');
    } catch (error) {
        logger.error('DFlow swap error:', error);
        throw error;
    }
}

// OKX Swap Implementation (placeholder - needs to be implemented based on OKX API docs)
async function tryOKXSwap(mintAddress, token_amounts_purchased, wallet, connection) {
    try {
        // TODO: Implement OKX swap logic based on their API documentation
        // This is a placeholder that needs to be filled with actual OKX API calls
        
        // For now, just throw an error to fall through to the next provider
        throw new Error('OKX swap not implemented yet');
        
        // The actual implementation would follow a similar pattern to Jupiter/DFlow:
        // 1. Get quote from OKX API
        // 2. Build swap transaction
        // 3. Sign and send transaction
        // 4. Return { signature, swapResponse, quoteResponse }
    } catch (error) {
        logger.error('OKX swap error:', error);
        throw error;
    }
}


export { monitorPositions };
