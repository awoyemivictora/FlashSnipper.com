import { Wallet } from "@project-serum/anchor";
import { Keypair } from "@solana/web3.js";
import bs58 from "bs58";
import dotenv from 'dotenv';


dotenv.config();


export function getWallet() {
    const secretKey = bs58.decode(process.env.PRIVATE_KEY);
    const keypair = Keypair.fromSecretKey(secretKey);
    const wallet = new Wallet(keypair);
    console.log(`✅ Wallet initialized: ${wallet.publicKey.toString()}`);
    return wallet;
}

