from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class WhatsAppLog(BaseModel):
    __tablename__ = 'whatsapp_logs'
    
    recipient_phone = Column(String(20), nullable=False)
    recipient_name = Column(String(100))
    message = Column(Text, nullable=False)
    message_type = Column(String(50))  # TEXT, TEMPLATE, MEDIA
    template_name = Column(String(100))
    status = Column(String(20), default="PENDING")  # PENDING, SENT, DELIVERED, FAILED
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    whatsapp_message_id = Column(String(100))
    reference_type = Column(String(50))
    reference_id = Column(Integer)
    created_by = Column(Integer)  # User ID