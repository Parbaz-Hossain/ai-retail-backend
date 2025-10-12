from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime
from app.models.shared.enums import ApprovalRequestType, ApprovalStatus, ApprovalResponseStatus

class ApprovalRequestBase(BaseModel):
    request_type: ApprovalRequestType
    employee_id: int
    request_data: Optional[Dict[str, Any]] = None  
    remarks: Optional[str] = None

class ApprovalRequestCreate(ApprovalRequestBase):
    pass

class EmployeeInfo(BaseModel):
    id: int
    employee_id: str
    first_name: str
    last_name: str
    email: str
    
    class Config:
        from_attributes = True

class ApprovalMemberInfo(BaseModel):
    id: int
    employee: EmployeeInfo
    
    class Config:
        from_attributes = True

class ApprovalResponseInfo(BaseModel):
    id: int
    approval_member: ApprovalMemberInfo
    status: ApprovalResponseStatus
    comments: Optional[str] = None
    responded_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ApprovalRequestResponse(ApprovalRequestBase):
    id: int
    employee: EmployeeInfo
    status: ApprovalStatus
    approval_responses: list[ApprovalResponseInfo] = []
    reference_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ApprovalActionRequest(BaseModel):
    action: str  # "approve" or "reject"
    comments: Optional[str] = None

class ApprovalSettingsResponse(BaseModel):
    is_enabled: bool
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ApprovalSettingsUpdate(BaseModel):
    is_enabled: bool