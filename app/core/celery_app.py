from celery import Celery
from app.core.config import settings

# Create Celery app
def create_celery_app():
    celery_app = Celery(
        "ai_retail_backend",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            'app.workers.celery_tasks.hr_tasks',
            # "app.workers.celery_tasks.email_tasks",
            # "app.workers.celery_tasks.report_tasks",
            'app.workers.celery_tasks.task_management_tasks'
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

    return celery_app

celery_app = create_celery_app()

    
  