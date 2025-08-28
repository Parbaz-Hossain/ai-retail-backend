"""
Task notification utilities
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.shared.enums import TaskStatus
from app.models.task.task import Task
from app.models.auth import User
from app.core.config import settings

class TaskNotificationService:
    """Service for sending task-related notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def notify_task_assigned(self, task: Task, assignee: User):
        """Send notification when task is assigned"""
        # Email notification
        await self._send_email_notification(
            to_email=assignee.email,
            subject=f"New Task Assigned: {task.title}",
            template="task_assigned",
            context={
                "task": task,
                "assignee": assignee,
                "due_date": task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else "No due date"
            }
        )
        
        # WhatsApp notification (if phone available)
        if assignee.phone:
            await self._send_whatsapp_notification(
                phone=assignee.phone,
                message=f"🔔 New task assigned: {task.title}. Priority: {task.priority.value}. Due: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'No due date'}"
            )
    
    async def notify_task_overdue(self, tasks: List[Task]):
        """Send notifications for overdue tasks"""
        # Group tasks by assignee
        tasks_by_user = {}
        for task in tasks:
            if task.assigned_to:
                if task.assigned_to not in tasks_by_user:
                    tasks_by_user[task.assigned_to] = []
                tasks_by_user[task.assigned_to].append(task)
        
        # Send notifications to each user
        for user_id, user_tasks in tasks_by_user.items():
            result = await self.db.execute(select(User).where(User.id == user_id))
            assignee = result.scalar_one_or_none()
            if assignee:
                await self._send_overdue_notification(assignee, user_tasks)
    
    async def notify_task_status_change(self, task: Task, old_status: str, new_status: str, changed_by: User):
        """Send notification when task status changes"""
        # Notify task creator if different from the person who changed it
        if task.created_by != changed_by.id:
            result = await self.db.execute(select(User).where(User.id == task.created_by))
            creator = result.scalar_one_or_none()
            if creator:
                await self._send_email_notification(
                    to_email=creator.email,
                    subject=f"Task Status Updated: {task.title}",
                    template="task_status_change",
                    context={
                        "task": task,
                        "old_status": old_status,
                        "new_status": new_status,
                        "changed_by": changed_by
                    }
                )
    
    async def notify_task_due_soon(self, tasks: List[Task], hours_until_due: int = 24):
        """Send notifications for tasks due soon"""
        # Group tasks by assignee
        tasks_by_user = {}
        for task in tasks:
            if task.assigned_to:
                if task.assigned_to not in tasks_by_user:
                    tasks_by_user[task.assigned_to] = []
                tasks_by_user[task.assigned_to].append(task)
        
        # Send notifications to each user
        for user_id, user_tasks in tasks_by_user.items():
            result = await self.db.execute(select(User).where(User.id == user_id))
            assignee = result.scalar_one_or_none()
            if assignee:
                await self._send_due_soon_notification(assignee, user_tasks, hours_until_due)
    
    async def notify_task_escalation(self, task: Task, escalated_to: User, escalated_by: User):
        """Send notification when task is escalated"""
        await self._send_email_notification(
            to_email=escalated_to.email,
            subject=f"Task Escalated: {task.title}",
            template="task_escalated",
            context={
                "task": task,
                "escalated_to": escalated_to,
                "escalated_by": escalated_by,
                "escalation_reason": f"Task overdue by {(task.due_date - task.created_at).days if task.due_date else 0} days"
            }
        )
    
    async def _send_email_notification(self, to_email: str, subject: str, template: str, context: dict):
        """Send email notification (implement based on your email service)"""
        # Implementation depends on your email service (SendGrid, AWS SES, etc.)
        # For now, just log the notification
        print(f"📧 EMAIL: {to_email} - {subject}")
        print(f"   Template: {template}")
        print(f"   Context: {context}")
        
        # Actual implementation would be:
        # async with aiohttp.ClientSession() as session:
        #     await session.post(
        #         "https://api.sendgrid.com/v3/mail/send",
        #         headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
        #         json=email_payload
        #     )
        pass
    
    async def _send_whatsapp_notification(self, phone: str, message: str):
        """Send WhatsApp notification (implement based on your WhatsApp integration)"""
        # Implementation depends on your WhatsApp service (Twilio, WhatsApp Business API, etc.)
        print(f"📱 WHATSAPP: {phone}")
        print(f"   Message: {message}")
        
        # Actual implementation would be:
        # async with aiohttp.ClientSession() as session:
        #     await session.post(
        #         f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
        #         auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        #         data={
        #             "From": f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
        #             "To": f"whatsapp:{phone}",
        #             "Body": message
        #         }
        #     )
        pass
    
    async def _send_sms_notification(self, phone: str, message: str):
        """Send SMS notification"""
        print(f"📱 SMS: {phone}")
        print(f"   Message: {message}")
        
        # Actual implementation would be similar to WhatsApp but without 'whatsapp:' prefix
        pass
    
    async def _send_overdue_notification(self, assignee: User, overdue_tasks: List[Task]):
        """Send notification for overdue tasks"""
        task_list = "\n".join([f"- {task.title} (Due: {task.due_date.strftime('%Y-%m-%d')})" for task in overdue_tasks])
        
        await self._send_email_notification(
            to_email=assignee.email,
            subject=f"⚠️ You have {len(overdue_tasks)} overdue task(s)",
            template="tasks_overdue",
            context={
                "assignee": assignee,
                "tasks": overdue_tasks,
                "task_count": len(overdue_tasks),
                "task_list": task_list
            }
        )
        
        # Also send WhatsApp/SMS for urgent overdue tasks
        urgent_overdue = [t for t in overdue_tasks if t.priority.value in ['URGENT', 'HIGH']]
        if urgent_overdue and assignee.phone:
            await self._send_whatsapp_notification(
                phone=assignee.phone,
                message=f"⚠️ URGENT: You have {len(urgent_overdue)} high-priority overdue tasks. Please check your task dashboard immediately."
            )
    
    async def _send_due_soon_notification(self, assignee: User, tasks: List[Task], hours_until_due: int):
        """Send notification for tasks due soon"""
        task_list = "\n".join([
            f"- {task.title} (Due: {task.due_date.strftime('%Y-%m-%d %H:%M')})" 
            for task in tasks if task.due_date
        ])
        
        await self._send_email_notification(
            to_email=assignee.email,
            subject=f"📅 {len(tasks)} task(s) due within {hours_until_due} hours",
            template="tasks_due_soon",
            context={
                "assignee": assignee,
                "tasks": tasks,
                "task_count": len(tasks),
                "task_list": task_list,
                "hours_until_due": hours_until_due
            }
        )
    
    async def send_daily_task_digest(self, user: User):
        """Send daily task digest to user"""
        from datetime import datetime, timedelta
        from app.models.shared.enums import TaskStatus, TaskPriority
        
        # Get user's tasks for digest
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        # Pending tasks
        pending_result = await self.db.execute(
            select(Task).where(
                Task.assigned_to == user.id,
                Task.status == TaskStatus.PENDING,
                Task.is_active == True
            ).limit(10)
        )
        pending_tasks = pending_result.scalars().all()
        
        # Tasks due today
        due_today_result = await self.db.execute(
            select(Task).where(
                Task.assigned_to == user.id,
                Task.due_date >= datetime.combine(today, datetime.min.time()),
                Task.due_date < datetime.combine(tomorrow, datetime.min.time()),
                Task.status != TaskStatus.COMPLETED,
                Task.is_active == True
            )
        )
        due_today_tasks = due_today_result.scalars().all()
        
        # Overdue tasks
        overdue_result = await self.db.execute(
            select(Task).where(
                Task.assigned_to == user.id,
                Task.due_date < datetime.now(),
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                Task.is_active == True
            )
        )
        overdue_tasks = overdue_result.scalars().all()
        
        # Only send if user has tasks
        if pending_tasks or due_today_tasks or overdue_tasks:
            await self._send_email_notification(
                to_email=user.email,
                subject=f"📋 Daily Task Digest - {today.strftime('%B %d, %Y')}",
                template="daily_task_digest",
                context={
                    "user": user,
                    "date": today.strftime('%B %d, %Y'),
                    "pending_tasks": pending_tasks,
                    "due_today_tasks": due_today_tasks,
                    "overdue_tasks": overdue_tasks,
                    "total_pending": len(pending_tasks),
                    "total_due_today": len(due_today_tasks),
                    "total_overdue": len(overdue_tasks)
                }
            )
    
    async def send_weekly_team_summary(self, manager: User, team_members: List[User]):
        """Send weekly team task summary to manager"""
        from datetime import datetime, timedelta
        from sqlalchemy import func, case
        
        week_start = datetime.now() - timedelta(days=7)
        
        # Team performance summary
        team_stats = {}
        for member in team_members:
            # Get member's task stats for the week
            stats_result = await self.db.execute(
                select(
                    func.count(Task.id).label('total_tasks'),
                    func.count(case([(Task.status == TaskStatus.COMPLETED, 1)])).label('completed_tasks'),
                    func.count(case([(Task.status == TaskStatus.OVERDUE, 1)])).label('overdue_tasks'),
                    func.avg(
                        case([
                            (Task.completed_at.isnot(None),
                             func.extract('epoch', Task.completed_at - Task.created_at) / 3600)
                        ])
                    ).label('avg_completion_time')
                ).where(
                    Task.assigned_to == member.id,
                    Task.created_at >= week_start,
                    Task.is_active == True
                )
            )
            stats = stats_result.first()
            
            team_stats[member.full_name] = {
                'total_tasks': stats.total_tasks or 0,
                'completed_tasks': stats.completed_tasks or 0,
                'overdue_tasks': stats.overdue_tasks or 0,
                'completion_rate': round((stats.completed_tasks / stats.total_tasks * 100) if stats.total_tasks > 0 else 0, 1),
                'avg_completion_time': round(float(stats.avg_completion_time or 0), 1)
            }
        
        await self._send_email_notification(
            to_email=manager.email,
            subject=f"📊 Weekly Team Task Summary - {week_start.strftime('%B %d')} to {datetime.now().strftime('%B %d, %Y')}",
            template="weekly_team_summary",
            context={
                "manager": manager,
                "team_stats": team_stats,
                "week_start": week_start.strftime('%B %d'),
                "week_end": datetime.now().strftime('%B %d, %Y'),
                "team_size": len(team_members)
            }
        )