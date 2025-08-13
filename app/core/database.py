# app/core/database.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

database_url = settings.DATABASE_URL

engine = create_async_engine(
    database_url,
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
