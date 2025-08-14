from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class FileUpload(BaseModel):
    __tablename__ = 'file_uploads'
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_type = Column(String(50))  # PROFILE_IMAGE, DOCUMENT, SIGNATURE, etc.
    entity_type = Column(String(50))  # USER, EMPLOYEE, ITEM, etc.
    entity_id = Column(Integer)
    uploaded_by = Column(Integer)  # User ID
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())