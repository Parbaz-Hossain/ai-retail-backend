from celery import Celery
from app.core.config import settings
import sys

# Create Celery app
celery_app = Celery(
    "ai_retail_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.celery_tasks.hr_tasks",
        # "app.workers.celery_tasks.email_tasks",
        # "app.workers.celery_tasks.report_tasks",
        "app.workers.celery_tasks.task_management_tasks"  
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
    # task_routes={
    #     "app.workers.celery_tasks.*": {"queue": "main"},
    # }
)

# Windows-specific configuration
if sys.platform == 'win32':
    celery_app.conf.update(
        worker_pool='threads',
        worker_concurrency=4
    )

# Combined beat schedule from both files
celery_app.conf.beat_schedule = {
    # Original schedules
    "generate-monthly-salaries": {
        "task": "app.workers.celery_tasks.hr_tasks.generate_monthly_salaries_task",
        "schedule": 86400.0 * 30,  # Every 30 days
    },
    "process-attendance-daily": {
        "task": "app.workers.celery_tasks.hr_tasks.process_daily_attendance_task",
        "schedule": 3600.0,  # Every hour
    },
    
    # Task management schedules (from task_management_tasks.py)
    'check-low-stock-every-hour': {
        'task': 'app.workers.celery_tasks.task_management_tasks.check_low_stock_and_create_tasks',
        # 'schedule': 3600.0,  # Every hour
        'schedule': 60.0,  # Every minute (for testing)
    },
    'create-monthly-salary-tasks': {
        'task': 'app.workers.celery_tasks.task_management_tasks.create_monthly_salary_tasks',
        'schedule': 86400.0,  # Daily
    },
    'create-maintenance-tasks': {
        'task': 'app.workers.celery_tasks.task_management_tasks.create_maintenance_tasks_for_all_locations',
        'schedule': 2592000.0,  # Monthly (30 days)
    },
    'check-overdue-tasks': {
        'task': 'app.workers.celery_tasks.task_management_tasks.check_overdue_tasks_and_notify',
        'schedule': 3600.0,  # Every hour
    },
    'check-tasks-due-soon': {
        'task': 'app.workers.celery_tasks.task_management_tasks.check_tasks_due_soon',
        'schedule': 10800.0,  # Every 3 hours
    },
    'send-daily-digests': {
        'task': 'app.workers.celery_tasks.task_management_tasks.send_daily_task_digests',
        'schedule': 86400.0,  # Daily
    },
    'escalate-overdue-tasks': {
        'task': 'app.workers.celery_tasks.task_management_tasks.escalate_overdue_high_priority_tasks',
        'schedule': 43200.0,  # Every 12 hours
    },
    'generate-analytics-cache': {
        'task': 'app.workers.celery_tasks.task_management_tasks.generate_task_analytics_cache',
        'schedule': 1800.0,  # Every 30 minutes
    },
    'cleanup-completed-tasks': {
        'task': 'app.workers.celery_tasks.task_management_tasks.cleanup_completed_tasks',
        'schedule': 604800.0,  # Weekly
    },
}

celery_app.conf.timezone = 'UTC'