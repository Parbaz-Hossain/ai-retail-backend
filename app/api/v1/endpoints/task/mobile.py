"""
Mobile-specific endpoints for task management
Optimized for the mobile UI shown in the images
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, or_, select, func

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth import User
from app.models.task.task import Task
from app.models.task.task_type import TaskType
from app.models.shared.enums import TaskStatus, TaskPriority

router = APIRouter()

@router.get("/dashboard/today")
async def get_today_dashboard(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get today's task overview for mobile dashboard"""
    from datetime import datetime, time
    
    # Get today's date range
    today = datetime.now().date()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)
    
    # Get user's tasks base query
    user_tasks_query = select(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True
        )
    )
    
    # Total tasks
    total_result = await db.execute(select(func.count()).select_from(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True
        )
    ))
    total_tasks = total_result.scalar()
    
    # Pending tasks
    pending_result = await db.execute(select(func.count()).select_from(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True,
            Task.status == TaskStatus.PENDING
        )
    ))
    pending_tasks = pending_result.scalar()
    
    # In progress tasks
    in_progress_result = await db.execute(select(func.count()).select_from(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True,
            Task.status == TaskStatus.IN_PROGRESS
        )
    ))
    in_progress_tasks = in_progress_result.scalar()
    
    # Urgent tasks
    urgent_result = await db.execute(select(func.count()).select_from(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True,
            Task.priority == TaskPriority.URGENT
        )
    ))
    urgent_tasks = urgent_result.scalar()
    
    # Due today
    due_today_result = await db.execute(select(func.count()).select_from(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True,
            Task.due_date >= start_of_day,
            Task.due_date <= end_of_day
        )
    ))
    due_today = due_today_result.scalar()
    
    # Completed tasks
    completed_result = await db.execute(select(func.count()).select_from(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True,
            Task.status == TaskStatus.COMPLETED
        )
    ))
    completed_tasks = completed_result.scalar()
    
    # Completion percentage
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Recent urgent tasks
    recent_tasks_query = select(Task).join(TaskType).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True,
            or_(
                Task.priority == TaskPriority.URGENT,
                Task.priority == TaskPriority.HIGH,
                Task.status == TaskStatus.IN_PROGRESS
            )
        )
    ).order_by(
        desc(Task.priority == TaskPriority.URGENT),
        desc(Task.priority == TaskPriority.HIGH),
        Task.due_date.asc()
    ).limit(3)
    
    recent_result = await db.execute(recent_tasks_query)
    recent_tasks = recent_result.scalars().all()
    
    # Format tasks for mobile
    formatted_tasks = []
    for task in recent_tasks:
        formatted_tasks.append({
            "id": task.id,
            "title": task.title,
            "category": task.task_type.category,
            "priority": task.priority.value,
            "status": task.status.value,
            "due_time": task.due_date.strftime("%I:%M %p") if task.due_date else None,
            "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            "color": _get_task_color(task.priority, task.status)
        })
    
    return {
        "greeting": f"Good {_get_greeting()}! 👋",
        "date": today.strftime("%A, %B %d, %Y"),
        "overview": {
            "completion_percentage": f"{completion_percentage:.0f}% Complete",
            "total_tasks": total_tasks,
            "pending": pending_tasks,
            "in_progress": in_progress_tasks,
            "urgent": urgent_tasks
        },
        "recent_tasks": formatted_tasks,
        "due_today": due_today
    }

@router.get("/dashboard/department-overview")
async def get_department_overview_mobile(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get department overview for mobile (like the Branch Manager view in image)"""
    
    # Get user's role-based access
    role_names = [role.role.name for role in current_user.user_roles if role.is_active]
    
    department_overview = []
    
    # Branch Manager Overview
    if "BRANCH_MANAGER" in role_names or current_user.is_superuser:
        branch_tasks_query = select(Task).join(TaskType).where(
            and_(
                TaskType.category.in_(["INVENTORY", "OPERATIONS", "PURCHASE"]),
                Task.is_active == True
            )
        )
        branch_result = await db.execute(branch_tasks_query)
        branch_tasks = branch_result.scalars().all()
        
        branch_summary = await _calculate_role_summary_mobile(branch_tasks, "Branch Manager", "👨‍💼")
        department_overview.append(branch_summary)
    
    # Chef Overview
    if "CHEF" in role_names or current_user.is_superuser:
        chef_tasks_query = select(Task).join(TaskType).where(
            and_(
                TaskType.category.in_(["OPERATIONS", "MAINTENANCE"]),
                Task.reference_type.in_(["LOW_STOCK_ALERT", "EQUIPMENT_MAINTENANCE", "MENU_PLANNING"]),
                Task.is_active == True
            )
        )
        chef_result = await db.execute(chef_tasks_query)
        chef_tasks = chef_result.scalars().all()
        
        chef_summary = await _calculate_role_summary_mobile(chef_tasks, "Chef", "👨‍🍳")
        department_overview.append(chef_summary)
    
    # Staff Overview
    staff_tasks_query = select(Task).where(
        and_(
            Task.assigned_to == current_user.id,
            Task.is_active == True
        )
    )
    staff_result = await db.execute(staff_tasks_query)
    staff_tasks = staff_result.scalars().all()
    
    staff_summary = await _calculate_role_summary_mobile(staff_tasks, "Staff", "👥")
    department_overview.append(staff_summary)
    
    return {
        "department_overview": department_overview
    }

@router.get("/tasks/by-role/{role_name}")
async def get_tasks_by_role_mobile(
    role_name: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get tasks filtered by role for mobile detail view"""
    
    # Map role names to task filters
    role_filters = {
        "branch_manager": {
            "categories": ["INVENTORY", "PURCHASE", "OPERATIONS"],
            "priorities": [TaskPriority.HIGH, TaskPriority.URGENT],
            "title": "Branch Manager Tasks"
        },
        "chef": {
            "categories": ["OPERATIONS", "MAINTENANCE"],
            "reference_types": ["LOW_STOCK_ALERT", "EQUIPMENT_MAINTENANCE"],
            "title": "Chef Tasks"
        },
        "staff": {
            "assigned_to": current_user.id,
            "title": "My Tasks"
        }
    }
    
    if role_name.lower() not in role_filters:
        raise HTTPException(status_code=404, detail="Role not found")
    
    filter_config = role_filters[role_name.lower()]
    
    # Build query based on filters
    query = select(Task).where(Task.is_active == True)
    
    if "categories" in filter_config:
        query = query.join(TaskType).where(TaskType.category.in_(filter_config["categories"]))
    
    if "assigned_to" in filter_config:
        query = query.where(Task.assigned_to == filter_config["assigned_to"])
    
    if "priorities" in filter_config:
        query = query.where(Task.priority.in_(filter_config["priorities"]))
    
    if "reference_types" in filter_config:
        query = query.where(Task.reference_type.in_(filter_config["reference_types"]))
    
    # Order by priority and due date
    query = query.order_by(
        desc(Task.priority == TaskPriority.URGENT),
        desc(Task.priority == TaskPriority.HIGH),
        Task.due_date.asc(),
        desc(Task.created_at)
    ).limit(50)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Group tasks by status for mobile display
    grouped_tasks = {
        "pending": [],
        "in_progress": [],
        "completed": []
    }
    
    for task in tasks:
        task_data = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "category": task.task_type.category,
            "priority": task.priority.value,
            "status": task.status.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "due_time": task.due_date.strftime("%I:%M %p") if task.due_date else None,
            "color": _get_task_color(task.priority, task.status),
            "tags": [task.task_type.category, task.priority.value]
        }
        
        if task.status == TaskStatus.PENDING:
            grouped_tasks["pending"].append(task_data)
        elif task.status == TaskStatus.IN_PROGRESS:
            grouped_tasks["in_progress"].append(task_data)
        elif task.status == TaskStatus.COMPLETED:
            grouped_tasks["completed"].append(task_data)
    
    # Summary counts
    summary = {
        "pending": len(grouped_tasks["pending"]),
        "in_progress": len(grouped_tasks["in_progress"]), 
        "completed": len(grouped_tasks["completed"])
    }
    
    return {
        "title": filter_config["title"],
        "summary": summary,
        "tasks": grouped_tasks
    }

def _get_greeting():
    """Get time-appropriate greeting"""
    from datetime import datetime
    hour = datetime.now().hour
    
    if hour < 12:
        return "Morning"
    elif hour < 17:
        return "Afternoon"
    else:
        return "Evening"

def _get_task_color(priority: TaskPriority, status: TaskStatus):
    """Get color scheme for task based on priority and status"""
    if status == TaskStatus.COMPLETED:
        return "green"
    elif priority == TaskPriority.URGENT:
        return "red"
    elif priority == TaskPriority.HIGH:
        return "orange" 
    elif priority == TaskPriority.MEDIUM:
        return "yellow"
    else:
        return "gray"

async def _calculate_role_summary_mobile(tasks: List[Task], role_name: str, icon: str):
    """Calculate summary for role tasks formatted for mobile"""
    total_tasks = len(tasks)
    pending_tasks = len([t for t in tasks if t.status == TaskStatus.PENDING])
    in_progress_tasks = len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS])
    completed_tasks = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    urgent_tasks = len([t for t in tasks if t.priority == TaskPriority.URGENT])
    
    progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return {
        "role": role_name,
        "icon": icon,
        "total_tasks": f"{total_tasks} total tasks",
        "urgent": f"{urgent_tasks} urgent",
        "progress": f"{progress:.0f}%",
        "summary": {
            "pending": pending_tasks,
            "completed": completed_tasks, 
            "in_progress": in_progress_tasks
        },
        "progress_bar": {
            "percentage": progress,
            "color": "green" if progress > 80 else "orange" if progress > 50 else "red"
        }
    }