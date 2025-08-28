from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, desc, select
from datetime import datetime
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
    def __init__(self, db: AsyncSession):
        self.db = db

    def generate_task_number(self) -> str:
        """Generate unique task number"""
        prefix = "TASK"
        timestamp = datetime.now().strftime("%y%m%d")
        random_suffix = str(uuid.uuid4())[:6].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"

    async def create_task(self, task_data: TaskCreate, created_by: int) -> Task:
        """Create a new task"""
        # Validate task type
        result = await self.db.execute(select(TaskType).where(TaskType.id == task_data.task_type_id))
        task_type = result.scalar_one_or_none()
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
        await self.db.flush()
        
        # Handle assignment
        if task_data.assigned_to:
            await self._assign_task(db_task.id, task_data.assigned_to, created_by)
        elif task_type.auto_assign_enabled:
            await self._auto_assign_task(db_task)
        
        await self.db.commit()
        await self.db.refresh(db_task)
        return db_task

    async def update_task(self, task_id: int, task_data: TaskUpdate, user_id: int) -> Task:
        """Update task"""
        db_task = await self.get_task_by_id(task_id)
        
        # Update fields
        for field, value in task_data.model_dump(exclude_unset=True).items():
            if field == "assigned_to" and value:
                await self._assign_task(task_id, value, user_id)
            else:
                setattr(db_task, field, value)
        
        db_task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(db_task)
        return db_task

    async def get_task_by_id(self, task_id: int) -> Task:
        """Get task by ID"""
        result = await self.db.execute(
            select(Task).where(
                and_(Task.id == task_id, Task.is_active == True)
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError("Task not found")
        return task

    async def get_tasks_by_user(
        self, 
        user_id: int, 
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        category: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Get tasks assigned to user"""
        query = select(Task).where(
            and_(
                Task.assigned_to == user_id,
                Task.is_active == True
            )
        )
        
        # Apply filters
        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        if category:
            query = query.join(TaskType).where(TaskType.category == category)
        
        # Ordering
        query = query.order_by(
            desc(Task.priority == TaskPriority.URGENT),
            desc(Task.priority == TaskPriority.HIGH),
            Task.due_date.asc(),
            desc(Task.created_at)
        )
        
        # Get total count
        count_query = select(func.count()).select_from(Task).where(
            and_(
                Task.assigned_to == user_id,
                Task.is_active == True
            )
        )
        if status:
            count_query = count_query.where(Task.status == status)
        if priority:
            count_query = count_query.where(Task.priority == priority)
        if category:
            count_query = count_query.join(TaskType).where(TaskType.category == category)
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated tasks
        paginated_query = query.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(paginated_query)
        tasks = result.scalars().all()
        
        return {
            "tasks": tasks,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        }

    async def get_task_summary(self, user_id: int, role_names: List[str]) -> TaskSummary:
        """Get task summary for user/role"""
        base_query = select(Task).where(Task.is_active == True)
        
        # Filter by user assignments or department/role-based tasks
        if "SUPER_ADMIN" not in role_names:
            user_query = base_query.where(Task.assigned_to == user_id)
        else:
            user_query = base_query
        
        # Calculate summary counts
        total_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True
        ))
        total_tasks = total_result.scalar()
        
        pending_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True,
            Task.status == TaskStatus.PENDING
        ))
        pending_tasks = pending_result.scalar()
        
        in_progress_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True,
            Task.status == TaskStatus.IN_PROGRESS
        ))
        in_progress_tasks = in_progress_result.scalar()
        
        completed_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True,
            Task.status == TaskStatus.COMPLETED
        ))
        completed_tasks = completed_result.scalar()
        
        # Overdue tasks
        overdue_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True,
            Task.due_date < datetime.utcnow(),
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        ))
        overdue_tasks = overdue_result.scalar()
        
        # Priority counts
        urgent_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True,
            Task.priority == TaskPriority.URGENT
        ))
        urgent_tasks = urgent_result.scalar()
        
        high_priority_result = await self.db.execute(select(func.count()).select_from(Task).where(
            Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
            Task.is_active == True,
            Task.priority == TaskPriority.HIGH
        ))
        high_priority_tasks = high_priority_result.scalar()
        
        # Completion percentage
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Status breakdown
        status_counts_result = await self.db.execute(
            select(Task.status, func.count(Task.id)).where(
                Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
                Task.is_active == True
            ).group_by(Task.status)
        )
        status_counts = status_counts_result.all()
        by_status = {status.value: count for status, count in status_counts}
        
        # Priority breakdown
        priority_counts_result = await self.db.execute(
            select(Task.priority, func.count(Task.id)).where(
                Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
                Task.is_active == True
            ).group_by(Task.priority)
        )
        priority_counts = priority_counts_result.all()
        by_priority = {priority.value: count for priority, count in priority_counts}
        
        # Category breakdown
        category_counts_result = await self.db.execute(
            select(TaskType.category, func.count(Task.id)).join(TaskType).where(
                Task.assigned_to == user_id if "SUPER_ADMIN" not in role_names else True,
                Task.is_active == True
            ).group_by(TaskType.category)
        )
        category_counts = category_counts_result.all()
        by_category = {category: count for category, count in category_counts}
        
        # Recent tasks
        recent_query = user_query.order_by(desc(Task.created_at)).limit(5)
        recent_result = await self.db.execute(recent_query)
        recent_tasks = recent_result.scalars().all()
        
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

    async def assign_task(self, task_id: int, assigned_to: int, assigned_by: int, notes: Optional[str] = None) -> Task:
        """Assign task to user"""
        task = await self.get_task_by_id(task_id)
        
        # Create assignment record
        await self._assign_task(task_id, assigned_to, assigned_by, notes)
        
        # Update task
        task.assigned_to = assigned_to
        task.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_task_status(self, task_id: int, status: TaskStatus, user_id: int, notes: Optional[str] = None, actual_hours: Optional[float] = None) -> Task:
        """Update task status"""
        task = await self.get_task_by_id(task_id)
        
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
        
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def _assign_task(self, task_id: int, assigned_to: int, assigned_by: int, notes: Optional[str] = None):
        """Create task assignment record"""
        # Deactivate previous assignments
        await self.db.execute(
            select(TaskAssignment).where(
                and_(
                    TaskAssignment.task_id == task_id,
                    TaskAssignment.is_active == True
                )
            ).values(is_active=False, unassigned_at=datetime.utcnow())
        )
        
        # Create new assignment
        assignment = TaskAssignment(
            task_id=task_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            notes=notes
        )
        self.db.add(assignment)

    async def _auto_assign_task(self, task: Task):
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
            result = await self.db.execute(
                select(User).limit(1)  # Simplified - would need proper role/department joins
            )
            potential_assignee = result.scalar_one_or_none()
            
            if potential_assignee:
                task.assigned_to = potential_assignee.id
                task.auto_assigned = True
                await self._assign_task(task.id, potential_assignee.id, task.created_by, "Auto-assigned by system")