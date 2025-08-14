from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class NotificationQueue(BaseModel):
    __tablename__ = 'notification_queue'
    
    notification_type = Column(String(50), nullable=False)  # EMAIL, WHATSAPP, PUSH
    recipient_id = Column(Integer)  # User/Employee ID
    recipient_email = Column(String(255))
    recipient_phone = Column(String(20))
    subject = Column(String(500))
    message = Column(Text, nullable=False)
    template_name = Column(String(100))
    template_data = Column(JSON)
    priority = Column(Integer, default=1)  # 1=High, 2=Medium, 3=Low
    status = Column(String(20), default="PENDING")  # PENDING, SENT, FAILED
    scheduled_for = Column(DateTime(timezone=True))
    sent_at = Column(DateTime(timezone=True))
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text)
    reference_type = Column(String(50))
    reference_id = Column(Integer)