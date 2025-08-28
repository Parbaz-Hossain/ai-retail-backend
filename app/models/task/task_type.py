from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class TaskType(BaseModel):
    __tablename__ = 'task_types'
    
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    category = Column(String(50), nullable=False)  # INVENTORY, HR, PURCHASE, LOGISTICS, MAINTENANCE
    
    # Auto-assignment configuration
    auto_assign_enabled = Column(Boolean, default=False)
    auto_assign_rules = Column(JSON)  # Rules for automatic assignment
    
    # Default settings
    default_priority = Column(String(20), default="MEDIUM")
    default_estimated_hours = Column(Numeric(4, 2))
    sla_hours = Column(Integer)  # Service Level Agreement in hours
    
    # Approval workflow
    requires_approval = Column(Boolean, default=False)
    approval_roles = Column(JSON)  # Roles that can approve
    
    # Notification settings
    notification_settings = Column(JSON)
    
    is_active = Column(Boolean, default=True)
    
    # Relationships
    tasks = relationship("Task", back_populates="task_type")