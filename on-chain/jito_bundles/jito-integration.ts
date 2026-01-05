// import { Connection, VersionedTransaction } from '@solana/web3.js';
// import { JitoJsonRpcClient } from 'jito-js-rpc';

// export interface JitoBundleResult {
//     bundleId: string;
//     success: boolean;
//     error?: string;
//     retryCount?: number;
//     endpointUsed?: string;
// }

// export class JitoBundleSender {
//     private jitoClients: Map<string, JitoJsonRpcClient> = new Map();
//     private readonly endpoints = [
//         'https://mainnet.block-engine.jito.wtf/api/v1',
//         'https://amsterdam.mainnet.block-engine.jito.wtf/api/v1',
//         'https://ny.mainnet.block-engine.jito.wtf/api/v1',
//         'https://frankfurt.mainnet.block-engine.jito.wtf/api/v1',
//         'https://tokyo.mainnet.block-engine.jito.wtf/api/v1'
//     ];
//     private currentEndpointIndex = 0;
//     private requestQueue: Array<() => Promise<any>> = [];
//     private isProcessingQueue = false;
//     private readonly MAX_CONCURRENT_REQUESTS = 1; // Conservative for rate limits
//     private readonly MIN_REQUEST_INTERVAL = 2000; // 2 seconds between requests

//     constructor() {
//         // Initialize clients for all endpoints
//         this.endpoints.forEach(endpoint => {
//             this.jitoClients.set(endpoint, new JitoJsonRpcClient(endpoint, ''));
//         });
//         console.log(`✅ Jito Bundle Sender initialized with ${this.endpoints.length} endpoints`);
//     }

//     async initialize(): Promise<void> {
//         // Test connection to all endpoints
//         console.log('🔗 Testing Jito endpoints...');
//         const connectionPromises = this.endpoints.map(async (endpoint, index) => {
//             try {
//                 const client = this.jitoClients.get(endpoint)!;
//                 const tipAccount = await client.getRandomTipAccount();
//                 console.log(`  ${index + 1}. ${endpoint.split('/')[2]} ✅`);
//                 return { endpoint, success: true };
//             } catch (error) {
//                 console.log(`  ${index + 1}. ${endpoint.split('/')[2]} ❌ (${error.message})`);
//                 return { endpoint, success: false };
//             }
//         });

//         await Promise.allSettled(connectionPromises);
//     }

//     async sendBundle(
//         transactions: VersionedTransaction[],
//         connection: Connection
//     ): Promise<JitoBundleResult> {
//         if (transactions.length === 0) {
//             return {
//                 bundleId: '',
//                 success: false,
//                 error: 'No transactions to bundle'
//             };
//         }

//         if (transactions.length > 5) {
//             transactions = transactions.slice(0, 5);
//         }

//         console.log(`📤 Preparing ${transactions.length} transaction${transactions.length > 1 ? 's' : ''} for Jito...`);

//         // Convert transactions to base64
//         const base64Transactions = transactions.map(tx => {
//             const serialized = tx.serialize();
//             return Buffer.from(serialized).toString('base64');
//         });

//         // Try with retry logic across different endpoints
//         const maxRetries = this.endpoints.length * 2; // Try each endpoint twice
//         let retryCount = 0;
//         let lastError: any = null;

//         while (retryCount < maxRetries) {
//             const endpoint = this.getNextEndpoint();
//             const client = this.jitoClients.get(endpoint)!;

//             try {
//                 // Wait between attempts (exponential backoff)
//                 if (retryCount > 0) {
//                     const backoffTime = Math.min(1000 * Math.pow(1.5, retryCount), 8000);
//                     console.log(`⏳ Waiting ${backoffTime}ms before retry ${retryCount + 1}/${maxRetries}...`);
//                     await new Promise(resolve => setTimeout(resolve, backoffTime));
//                 }

//                 console.log(`🚀 Attempt ${retryCount + 1}/${maxRetries} via ${endpoint.split('/')[2]}`);

//                 // Add Jito tip instruction to transactions (from Jito example)
//                 const { blockhash } = await connection.getLatestBlockhash('confirmed');
                
//                 // Get tip account
//                 let tipAccount;
//                 try {
//                     tipAccount = await client.getRandomTipAccount();
//                     console.log(`🎯 Using tip account: ${tipAccount.substring(0, 16)}...`);
//                 } catch (tipError) {
//                     console.log('⚠️ Could not get tip account, using fallback');
//                     tipAccount = '96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5';
//                 }

//                 // Send bundle using Jito SDK (EXACT format from examples)
//                 const result = await client.sendBundle([
//                     base64Transactions, 
//                     { encoding: 'base64' }
//                 ]);

//                 const bundleId = result.result;
//                 console.log(`✅ Jito bundle submitted: ${bundleId?.slice(0, 16)}...`);

//                 // Monitor confirmation in background
//                 this.monitorBundleConfirmation(bundleId, endpoint).catch(console.error);

//                 return {
//                     bundleId,
//                     success: true,
//                     retryCount,
//                     endpointUsed: endpoint
//                 };

//             } catch (error: any) {
//                 retryCount++;
//                 lastError = error;

//                 // Check error type
//                 if (error.response?.status === 429) {
//                     console.log(`⚠️ Rate limited on ${endpoint.split('/')[2]}, rotating endpoint...`);
//                     this.currentEndpointIndex = (this.currentEndpointIndex + 1) % this.endpoints.length;
//                     continue;
//                 } else if (error.response?.status === 400) {
//                     console.error(`❌ Bad request (likely transaction issue): ${error.message}`);
//                     break; // Don't retry 400 errors
//                 } else {
//                     console.error(`❌ Error on ${endpoint.split('/')[2]}: ${error.message}`);
//                     // Try next endpoint
//                     this.currentEndpointIndex = (this.currentEndpointIndex + 1) % this.endpoints.length;
//                 }
//             }
//         }

//         return {
//             bundleId: '',
//             success: false,
//             error: `Jito failed after ${retryCount} attempts: ${lastError?.message || 'Unknown error'}`,
//             retryCount
//         };
//     }

//     private getNextEndpoint(): string {
//         const endpoint = this.endpoints[this.currentEndpointIndex];
//         this.currentEndpointIndex = (this.currentEndpointIndex + 1) % this.endpoints.length;
//         return endpoint;
//     }

//     private async monitorBundleConfirmation(bundleId: string, endpoint: string): Promise<void> {
//         try {
//             // Wait before checking status
//             await new Promise(resolve => setTimeout(resolve, 3000));
            
//             const client = this.jitoClients.get(endpoint)!;
//             const status = await client.confirmInflightBundle(bundleId, 30000); // 30 second timeout
            
//             // Type guard to check which type of status we have
//             if ('confirmation_status' in status) {
//                 // Type 2: Detailed bundle status with confirmation_status
//                 if (status.confirmation_status === 'confirmed') {
//                     console.log(`✅ Bundle ${bundleId.slice(0, 16)}... confirmed on chain!`);
//                 } else if (status.err) {
//                     console.log(`⚠️ Bundle ${bundleId.slice(0, 16)}... failed:`, status.err);
//                 } else {
//                     console.log(`📊 Bundle ${bundleId.slice(0, 16)}... status: ${status.confirmation_status}`);
//                 }
//             } else if ('status' in status && typeof status.status === 'string') {
//                 // Type 1: Simple status object
//                 console.log(`📊 Bundle ${bundleId.slice(0, 16)}... status: ${status.status}`);
                
//                 if (status.status === 'Landed' && 'landed_slot' in status) {
//                     console.log(`   Landed at slot: ${status.landed_slot}`);
//                 }
//             } else {
//                 // Type 3: Generic status object
//                 console.log(`📊 Bundle ${bundleId.slice(0, 16)}... status: ${JSON.stringify(status)}`);
//             }
//         } catch (error) {
//             // Silent error for monitoring
//         }
//     }

//     // Utility function to test Jito connection
//     async testConnection(): Promise<boolean> {
//         console.log('🧪 Testing Jito connection with simple transaction...');
        
//         try {
//             const testKeypair = new (await import('@solana/web3.js')).Keypair();
//             const connection = new Connection('https://api.mainnet-beta.solana.com');
            
//             const transaction = new (await import('@solana/web3.js')).Transaction();
//             transaction.add(
//                 (await import('@solana/web3.js')).SystemProgram.transfer({
//                     fromPubkey: testKeypair.publicKey,
//                     toPubkey: testKeypair.publicKey,
//                     lamports: 1000
//                 })
//             );
            
//             const { blockhash } = await connection.getLatestBlockhash();
//             transaction.recentBlockhash = blockhash;
//             transaction.feePayer = testKeypair.publicKey;
//             transaction.sign(testKeypair);
            
//             // Convert to VersionedTransaction
//             const messageV0 = transaction.compileMessage();
//             const versionedTx = new VersionedTransaction(messageV0);
//             versionedTx.sign([testKeypair]);
            
//             console.log('✅ Test transaction created');
//             return true;
//         } catch (error) {
//             console.error('❌ Test failed:', error);
//             return false;
//         }
//     }
// }

// // Global instance - NO API KEY NEEDED
// export const jitoBundleSender = new JitoBundleSender();




































import { 
  Connection, 
  VersionedTransaction, 
  SystemProgram, 
  PublicKey, 
  TransactionMessage,
  AddressLookupTableAccount,
  MessageV0,
  TransactionInstruction
} from '@solana/web3.js';
import axios from 'axios';
import bs58 from 'bs58';

export interface JitoBundleResult {
  bundleId: string;
  success: boolean;
  error?: string;
  retryCount?: number;
  endpointUsed?: string;
  slot?: number;
}

// Updated Jito endpoints with proper REST API paths
const JITO_BUNDLE_ENDPOINTS = [
  'https://mainnet.block-engine.jito.wtf/api/v1/bundles',
  'https://ny.mainnet.block-engine.jito.wtf/api/v1/bundles',
  'https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/bundles',
  'https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/bundles',
  'https://tokyo.mainnet.block-engine.jito.wtf/api/v1/bundles',
];

// Main tip accounts (updated for 2026)
const JITO_TIP_ACCOUNTS = [
  '96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5',  // Primary
  'HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe',  // Fallback 1
  'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY',  // Fallback 2
];

export class JitoBundleSender {
  private connection: Connection;
  private currentTipAccountIndex = 0;
  private readonly MAX_BUNDLE_SIZE = 5; // Jito limit
  private readonly MIN_TIP_AMOUNT = 100_000; // 0.0001 SOL minimum
  private readonly RECOMMENDED_TIP = 500_000; // 0.0005 SOL for better chance
  private readonly MAX_RETRIES = 3;
  private rateLimitDelay = 1000; // Start with 1s

  constructor(connection: Connection) {
    this.connection = connection;
    console.log('✅ Jito Bundle Sender initialized (2026 implementation)');
  }

  /**
   * Send transactions as a Jito bundle with tip
   */
  async sendBundle(
    transactions: VersionedTransaction[],
    tipAmount?: number
  ): Promise<JitoBundleResult> {
    if (transactions.length === 0) {
      return {
        bundleId: '',
        success: false,
        error: 'No transactions to bundle'
      };
    }

    // Enforce bundle size limit
    const txsToSend = transactions.slice(0, this.MAX_BUNDLE_SIZE);
    console.log(`📦 Preparing ${txsToSend.length} transaction${txsToSend.length > 1 ? 's' : ''} for Jito bundle`);

    // Add tip to the first transaction
    const tippedTransaction = await this.addTipToTransaction(
      txsToSend[0],
      tipAmount || this.RECOMMENDED_TIP
    );
    
    // Replace first transaction with tipped version
    txsToSend[0] = tippedTransaction;

    // Serialize all transactions to base58
    const serializedTxs = txsToSend.map(tx => bs58.encode(tx.serialize()));

    let lastError: string = '';
    let retryCount = 0;

    // Try all endpoints with retries
    for (let attempt = 0; attempt < this.MAX_RETRIES; attempt++) {
      // Rotate through endpoints
      for (const endpoint of this.shuffleArray([...JITO_BUNDLE_ENDPOINTS])) {
        try {
          // Add delay between attempts (exponential backoff)
          if (attempt > 0) {
            const delay = Math.min(1000 * Math.pow(2, attempt), 8000);
            console.log(`⏳ Backoff delay: ${delay}ms`);
            await new Promise(resolve => setTimeout(resolve, delay));
          }

          console.log(`🚀 Attempt ${attempt + 1}: Sending to ${endpoint.split('/')[2]}`);
          
          const result = await this.sendToEndpoint(endpoint, serializedTxs);
          
          console.log(`✅ Bundle submitted: ${result.bundleId?.slice(0, 16)}...`);
          
          // Monitor bundle in background
          this.monitorBundle(result.bundleId, endpoint).catch(console.error);
          
          return {
            bundleId: result.bundleId,
            success: true,
            retryCount: attempt,
            endpointUsed: endpoint,
            slot: result.slot
          };

        } catch (error: any) {
          lastError = error.message;
          console.warn(`⚠️ Failed on ${endpoint.split('/')[2]}: ${error.message}`);
          
          // Handle rate limiting
          if (error.message.includes('429') || error.message.includes('rate limit')) {
            console.log('⏳ Rate limited, increasing delay...');
            this.rateLimitDelay = Math.min(this.rateLimitDelay * 2, 10000);
            await new Promise(resolve => setTimeout(resolve, this.rateLimitDelay));
          }
        }
      }
    }

    return {
      bundleId: '',
      success: false,
      error: `All attempts failed: ${lastError}`,
      retryCount: this.MAX_RETRIES
    };
  }

  /**
   * Send bundle to a specific Jito endpoint
   */
  private async sendToEndpoint(
    endpoint: string,
    serializedTxs: string[]
  ): Promise<{ bundleId: string; slot?: number }> {
    const response = await axios.post(
      endpoint,
      {
        jsonrpc: '2.0',
        id: 1,
        method: 'sendBundle',
        params: [serializedTxs]
      },
      {
        timeout: 15000,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        }
      }
    );

    if (response.data.error) {
      throw new Error(response.data.error.message || 'Jito API error');
    }

    if (!response.data.result) {
      throw new Error('No bundle ID returned');
    }

    return {
      bundleId: response.data.result
    };
  }

    /**
     * Add tip instruction to a transaction
     */
    private async addTipToTransaction(
    transaction: VersionedTransaction,
    tipAmount: number
    ): Promise<VersionedTransaction> {
    try {
        // Get tip account
        const tipAccount = await this.getTipAccount();
        console.log(`🎯 Adding ${tipAmount / 1e9} SOL tip to: ${tipAccount.slice(0, 16)}...`);

        // Get the transaction's message
        const message = transaction.message;
        
        // Get the fee payer (first signer)
        const feePayer = message.staticAccountKeys[0];
        
        // Create tip transfer instruction
        const tipIx = SystemProgram.transfer({
        fromPubkey: feePayer,
        toPubkey: new PublicKey(tipAccount),
        lamports: tipAmount
        });

        // Decompile the message to access instructions
        const decompiledMessage = TransactionMessage.decompile(message);
        
        // Extract lookup tables if they exist
        const lookupTables: AddressLookupTableAccount[] = [];
        
        // Check if message is V0 (has address lookup tables)
        if (message.version === 0 && 'addressTableLookups' in message) {
        // We need to fetch or handle lookup tables properly
        // For simplicity, we'll work without them for now
        console.log('⚠️ Transaction has lookup tables - tip addition may fail');
        }
        
        // Add tip instruction at the beginning
        const newInstructions = [tipIx, ...decompiledMessage.instructions];
        
        // Create new transaction message
        const newMessage = new TransactionMessage({
        payerKey: decompiledMessage.payerKey,
        recentBlockhash: decompiledMessage.recentBlockhash,
        instructions: newInstructions
        });

        // Compile to appropriate version
        let compiledMessage: MessageV0;
        if (message.version === 0) {
        compiledMessage = newMessage.compileToV0Message(lookupTables);
        } else {
        // Legacy transaction (not common in 2026)
        throw new Error('Legacy transactions not supported for Jito bundles');
        }
        
        // Create new versioned transaction
        const newTransaction = new VersionedTransaction(compiledMessage);
        
        // Copy signatures from original transaction
        newTransaction.signatures = transaction.signatures;
        
        return newTransaction;

    } catch (error) {
        console.warn('⚠️ Could not add tip, using original transaction:', error);
        return transaction;
    }
    }

  /**
   * Alternative method: Create a new transaction with tip added
   * This is simpler but requires recreating the transaction
   */
  private async addTipToTransactionAlt(
    transaction: VersionedTransaction,
    tipAmount: number
  ): Promise<VersionedTransaction> {
    try {
      // Get tip account
      const tipAccount = await this.getTipAccount();
      console.log(`🎯 Adding ${tipAmount / 1e9} SOL tip to: ${tipAccount.slice(0, 16)}...`);

      // Get message components
      const message = transaction.message;
      const decompiled = TransactionMessage.decompile(message, {
        addressLookupTableAccounts: []
      });

      // Get the fee payer
      const feePayer = decompiled.payerKey;

      // Create tip instruction
      const tipIx = SystemProgram.transfer({
        fromPubkey: feePayer,
        toPubkey: new PublicKey(tipAccount),
        lamports: tipAmount
      });

      // Create new instructions array with tip first
      const newInstructions = [tipIx, ...decompiled.instructions];

      // Create new transaction
      const { Keypair } = await import('@solana/web3.js');
      
      // Get blockhash if needed (use existing if available)
      let recentBlockhash = decompiled.recentBlockhash;
      if (!recentBlockhash) {
        const { blockhash } = await this.connection.getLatestBlockhash();
        recentBlockhash = blockhash;
      }

      // Create new message
      const newMessage = new TransactionMessage({
        payerKey: feePayer,
        recentBlockhash: recentBlockhash,
        instructions: newInstructions
      }).compileToV0Message();

      // Create new transaction
      const newTransaction = new VersionedTransaction(newMessage);
      
      // IMPORTANT: You need to re-sign the transaction
      // This depends on your setup - you may need to pass in signers
      console.warn('⚠️ Note: addTipToTransaction requires re-signing. Ensure you handle signatures properly.');
      
      return transaction; // Return original for now

    } catch (error) {
      console.warn('⚠️ Could not add tip, using original transaction:', error);
      return transaction;
    }
  }

  /**
   * SIMPLIFIED: Just modify the first transaction by prepending tip instruction
   * This assumes you can modify the transaction before it gets to this point
   */
  async prepareBundleWithTip(
    transactions: VersionedTransaction[],
    tipAmount: number = this.RECOMMENDED_TIP
  ): Promise<VersionedTransaction[]> {
    if (transactions.length === 0) return transactions;

    const tipAccount = await this.getTipAccount();
    console.log(`💰 Using tip account: ${tipAccount}`);

    // Return the original transactions - YOU should add the tip instruction 
    // when creating your transactions
    return transactions;
  }

  /**
   * Get a tip account (rotate through available accounts)
   */
  private async getTipAccount(): Promise<string> {
    // Simple round-robin for now
    this.currentTipAccountIndex = (this.currentTipAccountIndex + 1) % JITO_TIP_ACCOUNTS.length;
    return JITO_TIP_ACCOUNTS[this.currentTipAccountIndex];
  }

  /**
   * Monitor bundle confirmation
   */
  private async monitorBundle(bundleId: string, endpoint: string): Promise<void> {
    try {
      // Wait a bit before checking
      await new Promise(resolve => setTimeout(resolve, 2000));

      const statusEndpoint = endpoint.replace('/bundles', `/bundle/${bundleId}/status`);
      
      const response = await axios.get(statusEndpoint, {
        timeout: 10000
      });

      if (response.data.confirmation_status === 'confirmed') {
        console.log(`🎉 Bundle ${bundleId.slice(0, 16)}... CONFIRMED on chain!`);
        if (response.data.slot) {
          console.log(`   Slot: ${response.data.slot}`);
        }
      } else if (response.data.confirmation_status === 'failed') {
        console.log(`❌ Bundle ${bundleId.slice(0, 16)}... FAILED`);
      } else {
        console.log(`⏳ Bundle ${bundleId.slice(0, 16)}... status: ${response.data.confirmation_status}`);
      }

    } catch (error) {
      // Silent fail for monitoring
    }
  }

  /**
   * Check if Jito endpoints are responsive
   */
  async testEndpoints(): Promise<{ endpoint: string; responsive: boolean }[]> {
    const results = [];
    
    for (const endpoint of JITO_BUNDLE_ENDPOINTS) {
      try {
        await axios.get(endpoint.replace('/bundles', '/health'), {
          timeout: 5000
        });
        results.push({ endpoint, responsive: true });
        console.log(`✅ ${endpoint.split('/')[2]} is responsive`);
      } catch (error) {
        results.push({ endpoint, responsive: false });
        console.log(`❌ ${endpoint.split('/')[2]} is not responsive`);
      }
    }
    
    return results;
  }

  /**
   * Utility to shuffle array (for load balancing)
   */
  private shuffleArray<T>(array: T[]): T[] {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  }

  /**
   * Get current bundle stats from Jito
   */
  async getBundleStats(): Promise<any> {
    try {
      const response = await axios.get(
        'https://mainnet.block-engine.jito.wtf/api/v1/bundles/stats',
        { timeout: 10000 }
      );
      return response.data;
    } catch (error) {
      console.warn('Could not fetch bundle stats:', error);
      return null;
    }
  }
}

// Convenience function for quick usage
export async function sendJitoBundle(
  transactions: VersionedTransaction[],
  connection: Connection,
  tipAmount?: number
): Promise<JitoBundleResult> {
  const sender = new JitoBundleSender(connection);
  return sender.sendBundle(transactions, tipAmount);
}

// Helper to create a simple test bundle
export async function testJitoBundle(connection: Connection): Promise<boolean> {
  try {
    const { Keypair, TransactionMessage, VersionedTransaction } = await import('@solana/web3.js');
    const testKeypair = Keypair.generate();
    
    // Create a simple transfer transaction
    const { blockhash } = await connection.getLatestBlockhash('confirmed');
    
    const message = new TransactionMessage({
      payerKey: testKeypair.publicKey,
      recentBlockhash: blockhash,
      instructions: [
        SystemProgram.transfer({
          fromPubkey: testKeypair.publicKey,
          toPubkey: testKeypair.publicKey,
          lamports: 1000
        })
      ]
    });

    const transaction = new VersionedTransaction(message.compileToV0Message());
    transaction.sign([testKeypair]);

    const sender = new JitoBundleSender(connection);
    const result = await sender.sendBundle([transaction], 100_000);
    
    return result.success;
    
  } catch (error) {
    console.error('Test failed:', error);
    return false;
  }
}



export function createJitoBundleSender(connection: Connection): JitoBundleSender {
  return new JitoBundleSender(connection);
}

