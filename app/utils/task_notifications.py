"""
Task notification utilities
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.task.task import Task
from app.models.auth import User
from app.core.config import settings

class TaskNotificationService:
    """Service for sending task-related notifications"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def notify_task_assigned(self, task: Task, assignee: User):
        """Send notification when task is assigned"""
        # Email notification
        self._send_email_notification(
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
            self._send_whatsapp_notification(
                phone=assignee.phone,
                message=f"🔔 New task assigned: {task.title}. Priority: {task.priority.value}. Due: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'No due date'}"
            )
    
    def notify_task_overdue(self, tasks: List[Task]):
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
            assignee = self.db.query(User).filter(User.id == user_id).first()
            if assignee:
                self._send_overdue_notification(assignee, user_tasks)
    
    def notify_task_status_change(self, task: Task, old_status: str, new_status: str, changed_by: User):
        """Send notification when task status changes"""
        # Notify task creator if different from the person who changed it
        if task.created_by != changed_by.id:
            creator = self.db.query(User).filter(User.id == task.created_by).first()
            if creator:
                self._send_email_notification(
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
    
    def _send_email_notification(self, to_email: str, subject: str, template: str, context: dict):
        """Send email notification (implement based on your email service)"""
        # Implementation depends on your email service (SendGrid, AWS SES, etc.)
        pass
    
    def _send_whatsapp_notification(self, phone: str, message: str):
        """Send WhatsApp notification (implement based on your WhatsApp integration)"""
        # Implementation depends on your WhatsApp service (Twilio, WhatsApp Business API, etc.)
        pass
    
    def _send_overdue_notification(self, assignee: User, overdue_tasks: List[Task]):
        """Send notification for overdue tasks"""
        task_list = "\n".join([f"- {task.title} (Due: {task.due_date.strftime('%Y-%m-%d')})" for task in overdue_tasks])
        
        self._send_email_notification(
            to_email=assignee.email,
            subject=f"⚠️ You have {len(overdue_tasks)} overdue task(s)",
            template="tasks_overdue",
            context={
                "assignee": assignee,
                "tasks": overdue_tasks,
                "task_count": len(overdue_tasks)
            }
        )