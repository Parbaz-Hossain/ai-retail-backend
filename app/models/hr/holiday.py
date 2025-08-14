from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Holiday(BaseModel):
    __tablename__ = 'holidays'
    
    name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(Text)
    is_recurring = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)