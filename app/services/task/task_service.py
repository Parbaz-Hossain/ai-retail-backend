from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta
import uuid
from app.models.task.task import Task
from app.models.task.task_type import TaskType
from app.models.task.task_assignment import TaskAssignment
from app.models.task.task_comment import TaskComment
from app.models.auth import User
from app.models.shared.enums import TaskStatus, TaskPriority, ReferenceType
from app.schemas.task.task_schema import TaskCreate, TaskUpdate, TaskSummary
from app.core.exceptions import NotFoundError

class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def generate_task_number(self) -> str:
        """Generate unique task number"""
        prefix = "TASK"
        timestamp = datetime.now().strftime("%y%m%d")
        random_suffix = str(uuid.uuid4())[:6].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"

    def create_task(self, task_data: TaskCreate, created_by: int) -> Task:
        """Create a new task"""
        # Validate task type
        task_type = self.db.query(TaskType).filter(TaskType.id == task_data.task_type_id).first()
        if not task_type:
            raise NotFoundError("Task type not found")

        # Generate task number
        task_number = self.generate_task_number()
        
        # Create task
        db_task = Task(
            task_number=task_number,
            created_by=created_by,
            **task_data.model_dump(exclude={"assigned_to"})
        )
        
        # Set defaults from task type
        if not db_task.priority:
            db_task.priority = TaskPriority(task_type.default_priority)
        if not db_task.estimated_hours:
            db_task.estimated_hours = task_type.default_estimated_hours

        self.db.add(db_task)
        self.db.flush()
        
        # Handle assignment
        if task_data.assigned_to:
            self._assign_task(db_task.id, task_data.assigned_to, created_by)
        elif task_type.auto_assign_enabled:
            self._auto_assign_task(db_task)
        
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def update_task(self, task_id: int, task_data: TaskUpdate, user_id: int) -> Task:
        """Update task"""
        db_task = self.get_task_by_id(task_id)
        
        # Update fields
        for field, value in task_data.model_dump(exclude_unset=True).items():
            if field == "assigned_to" and value:
                self._assign_task(task_id, value, user_id)
            else:
                setattr(db_task, field, value)
        
        db_task.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def get_task_by_id(self, task_id: int) -> Task:
        """Get task by ID"""
        task = self.db.query(Task).filter(Task.id == task_id, Task.is_active == True).first()
        if not task:
            raise NotFoundError("Task not found")
        return task

    def get_tasks_by_user(
        self, 
        user_id: int, 
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        category: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Get tasks assigned to user"""
        query = self.db.query(Task).filter(
            Task.assigned_to == user_id,
            Task.is_active == True
        )
        
        # Apply filters
        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        if category:
            query = query.join(TaskType).filter(TaskType.category == category)
        
        # Ordering
        query = query.order_by(
            desc(Task.priority == TaskPriority.URGENT),
            desc(Task.priority == TaskPriority.HIGH),
            Task.due_date.asc(),
            desc(Task.created_at)
        )
        
        # Pagination
        total = query.count()
        tasks = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return {
            "tasks": tasks,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        }

    def get_task_summary(self, user_id: int, role_names: List[str]) -> TaskSummary:
        """Get task summary for user/role"""
        base_query = self.db.query(Task).filter(Task.is_active == True)
        
        # Filter by user assignments or department/role-based tasks
        if "SUPER_ADMIN" not in role_names:
            user_query = base_query.filter(Task.assigned_to == user_id)
        else:
            user_query = base_query
        
        # Calculate summary
        total_tasks = user_query.count()
        pending_tasks = user_query.filter(Task.status == TaskStatus.PENDING).count()
        in_progress_tasks = user_query.filter(Task.status == TaskStatus.IN_PROGRESS).count()
        completed_tasks = user_query.filter(Task.status == TaskStatus.COMPLETED).count()
        
        # Overdue tasks
        overdue_tasks = user_query.filter(
            and_(
                Task.due_date < datetime.utcnow(),
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
            )
        ).count()
        
        # Priority counts
        urgent_tasks = user_query.filter(Task.priority == TaskPriority.URGENT).count()
        high_priority_tasks = user_query.filter(Task.priority == TaskPriority.HIGH).count()
        
        # Completion percentage
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Status breakdown
        status_counts = self.db.query(
            Task.status,
            func.count(Task.id)
        ).filter(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True
        ).group_by(Task.status).all()
        
        by_status = {status.value: count for status, count in status_counts}
        
        # Priority breakdown
        priority_counts = self.db.query(
            Task.priority,
            func.count(Task.id)
        ).filter(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True
        ).group_by(Task.priority).all()
        
        by_priority = {priority.value: count for priority, count in priority_counts}
        
        # Category breakdown
        category_counts = self.db.query(
            TaskType.category,
            func.count(Task.id)
        ).join(TaskType).filter(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True
        ).group_by(TaskType.category).all()
        
        by_category = {category: count for category, count in category_counts}
        
        # Recent tasks
        recent_tasks = user_query.order_by(desc(Task.created_at)).limit(5).all()
        recent_tasks_data = [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority.value,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "created_at": task.created_at.isoformat()
            }
            for task in recent_tasks
        ]
        
        return TaskSummary(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            in_progress_tasks=in_progress_tasks,
            completed_tasks=completed_tasks,
            overdue_tasks=overdue_tasks,
            urgent_tasks=urgent_tasks,
            high_priority_tasks=high_priority_tasks,
            completion_percentage=round(completion_percentage, 2),
            by_status=by_status,
            by_priority=by_priority,
            by_category=by_category,
            recent_tasks=recent_tasks_data
        )

    def assign_task(self, task_id: int, assigned_to: int, assigned_by: int, notes: Optional[str] = None) -> Task:
        """Assign task to user"""
        task = self.get_task_by_id(task_id)
        
        # Create assignment record
        self._assign_task(task_id, assigned_to, assigned_by, notes)
        
        # Update task
        task.assigned_to = assigned_to
        task.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_task_status(self, task_id: int, status: TaskStatus, user_id: int, notes: Optional[str] = None, actual_hours: Optional[float] = None) -> Task:
        """Update task status"""
        task = self.get_task_by_id(task_id)
        
        # Update status and timestamps
        old_status = task.status
        task.status = status
        task.updated_at = datetime.utcnow()
        
        if status == TaskStatus.IN_PROGRESS and old_status == TaskStatus.PENDING:
            task.started_at = datetime.utcnow()
        elif status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
            if actual_hours:
                task.actual_hours = actual_hours
        
        # Add comment if notes provided
        if notes:
            comment = TaskComment(
                task_id=task_id,
                user_id=user_id,
                comment=f"Status updated to {status.value}. Notes: {notes}",
                is_internal=True
            )
            self.db.add(comment)
        
        self.db.commit()
        self.db.refresh(task)
        return task

    def _assign_task(self, task_id: int, assigned_to: int, assigned_by: int, notes: Optional[str] = None):
        """Create task assignment record"""
        # Deactivate previous assignments
        self.db.query(TaskAssignment).filter(
            TaskAssignment.task_id == task_id,
            TaskAssignment.is_active == True
        ).update({"is_active": False, "unassigned_at": datetime.utcnow()})
        
        # Create new assignment
        assignment = TaskAssignment(
            task_id=task_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            notes=notes
        )
        self.db.add(assignment)

    def _auto_assign_task(self, task: Task):
        """Auto-assign task based on rules"""
        task_type = task.task_type
        if not task_type.auto_assign_rules:
            return
        
        rules = task_type.auto_assign_rules
        
        # Simple rule-based assignment
        if "department_id" in rules and task.department_id:
            # Find users in the department with appropriate roles
            target_roles = rules.get("roles", [])
            
            # This would be more complex in real implementation
            # For now, just assign to department manager or first available user
            potential_assignee = self.db.query(User).join(
                # Join logic to find appropriate user
            ).first()
            
            if potential_assignee:
                task.assigned_to = potential_assignee.id
                task.auto_assigned = True
                self._assign_task(task.id, potential_assignee.id, task.created_by, "Auto-assigned by system")