from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class SystemSetting(BaseModel):
    __tablename__ = 'system_settings'
    
    category = Column(String(50), nullable=False)  # GENERAL, EMAIL, WHATSAPP, ATTENDANCE
    setting_key = Column(String(100), nullable=False, unique=True)
    setting_value = Column(Text)
    data_type = Column(String(20), default="STRING")  # STRING, INTEGER, BOOLEAN, JSON
    description = Column(Text)
    is_encrypted = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)  # System settings cannot be deleted
    updated_by = Column(Integer)  # User ID