from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime

class ApprovalMemberBase(BaseModel):
    employee_id: int
    module: str  # HR, INVENTORY, PURCHASE

class ApprovalMemberCreate(ApprovalMemberBase):
    @validator('module')
    def validate_module(cls, v):
        allowed_modules = ['HR', 'INVENTORY', 'PURCHASE', 'LOGISTICS']
        if v.upper() not in allowed_modules:
            raise ValueError(f'Module must be one of: {", ".join(allowed_modules)}')
        return v.upper()
    
class ApprovalMemberUpdate(BaseModel):
    module: Optional[str] = None  # HR, INVENTORY, PURCHASE, etc.
    is_active: Optional[bool] = None
    

class EmployeeInfo(BaseModel):
    id: int
    employee_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    
    class Config:
        from_attributes = True

class ApprovalMemberResponse(ApprovalMemberBase):
    id: int
    employee: EmployeeInfo
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ApprovalMemberListResponse(BaseModel):
    members: List[ApprovalMemberResponse]
    total: int
    
class ApprovalMembersByModule(BaseModel):
    module: str
    members: List[ApprovalMemberResponse]
    total: int