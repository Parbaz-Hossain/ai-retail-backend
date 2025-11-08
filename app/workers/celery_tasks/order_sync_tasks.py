"""
Order sync tasks - Celery background tasks for Foodics order synchronization
"""
import asyncio
from app.core.celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Create async engine for background tasks
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)

async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

def run_async_task(coro):
    """Helper function to run async coroutines in Celery tasks"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        print(f"Error in async task: {e}")
        raise
    finally:
        loop.close()


@celery_app.task(bind=True)
def sync_foodics_orders_hourly(self):
    """
    Hourly task to sync orders from Foodics API for all locations.
    This ensures the order data is always up-to-date.
    """
    async def _sync_orders():
        async with async_session_maker() as db:
            try:
                from app.services.inventory.foodics_order_service import FoodicsOrderService
                
                # Get Foodics API token
                foodics_token = getattr(settings, 'FOODICS_API_TOKEN', None)
                if not foodics_token:
                    print("❌ Foodics API token not configured")
                    return "Failed: Foodics API token not configured"
                
                # Create service and sync all locations
                service = FoodicsOrderService(db, foodics_token)
                result = await service.fetch_and_save_orders(location_id=None)  # Sync all locations
                
                if result["success"]:
                    print(f"✅ Hourly order sync completed: {result['orders_synced']} orders synced")
                    return f"Success: {result['orders_synced']} orders synced"
                else:
                    print(f"⚠️ Order sync completed with errors: {result['message']}")
                    return f"Partial success: {result['message']}"
                    
            except Exception as e:
                print(f"❌ Error in hourly order sync: {e}")
                raise
    
    return run_async_task(_sync_orders())