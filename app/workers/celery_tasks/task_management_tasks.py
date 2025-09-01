"""
Background tasks for periodic task creation and management
"""
import asyncio
from app.core.celery_app import celery_app
from app.core.database import get_async_session
from app.services.task.task_integration_service import TaskIntegrationService
from app.services.task.task_dashboard_service import TaskDashboardService
from app.utils.task_notifications import TaskNotificationService

# Create async engine for background tasks

def run_async_task(coro):
    """Helper function to run async coroutines in Celery tasks"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@celery_app.task
def check_low_stock_and_create_tasks():
    """Periodic task to check stock levels and create alert tasks"""
    async def _check_low_stock():
        db = await get_async_session()
        try:
            integration_service = TaskIntegrationService(db)
            await integration_service.check_and_create_low_stock_tasks()
            print("✅ Low stock check completed and tasks created")
        except Exception as e:
            print(f"❌ Error in low stock check: {e}")
        finally:
            await db.close()
    
    return run_async_task(_check_low_stock())

@celery_app.task
def create_monthly_salary_tasks():
    """Monthly task to create salary processing tasks"""
    async def _create_salary_tasks():
        db = await get_async_session()
        try:
            integration_service = TaskIntegrationService(db)
            await integration_service.create_salary_processing_tasks()
            print("✅ Monthly salary tasks created")
        except Exception as e:
            print(f"❌ Error creating salary tasks: {e}")
        finally:
            await db.close()
    
    return run_async_task(_create_salary_tasks())

@celery_app.task
def create_maintenance_tasks_for_all_locations():
    """Monthly task to create maintenance tasks for all locations"""
    async def _create_maintenance_tasks():
        from app.models.organization import Location
        from sqlalchemy import select
        
        db = await get_async_session()
        try:
            integration_service = TaskIntegrationService(db)
            
            # Get all active locations
            result = await db.execute(select(Location).where(Location.is_active == True))
            locations = result.scalars().all()
            
            for location in locations:
                await integration_service.create_maintenance_tasks(location.id)
            
            print(f"✅ Maintenance tasks created for {len(locations)} locations")
        except Exception as e:
            print(f"❌ Error creating maintenance tasks: {e}")
        finally:
            await db.close()
    
    return run_async_task(_create_maintenance_tasks())

@celery_app.task
def check_overdue_tasks_and_notify():
    """Daily task to check overdue tasks and send notifications"""
    async def _check_overdue_tasks():
        from app.models.task.task import Task
        from app.models.shared.enums import TaskStatus
        from sqlalchemy import select, and_
        from datetime import datetime
        
        db = await get_async_session()
        try:
            notification_service = TaskNotificationService(db)
            
            # Get overdue tasks
            result = await db.execute(
                select(Task).where(
                    and_(
                        Task.due_date < datetime.utcnow(),
                        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                        Task.is_active == True
                    )
                )
            )
            overdue_tasks = result.scalars().all()
            
            if overdue_tasks:
                await notification_service.notify_task_overdue(overdue_tasks)
                print(f"✅ Overdue notifications sent for {len(overdue_tasks)} tasks")
            else:
                print("✅ No overdue tasks found")
                
        except Exception as e:
            print(f"❌ Error checking overdue tasks: {e}")
        finally:
            await db.close()
    
    return run_async_task(_check_overdue_tasks())

@celery_app.task
def check_tasks_due_soon():
    """Task to check for tasks due within 24 hours and send notifications"""
    async def _check_tasks_due_soon():
        from app.models.task.task import Task
        from app.models.shared.enums import TaskStatus
        from sqlalchemy import select, and_
        from datetime import datetime, timedelta
        
        db = await get_async_session()
        try:
            notification_service = TaskNotificationService(db)
            
            # Get tasks due within 24 hours
            now = datetime.utcnow()
            tomorrow = now + timedelta(hours=24)
            
            result = await db.execute(
                select(Task).where(
                    and_(
                        Task.due_date >= now,
                        Task.due_date <= tomorrow,
                        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                        Task.is_active == True
                    )
                )
            )
            due_soon_tasks = result.scalars().all()
            
            if due_soon_tasks:
                await notification_service.notify_task_due_soon(due_soon_tasks, 24)
                print(f"✅ Due soon notifications sent for {len(due_soon_tasks)} tasks")
            else:
                print("✅ No tasks due soon found")
                
        except Exception as e:
            print(f"❌ Error checking tasks due soon: {e}")
        finally:
            await db.close()
    
    return run_async_task(_check_tasks_due_soon())

@celery_app.task
def send_daily_task_digests():
    """Daily task to send task digests to all active users"""
    async def _send_daily_digests():
        from app.models.auth import User
        from sqlalchemy import select
        
        db = await get_async_session()
        try:
            notification_service = TaskNotificationService(db)
            
            # Get all active users
            result = await db.execute(select(User).where(User.is_active == True))
            active_users = result.scalars().all()
            
            digest_count = 0
            for user in active_users:
                if user.email:  # Only send to users with email
                    await notification_service.send_daily_task_digest(user)
                    digest_count += 1
            
            print(f"✅ Daily task digests sent to {digest_count} users")
                
        except Exception as e:
            print(f"❌ Error sending daily digests: {e}")
        finally:
            await db.close()
    
    return run_async_task(_send_daily_digests())

@celery_app.task
def escalate_overdue_high_priority_tasks():
    """Task to escalate high priority tasks that are significantly overdue"""
    async def _escalate_overdue_tasks():
        from app.models.task.task import Task
        from app.models.shared.enums import TaskStatus, TaskPriority
        from app.models.auth import User
        from sqlalchemy import select, and_
        from datetime import datetime, timedelta
        
        db = await get_async_session()
        try:
            notification_service = TaskNotificationService(db)
            
            # Get high priority tasks overdue by more than 2 days
            escalation_threshold = datetime.utcnow() - timedelta(days=2)
            
            result = await db.execute(
                select(Task).where(
                    and_(
                        Task.due_date < escalation_threshold,
                        Task.priority.in_([TaskPriority.HIGH, TaskPriority.URGENT]),
                        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                        Task.escalation_level < 2,  # Don't escalate more than twice
                        Task.is_active == True
                    )
                )
            )
            overdue_high_priority_tasks = result.scalars().all()
            
            escalated_count = 0
            for task in overdue_high_priority_tasks:
                # Find a manager or admin to escalate to
                # This is simplified - in real implementation, you'd have proper hierarchy logic
                manager_result = await db.execute(
                    select(User).where(
                        and_(
                            User.is_active == True,
                            User.is_superuser == True  # Escalate to admin/superuser
                        )
                    ).limit(1)
                )
                manager = manager_result.scalar_one_or_none()
                
                if manager and task.assignee:
                    # Update escalation level
                    task.escalation_level += 1
                    task.escalated_at = datetime.utcnow()
                    
                    # Send escalation notification
                    await notification_service.notify_task_escalation(
                        task=task,
                        escalated_to=manager,
                        escalated_by=manager  # System escalation
                    )
                    escalated_count += 1
            
            if escalated_count > 0:
                await db.commit()
                print(f"✅ Escalated {escalated_count} overdue high-priority tasks")
            else:
                print("✅ No tasks require escalation")
                
        except Exception as e:
            print(f"❌ Error escalating overdue tasks: {e}")
        finally:
            await db.close()
    
    return run_async_task(_escalate_overdue_tasks())

@celery_app.task
def generate_task_analytics_cache():
    """Generate and cache task analytics for faster dashboard loading"""
    async def _generate_analytics_cache():
        import json
        from app.core.redis import redis_client  # Assuming you have Redis setup
        
        db = await get_async_session()
        try:
            dashboard_service = TaskDashboardService(db)
            
            # Generate analytics for different time periods
            periods = [7, 30, 90]
            
            for days in periods:
                analytics = await dashboard_service.get_task_analytics(days)
                
                # Cache analytics data (expires in 1 hour)
                cache_key = f"task_analytics_{days}_days"
                if hasattr(redis_client, 'setex'):
                    redis_client.setex(cache_key, 3600, json.dumps(analytics))
                
            print(f"✅ Task analytics cached for {len(periods)} periods")
                
        except Exception as e:
            print(f"❌ Error generating analytics cache: {e}")
        finally:
            await db.close()
    
    return run_async_task(_generate_analytics_cache())

@celery_app.task
def cleanup_completed_tasks():
    """Archive old completed tasks to keep database performance optimal"""
    async def _cleanup_completed_tasks():
        from app.models.task.task import Task
        from app.models.shared.enums import TaskStatus
        from sqlalchemy import select, and_, func
        from datetime import datetime, timedelta
        
        db = await get_async_session()
        try:
            # Archive tasks completed more than 6 months ago
            archive_threshold = datetime.utcnow() - timedelta(days=180)
            
            # Count tasks to be archived
            count_result = await db.execute(
                select(func.count()).select_from(Task).where(
                    and_(
                        Task.status == TaskStatus.COMPLETED,
                        Task.completed_at < archive_threshold,
                        Task.is_active == True
                    )
                )
            )
            tasks_to_archive = count_result.scalar()
            
            if tasks_to_archive > 0:
                # In a real implementation, you might move these to an archive table
                # For now, we'll just mark them as archived
                await db.execute(
                    select(Task).where(
                        and_(
                            Task.status == TaskStatus.COMPLETED,
                            Task.completed_at < archive_threshold,
                            Task.is_active == True
                        )
                    ).values(is_active=False)
                )
                
                await db.commit()
                print(f"✅ Archived {tasks_to_archive} old completed tasks")
            else:
                print("✅ No old completed tasks to archive")
                
        except Exception as e:
            print(f"❌ Error cleaning up completed tasks: {e}")
        finally:
            await db.close()
    
    return run_async_task(_cleanup_completed_tasks())

# Celery Beat Schedule (add to your celery configuration)
celery_app.conf.beat_schedule = {
    'check-low-stock-every-hour': {
        'task': 'app.workers.celery_tasks.task_management_tasks.check_low_stock_and_create_tasks',
        # 'schedule': 3600.0,  # Every hour
        'schedule': 60.0,  # Every minute (for testing purposes)
    },
    'create-monthly-salary-tasks': {
        'task': 'app.workers.celery_tasks.task_management_tasks.create_monthly_salary_tasks',
        'schedule': 86400.0,  # Daily (will only create if it's after 25th)
        'kwargs': {},
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
        'options': {'expires': 3600}  # Expire if not run within an hour
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