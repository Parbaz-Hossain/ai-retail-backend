"""
Fixed Background tasks with proper asyncio handling for Celery
"""
import asyncio
from app.core.celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.services.auth.user_service import UserService

# Create async engine for background tasks with proper pool settings
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections every hour
    pool_size=5,
    max_overflow=10
)

async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

def run_async_in_celery(coro):
    """
    Properly handle asyncio in Celery tasks
    This creates a clean event loop for each task execution
    """
    try:
        # Always create a new event loop for Celery tasks
        if hasattr(asyncio, '_get_running_loop') and asyncio._get_running_loop() is not None:
            # If there's already a running loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            # No running loop, safe to get or create one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(coro)
        finally:
            # Clean up the loop
            try:
                # Cancel any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                # Wait for cancelled tasks to complete
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass  # Ignore cleanup errors
            
            try:
                loop.close()
            except Exception:
                pass  # Ignore close errors
                
    except Exception as e:
        print(f"Error in async task execution: {e}")
        raise

@celery_app.task(bind=True)
def send_daily_hr_tasks(self):
    """Daily task to create and notify HR managers about daily tasks"""
    async def _send_daily_hr_tasks():
        async with async_session_maker() as db:
            try:
                from app.services.task.task_integration_service import TaskIntegrationService
                from app.services.communication.email_service import EmailService
                from app.services.notification.notification_service import NotificationService
                from app.services.auth.user_service import UserService
                
                integration_service = TaskIntegrationService(db)
                email_service = EmailService()
                notification_service = NotificationService(db)
                user_service = UserService(db)
                
                # Get HR managers
                hr_managers = await user_service.get_users_by_roles(["HR_MANAGER"])
                
                for hr_manager in hr_managers:
                    # Create daily attendance processing task
                    from app.schemas.task.task_schema import TaskCreate
                    from app.models.shared.enums import TaskPriority
                    from datetime import datetime, timedelta, date
                    
                    task_data = TaskCreate(
                        title=f"Daily Attendance Processing - {date.today()}",
                        description="Process and review daily employee attendance records",
                        task_type_id=5,  # Assuming HR task type ID
                        priority=TaskPriority.HIGH,
                        assigned_to=hr_manager.id,
                        due_date=datetime.utcnow() + timedelta(hours=8)
                    )
                    
                    task = await integration_service.task_service.create_task(task_data, created_by=1)
                    
                    # Send email notification
                    await email_service.send_email(
                        to_email=hr_manager.email,
                        subject="Daily HR Task - Attendance Processing",
                        html_content=f"""
                        <h2>Daily HR Task Assigned</h2>
                        <p>Your daily attendance processing task has been created:</p>
                        <ul>
                            <li><strong>Task:</strong> {task.title}</li>
                            <li><strong>Priority:</strong> {task.priority.value}</li>
                            <li><strong>Due:</strong> {task.due_date.strftime('%Y-%m-%d %H:%M')}</li>
                        </ul>
                        <p>Please complete this task in your dashboard.</p>
                        """,
                        text_content=f"Daily HR Task: {task.title}"
                    )
                    
                    # Send real-time UI notification
                    await notification_service.send_real_time_notification(
                        user_id=hr_manager.id,
                        notification_type="DAILY_TASK",
                        title="Daily HR Task Assigned",
                        message=f"Daily attendance processing task for {date.today()}",
                        data={"task_id": task.id}
                    )
                
                return f"✅ Daily HR tasks sent to {len(hr_managers)} managers"
                
            except Exception as e:
                print(f"❌ Error sending daily HR tasks: {e}")
                raise
    
    return run_async_in_celery(_send_daily_hr_tasks())

@celery_app.task(bind=True)
def send_daily_inventory_tasks(self):
    """Daily task to create and notify inventory managers"""
    async def _send_daily_inventory_tasks():
        async with async_session_maker() as db:
            try:
                from app.services.task.task_integration_service import TaskIntegrationService
                from app.services.communication.email_service import EmailService
                from app.services.notification.notification_service import NotificationService
                
                integration_service = TaskIntegrationService(db)
                email_service = EmailService()
                notification_service = NotificationService(db)                
                user_service = UserService(db)
                
                # Get HR managers
                inventory_managers = await user_service.get_users_by_roles(["INVENTORY_MANAGER"])
                
                for manager in inventory_managers:
                    # Create daily inventory count task
                    from app.schemas.task.task_schema import TaskCreate
                    from app.models.shared.enums import TaskPriority
                    from datetime import datetime, timedelta, date
                    
                    task_data = TaskCreate(
                        title=f"Daily Inventory Count - {date.today()}",
                        description="Perform daily inventory count and stock verification",
                        task_type_id=3,  # Assuming inventory task type ID
                        priority=TaskPriority.MEDIUM,
                        assigned_to=manager.id,
                        due_date=datetime.utcnow() + timedelta(hours=12)
                    )
                    
                    task = await integration_service.task_service.create_task(task_data, created_by=1)
                    
                    # Send email notification
                    await email_service.send_email(
                        to_email=manager.email,
                        subject="Daily Inventory Task - Stock Count",
                        html_content=f"""
                        <h2>Daily Inventory Task Assigned</h2>
                        <p>Your daily inventory count task has been created:</p>
                        <ul>
                            <li><strong>Task:</strong> {task.title}</li>
                            <li><strong>Priority:</strong> {task.priority.value}</li>
                            <li><strong>Due:</strong> {task.due_date.strftime('%Y-%m-%d %H:%M')}</li>
                        </ul>
                        <p>Please complete the stock count in your dashboard.</p>
                        """,
                        text_content=f"Daily Inventory Task: {task.title}"
                    )
                    
                    # Send real-time UI notification
                    await notification_service.send_real_time_notification(
                        user_id=manager.id,
                        notification_type="DAILY_TASK",
                        title="Daily Inventory Task Assigned",
                        message=f"Daily inventory count task for {date.today()}",
                        data={"task_id": task.id}
                    )
                
                return f"✅ Daily inventory tasks sent to {len(inventory_managers)} managers"
                
            except Exception as e:
                print(f"❌ Error sending daily inventory tasks: {e}")
                raise
    
    return run_async_in_celery(_send_daily_inventory_tasks())

@celery_app.task(bind=True)
def check_low_stock_and_create_tasks(self):
    """Periodic task to check stock levels and create alert tasks"""
    async def _check_low_stock():
        async with async_session_maker() as db:
            try:
                from app.services.task.task_integration_service import TaskIntegrationService
                
                integration_service = TaskIntegrationService(db)
                await integration_service.check_and_create_low_stock_tasks(user_id=1) # System user
                return "✅ Low stock check completed and tasks created"
            except Exception as e:
                print(f"❌ Error in low stock check: {e}")
                raise
    
    return run_async_in_celery(_check_low_stock())

@celery_app.task(bind=True)
def create_monthly_salary_tasks(self):
    """Monthly task to create salary processing tasks"""
    async def _create_salary_tasks():
        async with async_session_maker() as db:
            try:
                from app.services.task.task_integration_service import TaskIntegrationService
                
                integration_service = TaskIntegrationService(db)
                await integration_service.create_salary_processing_tasks(user_id=1)
                return "✅ Monthly salary tasks created"
            except Exception as e:
                print(f"❌ Error creating salary tasks: {e}")
                raise
    
    return run_async_in_celery(_create_salary_tasks())

@celery_app.task(bind=True)
def create_maintenance_tasks_for_all_locations(self):
    """Monthly task to create maintenance tasks for all locations"""
    async def _create_maintenance_tasks():
        async with async_session_maker() as db:
            try:
                from app.services.task.task_integration_service import TaskIntegrationService
                from sqlalchemy import select
                
                integration_service = TaskIntegrationService(db)
                
                # Get all active locations
                try:
                    from app.models.organization import Location
                    result = await db.execute(select(Location).where(Location.is_active == True))
                    locations = result.scalars().all()
                    
                    for location in locations:
                        await integration_service.create_maintenance_tasks(location.id)
                    
                    return f"✅ Maintenance tasks created for {len(locations)} locations"
                except ImportError:
                    # If Location model doesn't exist, skip
                    return "✅ Maintenance tasks skipped - Location model not found"
                    
            except Exception as e:
                print(f"❌ Error creating maintenance tasks: {e}")
                raise
    
    return run_async_in_celery(_create_maintenance_tasks())

@celery_app.task(bind=True)
def check_overdue_tasks_and_notify(self):
    """Daily task to check overdue tasks and send notifications"""
    async def _check_overdue_tasks():
        async with async_session_maker() as db:
            try:
                from app.models.task.task import Task
                from app.models.shared.enums import TaskStatus
                from app.utils.task_notifications import TaskNotificationService
                from sqlalchemy import select, and_
                from datetime import datetime
                
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
                    return f"✅ Overdue notifications sent for {len(overdue_tasks)} tasks"
                else:
                    return "✅ No overdue tasks found"
                    
            except Exception as e:
                print(f"❌ Error checking overdue tasks: {e}")
                raise
    
    return run_async_in_celery(_check_overdue_tasks())

@celery_app.task(bind=True)
def check_tasks_due_soon(self):
    """Task to check for tasks due within 24 hours and send notifications"""
    async def _check_tasks_due_soon():
        async with async_session_maker() as db:
            try:
                from app.models.task.task import Task
                from app.models.shared.enums import TaskStatus
                from app.utils.task_notifications import TaskNotificationService
                from sqlalchemy import select, and_
                from datetime import datetime, timedelta
                
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
                    return f"✅ Due soon notifications sent for {len(due_soon_tasks)} tasks"
                else:
                    return "✅ No tasks due soon found"
                    
            except Exception as e:
                print(f"❌ Error checking tasks due soon: {e}")
                raise
    
    return run_async_in_celery(_check_tasks_due_soon())

@celery_app.task(bind=True)
def send_daily_task_digests(self):
    """Daily task to send task digests to all active users"""
    async def _send_daily_digests():
        async with async_session_maker() as db:
            try:
                from app.models.auth import User
                from app.utils.task_notifications import TaskNotificationService
                from sqlalchemy import select
                
                notification_service = TaskNotificationService(db)
                
                # Get all active users
                result = await db.execute(select(User).where(User.is_active == True))
                active_users = result.scalars().all()
                
                digest_count = 0
                for user in active_users:
                    if user.email:  # Only send to users with email
                        await notification_service.send_daily_task_digest(user)
                        digest_count += 1
                
                return f"✅ Daily task digests sent to {digest_count} users"
                    
            except Exception as e:
                print(f"❌ Error sending daily digests: {e}")
                raise
    
    return run_async_in_celery(_send_daily_digests())

@celery_app.task(bind=True)
def escalate_overdue_high_priority_tasks(self):
    """Task to escalate high priority tasks that are significantly overdue"""
    async def _escalate_overdue_tasks():
        async with async_session_maker() as db:
            try:
                from app.models.task.task import Task
                from app.models.shared.enums import TaskStatus, TaskPriority
                from app.models.auth import User
                from app.utils.task_notifications import TaskNotificationService
                from sqlalchemy import select, and_
                from datetime import datetime, timedelta
                
                notification_service = TaskNotificationService(db)
                
                # Get high priority tasks overdue by more than 2 days
                escalation_threshold = datetime.utcnow() - timedelta(days=2)
                
                result = await db.execute(
                    select(Task).where(
                        and_(
                            Task.due_date < escalation_threshold,
                            Task.priority.in_([TaskPriority.HIGH, TaskPriority.URGENT]),
                            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                            Task.is_active == True
                        )
                    )
                )
                overdue_high_priority_tasks = result.scalars().all()
                
                escalated_count = 0
                for task in overdue_high_priority_tasks:
                    # Find a manager or admin to escalate to
                    manager_result = await db.execute(
                        select(User).where(
                            and_(
                                User.is_active == True,
                                User.is_superuser == True
                            )
                        ).limit(1)
                    )
                    manager = manager_result.scalar_one_or_none()
                    
                    if manager:
                        await notification_service.notify_task_escalation(
                            task=task,
                            escalated_to=manager,
                            escalated_by=manager
                        )
                        escalated_count += 1
                
                if escalated_count > 0:
                    await db.commit()
                    return f"✅ Escalated {escalated_count} overdue high-priority tasks"
                else:
                    return "✅ No tasks require escalation"
                    
            except Exception as e:
                print(f"❌ Error escalating overdue tasks: {e}")
                raise
    
    return run_async_in_celery(_escalate_overdue_tasks())

@celery_app.task(bind=True)
def generate_task_analytics_cache(self):
    """Generate and cache task analytics for faster dashboard loading"""
    async def _generate_analytics_cache():
        async with async_session_maker() as db:
            try:
                from app.services.task.task_dashboard_service import TaskDashboardService
                
                dashboard_service = TaskDashboardService(db)
                
                # Generate analytics for different time periods
                periods = [7, 30, 90]
                cached_periods = []
                
                for days in periods:
                    analytics = await dashboard_service.get_task_analytics(days)
                    cached_periods.append(days)
                    # Note: Redis caching removed since it may not be configured for caching
                    
                return f"✅ Task analytics generated for {len(cached_periods)} periods"
                    
            except Exception as e:
                print(f"❌ Error generating analytics cache: {e}")
                raise
    
    return run_async_in_celery(_generate_analytics_cache())

@celery_app.task(bind=True)
def cleanup_completed_tasks(self):
    """Archive old completed tasks to keep database performance optimal"""
    async def _cleanup_completed_tasks():
        async with async_session_maker() as db:
            try:
                from app.models.task.task import Task
                from app.models.shared.enums import TaskStatus
                from sqlalchemy import select, and_, func, update
                from datetime import datetime, timedelta
                
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
                    # Mark them as archived
                    await db.execute(
                        update(Task).where(
                            and_(
                                Task.status == TaskStatus.COMPLETED,
                                Task.completed_at < archive_threshold,
                                Task.is_active == True
                            )
                        ).values(is_active=False)
                    )
                    
                    await db.commit()
                    return f"✅ Archived {tasks_to_archive} old completed tasks"
                else:
                    return "✅ No old completed tasks to archive"
                    
            except Exception as e:
                print(f"❌ Error cleaning up completed tasks: {e}")
                raise
    
    return run_async_in_celery(_cleanup_completed_tasks())

# Simple test task for debugging
@celery_app.task(bind=True)
def simple_test_task(self):
    """Simple test task without database connections"""
    import time
    print("🚀 Simple test task started!")
    time.sleep(2)
    print("✅ Simple test task completed!")
    return "Simple task completed successfully!"