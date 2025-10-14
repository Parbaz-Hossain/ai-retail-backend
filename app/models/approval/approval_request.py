from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum as SQLEnum, JSON, DateTime
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import ApprovalRequestType, ApprovalStatus

class ApprovalRequest(BaseModel):
    __tablename__ = 'approval_requests'
    
    request_type = Column(SQLEnum(ApprovalRequestType), nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    requested_by = Column(Integer, nullable=False)  # User ID who created the request
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    request_data = Column(JSON, nullable=False)  # Store the actual data for the operation
    remarks = Column(Text)
    approved_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    
    # Reference IDs for the actual records (set after approval)
    reference_id = Column(Integer)  # ID of the created Shift/Salary/Offday record
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    approval_responses = relationship("ApprovalResponse", back_populates="approval_request", cascade="all, delete-orphan")