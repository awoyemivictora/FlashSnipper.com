// import { Wallet } from "@project-serum/anchor";
// import { Keypair } from "@solana/web3.js";
// import bs58 from "bs58";
// import dotenv from 'dotenv';


// dotenv.config();


// export function getWallet() {
//     const secretKey = bs58.decode(process.env.PRIVATE_KEY);
//     const keypair = Keypair.fromSecretKey(secretKey);
//     const wallet = new Wallet(keypair);
//     console.log(`✅ Wallet initialized: ${wallet.publicKey.toString()}`);
//     return wallet;
// }







import { Keypair } from '@solana/web3.js';
import { Buffer } from 'buffer';

export const getOrCreateWallet = (privateKeyBase64) => {
  let keypair;
  if (privateKeyBase64) {
    try {
      // Decode base64 private key and create keypair
      const privateKeyBytes = Buffer.from(privateKeyBase64, 'base64');
      keypair = Keypair.fromSecretKey(privateKeyBytes);
      console.log('Imported wallet:', keypair.publicKey.toBase58());
    } catch (error) {
      console.error('Failed to import private key:', error);
      throw new Error('Invalid private key format');
    }
  } else {
    // Generate a new wallet
    keypair = Keypair.generate();
    console.log('New wallet generated:', keypair.publicKey.toBase58());
  }
  return keypair;
};

