from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from datetime import datetime, timedelta, date
from app.models.task.task import Task
from app.models.task.task_type import TaskType
from app.models.auth import User
from app.models.shared.enums import TaskStatus, TaskPriority

class TaskDashboardService:
    """Service for task dashboard and analytics"""
    
    def __init__(self, db: Session):
        self.db = db

    def get_department_overview(self, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Get department task overview by roles"""
        
        # Base query for tasks
        base_query = self.db.query(Task).filter(Task.is_active == True)
        
        if department_id:
            base_query = base_query.filter(Task.department_id == department_id)
        
        # Get role-based task summaries
        role_summaries = {}
        
        # Branch Manager tasks
        branch_manager_tasks = self._get_branch_manager_tasks(base_query)
        role_summaries["Branch Manager"] = self._calculate_role_summary(
            branch_manager_tasks, "Branch Manager", "👨‍💼"
        )
        
        # Chef tasks  
        chef_tasks = self._get_chef_tasks(base_query)
        role_summaries["Chef"] = self._calculate_role_summary(
            chef_tasks, "Chef", "👨‍🍳"
        )
        
        # Staff tasks
        staff_tasks = self._get_staff_tasks(base_query)
        role_summaries["Staff"] = self._calculate_role_summary(
            staff_tasks, "Staff", "👥"
        )
        
        # HR Manager tasks
        hr_tasks = self._get_hr_manager_tasks(base_query)
        if hr_tasks:
            role_summaries["HR Manager"] = self._calculate_role_summary(
                hr_tasks, "HR Manager", "👨‍💼"
            )
        
        # Inventory Manager tasks
        inventory_tasks = self._get_inventory_manager_tasks(base_query)
        if inventory_tasks:
            role_summaries["Inventory Manager"] = self._calculate_role_summary(
                inventory_tasks, "Inventory Manager", "📦"
            )
        
        # Warehouse Manager tasks
        warehouse_tasks = self._get_warehouse_manager_tasks(base_query)
        if warehouse_tasks:
            role_summaries["Warehouse Manager"] = self._calculate_role_summary(
                warehouse_tasks, "Warehouse Manager", "🏭"
            )
        
        return role_summaries

    def get_task_analytics(self, days: int = 30, user_id: Optional[int] = None, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Get task analytics for specified period"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Base query with filters
        base_query = self.db.query(Task).filter(
            Task.created_at >= start_date,
            Task.is_active == True
        )
        
        if user_id:
            base_query = base_query.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            base_query = base_query.filter(Task.department_id == department_id)
        
        # Task completion trend (daily)
        completion_trend = self.db.query(
            func.date(Task.completed_at).label('date'),
            func.count(Task.id).label('completed')
        ).filter(
            Task.completed_at >= start_date,
            Task.status == TaskStatus.COMPLETED,
            Task.is_active == True
        )
        
        if user_id:
            completion_trend = completion_trend.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            completion_trend = completion_trend.filter(Task.department_id == department_id)
        
        completion_data = completion_trend.group_by(func.date(Task.completed_at)).all()
        
        # Task creation trend (daily)
        creation_trend = self.db.query(
            func.date(Task.created_at).label('date'),
            func.count(Task.id).label('created')
        ).filter(
            Task.created_at >= start_date,
            Task.is_active == True
        )
        
        if user_id:
            creation_trend = creation_trend.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            creation_trend = creation_trend.filter(Task.department_id == department_id)
        
        creation_data = creation_trend.group_by(func.date(Task.created_at)).all()
        
        # Performance by category
        category_performance = self.db.query(
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
        ).join(TaskType).filter(
            Task.created_at >= start_date,
            Task.is_active == True
        )
        
        if user_id:
            category_performance = category_performance.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            category_performance = category_performance.filter(Task.department_id == department_id)
        
        category_data = category_performance.group_by(TaskType.category).all()
        
        # Priority distribution
        priority_distribution = self.db.query(
            Task.priority,
            func.count(Task.id).label('count')
        ).filter(
            Task.created_at >= start_date,
            Task.is_active == True
        )
        
        if user_id:
            priority_distribution = priority_distribution.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            priority_distribution = priority_distribution.filter(Task.department_id == department_id)
        
        priority_data = priority_distribution.group_by(Task.priority).all()
        
        # Status distribution
        status_distribution = self.db.query(
            Task.status,
            func.count(Task.id).label('count')
        ).filter(
            Task.created_at >= start_date,
            Task.is_active == True
        )
        
        if user_id:
            status_distribution = status_distribution.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            status_distribution = status_distribution.filter(Task.department_id == department_id)
        
        status_data = status_distribution.group_by(Task.status).all()
        
        # Top performers (users with most completed tasks)
        top_performers = self.db.query(
            User.full_name,
            User.id,
            func.count(Task.id).label('completed_tasks'),
            func.avg(
                case([
                    (Task.completed_at.isnot(None),
                     func.extract('epoch', Task.completed_at - Task.created_at) / 3600)
                ])
            ).label('avg_completion_time')
        ).join(Task, Task.assigned_to == User.id).filter(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at >= start_date,
            Task.is_active == True
        )
        
        if department_id:
            top_performers = top_performers.filter(Task.department_id == department_id)
        
        performer_data = top_performers.group_by(User.id, User.full_name).order_by(
            desc('completed_tasks')
        ).limit(10).all()
        
        # Task aging analysis
        aging_analysis = self.db.query(
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
        ).filter(
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            Task.is_active == True
        )
        
        if user_id:
            aging_analysis = aging_analysis.filter(
                or_(Task.assigned_to == user_id, Task.created_by == user_id)
            )
        
        if department_id:
            aging_analysis = aging_analysis.filter(Task.department_id == department_id)
        
        aging_data = aging_analysis.first()
        
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

    def get_user_productivity_metrics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get productivity metrics for specific user"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        user_tasks = self.db.query(Task).filter(
            Task.assigned_to == user_id,
            Task.created_at >= start_date,
            Task.is_active == True
        )
        
        total_tasks = user_tasks.count()
        completed_tasks = user_tasks.filter(Task.status == TaskStatus.COMPLETED).count()
        overdue_tasks = user_tasks.filter(
            and_(
                Task.due_date < datetime.utcnow(),
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
            )
        ).count()
        
        # Average completion time
        avg_completion = self.db.query(
            func.avg(
                func.extract('epoch', Task.completed_at - Task.created_at) / 3600
            )
        ).filter(
            Task.assigned_to == user_id,
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at >= start_date
        ).scalar()
        
        # Task completion by priority
        priority_completion = self.db.query(
            Task.priority,
            func.count(Task.id).label('total'),
            func.count(case([(Task.status == TaskStatus.COMPLETED, 1)])).label('completed')
        ).filter(
            Task.assigned_to == user_id,
            Task.created_at >= start_date,
            Task.is_active == True
        ).group_by(Task.priority).all()
        
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

    def get_overdue_tasks_summary(self, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of overdue tasks"""
        overdue_query = self.db.query(Task).filter(
            Task.due_date < datetime.utcnow(),
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            Task.is_active == True
        )
        
        if department_id:
            overdue_query = overdue_query.filter(Task.department_id == department_id)
        
        overdue_tasks = overdue_query.all()
        
        # Group by assignee
        by_assignee = {}
        for task in overdue_tasks:
            if task.assigned_to:
                if task.assigned_to not in by_assignee:
                    assignee = self.db.query(User).filter(User.id == task.assigned_to).first()
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

    def _get_branch_manager_tasks(self, base_query) -> List[Task]:
        """Get tasks relevant to branch managers"""
        return base_query.join(TaskType).filter(
            or_(
                TaskType.category.in_(["INVENTORY", "PURCHASE", "OPERATIONS"]),
                Task.priority.in_([TaskPriority.HIGH, TaskPriority.URGENT]),
                TaskType.requires_approval == True
            )
        ).all()

    def _get_chef_tasks(self, base_query) -> List[Task]:
        """Get tasks relevant to chefs"""
        return base_query.join(TaskType).filter(
            or_(
                TaskType.category.in_(["OPERATIONS", "MAINTENANCE"]),
                Task.reference_type.in_(["LOW_STOCK_ALERT", "EQUIPMENT_MAINTENANCE", "MENU_PLANNING"])
            )
        ).all()

    def _get_staff_tasks(self, base_query) -> List[Task]:
        """Get general staff tasks"""
        return base_query.join(TaskType).filter(
            TaskType.category.in_(["OPERATIONS", "CUSTOMER_SERVICE"]),
            Task.priority.in_([TaskPriority.LOW, TaskPriority.MEDIUM])
        ).all()

    def _get_hr_manager_tasks(self, base_query) -> List[Task]:
        """Get HR manager tasks"""
        return base_query.join(TaskType).filter(
            TaskType.category == "HR"
        ).all()

    def _get_inventory_manager_tasks(self, base_query) -> List[Task]:
        """Get inventory manager tasks"""
        return base_query.join(TaskType).filter(
            TaskType.category == "INVENTORY"
        ).all()

    def _get_warehouse_manager_tasks(self, base_query) -> List[Task]:
        """Get warehouse manager tasks"""
        return base_query.join(TaskType).filter(
            or_(
                TaskType.category.in_(["INVENTORY", "LOGISTICS"]),
                Task.reference_type.in_(["TRANSFER_REQUEST", "STOCK_COUNT"])
            )
        ).all()

    def _calculate_role_summary(self, tasks: List[Task], role_name: str, icon: str = "") -> Dict[str, Any]:
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