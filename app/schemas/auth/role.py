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
    is_active: bool
    is_system_role: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class Role(RoleInDBBase):
    permissions: List['Permission'] = []