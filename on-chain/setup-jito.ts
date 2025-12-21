// import { Connection, LAMPORTS_PER_SOL } from "@solana/web3.js";
// import { jitoBundleSender, JitoBundleSender } from "jito-integration";
// import * as fs from 'fs';
// import * as path from 'path';

// const RPC_URL = process.env.RPC_URL || 'https://api.mainnet-beta.solana.com';
// const connection = new Connection(RPC_URL, 'confirmed');

// async function setupJito() {
//     console.log('🛠️ Setting up Jito Bundle Sender...');

//     // 1. Initialize Jito (will generate new keypair)
//     await jitoBundleSender.initialize();

//     // 2. Fund the tip account with some SOL
//     console.log('\n💸 Funding Jito tip account...');
//     const tipAmount = 0.01; // 0.01 SOL for tips

//     try {

//     } catch (error) {
//         console.error('⚠️ Could not fund tip account (might need manual funding):', error);
//         console.log('\n📝 Manual funding required:');
//         console.log('1. Send SOL to tip account address (check logs above)');
//         console.log('2. Then run the sniper engine');
//     }

//     // 3. Check Jito leader schedule
//     console.log('\n🎯 Checking Jito leader schedule...');
    
//     try {
//         const leaderInfo = await jitoBundleSender.getLeaderInfo();
//         console.log(`Current slot: ${leaderInfo.currentSlot}`);
//         console.log(`Next Jito leader: ${leaderInfo.nextLeaderSlot}`);
//         console.log(`Slots unti Jito leader: ${leaderInfo.slotsUntilLeader}`);
//     } catch (error) {
//         console.error('⚠️ Could not get leader info:', error);
//     }

//     console.log('\n✅ Jito setup complete!');
//     console.log('\n📋 Next steps:');
//     console.log('1. Ensure your tip account has at least 0.01 SOL');
//     console.log('2. Run the sniper engine with: npm start');
//     console.log('3. Monitor Jito bundle results in the logs');
// }

// // Run setup
// setupJito().catch(console.error);








