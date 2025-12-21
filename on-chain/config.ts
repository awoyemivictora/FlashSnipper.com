// import { Connection, PublicKey, Keypair } from "@solana/web3.js";
// import {
//  TxVersion
// } from "@raydium-io/raydium-sdk";
// import * as bs58 from 'bs58';
// import { Wallet } from "@project-serum/anchor";


// // define these
// //export const blockEngineUrl = 'tokyo.mainnet.block-engine.jito.wtf';
// export const blockEngineUrl = 'frankfurt.mainnet.block-engine.jito.wtf';


// const privateKey = new Uint8Array([
//   //your private key
// ]);
// export const wallet = new Wallet(Keypair.fromSecretKey(privateKey));



// export const rpc_https_url = "https://rpc.shyft.to?api_key=your api key";



// export const lookupTableCache= {}
// export const connection = new Connection(rpc_https_url, "confirmed");
// export const makeTxVersion = TxVersion.V0 // LEGACY
// export const addLookupTableInfo = undefined // only mainnet. other = undefined




// // on-chain/config.ts
// // Configuration constants for the sniper engine

// export const MIN_PUMPFUN_LIQUIDITY = 0.5; // Minimum 0.5 SOL liquidity
// export const MAX_USERS_PER_SNIPE = 20; // Max users per snipe operation
// export const MIN_USER_BALANCE = 0.1; // Minimum user balance to snipe

// // Jupiter configuration
// export const JUPITER_ENDPOINT = 'https://quote-api.jup.ag/v6';
// export const JUPITER_SWAP_ENDPOINT = 'https://quote-api.jup.ag/v6/swap';





// // on-chain/config.ts
// export const JUPITER_QUOTE_API = 'https://quote-api.jup.ag/v6/quote';
// export const JUPITER_SWAP_API = 'https://quote-api.jup.ag/v6/swap';

// // Slippage configuration
// export const MIN_SLIPPAGE_BPS = 10;      // 0.1% minimum
// export const MAX_SLIPPAGE_BPS = 5000;    // 50% maximum for emergencies
// export const DEFAULT_SLIPPAGE_BPS = 100; // 1% default

// // Jupiter referral (optional)
// export const JUPITER_REFERRAL_FEE_BPS = 10; // 0.1% referral fee

// // Risk analysis thresholds
// export const MIN_SAFE_CREATOR_BALANCE = 1.0; // 1 SOL minimum
// export const PUMPFUN_PROGRAM_ID = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P';

// // RPC endpoints for redundancy
// export const RPC_ENDPOINTS = [
//     'https://api.mainnet-beta.solana.com',
//     'https://solana-api.projectserum.com',
//     'https://rpc.ankr.com/solana',
//     'https://solana.public-rpc.com'
// ];

// // Performance settings
// export const SNIPE_TIMEOUT_MS = 8000; // 8 second timeout
// export const RATE_LIMIT_DELAY_MS = 50; // 50ms between snipes
// export const MAX_PARALLEL_SWAPS = 10; // Maximum parallel swap operations
// export const JITO_TIP_AMOUNT = 50000; // 0.00005 SOL tip for Jito




// on-chain/config.ts - UPDATED
export const MIN_PUMPFUN_LIQUIDITY = 0.5; // Minimum 0.5 SOL liquidity
export const MAX_USERS_PER_SNIPE = 20; // Max users per snipe operation
export const MIN_USER_BALANCE = 0.1; // Minimum user balance to snipe

// Jupiter configuration
export const JUPITER_ENDPOINT = 'https://quote-api.jup.ag/v6';
export const JUPITER_SWAP_ENDPOINT = 'https://quote-api.jup.ag/v6/swap';
export const JUPITER_QUOTE_API = 'https://quote-api.jup.ag/v6/quote';
export const JUPITER_SWAP_API = 'https://quote-api.jup.ag/v6/swap';

// Slippage configuration
export const MIN_SLIPPAGE_BPS = 10;      // 0.1% minimum
export const MAX_SLIPPAGE_BPS = 5000;    // 50% maximum for emergencies
export const DEFAULT_SLIPPAGE_BPS = 100; // 1% default

// Jupiter referral (optional)
export const JUPITER_REFERRAL_FEE_BPS = 10; // 0.1% referral fee

// Risk analysis thresholds
export const MIN_SAFE_CREATOR_BALANCE = 1.0; // 1 SOL minimum
export const PUMPFUN_PROGRAM_ID = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P';

// RPC endpoints for redundancy
export const RPC_ENDPOINTS = [
    'https://api.mainnet-beta.solana.com',
    'https://solana-api.projectserum.com',
    'https://rpc.ankr.com/solana',
    'https://solana.public-rpc.com'
];

// Performance settings
export const SNIPE_TIMEOUT_MS = 8000; // 8 second timeout
export const RATE_LIMIT_DELAY_MS = 50; // 50ms between snipes
export const MAX_PARALLEL_SWAPS = 10; // Maximum parallel swap operations
export const JITO_TIP_AMOUNT = 50000; // 0.00005 SOL tip for Jito
