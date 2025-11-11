import logging
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


############################################################
# 5a. Rugcheck Analysis
############################################################
import aiohttp


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

