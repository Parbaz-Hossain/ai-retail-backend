from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth import User
from app.models.task.task_type import TaskType
from app.schemas.task.task_type_schema import TaskTypeCreate, TaskTypeUpdate, TaskTypeResponse

router = APIRouter()

@router.post("/", response_model=TaskTypeResponse, status_code=status.HTTP_201_CREATED)
def create_task_type(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_type_in: TaskTypeCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create new task type"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    task_type = TaskType(**task_type_in.model_dump())
    db.add(task_type)
    db.commit()
    db.refresh(task_type)
    return task_type

@router.get("/", response_model=List[TaskTypeResponse])
def get_task_types(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    category: str = None
) -> Any:
    """Get all task types"""
    query = db.query(TaskType).filter(TaskType.is_active == True)
    
    if category:
        query = query.filter(TaskType.category == category)
    
    task_types = query.all()
    return task_types

@router.get("/{task_type_id}", response_model=TaskTypeResponse)
def get_task_type(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_type_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get task type by ID"""
    task_type = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if not task_type:
        raise HTTPException(status_code=404, detail="Task type not found")
    return task_type

@router.put("/{task_type_id}", response_model=TaskTypeResponse)
def update_task_type(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_type_id: int,
    task_type_in: TaskTypeUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update task type"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    task_type = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if not task_type:
        raise HTTPException(status_code=404, detail="Task type not found")
    
    for field, value in task_type_in.model_dump(exclude_unset=True).items():
        setattr(task_type, field, value)
    
    db.commit()
    db.refresh(task_type)
    return task_type

@router.delete("/{task_type_id}")
def delete_task_type(
    *,
    db: AsyncSession = Depends(get_async_session),
    task_type_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete task type"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    task_type = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if not task_type:
        raise HTTPException(status_code=404, detail="Task type not found")
    
    task_type.is_active = False
    db.commit()
    
    return {"message": "Task type deleted successfully"}