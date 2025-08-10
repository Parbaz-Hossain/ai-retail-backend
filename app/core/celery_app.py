from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "ai_retail_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.celery_tasks.inventory_tasks",
        "app.workers.celery_tasks.hr_tasks",
        "app.workers.celery_tasks.email_tasks",
        "app.workers.celery_tasks.report_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_routes={
        "app.workers.celery_tasks.*": {"queue": "main"},
    }
)

# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "check-low-stock-daily": {
        "task": "app.workers.celery_tasks.inventory_tasks.check_low_stock_alerts",
        "schedule": 86400.0,  # Every 24 hours
    },
    "generate-monthly-salaries": {
        "task": "app.workers.celery_tasks.hr_tasks.generate_monthly_salaries",
        "schedule": 86400.0 * 30,  # Every 30 days
    },
    "process-attendance-daily": {
        "task": "app.workers.celery_tasks.hr_tasks.process_daily_attendance",
        "schedule": 3600.0,  # Every hour
    },
    "cleanup-old-logs": {
        "task": "app.workers.celery_tasks.system_tasks.cleanup_old_logs",
        "schedule": 86400.0 * 7,  # Weekly
    },
}
