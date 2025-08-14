from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class EmailLog(BaseModel):
    __tablename__ = 'email_logs'
    
    recipient_email = Column(String(255), nullable=False)
    recipient_name = Column(String(100))
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    email_type = Column(String(50))  # WELCOME, PASSWORD_RESET, NOTIFICATION, etc.
    status = Column(String(20), default="PENDING")  # PENDING, SENT, FAILED
    sent_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    reference_type = Column(String(50))
    reference_id = Column(Integer)
    created_by = Column(Integer)  # User ID