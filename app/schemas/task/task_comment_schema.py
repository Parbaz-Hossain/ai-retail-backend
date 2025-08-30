from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class TaskCommentCreate(BaseModel):
    comment: str = Field(..., min_length=1)
    is_internal: bool = False

class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    comment: str
    is_internal: Optional[bool] = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True