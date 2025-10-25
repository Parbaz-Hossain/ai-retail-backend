from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from app.models.shared.enums import ApprovalRequestType

class ApprovalMemberBase(BaseModel):
    employee_id: int
    module: str  # HR, INVENTORY, PURCHASE
    action_types: List[str]  # ["SALARY", "SHIFT", "DAYOFF"]

class ApprovalMemberCreate(ApprovalMemberBase):
    @validator('module')
    def validate_module(cls, v):
        allowed_modules = ['HR', 'INVENTORY', 'PURCHASE', 'LOGISTICS']
        if v.upper() not in allowed_modules:
            raise ValueError(f'Module must be one of: {", ".join(allowed_modules)}')
        return v.upper()
    
    @validator('action_types')
    def validate_action_types(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one action type is required')
        
        # Validate each action type
        valid_types = [e.value for e in ApprovalRequestType]
        for action_type in v:
            if action_type.upper() not in valid_types:
                raise ValueError(f'Invalid action type: {action_type}. Must be one of: {", ".join(valid_types)}')
        
        # Remove duplicates and convert to uppercase
        return list(set([a.upper() for a in v]))
    
class ApprovalMemberUpdate(BaseModel):
    module: Optional[str] = None
    action_types: Optional[List[str]] = None
    is_active: Optional[bool] = None
    
    @validator('action_types')
    def validate_action_types(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError('At least one action type is required')
            
            valid_types = [e.value for e in ApprovalRequestType]
            for action_type in v:
                if action_type.upper() not in valid_types:
                    raise ValueError(f'Invalid action type: {action_type}')
            
            return list(set([a.upper() for a in v]))
        return v

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