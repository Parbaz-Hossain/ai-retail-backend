from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class AutomationLog(BaseModel):
    __tablename__ = 'automation_logs'
    
    rule_id = Column(Integer, ForeignKey('automation_rules.id'), nullable=False)
    execution_time = Column(DateTime(timezone=True), nullable=False)
    trigger_data = Column(JSON)  # Data that triggered the rule
    action_results = Column(JSON)  # Results of actions performed
    status = Column(String(20), nullable=False)  # SUCCESS, FAILED, PARTIAL
    error_message = Column(Text)
    processing_time_ms = Column(Integer)
    
    # Relationships
    rule = relationship("AutomationRule")