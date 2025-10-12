from sqlalchemy import Column, Integer, Boolean, ForeignKey, String
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class ApprovalMember(BaseModel):
    __tablename__ = 'approval_members'
    
    module = Column(String(50), nullable=False, unique=True)  # HR, INVENTORY, PURCHASE, etc.
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    added_by = Column(Integer, nullable=False)  # HR Manager user ID
    is_active = Column(Boolean, default=True)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    approval_responses = relationship("ApprovalResponse", back_populates="approval_member")