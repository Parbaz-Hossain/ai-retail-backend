from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class TaskCommentCreate(BaseModel):
    comment: str = Field(..., min_length=1)
    is_internal: bool = False

class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    user: Dict[str, Any]
    comment: str
    is_internal: bool
    created_at: datetime
    
    class Config:
        from_attributes = True