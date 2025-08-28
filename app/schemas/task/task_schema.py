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

class TaskResponse(BaseModel):
    id: int
    task_number: str
    title: str
    description: Optional[str]
    task_type: Dict[str, Any]
    reference_type: Optional[str]
    reference_id: Optional[int]
    reference_data: Optional[Dict[str, Any]]
    created_by: Dict[str, Any]
    assigned_to: Optional[Dict[str, Any]]
    department: Optional[Dict[str, Any]]
    location: Optional[Dict[str, Any]]
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_hours: Optional[float]
    actual_hours: Optional[float]
    tags: Optional[str]
    is_recurring: bool
    recurrence_pattern: Optional[str]
    parent_task_id: Optional[int]
    auto_assigned: bool
    escalation_level: int
    created_at: datetime
    updated_at: datetime
    
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