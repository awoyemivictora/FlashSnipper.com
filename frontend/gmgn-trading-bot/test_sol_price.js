import { getTokenPrice } from './src/token_logics.js';

const solMint = "So11111111111111111111111111111111111111112"; // SOL
const usdcMint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"; // USDC
const a = "CzHc1ugMNhim5JCJC8ebbp4k14jfrbZx1HNcMyEppump"


// Test script for getSolPrice()
async function testGetSolPrice() {
  try {
    const solPrice = await getTokenPrice(solMint);
    console.log(`SOL Price: $${solPrice}`);

    const usdcPrice = await getTokenPrice(usdcMint);
    console.log(`USDC Price: $${usdcPrice}`);

    const aPrice = await getTokenPrice(a);
    console.log(`a Price: $${aPrice}`);
  } catch (error) {
    console.error(`❌ Error fetching SOL price: ${error.message}`);
  }
}

// Run the test
testGetSolPrice();

