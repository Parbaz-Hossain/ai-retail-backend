from datetime import date, datetime, timedelta
from app.services.hr.attendance_service import AttendanceService
from app.services.hr.salary_service import SalaryService
from app.core.database import get_async_session
from app.core.celery_app import celery_app


@celery_app.task
async def process_daily_attendance_task():
    """Daily task to process attendance for all employees"""
    db = next(get_async_session)
    service = AttendanceService(db)
    
    yesterday = date.today() - timedelta(days=1)
    result = await service.process_daily_attendance(yesterday)
    
    return result

@celery_app.task
async def generate_monthly_salaries_task(salary_month: str):
    """Monthly task to generate salaries for all employees"""
    db = next(get_async_session)
    service = SalaryService(db)
    
    month_date = datetime.strptime(salary_month, '%Y-%m-%d').date()
    result = await service.generate_bulk_salary(month_date, current_user_id=0)  # System generated
    
    return result

# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "process-attendance-daily": {
        "task": "app.workers.celery_tasks.hr_tasks.process_daily_attendance_task",
        # "schedule": 3600.0,  # Every hour
        "schedule": 60.0,  # Every miunute (for testing purposes)
    },    
    "generate-monthly-salaries": {
        "task": "app.workers.celery_tasks.hr_tasks.generate_monthly_salaries_task",
        "schedule": 86400.0 * 30,  # Every 30 days
    }
}

celery_app.conf.timezone = 'UTC'