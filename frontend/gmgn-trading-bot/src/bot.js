import tradeTokens from './trader.js';
import { monitorPositions } from './monitor.js';

async function main() {
  console.log("🚀 Starting GMGN Trading Bot...");
  
  // Rurn tradeTokens in a separate async loop
  (async () => {
    while (true) {
      try {
        await tradeTokens();
        console.log("✅ Trading cycle complete.");
        // Sleep for 1 hour after successful trade
        await new Promise(res => setTimeout(res, 3600000));
      } catch (error) {
        console.error("❌ Error in trading:", error);
        // Sleep for 1 hour before retrying
        await new Promise(res => setTimeout(res, 3600000));

      }
    }
  })();

  
  // Continuosly monitor positions every 5 minutes
  setInterval(async () => {
    try {
      console.log("🔄 Checking for stop loss and take profit triggers...");
      await monitorPositions();
    } catch (error) {
      console.error("❌ Error in monitoring:", error);
    }
  }, 30000);   // 300000 ms = 5 minutes, 60000 ms = 1 mins, 30000 = 30 secs
}

main().catch(console.error);