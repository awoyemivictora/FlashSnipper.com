import { getReceivedSolAmount } from './src/token_logics.js';



async function testGetReceivedSolAmount() {
    try {
        // Test with a known successful swap transaction signature
        const testTxSignature = '4JWPrGJkd1tzBC9BqnC9reCBZxmYTq14mJzGTts54m2E4hwLyv6dHzUt28PU7f3cdBkRTYY3UDobv3L23jWPhHxG';
        
        console.log(`Testing with tx: ${testTxSignature}`);
        
        // Initialize wallet for testing purposes if not already done
        // (Assuming getWallet() handles initialization or fetches a predefined wallet)
        // const wallet = getWallet();
        // if (!wallet || !wallet.publicKey) {
        //      console.error('Wallet not initialized for testing.');
        //      process.exit(1);
        // }
        // console.log(`✅ Wallet initialized: ${wallet.publicKey.toBase58()}`);

        const receivedAmount = await getReceivedSolAmount(testTxSignature);
        
        console.log('✅ Test successful!');
        console.log(`Received amount: ${receivedAmount} SOL`);
        console.log(`(${receivedAmount.toFixed(9)} SOL)`);
        
        return receivedAmount;
    } catch (error) {
        console.error('❌ Test failed:', error);
        throw error;
    }
}

// Run the test
testGetReceivedSolAmount()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));