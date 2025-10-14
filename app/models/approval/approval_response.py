from sqlalchemy import Column, Integer, Text, ForeignKey, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import ApprovalResponseStatus

class ApprovalResponse(BaseModel):
    __tablename__ = 'approval_responses'
    
    approval_request_id = Column(Integer, ForeignKey('approval_requests.id'), nullable=False)
    approval_member_id = Column(Integer, ForeignKey('approval_members.id'), nullable=False)
    status = Column(SQLEnum(ApprovalResponseStatus), default=ApprovalResponseStatus.PENDING)
    comments = Column(Text)
    responded_at = Column(DateTime(timezone=True))
    
    # Relationships
    approval_request = relationship("ApprovalRequest", back_populates="approval_responses")
    approval_member = relationship("ApprovalMember", back_populates="approval_responses")