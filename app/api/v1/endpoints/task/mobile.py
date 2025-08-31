"""
Enhanced Mobile-specific endpoints for task management
Matching the mobile UI requirements from the provided image
"""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, or_, select, func, case
from sqlalchemy.orm import selectinload
from datetime import datetime, time, timedelta, timezone

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth import User
from app.models.auth.user_role import UserRole
from app.models.task.task import Task
from app.models.task.task_type import TaskType
from app.models.shared.enums import TaskStatus, TaskPriority

router = APIRouter()

@router.get("/dashboard/summary")
async def get_user_task_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get login user task summary
    Returns: Total, Pending, In Progress, Completed tasks with completion percentage
    """
    try:
        # Get user's tasks base query
        user_tasks_base = select(Task).where(
            and_(
                Task.assigned_to == current_user.id,
                Task.is_active == True
            )
        )
        
        # Total tasks
        total_result = await db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == current_user.id,
                    Task.is_active == True
                )
            )
        )
        total_tasks = total_result.scalar() or 0
        
        # Pending tasks
        pending_result = await db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == current_user.id,
                    Task.is_active == True,
                    Task.status == TaskStatus.PENDING
                )
            )
        )
        pending_tasks = pending_result.scalar() or 0
        
        # In progress tasks
        in_progress_result = await db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == current_user.id,
                    Task.is_active == True,
                    Task.status == TaskStatus.IN_PROGRESS
                )
            )
        )
        in_progress_tasks = in_progress_result.scalar() or 0
        
        # Completed tasks
        completed_result = await db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.assigned_to == current_user.id,
                    Task.is_active == True,
                    Task.status == TaskStatus.COMPLETED
                )
            )
        )
        completed_tasks = completed_result.scalar() or 0
        
        # Calculate completion percentage
        completion_percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        # Format numbers for display (201+ format)
        def format_task_count(count):
            if count > 200:
                return "201+"
            return str(count)
        
        return {
            "user_name": current_user.full_name,
            "greeting": f"Hi, {current_user.full_name.split()[0]}!",
            "date": datetime.now().strftime("%A, %B %d, %Y"),
            "task_summary": {
                "total_task": {
                    "count": format_task_count(total_tasks),
                    "actual_count": total_tasks
                },
                "pending_task": {
                    "count": format_task_count(pending_tasks),
                    "actual_count": pending_tasks
                },
                "in_progress": {
                    "count": format_task_count(in_progress_tasks),
                    "actual_count": in_progress_tasks
                },
                "completed": {
                    "count": format_task_count(completed_tasks),
                    "actual_count": completed_tasks
                }
            },
            "completion_percentage": f"{completion_percentage}%",
            "completion_color": _get_progress_color(completion_percentage)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching task summary: {str(e)}")

@router.get("/dashboard/tasks")
async def get_user_task_details(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    limit: int = 10
) -> Any:
    """
    Get login user pending and in-progress task detail overview
    Returns: Detailed list of pending and in-progress tasks
    """
    try:
        # Get pending and in-progress tasks
        tasks_query = select(Task).options(
            # Using selectinload for eager loading
        ).join(TaskType).where(
            and_(
                Task.assigned_to == current_user.id,
                Task.is_active == True,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
            )
        ).order_by(
            # Order by priority (urgent first) then by due date
            desc(Task.priority == TaskPriority.URGENT),
            desc(Task.priority == TaskPriority.HIGH),
            Task.due_date.asc(),
            desc(Task.created_at)
        ).limit(limit)
        
        result = await db.execute(tasks_query)
        tasks = result.scalars().all()
        
        # Get task type information for each task
        formatted_tasks = []
        for task in tasks:
            # Get task type info
            task_type_result = await db.execute(
                select(TaskType).where(TaskType.id == task.task_type_id)
            )
            task_type = task_type_result.scalar_one_or_none()
            
            # Calculate days until due or overdue
            days_info = None
            if task.due_date:
                days_diff = (task.due_date - datetime.now(timezone.utc)).days
                if days_diff < 0:
                    days_info = f"{abs(days_diff)} days overdue"
                elif days_diff == 0:
                    days_info = "Due today"
                else:
                    days_info = f"Due in {days_diff} days"
            
            formatted_task = {
                "id": task.id,
                "task_number": task.task_number,
                "title": task.title,
                "description": task.description,
                "category": task_type.category if task_type else "GENERAL",
                "priority": task.priority.value,
                "status": task.status.value,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "due_time": task.due_date.strftime("%I:%M %p") if task.due_date else None,
                "days_info": days_info,
                "created_at": task.created_at.isoformat(),
                "estimated_hours": float(task.estimated_hours) if task.estimated_hours else None,
                "tags": task.tags.split(",") if task.tags else [],
                "color": _get_task_color(task.priority, task.status),
                "is_urgent": task.priority == TaskPriority.URGENT
            }
            formatted_tasks.append(formatted_task)
        
        # Group tasks by status
        pending_tasks = [t for t in formatted_tasks if t["status"] == "PENDING"]
        in_progress_tasks = [t for t in formatted_tasks if t["status"] == "IN_PROGRESS"]
        
        # Count urgent tasks
        urgent_count = len([t for t in formatted_tasks if t["is_urgent"]])
        
        return {
            "total_tasks": len(formatted_tasks),
            "urgent_count": urgent_count,
            "pending_count": len(pending_tasks),
            "in_progress_count": len(in_progress_tasks),
            "tasks": {
                "pending": pending_tasks,
                "in_progress": in_progress_tasks,
                "all": formatted_tasks
            },
            "has_urgent": urgent_count > 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching task details: {str(e)}")

@router.get("/dashboard/department-overview")
async def get_department_overview(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Department overview API
    Branch managers can view all role task summaries, others see only their own
    """
    try:
        # Get user's roles
        user_result = await db.execute(
            select(User)
                .options(
                    selectinload(User.user_roles).selectinload(UserRole.role)
                )
                .where(User.id == current_user.id)
        )
        user = user_result.scalar_one_or_none()
    
        user_roles = [role.role.name for role in user.user_roles if role.is_active]
        is_branch_manager = "BRANCH_MANAGER" in user_roles or current_user.is_superuser
        
        department_overview = []
        
        if is_branch_manager:
            # Branch managers see all department summaries
            
            # 1. Branch Manager Tasks
            branch_tasks = await _get_tasks_by_role(db, "BRANCH_MANAGER")
            branch_summary = await _calculate_department_summary(
                branch_tasks, "Branch Manager", "👨‍💼", "branch_manager"
            )
            department_overview.append(branch_summary)
            
            # 2. Chef Tasks
            chef_tasks = await _get_tasks_by_role(db, "CHEF")
            chef_summary = await _calculate_department_summary(
                chef_tasks, "Chef", "👨‍🍳", "chef"
            )
            department_overview.append(chef_summary)
            
            # 3. HR Manager Tasks
            hr_tasks = await _get_tasks_by_role(db, "HR_MANAGER")
            if hr_tasks:
                hr_summary = await _calculate_department_summary(
                    hr_tasks, "HR Manager", "👤", "hr_manager"
                )
                department_overview.append(hr_summary)
            
            # 4. Inventory Manager Tasks
            inventory_tasks = await _get_tasks_by_role(db, "INVENTORY_MANAGER")
            if inventory_tasks:
                inventory_summary = await _calculate_department_summary(
                    inventory_tasks, "Inventory Manager", "📦", "inventory_manager"
                )
                department_overview.append(inventory_summary)
            
            # 5. Staff Tasks (General)
            staff_tasks = await _get_general_staff_tasks(db)
            staff_summary = await _calculate_department_summary(
                staff_tasks, "Staff", "👥", "staff"
            )
            department_overview.append(staff_summary)
            
        else:
            # Non-branch managers see only their own tasks
            user_tasks_query = select(Task).where(
                and_(
                    Task.assigned_to == current_user.id,
                    Task.is_active == True
                )
            )
            user_result = await db.execute(user_tasks_query)
            user_tasks = user_result.scalars().all()
            
            # Determine user's primary role
            primary_role = "Staff"
            role_icon = "👤"
            if "BRANCH_MANAGER" in user_roles:
                primary_role = "Branch Manager"
                role_icon = "👨‍💼"
            elif "CHEF" in user_roles:
                primary_role = "Chef"
                role_icon = "👨‍🍳"
            elif "HR_MANAGER" in user_roles:
                primary_role = "HR Manager"
                role_icon = "👤"
            elif "INVENTORY_MANAGER" in user_roles:
                primary_role = "Inventory Manager"
                role_icon = "📦"
            
            user_summary = await _calculate_department_summary(
                user_tasks, f"My Tasks ({primary_role})", role_icon, "my_tasks"
            )
            department_overview.append(user_summary)
        
        return {
            "user_role": "Branch Manager" if is_branch_manager else "Staff",
            "can_view_all": is_branch_manager,
            "department_overview": department_overview,
            "total_departments": len(department_overview)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching department overview: {str(e)}")

# Helper functions

async def _get_tasks_by_role(db: AsyncSession, role_name: str) -> List[Task]:
    """Get tasks relevant to a specific role"""
    if role_name == "BRANCH_MANAGER":
        # Branch manager sees high priority, approval tasks, and category-specific tasks
        query = select(Task).join(TaskType).where(
            and_(
                Task.is_active == True,
                or_(
                    TaskType.category.in_(["INVENTORY", "PURCHASE", "OPERATIONS"]),
                    Task.priority.in_([TaskPriority.HIGH, TaskPriority.URGENT]),
                    TaskType.requires_approval == True
                )
            )
        )
    elif role_name == "CHEF":
        # Chef sees operations and maintenance tasks
        query = select(Task).join(TaskType).where(
            and_(
                Task.is_active == True,
                or_(
                    TaskType.category.in_(["OPERATIONS", "MAINTENANCE"]),
                    Task.reference_type.in_(["LOW_STOCK_ALERT", "EQUIPMENT_MAINTENANCE", "MENU_PLANNING"])
                )
            )
        )
    elif role_name == "HR_MANAGER":
        # HR manager sees HR category tasks
        query = select(Task).join(TaskType).where(
            and_(
                Task.is_active == True,
                TaskType.category == "HR"
            )
        )
    elif role_name == "INVENTORY_MANAGER":
        # Inventory manager sees inventory tasks
        query = select(Task).join(TaskType).where(
            and_(
                Task.is_active == True,
                TaskType.category == "INVENTORY"
            )
        )
    else:
        return []
    
    result = await db.execute(query)
    return result.scalars().all()

async def _get_general_staff_tasks(db: AsyncSession) -> List[Task]:
    """Get general staff tasks"""
    query = select(Task).join(TaskType).where(
        and_(
            Task.is_active == True,
            TaskType.category.in_(["OPERATIONS", "CUSTOMER_SERVICE"]),
            Task.priority.in_([TaskPriority.LOW, TaskPriority.MEDIUM])
        )
    )
    result = await db.execute(query)
    return result.scalars().all()

async def _calculate_department_summary(
    tasks: List[Task], 
    role_name: str, 
    icon: str, 
    role_key: str
) -> Dict[str, Any]:
    """Calculate department summary statistics"""
    total_tasks = len(tasks)
    
    if total_tasks == 0:
        return {
            "role": role_name,
            "role_key": role_key,
            "icon": icon,
            "total_tasks": 0,
            "task_summary": "0 total tasks",
            "urgent_count": 0,
            "progress_percentage": 0,
            "progress_color": "gray",
            "breakdown": {
                "pending": 0,
                "in_progress": 0,
                "completed": 0
            }
        }
    
    pending_tasks = len([t for t in tasks if t.status == TaskStatus.PENDING])
    in_progress_tasks = len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS])
    completed_tasks = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    urgent_tasks = len([t for t in tasks if t.priority == TaskPriority.URGENT])
    
    # Calculate completion percentage
    progress_percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    
    return {
        "role": role_name,
        "role_key": role_key,
        "icon": icon,
        "total_tasks": total_tasks,
        "task_summary": f"Total Task {total_tasks}",
        "urgent_count": urgent_tasks,
        "urgent_text": f"{urgent_tasks} Urgent" if urgent_tasks > 0 else "No urgent tasks",
        "progress_percentage": progress_percentage,
        "progress_text": f"Done {progress_percentage}%",
        "progress_color": _get_progress_color(progress_percentage),
        "breakdown": {
            "pending": pending_tasks,
            "in_progress": in_progress_tasks, 
            "completed": completed_tasks
        },
        "breakdown_display": f"{pending_tasks} Pending  {completed_tasks} Completed  {in_progress_tasks} In Progress"
    }

def _get_task_color(priority: TaskPriority, status: TaskStatus) -> str:
    """Get color scheme for task based on priority and status"""
    if status == TaskStatus.COMPLETED:
        return "#4CAF50"  # Green
    elif priority == TaskPriority.URGENT:
        return "#F44336"  # Red
    elif priority == TaskPriority.HIGH:
        return "#FF9800"  # Orange
    elif priority == TaskPriority.MEDIUM:
        return "#FFC107"  # Yellow
    else:
        return "#9E9E9E"  # Gray

def _get_progress_color(progress: float) -> str:
    """Get color based on progress percentage"""
    if progress >= 80:
        return "#4CAF50"  # Green
    elif progress >= 60:
        return "#8BC34A"  # Light Green
    elif progress >= 40:
        return "#FF9800"  # Orange
    elif progress >= 20:
        return "#FF5722"  # Deep Orange
    else:
        return "#F44336"  # Red