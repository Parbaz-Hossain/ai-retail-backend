from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class AutomationRule(BaseModel):
    __tablename__ = 'automation_rules'
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    rule_type = Column(String(50), nullable=False)  # REORDER, ALERT, APPROVAL, etc.
    trigger_condition = Column(JSON, nullable=False)  # Conditions that trigger the rule
    action_config = Column(JSON, nullable=False)  # Actions to perform
    priority = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    last_executed = Column(DateTime(timezone=True))
    execution_count = Column(Integer, default=0)
    created_by = Column(Integer)  # User ID