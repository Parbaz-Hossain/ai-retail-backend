from typing import Any, List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth import User
from app.models.task.task_comment import TaskComment
from app.schemas.task.task_comment_schema import TaskCommentCreate, TaskCommentResponse
from app.schemas.task.task_schema import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, 
    TaskSummary, TaskAssignRequest, TaskStatusUpdate
)
from app.services.task.task_service import TaskService
from app.services.task.task_dashboard_service import TaskDashboardService
from app.models.shared.enums import TaskStatus, TaskPriority

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=TaskResponse, status_code=http_status.HTTP_201_CREATED)
async def create_task(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create new task"""
    try:
        task_service = TaskService(db)
        task = await task_service.create_task(task_in, current_user.id)
        return task
    except HTTPException as e:
        logger.error(f"HTTP error creating task: {e.detail}")
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error creating task: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating task"
        )

@router.get("/", response_model=TaskListResponse)
async def get_tasks(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page")
) -> Any:
    """Get tasks for current user"""
    try:
        task_service = TaskService(db)
        tasks = await task_service.get_tasks_by_user(
            user_id=current_user.id,
            status=status,
            priority=priority,
            category=category,
            page=page,
            per_page=per_page
        )
        return tasks
    except HTTPException as e:
        logger.error(f"HTTP error getting tasks: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error getting tasks: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving tasks"
        )
    
# region Task Summary, Dashboard Overview and Analytics
# @router.get("/summary", response_model=TaskSummary)
# async def get_task_summary(
#     db: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ) -> Any:
#     """Get task summary for current user"""
#     try:
#         task_service = TaskService(db)
        
#         # Get user roles
#         role_names = [role.role.name for role in current_user.user_roles if role.is_active]
        
#         summary = await task_service.get_task_summary(current_user.id, role_names)
#         return summary
#     except HTTPException as e:
#         logger.error(f"HTTP error getting task summary: {e.detail}")
#         raise e
#     except Exception as e:
#         logger.error(f"Unexpected error getting task summary: {str(e)}")
#         raise HTTPException(
#             status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An unexpected error occurred while retrieving task summary"
#         )

# @router.get("/analytics")
# async def get_task_analytics(
#     db: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user),
#     days: int = Query(30, ge=1, le=365, description="Number of days for analytics")
# ) -> Any:
#     """Get task analytics"""
#     try:
#         dashboard_service = TaskDashboardService(db)
#         analytics = await dashboard_service.get_task_analytics(days)
#         return analytics
#     except HTTPException as e:
#         logger.error(f"HTTP error getting task analytics: {e.detail}")
#         raise e
#     except Exception as e:
#         logger.error(f"Unexpected error getting task analytics: {str(e)}")
#         raise HTTPException(
#             status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An unexpected error occurred while retrieving task analytics"
#         )

# @router.get("/dashboard/overview")
# async def get_dashboard_overview(
#     db: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user),
#     department_id: Optional[int] = Query(None, description="Filter by department")
# ) -> Any:
#     """Get dashboard overview for department/role"""
#     try:
#         dashboard_service = TaskDashboardService(db)
#         overview = await dashboard_service.get_department_overview(department_id)
#         return overview
#     except HTTPException as e:
#         logger.error(f"HTTP error getting dashboard overview: {e.detail}")
#         raise e
#     except Exception as e:
#         logger.error(f"Unexpected error getting dashboard overview: {str(e)}")
#         raise HTTPException(
#             status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An unexpected error occurred while retrieving dashboard overview"
#         )
# endregion

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get task by ID"""
    try:
        task_service = TaskService(db)
        task = await task_service.get_task_by_id(task_id)
        
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Check if user has access to this task
        if (task.assigned_to != current_user.id and 
            task.created_by != current_user.id and 
            not current_user.is_superuser):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        return task
    except HTTPException as e:
        logger.error(f"HTTP error getting task {task_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error getting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving task"
        )

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update task"""
    try:
        task_service = TaskService(db)
        
        # Check permissions
        task = await task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        if (task.assigned_to != current_user.id and 
            task.created_by != current_user.id and 
            not current_user.is_superuser):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        updated_task = await task_service.update_task(task_id, task_in, current_user.id)
        return updated_task
    except HTTPException as e:
        logger.error(f"HTTP error updating task {task_id}: {e.detail}")
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error updating task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating task"
        )

@router.delete("/{task_id}")
async def delete_task(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete task (soft delete)"""
    try:
        task_service = TaskService(db)
        
        # Check permissions
        task = await task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        if (task.created_by != current_user.id and not current_user.is_superuser):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        task.is_active = False
        task.is_deleted = True
        await db.commit()
        
        return {"message": "Task deleted successfully"}
    except HTTPException as e:
        logger.error(f"HTTP error deleting task {task_id}: {e.detail}")
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error deleting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting task"
        )

@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    assign_data: TaskAssignRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Assign task to user"""
    try:
        task_service = TaskService(db)
        task = await task_service.assign_task(
            task_id=task_id,
            assigned_to=assign_data.assigned_to,
            assigned_by=current_user.id,
            notes=assign_data.notes
        )
        return task
    except HTTPException as e:
        logger.error(f"HTTP error assigning task {task_id}: {e.detail}")
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error assigning task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while assigning task"
        )

@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    status_data: TaskStatusUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update task status"""
    try:
        task_service = TaskService(db)
        
        # Check permissions
        task = await task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        if (task.assigned_to != current_user.id and not current_user.is_superuser):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        updated_task = await task_service.update_task_status(
            task_id=task_id,
            status=status_data.status,
            user_id=current_user.id,
            notes=status_data.notes,
            actual_hours=status_data.actual_hours
        )
        return updated_task
    except HTTPException as e:
        logger.error(f"HTTP error updating task status {task_id}: {e.detail}")
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error updating task status {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating task status"
        )

@router.get("/{task_id}/comments")
async def get_task_comments(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    current_user: User = Depends(get_current_user)
) -> List[TaskCommentResponse]:
    """Get task comments"""
    try:
        # Check if user has access to this task
        task_service = TaskService(db)
        task = await task_service.get_task_by_id(task_id)
        
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        if (task.assigned_to != current_user.id and 
            task.created_by != current_user.id and 
            not current_user.is_superuser):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        result = await db.execute(
            select(TaskComment).where(
                TaskComment.task_id == task_id,
                TaskComment.is_active == True
            ).order_by(desc(TaskComment.created_at))
        )
        comments = result.scalars().all()
        
        # Convert to dictionaries
        return [TaskCommentResponse.model_validate(comment, from_attributes=True) for comment in comments]
    except HTTPException as e:
        logger.error(f"HTTP error getting task comments {task_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error getting task comments {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving task comments"
        )

@router.post("/{task_id}/comments")
async def add_task_comment(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_id: int,
    comment_data: TaskCommentCreate,
    current_user: User = Depends(get_current_user)
) -> TaskCommentResponse:
    """Add comment to task"""
    try:
        # Validate comment data
        if not comment_data.comment or comment_data.comment.strip() == "":
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Comment text is required"
            )
        
        # Check if user has access to this task
        task_service = TaskService(db)
        task = await task_service.get_task_by_id(task_id)
        
        if not task:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        if (task.assigned_to != current_user.id and 
            task.created_by != current_user.id and 
            not current_user.is_superuser):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        comment = TaskComment(
            task_id=task_id,
            user_id=current_user.id,
            comment=comment_data.comment,
            is_internal=comment_data.is_internal
        )
        
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        
        return TaskCommentResponse.model_validate(comment, from_attributes=True)
    except HTTPException as e:
        logger.error(f"HTTP error adding task comment {task_id}: {e.detail}")
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error adding task comment {task_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding task comment"
        )