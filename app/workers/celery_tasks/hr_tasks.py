"""
Fixed HR Tasks - Using correct Celery app and sync functions
"""
import asyncio
from app.core.celery_app import celery_app  # ← Import from main celery app
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Create async engine for background tasks
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
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

@celery_app.task  # ← Use main celery_app
def process_daily_attendance_task():
    """Daily task to process attendance for all employees"""
    async def _process_attendance():
        async with async_session_maker() as db:
            try:
                # Import inside function to avoid circular imports
                from app.services.hr.attendance_service import AttendanceService
                
                service = AttendanceService(db)
                yesterday = date.today() - timedelta(days=1)
                result = await service.process_daily_attendance(yesterday)
                
                return f"✅ Daily attendance processed: {result}"
            except Exception as e:
                print(f"❌ Error processing attendance: {e}")
                raise
    
    return run_async_task(_process_attendance())

@celery_app.task  # ← Use main celery_app
def generate_monthly_salaries_task(salary_month: str = None):
    """Monthly task to generate salaries for all employees"""
    async def _generate_salaries():
        async with async_session_maker() as db:
            try:
                # Import inside function to avoid circular imports
                from app.services.hr.salary_service import SalaryService
                
                service = SalaryService(db)
                
                # If no salary_month provided, use current month
                if not salary_month:
                    month_date = date.today().replace(day=1)
                else:
                    month_date = datetime.strptime(salary_month, '%Y-%m-%d').date()
                
                result = await service.generate_bulk_salary(month_date, current_user_id=1)  # System user
                
                return f"✅ Monthly salaries generated: {result}"
            except Exception as e:
                print(f"❌ Error generating salaries: {e}")
                raise
    
    return run_async_task(_generate_salaries())

# Simple test task for HR module
@celery_app.task
def simple_hr_test_task():
    """Simple test task for HR module"""
    import time
    print("🚀 Simple HR test task started!")
    time.sleep(2)
    print("✅ Simple HR test task completed!")
    return "Simple HR task completed successfully!"