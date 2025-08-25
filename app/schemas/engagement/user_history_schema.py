from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.shared.enums import HistoryActionType

class UserHistoryBase(BaseModel):
    action_type: HistoryActionType
    resource_type: str = Field(..., max_length=50)
    resource_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = Field(None, max_length=100)

class UserHistoryCreate(UserHistoryBase):
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)

class UserHistoryResponse(UserHistoryBase):
    id: int
    user_id: int
    is_favorite: bool
    is_archived: bool
    archived_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserHistoryListResponse(BaseModel):
    histories: List[UserHistoryResponse]
    total: int
    page: int
    limit: int
    has_next: bool

class UserHistoryStats(BaseModel):
    total_actions: int
    actions_today: int
    actions_this_week: int
    actions_this_month: int
    most_used_resource: str
    favorite_count: int