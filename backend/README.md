# Robert Peaneur Solana Snipping Bot FastAPI Backend


Got it! Since Bitquery doesn't support running all queries at once, you need a sequential approach:

First Query: Fetch newly created Pump.fun tokens.
Second Query: Fetch Buy/Sell/Trade data for a specific token pair.
Third Query: Fetch Market Cap, Liquidity, and Volume.
Solution:
Step 1: Run the first query to get newly created tokens.
Step 2: For each token from step 1, extract MintAddress and run the second query.
Step 3: After getting the trade data, run the third query for liquidity and volume.
Implementation:
Use a loop to handle tokens one by one.
Add delays if needed to avoid rate limits.
Use a task queue (like Celery or Redis Queue) for automation.
Are you running these queries manually or need a script to automate this process? I can write a Python script using requests and asyncio to optimize execution.

