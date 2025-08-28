from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class TaskTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category: str
    auto_assign_enabled: bool = False
    auto_assign_rules: Optional[Dict[str, Any]] = None
    default_priority: str = "MEDIUM"
    default_estimated_hours: Optional[float] = None
    sla_hours: Optional[int] = None
    requires_approval: bool = False
    approval_roles: Optional[List[str]] = None
    notification_settings: Optional[Dict[str, Any]] = None

class TaskTypeCreate(TaskTypeBase):
    pass

class TaskTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = None
    auto_assign_enabled: Optional[bool] = None
    auto_assign_rules: Optional[Dict[str, Any]] = None
    default_priority: Optional[str] = None
    default_estimated_hours: Optional[float] = None
    sla_hours: Optional[int] = None
    requires_approval: Optional[bool] = None
    approval_roles: Optional[List[str]] = None
    notification_settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class TaskTypeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: str
    auto_assign_enabled: bool
    auto_assign_rules: Optional[Dict[str, Any]]
    default_priority: str
    default_estimated_hours: Optional[float]
    sla_hours: Optional[int]
    requires_approval: bool
    approval_roles: Optional[List[str]]
    notification_settings: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True