from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class TaskAttachment(BaseModel):
    __tablename__ = 'task_attachments'
    
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Numeric(12, 0))  # Size in bytes
    mime_type = Column(String(100))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    task = relationship("Task", back_populates="attachments")
    uploader = relationship("User")