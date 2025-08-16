from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.schemas.auth.permission import Permission

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class RoleInDBBase(RoleBase):
    id: int
    is_active: bool = None
    is_system_role: bool = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Role(RoleInDBBase):
    permissions: List['Permission'] = []