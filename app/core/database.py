# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "postgresql+asyncpg://postgres:pgadmin123@localhost/ai_retail_db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session() -> AsyncSession:   
    async with async_session_maker() as session:
        yield session
