from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import HistoryActionType

class UserHistory(BaseModel):
    __tablename__ = 'user_histories'
    
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    action_type = Column(SQLEnum(HistoryActionType), nullable=False)
    resource_type = Column(String(50), nullable=False)  # FAQ, Task, Purchase, etc.
    resource_id = Column(Integer)  # ID of the related resource
    title = Column(String(255), nullable=False)
    description = Column(Text)
    metadata = Column(JSON)  # Store additional context data
    session_id = Column(String(100))  # Chat session identifier
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<UserHistory {self.user_id}: {self.action_type} - {self.title}>"