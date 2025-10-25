from sqlalchemy import Column, Integer, Boolean, String, Enum as SQLEnum
from app.db.base import BaseModel
from app.models.shared.enums import ApprovalRequestType

class ApprovalSettings(BaseModel):
    __tablename__ = 'approval_settings'
    
    module = Column(String(50), nullable=False)  # HR, INVENTORY, PURCHASE, etc.
    action_type = Column(SQLEnum(ApprovalRequestType), nullable=False)  # SALARY, SHIFT, DAYOFF, etc.
    is_enabled = Column(Boolean, default=False)
    updated_by = Column(Integer, nullable=False)  # HR Manager user ID