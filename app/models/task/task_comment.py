from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class TaskComment(BaseModel):
    __tablename__ = 'task_comments'
    
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    comment = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)  # Internal comments vs customer-facing
    is_active = Column(Boolean, default=True)
    
    # Relationships
    task = relationship("Task", back_populates="comments")
    user = relationship("User")