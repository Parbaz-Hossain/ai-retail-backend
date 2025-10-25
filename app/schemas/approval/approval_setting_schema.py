from pydantic import BaseModel, validator
from typing import Optional, List, Dict
from datetime import datetime
from app.models.shared.enums import ApprovalRequestType

class ApprovalSettingsBase(BaseModel):
    module: str
    action_type: ApprovalRequestType
    is_enabled: bool

class ApprovalSettingsCreate(ApprovalSettingsBase):
    @validator('module')
    def validate_module(cls, v):
        allowed_modules = ['HR', 'INVENTORY', 'PURCHASE', 'LOGISTICS']
        if v.upper() not in allowed_modules:
            raise ValueError(f'Module must be one of: {", ".join(allowed_modules)}')
        return v.upper()

class ApprovalSettingsUpdate(BaseModel):
    is_enabled: bool

class ApprovalSettingsResponse(ApprovalSettingsBase):
    id: int
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ApprovalSettingsBulkUpdate(BaseModel):
    """Bulk update settings for multiple module-action combinations"""
    settings: List[ApprovalSettingsCreate]

class ApprovalSettingsGroupedResponse(BaseModel):
    """Grouped settings by module for easier UI display"""
    module: str
    settings: Dict[str, bool]  # {action_type: is_enabled}
    
class ApprovalSettingsListResponse(BaseModel):
    """List all settings grouped by module"""
    data: List[ApprovalSettingsGroupedResponse]