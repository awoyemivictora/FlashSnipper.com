import { VersionedTransaction, Connection, PublicKey } from '@solana/web3.js';
import fetch from 'node-fetch';
import client from '../db/index.js';
import { getWallet } from './wallet.js';
import { sleep, sendTelegramMessage } from './utils.js';
import dotenv from 'dotenv';
import logger from './logger.js';
import { getTokenPrice } from './token_logics.js';

dotenv.config();

const API_HOST = process.env.API_HOST || 'https://gmgn.ai';
const connection = new Connection('https://api.mainnet-beta.solana.com');

// Changed to 0.01 SOL (10,000,000 lamports)
const amount = '10000000';
const inputToken = 'So11111111111111111111111111111111111111112';
const slippage = 0.5;
const fromAddress = 'SaM9Aude4aEE7k1KZSXcn7sxPq7oQy95iXDPzKzPpjv';
const fee = 0.003;





async function tradeTokens() {
  try {
    const wallet = getWallet();

    // Fetch tokens from the database
    const result = await client.query("SELECT * FROM token_metadata WHERE is_candidate = true AND is_bought = false");
    const tokens = result.rows;

    logger.info(`📝 Found ${tokens.length} candidate tokens.`);

    // --- Fetch SOL price once before the loop to avoid redundant API calls ----
    const currentSolPrice = await getTokenPrice(inputToken);
    if (currentSolPrice === null) {
      logger.error("FATAL: Could not get current SOL price. Aborting tradeTokens loop.");
      return; // Exit if SOL price is critical and not obtained
    }
    logger.info(`Current SOL price: ${currentSolPrice.toFixed(6)}`);

    for (const token of tokens) {
      const { mint_address, token_name } = token;

      try {
        // Get quote and unsigned transaction
        const quoteUrl = `${API_HOST}/defi/router/v1/sol/tx/get_swap_route?token_in_address=${inputToken}&token_out_address=${mint_address}&in_amount=${amount}&from_address=${fromAddress}&slippage=${slippage}&fee=${fee}`;
        logger.info(`📡 Requesting route from: ${quoteUrl}`);
        
        let routeRes = await fetch(quoteUrl);
        if (!routeRes.ok) {
          const text = await routeRes.text();
          throw new Error(`❌ Failed to fetch route: HTTP ${routeRes.status} - ${text}`);
        }
        
        let route = await routeRes.json();
        logger.debug('Route response:', JSON.stringify(route, null, 2));

        // Extract the amount of tokens recieved (token_out_address)
        // The 'outAmount' field from the API response will give us this.
        const rawTokenAmountsPurchased = route.data.quote.outAmount;

        if (!rawTokenAmountsPurchased) {
          throw new Error(`Missing outAmount from swap route for ${mint_address}`);
        }

        let tokenAmountsPurchased;
        let storedDecimals = null;
        try {
          // Fetch token decimals for mint_address
          const mintAccountInfo = await connection.getParsedAccountInfo(new PublicKey(mint_address));
          if (!mintAccountInfo || !mintAccountInfo.value || !mintAccountInfo.value.data || !mintAccountInfo.value.data.parsed || !mintAccountInfo.value.data.parsed.info) {
            throw new Error(`Could not fetch mint info for ${mint_address} to determine decimals.`);
          }
          const storedDecimals = mintAccountInfo.value.data.parsed.info.decimals;
          logger.info(`Fetched token decimal for ${mint_address}: ${storedDecimals}`);

          tokenAmountsPurchased = parseFloat(rawTokenAmountsPurchased) / (10 ** storedDecimals);
          logger.info(`✨ Successfully Bought ${tokenAmountsPurchased} ${token_name}`)
        } catch (decimalError) {
          logger.warn(`Could not get decimals for ${mint_address}, storing raw amount. ${decimalError.message}`);
          tokenAmountsPurchased = parseFloat(rawTokenAmountsPurchased);  // Fallback to raw if decimals can't be fetched
        }

        // Calculate entryPrice based on the amount of SOL spent and its current USD price
        const inputSOLAmount = parseFloat(amount) / 1000000000; // Correct lamports to SOL (1 SOL = 1,000,000,000 lamports)
        if (isNaN(inputSOLAmount) || inputSOLAmount <= 0) {
          throw new Error(`Invalid input 'amount' in lamports: ${amount}`);
        }
        const entryPrice = inputSOLAmount * currentSolPrice;  // This is our actual cost in USD for the trade

        if (isNaN(entryPrice) || entryPrice <= 0) {
          throw new Error(`Calculated entry price is invalid: ${entryPrice}. This indicates an issue with currentSOLPrice or input amount.`);
        }

        logger.info(`✅ Successfully bought token ${mint_address} for $${entryPrice.toFixed(6)}`);


        // Sign transaction
        const swapTransactionBuf = Buffer.from(route.data.raw_tx.swapTransaction, 'base64');
        const transaction = VersionedTransaction.deserialize(swapTransactionBuf);
        transaction.sign([wallet.payer]);
        const signedTx = Buffer.from(transaction.serialize()).toString('base64');

        // Submit transaction - USING CORRECT ENDPOINT FROM DOCS
        const submitUrl = `${API_HOST}/txproxy/v1/send_transaction`;
        let res = await fetch(submitUrl, {
          method: 'POST',
          headers: {'content-type': 'application/json'},
          body: JSON.stringify({
            "chain": "sol",
            "signedTx": signedTx
          })
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`❌ Transaction submission failed: HTTP ${res.status} - ${text}`);
        }

        res = await res.json();
        
        if (!res.data?.hash) {
          throw new Error(`Transaction submission failed: ${res.msg || 'Unknown error'}`);
        }

        const transactionHash = res.data.hash;
        logger.info(`✅ Transaction Hash: ${transactionHash}`);

        // Wait for transaction confirmation
        let confirmationStatus;
        const lastValidBlockHeight = route.data.raw_tx.lastValidBlockHeight;
        const startTime = Date.now();
        const timeout = 60000; // 60 seconds timeout
        
        while (Date.now() - startTime < timeout) {
          const statusUrl = `${API_HOST}/defi/router/v1/sol/tx/get_transaction_status?hash=${transactionHash}&last_valid_height=${lastValidBlockHeight}`;
          let statusRes = await fetch(statusUrl);
          
          if (!statusRes.ok) {
            await sleep(1000);
            continue;
          }
          
          let status = await statusRes.json();
          
          if (status?.data?.success === true) {
            confirmationStatus = 'confirmed';
            break;
          } else if (status?.data?.expired === true) {
            confirmationStatus = 'expired';
            break;
          }
          
          await sleep(1000);
        }

        if (!confirmationStatus) {
          throw new Error('Transaction confirmation timed out');
        }

        if (confirmationStatus === 'expired') {
          throw new Error('Transaction expired');
        }


      // --- Calculate Stop Loss and Take Profit ---
      // These should be based on the actual entryPrice (cost basis)
      const stopLoss = entryPrice * 0.7;   // 30% below entry price
      const takeProfit = entryPrice * 1.9; // 90% above entry price
      logger.info(`Set SL: ${stopLoss.toFixed(6)} and TP: ${takeProfit.toFixed(6)}`);

      
      // Get the current date and time in a human-readable format
      const date = new Date();
      const formattedDate = date.toLocaleString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
        });

        // Update the database
        await client.query(
        `UPDATE token_metadata 
        SET is_bought = true, 
            buy_timestamp = NOW(), 
            buy_price = $1, 
            entry_price = $1, 
            buy_tx_hash = $2, 
            stop_loss = $3, 
            take_profit = $4,
            token_amounts_purchased = $6,
            token_decimals = $7
        WHERE mint_address = $5`,
        [entryPrice, transactionHash, stopLoss, takeProfit, mint_address, tokenAmountsPurchased, storedDecimals]
        );

        // Send Telegram notification
        const message = `
          🚀 *Token Purchase Confirmed\\!*

          🗓 *Date:* ${formattedDate.replace(/[_*[\]()~`>#\+=|{}.!-]/g, '\\$&')}
          🪙 *Token Address:* \`${mint_address.replace(/[`\\]/g, '\\$&')}\`
          ✨ *Decimals:* \`${(storedDecimals !== null ? storedDecimals : 'N/A').toString().replace(/[`\\]/g, '\\$&')}\`
          🔢 *Amount Purchased:* \`${tokenAmountsPurchased.toFixed(9).replace(/[`\\]/g, '\\$&')}\`
          💲 *Entry Price:* \\$${entryPrice.toFixed(6).replace(/[_*[\]()~`>#\+=|{}.!-]/g, '\\$&')}
          📉 *Stop Loss:* \\$${stopLoss.toFixed(6).replace(/[_*[\]()~`>#\+=|{}.!-]/g, '\\$&')} \\(30\\% below entry\\)
          📈 *Take Profit:* \\$${takeProfit.toFixed(6).replace(/[_*[\]()~`>#\+=|{}.!-]/g, '\\$&')} \\(90\\% above entry\\)
          🔗 *Transaction Hash:* \`${transactionHash.replace(/[`\\]/g, '\\$&')}\`

          💰 *Total Spent \\(USD\\):* \\$${entryPrice.toFixed(6).replace(/[_*[\]()~`>#\+=|{}.!-]/g, '\\$&')}

          🕛 Stay sharp, the trade is live\\! 🚀

          *MONITORING FOR STOP\\-LOSS & TAKE\\-PROFIT*
          `;

        await sendTelegramMessage(message);
        logger.info("Telegram message sent successfully!")
        

        // Sleep for 30 seconds before moving to the next token
        // logger.info("⏲️ Waiting 2 mins before the next purchase...");
        // await sleep(120000);

        logger.info("⏲️ Waiting 1 hour before the next purchase...");
        await sleep(3600000);

      } catch (error) {
        logger.error(`❌ Error processing token ${mint_address}:`, error.message);
        logger.info("⏲️ Waiting 2 mins to retry the next purchase...");
        await sleep(120000);
        continue;
      }
    }

  } catch (error) {
    logger.error("❌ Error in trading:", error);
  }
}


export default tradeTokens;










































































































// import { VersionedTransaction, Connection, LAMPORTS_PER_SOL } from '@solana/web3.js';
// import fetch from 'node-fetch';
// import client from '../db/index.js';
// import { getWallet } from './wallet.js';
// import { sleep, sendTelegramMessage } from './utils.js';
// import dotenv from 'dotenv';
// import logger from './logger.js';

// dotenv.config();

// const API_HOST = process.env.API_HOST;
// const connection = new Connection('https://api.mainnet-beta.solana.com');

// const SOL_AMOUNT_TO_SPEND = 0.01; // Amount of SOL to spend per trade (0.1 SOL)
// const inputToken = 'So11111111111111111111111111111111111111112'; // SOL mint address
// const slippage = 0.5;
// const fromAddress = 'SaM9Aude4aEE7k1KZSXcn7sxPq7oQy95iXDPzKzPpjv';
// const fee = 0.003;
// let currentSolPrice = null; // Cache the SOL price



// Function to get current SOL price in USD
// export async function getSolPrice() {
//   // if (currentSolPrice) return currentSolPrice; // Use cached price if available
  
//   try {
//     // Try Jupiter API v2 first
//     const response = await fetch('https://lite-api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112');
//     const data = await response.json();
//     currentSolPrice = parseFloat(data.data['So11111111111111111111111111111111111111112'].price);
//     logger.info(`✅ Fetched SOL price from Jupiter: $${currentSolPrice}`);
//     return currentSolPrice;
//   } catch (jupiterError) {
//     logger.warn('⚠️ Failed to fetch SOL price from Jupiter, trying CoinGecko...');
    
//     try {
//       // Fallback to CoinGecko
//       const coingeckoResponse = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd');
//       const coingeckoData = await coingeckoResponse.json();
//       currentSolPrice = coingeckoData.solana.usd;
//       logger.info(`✅ Fetched SOL price from CoinGecko: $${currentSolPrice}`);
//       return currentSolPrice;
//     } catch (coingeckoError) {
//       logger.error('❌ Failed to fetch SOL price from all sources');
//       throw new Error('Could not fetch SOL price from any source');
//     }
//   }
// }




// // Function to calculate the amount of tokens to buy based on 0.1 SOL
// async function calculateTokenAmount(mintAddress) {
//   try {
//     // First get the SOL price
//     const solPrice = await getSolPrice();
//     logger.info(`💰 Current SOL price: $${solPrice}`);
    
//     // Calculate USD value of 0.1 SOL
//     const usdValue = SOL_AMOUNT_TO_SPEND * solPrice;
//     logger.info(`💵 ${SOL_AMOUNT_TO_SPEND} SOL is worth $${usdValue.toFixed(2)}`);
    
//     // Convert SOL amount to lamports (integer)
//     const solAmountInLamports = Math.floor(SOL_AMOUNT_TO_SPEND * LAMPORTS_PER_SOL);
    
//     // Get quote for 0.1 SOL worth of the token
//     const quoteUrl = `${API_HOST}/defi/router/v1/sol/tx/get_swap_route?token_in_address=${inputToken}&token_out_address=${mintAddress}&in_amount=${solAmountInLamports}&from_address=${fromAddress}&slippage=${slippage}&fee=${fee}`;
    
//     logger.info(`🔍 Fetching swap route for ${mintAddress}...`);
//     let route = await fetch(quoteUrl);
//     route = await route.json();
//     console.log('Full API response:', JSON.stringify(route, null, 2))
    
//     return {
//       amount: solAmountInLamports.toString(),
//       amountInUSD: usdValue,
//       route: route
//     };
//   } catch (error) {
//     logger.error(`❌ Error calculating token amount for ${mintAddress}:`, error);
//     throw error;
//   }
// }





// async function tradeTokens() {
//   try {
//     const wallet = getWallet();

//     // Fetch tokens from the database
//     const result = await client.query("SELECT * FROM token_metadata WHERE is_candidate = true AND is_bought = false");
//     const tokens = result.rows;

//     logger.info(`📝 Found ${tokens.length} candidate tokens.`);

//     for (const token of tokens) {
//       const { mint_address } = token;

//       try {
//         // Calculate the amount to buy (0.1 SOL worth)
//         const { amount, amountInUSD, route } = await calculateTokenAmount(mint_address);
        
//         // if (!route?.data?.raw_tx?.swapTransaction) {
//         //   logger.error(`❌ Invalid swap route response for ${mint_address}`);
//         //   continue;
//         // }

//         // logger.debug('Swap route response:', JSON.stringify(route, null, 2));

//         // Sign transaction
//         const swapTransactionBuf = Buffer.from(route.data.raw_tx.swapTransaction, 'base64');
//         const transaction = VersionedTransaction.deserialize(swapTransactionBuf);
//         transaction.sign([wallet.payer]);
//         const signedTx = Buffer.from(transaction.serialize()).toString('base64');

//         // Submit transaction
//         let res = await fetch(`${API_HOST}/defi/router/v1/sol/tx/submit_signed_transaction`,
//           {
//             method: 'POST',
//             headers: {'content-type': 'application/json'},
//             body: JSON.stringify({"signed_tx": signedTx})
//           });
//         res = await res.json();
        
//         if (!res.data?.hash) {
//           throw new Error(`Transaction submission failed: ${res.msg || 'Unknown error'}`);
//         }

//         const transactionHash = res.data.hash;
//         logger.info(`🔗 Transaction Hash: ${transactionHash}`);

//         // Wait for transaction confirmation
//         let confirmationStatus;
//         const lastValidBlockHeight = route.data.raw_tx.lastValidBlockHeight;
//         const startTime = Date.now();
//         const timeout = 60000; // 60 seconds timeout
        
//         while (Date.now() - startTime < timeout) {
//           const statusUrl = `${API_HOST}/defi/router/v1/sol/tx/get_transaction_status?hash=${transactionHash}&last_valid_height=${lastValidBlockHeight}`;
//           let status = await fetch(statusUrl);
//           status = await status.json();
          
//           if (status?.data?.success === true) {
//             confirmationStatus = 'confirmed';
//             break;
//           } else if (status?.data?.expired === true) {
//             confirmationStatus = 'expired';
//             break;
//           }
          
//           await sleep(1000);
//         }

//         if (!confirmationStatus) {
//           throw new Error('Transaction confirmation timed out');
//         }

//         if (confirmationStatus === 'expired') {
//           throw new Error('Transaction expired');
//         }

//         logger.info(`✅ Successfully bought token ${mint_address} for ${SOL_AMOUNT_TO_SPEND} SOL ($${amountInUSD.toFixed(2)})`);

//         // Calculate stop loss and take profit
//         const entryPrice = parseFloat(amountInUSD);
//         const stopLoss = entryPrice * 0.7;   // 30% below entry price
//         const takeProfit = entryPrice * 1.9; // 90% above entry price

//         // Get the current date and time
//         const formattedDate = new Date().toLocaleString('en-US', {
//           weekday: 'long',
//           year: 'numeric',
//           month: 'long',
//           day: 'numeric',
//           hour: '2-digit',
//           minute: '2-digit',
//           second: '2-digit',
//           hour12: true
//         });

//         // Update the database
//         await client.query(
//           `UPDATE token_metadata 
//           SET is_bought = true, 
//               buy_timestamp = NOW(), 
//               buy_price = $1, 
//               entry_price = $1, 
//               tx_hash = $2, 
//               stop_loss = $3, 
//               take_profit = $4 
//           WHERE mint_address = $5`,
//           [entryPrice, transactionHash, stopLoss, takeProfit, mint_address]
//         );

//         // Send Telegram notification
//         const message = `
//           🚀 *Token Purchase Confirmed\\!*
          
//           🗓 *Date:* ${formattedDate.replace(/[_\*\[\]()~`>#+-=|{}.!]/g, '\\$&')}
//           🪙 *Token Address:* \`${mint_address}\`
//           💲 *Entry Price:* \\$${entryPrice.toFixed(6)}
//           📉 *Stop Loss:* \\$${stopLoss.toFixed(6)} \\(30% below entry\\)
//           📈 *Take Profit:* \\$${takeProfit.toFixed(6)} \\(90% above entry\\)
//           🔗 *Transaction Hash:* \`${transactionHash}\`
          
//           💰 *Total Spent:* ${SOL_AMOUNT_TO_SPEND} SOL \\(~\\$${entryPrice.toFixed(2)}\\)
          
//           🕛 Stay sharp, the trade is live\\! 🚀
//         `;

//         await sendTelegramMessage(message);

//         // Sleep before next purchase
//         // logger.info("⏲️ Waiting 2 mins before the next purchase...");
//         // await sleep(120000);

//         // Sleep before next purchase
//         logger.info("⏲️ Waiting 1 hour before the next purchase...");
//         await sleep(3600000);


//       } catch (error) {
//         logger.error(`❌ Error processing token ${mint_address}:`, error.message);
//         // Continue to next token even if this one fails
//         continue;
//       }
//     }

//   } catch (error) {
//     logger.error("❌ Error in trading:", error);
//   }
// }







// export default tradeTokens;