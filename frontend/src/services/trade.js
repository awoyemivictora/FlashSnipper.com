// src/services/trade.js
import { Connection, PublicKey, VersionedTransaction, LAMPORTS_PER_SOL } from '@solana/web3.js';
import { Buffer } from 'buffer'; // Ensure buffer polyfill is active
import bs58 from 'bs58';
import logger from "./logger.js";

const RPC_ENDPOINT = 'https://api.mainnet-beta.solana.com'; // Or your preferred endpoint
const BACKEND_API_URL = 'http://localhost:8000'; // Your FastAPI backend URL
const connection = new Connection(RPC_ENDPOINT, 'confirmed');




export async function getTokenPrice(mintAddress) {
  if (!mintAddress) throw new Error("Mint address is required");

  try {
    const url = `https://lite-api.jup.ag/price/v2?ids=${mintAddress}`;
    const response = await fetch(url, {
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    const tokenData = data.data[mintAddress];

    if (!tokenData || !tokenData.price) {
      throw new Error(`No price data found for mint address: ${mintAddress}`);
    }

    const price = parseFloat(tokenData.price);

    logger.info(`✅ Current token price for ${mintAddress}: $${price}`);
    return price;
  } catch (error) {
    logger.error(`❌ Failed to fetch token price for ${mintAddress}: ${error.message}`);
    throw new Error(`Could not fetch price for token: ${mintAddress}`);
  }
}



// export async function getReceivedSolAmount(txSignature, retries = 5, delay = 2000) {
//     const connection = new Connection(RPC_ENDPOINT, {
//         commitment: 'confirmed',
//         confirmTransactionInitialTimeout: 60000,
//     });

//     const wallet = getWallet(); // Get wallet once

//     for (let i = 0; i < retries; i++) {
//         try {
//             const tx = await connection.getTransaction(txSignature, {
//                 maxSupportedTransactionVersion: 0,
//                 commitment: 'confirmed', // Use 'confirmed' or 'finalized' for more robust check
//             });

//             if (!tx) {
//                 logger.warn(`Attempt ${i + 1}/${retries}: Transaction ${txSignature} not found or not yet confirmed. Retrying...`);
//                 await new Promise(resolve => setTimeout(resolve, delay));
//                 continue; // Try again
//             }

//             if (!tx.meta) {
//                 logger.error(`Transaction ${txSignature} metadata not available.`);
//                 throw new Error('Transaction metadata not available.');
//             }

//             const preBalances = tx.meta.preBalances;
//             const postBalances = tx.meta.postBalances;
            
//             // IMPORTANT: For versioned transactions, accountKeys are typically in staticAccountKeys
//             const accountKeys = tx.transaction.message.staticAccountKeys || tx.transaction.message.accountKeys;

//             if (!accountKeys) {
//                 logger.error(`Account keys not found in transaction message for ${txSignature}.`);
//                 throw new Error('Account keys not found in transaction message.');
//             }

//             const walletPubkey = wallet.publicKey.toString();
//             const solAccountIndex = accountKeys.findIndex(
//                 key => key.toString() === walletPubkey
//             );

//             if (solAccountIndex === -1) {
//                 logger.error(`Wallet SOL account ${walletPubkey} not found in transaction accounts for ${txSignature}.`);
//                 // This might happen if your wallet wasn't directly involved in a SOL transfer,
//                 // but perhaps an associated token account.
//                 // For a sell of an SPL token to SOL, the wallet's main SOL account should change.
//                 throw new Error('Wallet SOL account not found in transaction accounts for balance calculation.');
//             }

//             const lamportsReceived = postBalances[solAccountIndex] - preBalances[solAccountIndex];
//             const solReceived = lamportsReceived / LAMPORTS_PER_SOL;

//             if (solReceived <= 0) {
//                 logger.warn(`No positive SOL change detected for wallet in transaction ${txSignature}. Amount: ${solReceived}. This might be expected if the transaction was just for a token transfer or fees.`);
//                 // You might choose to throw an error here if you *expect* to always receive SOL.
//                 // For now, returning 0 might be safer.
//                 return 0;
//             }

//             logger.info(`Successfully retrieved ${solReceived} SOL for transaction ${txSignature}.`);
//             return solReceived; // Success, return the amount

//         } catch (error) {
//             logger.error(`Error calculating received SOL amount for tx ${txSignature} (Attempt ${i + 1}/${retries}): ${error.message}`);
//             if (i < retries - 1) {
//                 logger.warn(`Retrying getReceivedSolAmount for ${txSignature} in ${delay / 1000} seconds...`);
//                 await new Promise(resolve => setTimeout(resolve, delay));
//             } else {
//                 throw error; // Re-throw the error after all retries are exhausted
//             }
//         }
//     }
//     // This line should ideally not be reached if an error is always thrown on final failure
//     throw new Error(`Failed to calculate received SOL amount for tx ${txSignature} after ${retries} attempts.`);
// }













// Helper for logging to frontend UI (and possibly sending to backend WS)
function logToUI(message) {
  const logDisplay = document.getElementById('trade-logs-display');
  if (logDisplay) {
    logDisplay.textContent += `\n[${new Date().toLocaleTimeString()}] ${message}`;
    logDisplay.scrollTop = logDisplay.scrollHeight; // Auto-scroll
  }
  console.log(message);
}

// Centralized function to send trade logs to backend
async function sendTradeLogToBackend(logData, authToken, userWalletAddress) {
  try {
    const response = await fetch(`${BACKEND_API_URL}/trade/log-trade`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        ...logData,
        user_wallet_address: userWalletAddress // Ensure wallet address is included
      })
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Failed to log trade on backend: ${errorData.detail || response.statusText}`);
    }
    logToUI("Trade successfully logged on backend.");
  } catch (error) {
    logToUI(`Error logging trade to backend: ${error.message}`);
    console.error("Backend trade log error:", error);
  }
}



// Executes a buy or sell trade
export async function executeTrade(walletKeypair, userWalletAddress, authToken, tradeParams) {
  const { mint_address, amount_sol, trade_type, token_symbol } = tradeParams;
  logToUI(`Initiating ${trade_type} trade for ${amount_sol} SOL on token ${mint_address}...`);

  try {
    let tokenInAddress, tokenOutAddress, amountIn;

    if (trade_type === 'buy') {
      tokenInAddress = "So11111111111111111111111111111111111111112"; // SOL mint address
      tokenOutAddress = mint_address;
      amountIn = amount_sol; // Amount of SOL
    } else if (trade_type === 'sell') {
      tokenInAddress = mint_address;
      tokenOutAddress = "So11111111111111111111111111111111111111112"; // SOL mint address
      // For selling, `amount_sol` here represents the amount of *tokens* to sell,
      // not SOL. You'll need to manage actual token balance from user's wallet.
      // For simplicity, let's assume `amount_sol` is the human-readable token amount.
      // You'd get the actual token amount from `token_metadata` table or calculate it.
      // This is a major point of difference from your old `sellToken`
      // For now, assume `amount_sol` is the float amount of `tokenInAddress` to sell.
      
      // You'll need `token_decimals` for the `tokenInAddress` to convert `amount_sol`
      // to smallest units for the quote request.
      const mintAccountInfo = await connection.getParsedAccountInfo(new PublicKey(tokenInAddress));
      if (!mintAccountInfo || !mintAccountInfo.value || !mintAccountInfo.value.data || !mintAccountInfo.value.data.parsed || !mintAccountInfo.value.data.parsed.info) {
        throw new Error(`Could not fetch mint info for ${tokenInAddress} to determine decimals for sell.`);
      }
      const tokenDecimals = mintAccountInfo.value.data.parsed.info.decimals;
      amountIn = parseInt(amount_sol * (10 ** tokenDecimals)); // Convert to smallest units for the API call
      logToUI(`Selling ${amount_sol} of ${token_symbol} (${tokenInAddress}), which is ${amountIn} in smallest units.`);

    } else {
      throw new Error("Invalid trade type. Must be 'buy' or 'sell'.");
    }


    // 1. Get Trade Quote from Backend Proxy
    const quoteResponse = await fetch(`${BACKEND_API_URL}/trade/quote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token_in_address: tokenInAddress,
        token_out_address: tokenOutAddress,
        in_amount: amountIn, // This should be in smallest units for the API
        user_wallet_address: userWalletAddress,
        slippage: 0.005, // Example slippage
      }),
    });

    if (!quoteResponse.ok) {
      const errorData = await quoteResponse.json();
      throw new Error(`Failed to get trade quote: ${errorData.detail || quoteResponse.statusText}`);
    }
    const { raw_tx_base64, last_valid_block_height, quote_data } = await quoteResponse.json();

    logToUI(`Received quote. Out amount: ${quote_data.outAmount / (10 ** quote_data.tokenOut.decimals)} ${quote_data.tokenOut.symbol}`);

    // 2. Deserialize, Sign, and Serialize Transaction
    const swapTransactionBuf = Buffer.from(raw_tx_base64, 'base64');
    const transaction = VersionedTransaction.deserialize(swapTransactionBuf);
    transaction.sign([walletKeypair]); // SIGNING HAPPENS HERE ON THE FRONTEND!
    const signedTxBase64 = Buffer.from(transaction.serialize()).toString('base64');

    logToUI("Transaction signed by wallet. Sending to backend for broadcast...");

    // 3. Send Signed Transaction to Backend for Broadcast
    const sendTxResponse = await fetch(`${BACKEND_API_URL}/trade/send-signed-transaction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signed_tx_base64: signedTxBase64 }),
    });

    if (!sendTxResponse.ok) {
      const errorData = await sendTxResponse.json();
      throw new Error(`Failed to broadcast transaction: ${errorData.detail || sendTxResponse.statusText}`);
    }
    const { transaction_hash } = await sendTxResponse.json();
    logToUI(`Transaction broadcasted. Hash: ${transaction_hash}`);

    // 4. Wait for Transaction Confirmation (Client-side)
    logToUI(`Waiting for confirmation of transaction: ${transaction_hash}`);
    const confirmation = await connection.confirmTransaction({
        signature: transaction_hash,
        lastValidBlockHeight: last_valid_block_height,
        blockhash: transaction.message.recentBlockhash // Use the blockhash from the signed transaction
    }, 'confirmed');

    if (confirmation.value.err) {
      throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
    }
    logToUI(`Transaction confirmed: https://solscan.io/tx/${transaction_hash}`);


    // --- Calculate Trade Metrics & Log to Backend ---
    let logMessage = `${trade_type.toUpperCase()} successful for ${token_symbol}. Tx: ${transaction_hash}`;
    let profitUsd = null;
    let profitSol = null;
    let buyPrice = null;
    let entryPrice = null;
    let stopLoss = null;
    let takeProfit = null;
    let tokenAmountsPurchased = null;
    let tokenDecimals = null;
    let sellReason = null;
    let swapProvider = "DEX Aggregator"; // Default provider for now

    // Get current SOL price for USD conversion
    const currentSolPrice = await getTokenPrice("So11111111111111111111111111111111111111112");
    if (!currentSolPrice) {
      logToUI("Warning: Could not fetch current SOL price for accurate USD calculations.");
    }

    if (trade_type === 'buy') {
      const inputSOLAmount = amount_sol; // This is the amount of SOL spent
      entryPrice = inputSOLAmount * currentSolPrice; // Cost in USD
      buyPrice = entryPrice; // For consistency with old code
      tokenAmountsPurchased = quote_data.outAmount / (10 ** quote_data.tokenOut.decimals);
      tokenDecimals = quote_data.tokenOut.decimals;

      // Calculate SL/TP based on entryPrice
      stopLoss = entryPrice * 0.7; // 30% below entry
      takeProfit = entryPrice * 1.9; // 90% above entry

      logMessage = `Successfully bought ${tokenAmountsPurchased.toFixed(6)} ${token_symbol} for $${entryPrice.toFixed(6)}. Tx: ${transaction_hash}`;
      logToUI(logMessage);

    } else if (trade_type === 'sell') {
      // For selling, you'd need the original buy price and amount to calculate profit
      // This data should ideally come from backend's `TokenMetadata` or `Trade` history
      // For this example, let's assume we fetch some data related to a previously bought token
      // or receive it in `tradeParams`.
      // The `amount_sol` for a sell trade means the amount of *tokens* sold.
      // `quote_data.outAmount` would be the SOL received in lamports.
      
      const receivedSOLAmount = quote_data.outAmount / 1_000_000_000; // SOL received
      const receiveUSDAmount = receivedSOLAmount * currentSolPrice; // USD received from sell
      
      // You'll need to fetch the `buy_price` for the given `mint_address` from your backend's database
      // if you want to calculate accurate profit.
      // For now, let's simulate by passing it in tradeParams or fetching from a mock source.
      const previousBuyPrice = tradeParams.previousBuyPrice || 0; // Assume passed or fetched
      profitUsd = receiveUSDAmount - previousBuyPrice;
      profitSol = receivedSOLAmount - (previousBuyPrice / currentSolPrice); // Rough SOL profit
      sellReason = tradeParams.reason || "Manual Sell"; // E.g., "Take Profit", "Stop Loss"
      
      logMessage = `Successfully sold ${amount_sol} ${token_symbol} for $${receiveUSDAmount.toFixed(6)}. Profit: $${profitUsd.toFixed(6)}. Tx: ${transaction_hash}`;
      logToUI(logMessage);
    }

    // Send detailed log to backend
    await sendTradeLogToBackend({
      mint_address: mint_address,
      token_symbol: token_symbol,
      trade_type: trade_type,
      amount_sol: amount_sol, // This is the input amount (SOL for buy, tokens for sell)
      amount_tokens: tokenAmountsPurchased || amount_sol, // Tokens involved (bought or sold)
      price_sol_per_token: quote_data.outAmount / quote_data.inAmount, // Approx price from quote
      price_usd_at_trade: trade_type === 'buy' ? entryPrice : (amount_sol * await getTokenPrice(mint_address)), // Est. USD value
      tx_hash: transaction_hash,
      log_message: logMessage,
      profit_usd: profitUsd,
      profit_sol: profitSol,
      buy_price: buyPrice,
      entry_price: entryPrice,
      stop_loss: stopLoss,
      take_profit: takeProfit,
      token_amounts_purchased: tokenAmountsPurchased,
      token_decimals: tokenDecimals,
      sell_reason: sellReason,
      swap_provider: swapProvider
    }, authToken, userWalletAddress);

    return { success: true, transaction_hash };

  } catch (error) {
    const errorMessage = `Trade failed: ${error.message}`;
    logToUI(errorMessage);
    console.error("Trade execution error:", error);
    // You might still want to log failed trade attempts to backend for analytics
    await sendTradeLogToBackend({
        mint_address: mint_address,
        token_symbol: token_symbol,
        trade_type: trade_type,
        amount_sol: amount_sol,
        log_message: `FAILED: ${errorMessage}`,
        tx_hash: "N/A", // No hash if it failed before broadcast
        status: "failed" // Add a status field to your log model if needed
    }, authToken, userWalletAddress);
    return { success: false, error: errorMessage };
  }
}

// Your monitorPositions and sellToken logic will go here as well,
// making calls to executeTrade.
// We'll adapt them into React components/hooks in App.jsx or a separate hook.

