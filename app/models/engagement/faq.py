from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class FAQ(BaseModel):
    __tablename__ = 'faqs'
    
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100))  # General, Inventory, HR, Purchase, etc.
    tags = Column(String(500))  # Comma separated tags
    priority = Column(Integer, default=0)  # Higher number = higher priority
    is_public = Column(Boolean, default=False)  # Can be shared with other users
    is_active = Column(Boolean, default=True)
    view_count = Column(Integer, default=0)
    last_viewed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<FAQ {self.id}: {self.question[:50]}...>"