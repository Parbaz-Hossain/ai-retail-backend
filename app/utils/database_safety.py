"""
Database Safety Utilities
Prevents accidental destructive operations
"""
import os
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DatabaseSafetyError(Exception):
    """Raised when unsafe database operation is attempted"""
    pass

class DatabaseSafety:
    """Database safety checks and protection"""
    
    @staticmethod
    def check_environment() -> str:
        """Get and validate current environment"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        return env
    
    @staticmethod
    async def verify_database_integrity(session: AsyncSession) -> bool:
        """Verify database exists and has expected tables"""
        try:
            # Check if core tables exist
            result = await session.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            tables = [row[0] for row in result.fetchall()]
            
            core_tables = ["users", "roles", "permissions", "departments", "locations"]
            missing_tables = [table for table in core_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"🚨 Missing core tables: {missing_tables}")
                return False
                
            logger.info(f"✅ Database integrity verified. Found {len(tables)} tables.")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database integrity check failed: {e}")
            return False
    
    @staticmethod
    def prevent_destructive_operations():
        """Prevent destructive operations in production"""
        env = DatabaseSafety.check_environment()
        
        if env == "production":
            # Additional safety measures for production
            os.environ["ALEMBIC_SKIP_REV_CHECK"] = "false"
            os.environ["PREVENT_DROP_TABLES"] = "true"
            
        logger.info(f"🛡️ Database safety measures active for {env} environment")