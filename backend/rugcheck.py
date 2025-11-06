import asyncio
import aiohttp
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_rug(mint: str):
    """
    Checks the rug risk of a token using the RugCheck API.
    """
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data # Return RugCheck report
                else:
                    error_message = await response.text()
                    logger.error(f"Error checking RugCheck API for {mint}: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Failed to connect to RugCheck API for {mint}: {e}")
        return None



async def test_check_rug():
    # mint = "BMzExALxUEjwdZmzSEiLRgcLU7JSNA9xNaYvLnfApump" 
    mint = "GnQUsLcyZ3NXUAPXymWoefMYfCwmJazBVkko4vb7pump" 
    result = await check_rug(mint)
    
    if result:
        print("✅ RugCheck Data:", result)
    else:
        print("❌ Failed to fetch RugCheck data")

# Run the test
asyncio.run(test_check_rug())

