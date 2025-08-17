import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine
from app.models import *  # Import all models
# from app.db.seeds.initial_data import create_initial_data
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

async def create_tables():
    """Create all database tables"""
    try:
        from app.db.base import Base
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Database tables created successfully")
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {str(e)}")
        raise

async def init_db():
    """Initialize the database"""
    try:
        from app.utils.database_safety import DatabaseSafety
        
        # Environment safety check
        env = DatabaseSafety.check_environment()
        logger.info(f"🗄️  Initializing database for {env} environment...")
        
        # Enable safety measures
        DatabaseSafety.prevent_destructive_operations()
        
        # Connect to Redis
        await redis_client.connect()
        
        # Create tables
        await create_tables()
        
        # Verify database integrity
        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            integrity_ok = await DatabaseSafety.verify_database_integrity(session)
            if not integrity_ok:
                raise RuntimeError("Database integrity check failed!")
        
        # Create initial data
        # async with async_session_maker() as session:
        #     await create_initial_data(session)
        
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise
    """Initialize the database"""
    try:
        logger.info("🗄️  Initializing database...")
        
        # Connect to Redis
        await redis_client.connect()
        
        # Create tables
        await create_tables()
        
        # Create initial data
        # async with async_session_maker() as session:
        #     await create_initial_data(session)
        
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise