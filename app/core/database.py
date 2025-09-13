# app/core/database.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

database_url = settings.DATABASE_URL

engine = create_async_engine(
    database_url,
    pool_size=20,           # Increase from 5
    max_overflow=30,        # Increase from 10
    pool_timeout=60,        # Increase timeout
    pool_recycle=3600,      # Recycle connections every hour
    echo=False,
    future=True,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
