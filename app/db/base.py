from sqlalchemy import Column, Integer, DateTime, Boolean, String
from sqlalchemy.sql import func
from app.models.base import Base

class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)