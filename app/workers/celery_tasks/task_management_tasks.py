"""
Background tasks for periodic task creation and management
"""
from celery import Celery
from app.db.base import SessionLocal
from app.services.task.task_integration_service import TaskIntegrationService

# Initialize Celery (you'll need to configure this based on your setup)
celery_app = Celery('tasks')

@celery_app.task
def check_low_stock_and_create_tasks():
    """Periodic task to check stock levels and create alert tasks"""
    db = SessionLocal()
    try:
        integration_service = TaskIntegrationService(db)
        integration_service.check_and_create_low_stock_tasks()
    finally:
        db.close()

@celery_app.task
def create_monthly_salary_tasks():
    """Monthly task to create salary processing tasks"""
    db = SessionLocal()
    try:
        integration_service = TaskIntegrationService(db)
        integration_service.create_salary_processing_tasks()
    finally:
        db.close()

@celery_app.task
def create_maintenance_tasks_for_all_locations():
    """Monthly task to create maintenance tasks for all locations"""
    from app.models.organization import Location
    
    db = SessionLocal()
    try:
        integration_service = TaskIntegrationService(db)
        locations = db.query(Location).filter(Location.is_active == True).all()
        
        for location in locations:
            integration_service.create_maintenance_tasks(location.id)
    finally:
        db.close()