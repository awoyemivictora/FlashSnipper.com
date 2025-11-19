# test_tavily.py
import asyncio
from app.utils.tavily_api import tavily_client

async def main():
    print("Testing Tavily API...")
    try:
        results = await tavily_client.search_news("DeepSeek AI crypto", max_results=3)
        print("Success! Got results:")
        for r in results:
            print(f"- {r.get('title')} | {r.get('url')}")
    except Exception as e:
        print("Tavily failed:", e)

if __name__ == "__main__":
    asyncio.run(main())