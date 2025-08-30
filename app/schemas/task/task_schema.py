from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.shared.enums import TaskStatus, TaskPriority

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    task_type_id: int
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    reference_data: Optional[Dict[str, Any]] = None
    department_id: Optional[int] = None
    location_id: Optional[int] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    tags: Optional[str] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    parent_task_id: Optional[int] = None

class TaskCreate(TaskBase):
    assigned_to: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    department_id: Optional[int] = None
    location_id: Optional[int] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    tags: Optional[str] = None

class TaskAssignRequest(BaseModel):
    assigned_to: int
    notes: Optional[str] = None

class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    notes: Optional[str] = None
    actual_hours: Optional[float] = None

class LocationInfo(BaseModel):
    id: int
    name: str

class DepartmentInfo(BaseModel):
    id: int
    name: str

class TaskTypeInfo(BaseModel):
    id: int
    name: str
    category: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    task_number: str
    title: str
    description: Optional[str] = None
    task_type: Optional['TaskTypeInfo'] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    reference_data: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None
    assigned_to: Optional[int] = None
    department: Optional['DepartmentInfo'] = None
    location: Optional['LocationInfo'] = None
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    tags: Optional[str] = None
    is_recurring: bool
    recurrence_pattern: Optional[str] = None
    parent_task_id: Optional[int] = None
    auto_assigned: Optional[bool] = None
    escalation_level: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    per_page: int
    pages: int

class TaskSummary(BaseModel):
    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    overdue_tasks: int
    urgent_tasks: int
    high_priority_tasks: int
    completion_percentage: float
    
    # Role-specific summary
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    by_category: Dict[str, int]
    recent_tasks: List[Dict[str, Any]]