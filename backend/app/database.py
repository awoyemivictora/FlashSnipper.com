from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No DATABASE_URL set for SQLAlchemy connection")

# This will create a connection to the database (async)
async_engine = create_async_engine(DATABASE_URL, echo=False)

# This will create an async session that talks to the database
AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# This is used for defining database models.
Base = declarative_base()




async def get_db():
    async with AsyncSessionLocal() as session: # This line creates an async session
        yield session   # This line passes the session to the function that needs it.
    # When the function is done, the session automatically closes.



