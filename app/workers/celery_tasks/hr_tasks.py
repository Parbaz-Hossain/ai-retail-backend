from celery import Celery
from datetime import date, datetime, timedelta
from services.hr.attendance_service import AttendanceService
from services.hr.salary_service import SalaryService
from core.database import get_async_session

app = Celery('hr_automation')

@app.task
async def process_daily_attendance_task():
    """Daily task to process attendance for all employees"""
    db = next(get_async_session)
    service = AttendanceService(db)
    
    yesterday = date.today() - timedelta(days=1)
    result = await service.process_daily_attendance(yesterday)
    
    return result

@app.task
async def generate_monthly_salaries_task(salary_month: str):
    """Monthly task to generate salaries for all employees"""
    db = next(get_async_session)
    service = SalaryService(db)
    
    month_date = datetime.strptime(salary_month, '%Y-%m-%d').date()
    result = await service.generate_bulk_salary(month_date, current_user_id=0)  # System generated
    
    return result