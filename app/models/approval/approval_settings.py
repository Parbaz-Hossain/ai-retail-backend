from sqlalchemy import Column, Integer, Boolean, String
from app.db.base import BaseModel

class ApprovalSettings(BaseModel):
    __tablename__ = 'approval_settings'
    
    # module = Column(String(50), nullable=False, unique=True)  # HR, INVENTORY, PURCHASE, etc.
    is_enabled = Column(Boolean, default=False)
    updated_by = Column(Integer, nullable=False)  # HR Manager user ID