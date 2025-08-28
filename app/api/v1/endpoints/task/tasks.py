from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth import User
from app.models.task.task_comment import TaskComment
from app.schemas.task.task_schema import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, 
    TaskSummary, TaskAssignRequest, TaskStatusUpdate
)
from app.services.task.task_service import TaskService
from app.services.task.task_dashboard_service import TaskDashboardService
from app.models.shared.enums import TaskStatus, TaskPriority

router = APIRouter()

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create new task"""
    task_service = TaskService(db)
    task = task_service.create_task(task_in, current_user.id)
    return task

@router.get("/", response_model=TaskListResponse)
def get_tasks(
     db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page")
) -> Any:
    """Get tasks for current user"""
    task_service = TaskService(db)
    result = task_service.get_tasks_by_user(
        user_id=current_user.id,
        status=status,
        priority=priority,
        category=category,
        page=page,
        per_page=per_page
    )
    return TaskListResponse(**result)

@router.get("/summary", response_model=TaskSummary)
def get_task_summary(
     db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get task summary for current user"""
    task_service = TaskService(db)
    
    # Get user roles
    role_names = [role.role.name for role in current_user.user_roles if role.is_active]
    
    summary = task_service.get_task_summary(current_user.id, role_names)
    return summary

@router.get("/dashboard/overview")
def get_dashboard_overview(
     db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    department_id: Optional[int] = Query(None, description="Filter by department")
) -> Any:
    """Get dashboard overview for department/role"""
    dashboard_service = TaskDashboardService(db)
    overview = dashboard_service.get_department_overview(department_id)
    return overview

@router.get("/analytics")
def get_task_analytics(
     db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Number of days for analytics")
) -> Any:
    """Get task analytics"""
    dashboard_service = TaskDashboardService(db)
    analytics = dashboard_service.get_task_analytics(days)
    return analytics

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get task by ID"""
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id)
    
    # Check if user has access to this task
    if (task.assigned_to != current_user.id and 
        task.created_by != current_user.id and 
        not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update task"""
    task_service = TaskService(db)
    
    # Check permissions
    task = task_service.get_task_by_id(task_id)
    if (task.assigned_to != current_user.id and 
        task.created_by != current_user.id and 
        not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    task = task_service.update_task(task_id, task_in, current_user.id)
    return task

@router.delete("/{task_id}")
def delete_task(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete task (soft delete)"""
    task_service = TaskService(db)
    
    # Check permissions
    task = task_service.get_task_by_id(task_id)
    if (task.created_by != current_user.id and not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    task.is_active = False
    task_service.db.commit()
    
    return {"message": "Task deleted successfully"}

@router.post("/{task_id}/assign", response_model=TaskResponse)
def assign_task(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    assign_data: TaskAssignRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Assign task to user"""
    task_service = TaskService(db)
    task = task_service.assign_task(
        task_id=task_id,
        assigned_to=assign_data.assigned_to,
        assigned_by=current_user.id,
        notes=assign_data.notes
    )
    return task

@router.patch("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    status_data: TaskStatusUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update task status"""
    task_service = TaskService(db)
    
    # Check permissions
    task = task_service.get_task_by_id(task_id)
    if (task.assigned_to != current_user.id and not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    task = task_service.update_task_status(
        task_id=task_id,
        status=status_data.status,
        user_id=current_user.id,
        notes=status_data.notes,
        actual_hours=status_data.actual_hours
    )
    return task

@router.get("/{task_id}/comments")
def get_task_comments(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get task comments"""
    
    # Check if user has access to this task
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id)
    
    if (task.assigned_to != current_user.id and 
        task.created_by != current_user.id and 
        not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    comments = db.query(TaskComment).filter(
        TaskComment.task_id == task_id,
        TaskComment.is_active == True
    ).order_by(TaskComment.created_at.desc()).all()
    
    return comments

@router.post("/{task_id}/comments")
def add_task_comment(
    *,
     db: AsyncSession = Depends(get_async_session),
    task_id: int,
    comment_data: dict,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Add comment to task"""
    
    # Check if user has access to this task
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id)
    
    if (task.assigned_to != current_user.id and 
        task.created_by != current_user.id and 
        not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    comment = TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        comment=comment_data["comment"],
        is_internal=comment_data.get("is_internal", False)
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return comment