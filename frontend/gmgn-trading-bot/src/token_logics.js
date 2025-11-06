import logger from "./logger.js";
// test_received_sol.js
import { Connection, PublicKey, LAMPORTS_PER_SOL } from '@solana/web3.js';
const RPC_ENDPOINT = 'https://api.mainnet-beta.solana.com'; // Or your preferred endpoint
import { getWallet } from './wallet.js';


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








export async function getReceivedSolAmount(signature) {
    try {
        // Create connection with versioned transaction support
        const connection = new Connection(RPC_ENDPOINT, {
            commitment: 'confirmed',
            confirmTransactionInitialTimeout: 60000, // Increase timeout if needed
        });
        
        const wallet = getWallet();
        
        // 1. Get the transaction with version support
        const tx = await connection.getTransaction(signature, {
            maxSupportedTransactionVersion: 0, // This is crucial for versioned transactions
            commitment: 'confirmed', // Ensure full data is available
        });
        
        if (!tx) {
            throw new Error('Transaction not found or not confirmed yet.');
        }

        if (!tx.meta) {
            throw new Error('Transaction metadata not available.');
        }

        // 2. Get the SOL balance changes
        const preBalances = tx.meta.preBalances;
        const postBalances = tx.meta.postBalances;
        
        // IMPORTANT: For versioned transactions, accountKeys are typically in staticAccountKeys
        // If it's a legacy transaction, accountKeys might be directly on tx.transaction.message.accountKeys
        const accountKeys = tx.transaction.message.staticAccountKeys || tx.transaction.message.accountKeys;

        if (!accountKeys) {
            throw new Error('Account keys not found in transaction message.');
        }

        // 3. Find the wallet's SOL account index
        const walletPubkey = wallet.publicKey.toString();
        const solAccountIndex = accountKeys.findIndex(
            key => key.toString() === walletPubkey
        );

        if (solAccountIndex === -1) {
            throw new Error('Wallet SOL account not found in transaction accounts.');
        }

        // 4. Calculate SOL difference (convert lamports to SOL)
        const lamportsReceived = postBalances[solAccountIndex] - preBalances[solAccountIndex];
        const solReceived = lamportsReceived / LAMPORTS_PER_SOL;

        // Note: You might want to also check tx.meta.postTokenBalances and preTokenBalances
        // if you're dealing with SPL tokens, but for raw SOL this is sufficient.

        if (solReceived <= 0) {
            // It's possible the transaction involved the wallet but no SOL was received
            // (e.g., sending SOL, or an unrelated interaction).
            // You might want to adjust this check based on your specific requirements.
            logger.warn(`No positive SOL change detected for wallet in transaction ${signature}. Amount: ${solReceived}`);
            return 0; // Return 0 if no SOL was received, rather than throwing an error
        }

        return solReceived;
    } catch (error) {
        logger.error(`Error calculating received SOL amount for tx ${signature}:`, error);
        throw error;
    }
}



