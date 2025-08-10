from celery import current_task
import logging
from datetime import datetime, timedelta
from app.core.celery_app import celery_app
from app.services.hr.salary_service import SalaryService
from app.services.hr.attendance_service import AttendanceService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def generate_monthly_salaries(self):
    """Generate monthly salaries for all employees"""
    try:
        current_date = datetime.now()
        
        # Only generate if it's after the 25th of the month
        if current_date.day < 25:
            logger.info("⏰ Salary generation only allowed from 25th day of month")
            return {"status": "skipped", "reason": "Too early in month"}
        
        logger.info(f"💰 Generating monthly salaries for {current_date.strftime('%B %Y')}")
        
        salary_service = SalaryService()
        
        # Generate salaries for all active employees
        results = salary_service.generate_monthly_salaries_sync(
            month=current_date.month,
            year=current_date.year
        )
        
        logger.info(f"✅ Generated {results['generated_count']} salary records")
        
        return {
            "status": "completed",
            "generated_count": results["generated_count"],
            "failed_count": results["failed_count"],
            "total_amount": results["total_amount"],
            "month": current_date.month,
            "year": current_date.year
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating salaries: {str(e)}")
        raise self.retry(exc=e, countdown=3600, max_retries=3)  # Retry after 1 hour

@celery_app.task(bind=True)
def process_daily_attendance(self):
    """Process daily attendance and mark absent employees"""
    try:
        current_date = datetime.now().date()
        logger.info(f"👥 Processing attendance for {current_date}")
        
        attendance_service = AttendanceService()
        
        # Process attendance for today
        results = attendance_service.process_daily_attendance_sync(current_date)
        
        logger.info(f"✅ Processed attendance: {results['processed_count']} employees")
        
        return {
            "status": "completed",
            "date": str(current_date),
            "processed_count": results["processed_count"],
            "present_count": results["present_count"],
            "absent_count": results["absent_count"],
            "late_count": results["late_count"]
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing attendance: {str(e)}")
        raise self.retry(exc=e, countdown=1800, max_retries=5)  # Retry after 30 minutes