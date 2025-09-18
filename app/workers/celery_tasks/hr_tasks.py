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
def process_daily_attendance():
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
def generate_monthly_salaries(salary_month: str = None):
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

@celery_app.task
def send_attendance_warnings():
    """Daily task to check late/absent employees and send WhatsApp warnings"""
    async def _send_warnings():
        async with async_session_maker() as db:
            try:
                # Import inside function to avoid circular imports
                from app.models.hr.attendance import Attendance
                from app.models.hr.employee import Employee
                from app.models.shared.enums import AttendanceStatus
                from app.services.communication.whatsapp_service import WhatsAppClient
                from sqlalchemy import select, and_
                
                # Get today's date
                today = date.today()
                
                # Query employees with late or absent attendance for today
                query = select(Attendance, Employee).join(
                    Employee, Attendance.employee_id == Employee.id
                ).where(
                    and_(
                        Attendance.attendance_date == today,
                        Attendance.status.in_([AttendanceStatus.LATE, AttendanceStatus.ABSENT]),
                        Employee.is_active == True,
                        Employee.phone.is_not(None)
                    )
                )
                
                result = await db.execute(query)
                attendance_records = result.all()
                
                # Initialize WhatsApp client
                whatsapp_client = WhatsAppClient()
                
                sent_count = 0
                
                for attendance, employee in attendance_records:
                    # Prepare warning message based on attendance status
                    if attendance.status == AttendanceStatus.LATE:
                        message = f"⚠️ Warning: Dear {employee.first_name}, you were late today by {attendance.late_minutes} minutes. Please ensure punctuality. - Management"
                    elif attendance.status == AttendanceStatus.ABSENT:
                        message = f"⚠️ Warning: Dear {employee.first_name}, you were absent today without prior notice. Please contact HR immediately. - Management"
                    
                    # Send WhatsApp message
                    whatsapp_response = await whatsapp_client.send(
                        phone=employee.phone,
                        body=message
                    )
                    
                    if whatsapp_response.get("status") == "ok":
                        sent_count += 1
                        print(f"✅ Warning sent to {employee.first_name} ({employee.phone})")
                    else:
                        print(f"❌ Failed to send warning to {employee.first_name}: {whatsapp_response}")
                
                return f"✅ Attendance warnings sent: {sent_count} messages"
                
            except Exception as e:
                print(f"❌ Error sending attendance warnings: {e}")
                raise
    
    return run_async_task(_send_warnings())
