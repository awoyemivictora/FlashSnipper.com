import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.database import DATABASE_URL, Base
from app.models import *  # This imports all your models so Base knows about all tables
import os

# Optional: load .env if you run this script directly
from dotenv import load_dotenv
load_dotenv()

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found! Check your .env")

print(f"Connecting to: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
print("DROPPING ALL TABLES IN 5 SECONDS... (Ctrl+C to cancel)")
asyncio.run(asyncio.sleep(5))

async def nuke():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    print("NUKE COMPLETE — ALL TABLES DELETED!")

if __name__ == "__main__":
    asyncio.run(nuke())