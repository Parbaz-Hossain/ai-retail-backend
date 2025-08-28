from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_, desc, case, select
from datetime import datetime, timedelta, date
from app.models.task.task import Task
from app.models.task.task_type import TaskType
from app.models.auth import User
from app.models.shared.enums import TaskStatus, TaskPriority

class TaskDashboardService:
    """Service for task dashboard and analytics"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_department_overview(self, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Get department task overview by roles"""
        
        # Base query for tasks
        base_query = select(Task).where(Task.is_active == True)
        
        if department_id:
            base_query = base_query.where(Task.department_id == department_id)
        
        # Get role-based task summaries
        role_summaries = {}
        
        # Branch Manager tasks
        branch_manager_tasks = await self._get_branch_manager_tasks(base_query)
        role_summaries["Branch Manager"] = await self._calculate_role_summary(
            branch_manager_tasks, "Branch Manager", "👨‍💼"
        )
        
        # Chef tasks  
        chef_tasks = await self._get_chef_tasks(base_query)
        role_summaries["Chef"] = await self._calculate_role_summary(
            chef_tasks, "Chef", "👨‍🍳"
        )
        
        # Staff tasks
        staff_tasks = await self._get_staff_tasks(base_query)
        role_summaries["Staff"] = await self._calculate_role_summary(
            staff_tasks, "Staff", "👥"
        )
        
        # HR Manager tasks
        hr_tasks = await self._get_hr_manager_tasks(base_query)
        if hr_tasks:
            role_summaries["HR Manager"] = await self._calculate_role_summary(
                hr_tasks, "HR Manager", "👨‍💼"
            )
        
        # Inventory Manager tasks
        inventory_tasks = await self._get_inventory_manager_tasks(base_query)
        if inventory_tasks:
            role_summaries["Inventory Manager"] = await self._calculate_role_summary(
                inventory_tasks, "Inventory Manager", "📦"
            )
        
        # Warehouse Manager tasks
        warehouse_tasks = await self._get_warehouse_manager_tasks(base_query)
        if warehouse_tasks:
            role_summaries["Warehouse Manager"] = await self._calculate_role_summary(
                warehouse_tasks, "Warehouse Manager", "🏭"
            )
        
        return role_summaries

    async def get_task_analytics(self, days: int = 30, user_id: Optional[int] = None, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Get task analytics for specified period"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Base query with filters
        base_conditions = [
            Task.created_at >= start_date,
            Task.is_active == True
        ]
        
        if user_id:
            base_conditions.append(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            base_conditions.append(Task.department_id == department_id)
        
        # Task completion trend (daily)
        completion_conditions = [
            Task.completed_at >= start_date,
            Task.status == TaskStatus.COMPLETED,
            Task.is_active == True
        ]
        
        if user_id:
            completion_conditions.append(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            completion_conditions.append(Task.department_id == department_id)
        
        completion_trend_result = await self.db.execute(
            select(
                func.date(Task.completed_at).label('date'),
                func.count(Task.id).label('completed')
            ).where(and_(*completion_conditions)).group_by(func.date(Task.completed_at))
        )
        completion_data = completion_trend_result.all()
        
        # Task creation trend (daily)
        creation_trend_result = await self.db.execute(
            select(
                func.date(Task.created_at).label('date'),
                func.count(Task.id).label('created')
            ).where(and_(*base_conditions)).group_by(func.date(Task.created_at))
        )
        creation_data = creation_trend_result.all()
        
        # Performance by category
        category_conditions = base_conditions.copy()
        category_performance_result = await self.db.execute(
            select(
                TaskType.category,
                func.count(Task.id).label('total'),
                func.count(case([(Task.status == TaskStatus.COMPLETED, 1)])).label('completed'),
                func.avg(
                    case([
                        (Task.completed_at.isnot(None), 
                         func.extract('epoch', Task.completed_at - Task.created_at) / 3600)
                    ])
                ).label('avg_completion_hours'),
                func.count(case([(Task.status == TaskStatus.OVERDUE, 1)])).label('overdue')
            ).join(TaskType).where(and_(*category_conditions)).group_by(TaskType.category)
        )
        category_data = category_performance_result.all()
        
        # Priority distribution
        priority_distribution_result = await self.db.execute(
            select(
                Task.priority,
                func.count(Task.id).label('count')
            ).where(and_(*base_conditions)).group_by(Task.priority)
        )
        priority_data = priority_distribution_result.all()
        
        # Status distribution
        status_distribution_result = await self.db.execute(
            select(
                Task.status,
                func.count(Task.id).label('count')
            ).where(and_(*base_conditions)).group_by(Task.status)
        )
        status_data = status_distribution_result.all()
        
        # Top performers (users with most completed tasks)
        top_performer_conditions = [
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at >= start_date,
            Task.is_active == True
        ]
        
        if department_id:
            top_performer_conditions.append(Task.department_id == department_id)
        
        top_performers_result = await self.db.execute(
            select(
                User.full_name,
                User.id,
                func.count(Task.id).label('completed_tasks'),
                func.avg(
                    case([
                        (Task.completed_at.isnot(None),
                         func.extract('epoch', Task.completed_at - Task.created_at) / 3600)
                    ])
                ).label('avg_completion_time')
            ).join(Task, Task.assigned_to == User.id).where(
                and_(*top_performer_conditions)
            ).group_by(User.id, User.full_name).order_by(
                desc('completed_tasks')
            ).limit(10)
        )
        performer_data = top_performers_result.all()
        
        # Task aging analysis
        aging_conditions = [
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            Task.is_active == True
        ]
        
        if user_id:
            aging_conditions.append(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            aging_conditions.append(Task.department_id == department_id)
        
        aging_analysis_result = await self.db.execute(
            select(
                func.count(case([
                    (func.extract('day', func.now() - Task.created_at) <= 1, 1)
                ])).label('less_than_1_day'),
                func.count(case([
                    (and_(
                        func.extract('day', func.now() - Task.created_at) > 1,
                        func.extract('day', func.now() - Task.created_at) <= 3
                    ), 1)
                ])).label('1_to_3_days'),
                func.count(case([
                    (and_(
                        func.extract('day', func.now() - Task.created_at) > 3,
                        func.extract('day', func.now() - Task.created_at) <= 7
                    ), 1)
                ])).label('3_to_7_days'),
                func.count(case([
                    (func.extract('day', func.now() - Task.created_at) > 7, 1)
                ])).label('more_than_7_days')
            ).where(and_(*aging_conditions))
        )
        aging_data = aging_analysis_result.first()
        
        return {
            "period": f"{days} days",
            "start_date": start_date.isoformat(),
            "completion_trend": [
                {"date": str(item.date), "completed": item.completed}
                for item in completion_data
            ],
            "creation_trend": [
                {"date": str(item.date), "created": item.created}
                for item in creation_data
            ],
            "category_performance": [
                {
                    "category": item.category,
                    "total": item.total,
                    "completed": item.completed,
                    "completion_rate": round((item.completed / item.total * 100) if item.total > 0 else 0, 2),
                    "avg_completion_hours": round(float(item.avg_completion_hours or 0), 2),
                    "overdue": item.overdue
                }
                for item in category_data
            ],
            "priority_distribution": [
                {"priority": item.priority.value, "count": item.count}
                for item in priority_data
            ],
            "status_distribution": [
                {"status": item.status.value, "count": item.count}
                for item in status_data
            ],
            "top_performers": [
                {
                    "name": item.full_name,
                    "user_id": item.id,
                    "completed_tasks": item.completed_tasks,
                    "avg_completion_time": round(float(item.avg_completion_time or 0), 2)
                }
                for item in performer_data
            ],
            "task_aging": [
                {
                    "less_than_1_day": aging_data.less_than_1_day or 0,
                    "1_to_3_days": getattr(aging_data, "1_to_3_days", 0) or 0,
                    "3_to_7_days": getattr(aging_data, "3_to_7_days", 0) or 0,
                    "more_than_7_days": aging_data.more_than_7_days or 0
                }
            ]
        }

    async def get_user_productivity_metrics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get productivity metrics for specific user"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total tasks
        total_result = await self.db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == user_id,
                    Task.created_at >= start_date,
                    Task.is_active == True
                )
            )
        )
        total_tasks = total_result.scalar()
        
        # Completed tasks
        completed_result = await self.db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == user_id,
                    Task.created_at >= start_date,
                    Task.is_active == True,
                    Task.status == TaskStatus.COMPLETED
                )
            )
        )
        completed_tasks = completed_result.scalar()
        
        # Overdue tasks
        overdue_result = await self.db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == user_id,
                    Task.created_at >= start_date,
                    Task.is_active == True,
                    Task.due_date < datetime.utcnow(),
                    Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
                )
            )
        )
        overdue_tasks = overdue_result.scalar()
        
        # Average completion time
        avg_completion_result = await self.db.execute(
            select(
                func.avg(
                    func.extract('epoch', Task.completed_at - Task.created_at) / 3600
                )
            ).where(
                and_(
                    Task.assigned_to == user_id,
                    Task.status == TaskStatus.COMPLETED,
                    Task.completed_at >= start_date
                )
            )
        )
        avg_completion = avg_completion_result.scalar()
        
        # Task completion by priority
        priority_completion_result = await self.db.execute(
            select(
                Task.priority,
                func.count(Task.id).label('total'),
                func.count(case([(Task.status == TaskStatus.COMPLETED, 1)])).label('completed')
            ).where(
                and_(
                    Task.assigned_to == user_id,
                    Task.created_at >= start_date,
                    Task.is_active == True
                )
            ).group_by(Task.priority)
        )
        priority_completion = priority_completion_result.all()
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2),
            "overdue_tasks": overdue_tasks,
            "avg_completion_hours": round(float(avg_completion or 0), 2),
            "priority_breakdown": [
                {
                    "priority": item.priority.value,
                    "total": item.total,
                    "completed": item.completed,
                    "completion_rate": round((item.completed / item.total * 100) if item.total > 0 else 0, 2)
                }
                for item in priority_completion
            ]
        }

    async def get_overdue_tasks_summary(self, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of overdue tasks"""
        overdue_conditions = [
            Task.due_date < datetime.utcnow(),
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            Task.is_active == True
        ]
        
        if department_id:
            overdue_conditions.append(Task.department_id == department_id)
        
        overdue_result = await self.db.execute(
            select(Task).where(and_(*overdue_conditions))
        )
        overdue_tasks = overdue_result.scalars().all()
        
        # Group by assignee
        by_assignee = {}
        for task in overdue_tasks:
            if task.assigned_to:
                if task.assigned_to not in by_assignee:
                    assignee_result = await self.db.execute(
                        select(User).where(User.id == task.assigned_to)
                    )
                    assignee = assignee_result.scalar_one_or_none()
                    by_assignee[task.assigned_to] = {
                        "name": assignee.full_name if assignee else "Unknown",
                        "tasks": []
                    }
                by_assignee[task.assigned_to]["tasks"].append({
                    "id": task.id,
                    "title": task.title,
                    "priority": task.priority.value,
                    "due_date": task.due_date.isoformat(),
                    "days_overdue": (datetime.utcnow() - task.due_date).days
                })
        
        # Group by priority
        by_priority = {}
        for task in overdue_tasks:
            priority = task.priority.value
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append({
                "id": task.id,
                "title": task.title,
                "assignee": task.assignee.full_name if task.assignee else "Unassigned",
                "due_date": task.due_date.isoformat(),
                "days_overdue": (datetime.utcnow() - task.due_date).days
            })
        
        return {
            "total_overdue": len(overdue_tasks),
            "by_assignee": by_assignee,
            "by_priority": by_priority,
            "critical_overdue": len([t for t in overdue_tasks if t.priority == TaskPriority.URGENT]),
            "avg_days_overdue": sum([(datetime.utcnow() - t.due_date).days for t in overdue_tasks]) / len(overdue_tasks) if overdue_tasks else 0
        }

    async def _get_branch_manager_tasks(self, base_query) -> List[Task]:
        """Get tasks relevant to branch managers"""
        result = await self.db.execute(
            base_query.join(TaskType).where(
                or_(
                    TaskType.category.in_(["INVENTORY", "PURCHASE", "OPERATIONS"]),
                    Task.priority.in_([TaskPriority.HIGH, TaskPriority.URGENT]),
                    TaskType.requires_approval == True
                )
            )
        )
        return result.scalars().all()

    async def _get_chef_tasks(self, base_query) -> List[Task]:
        """Get tasks relevant to chefs"""
        result = await self.db.execute(
            base_query.join(TaskType).where(
                or_(
                    TaskType.category.in_(["OPERATIONS", "MAINTENANCE"]),
                    Task.reference_type.in_(["LOW_STOCK_ALERT", "EQUIPMENT_MAINTENANCE", "MENU_PLANNING"])
                )
            )
        )
        return result.scalars().all()

    async def _get_staff_tasks(self, base_query) -> List[Task]:
        """Get general staff tasks"""
        result = await self.db.execute(
            base_query.join(TaskType).where(
                and_(
                    TaskType.category.in_(["OPERATIONS", "CUSTOMER_SERVICE"]),
                    Task.priority.in_([TaskPriority.LOW, TaskPriority.MEDIUM])
                )
            )
        )
        return result.scalars().all()

    async def _get_hr_manager_tasks(self, base_query) -> List[Task]:
        """Get HR manager tasks"""
        result = await self.db.execute(
            base_query.join(TaskType).where(TaskType.category == "HR")
        )
        return result.scalars().all()

    async def _get_inventory_manager_tasks(self, base_query) -> List[Task]:
        """Get inventory manager tasks"""
        result = await self.db.execute(
            base_query.join(TaskType).where(TaskType.category == "INVENTORY")
        )
        return result.scalars().all()

    async def _get_warehouse_manager_tasks(self, base_query) -> List[Task]:
        """Get warehouse manager tasks"""
        result = await self.db.execute(
            base_query.join(TaskType).where(
                or_(
                    TaskType.category.in_(["INVENTORY", "LOGISTICS"]),
                    Task.reference_type.in_(["TRANSFER_REQUEST", "STOCK_COUNT"])
                )
            )
        )
        return result.scalars().all()

    async def _calculate_role_summary(self, tasks: List[Task], role_name: str, icon: str = "") -> Dict[str, Any]:
        """Calculate summary statistics for role tasks"""
        total_tasks = len(tasks)
        pending_tasks = len([t for t in tasks if t.status == TaskStatus.PENDING])
        in_progress_tasks = len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS])
        completed_tasks = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
        urgent_tasks = len([t for t in tasks if t.priority == TaskPriority.URGENT])
        overdue_tasks = len([t for t in tasks if t.due_date and t.due_date < datetime.utcnow() and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]])
        
        progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "role": role_name,
            "icon": icon,
            "total_tasks": total_tasks,
            "pending": pending_tasks,
            "completed": completed_tasks,
            "in_progress": in_progress_tasks,
            "urgent": urgent_tasks,
            "overdue": overdue_tasks,
            "progress": round(progress, 0),
            "progress_color": self._get_progress_color(progress)
        }

    def _get_progress_color(self, progress: float) -> str:
        """Get color based on progress percentage"""
        if progress >= 80:
            return "green"
        elif progress >= 60:
            return "yellow"
        elif progress >= 40:
            return "orange"
        else:
            return "red"