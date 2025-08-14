from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class PerformanceMetrics(BaseModel):
    __tablename__ = 'performance_metrics'
    
    metric_type = Column(String(50), nullable=False)  # ATTENDANCE, PRODUCTIVITY, EFFICIENCY
    entity_type = Column(String(50), nullable=False)  # EMPLOYEE, DEPARTMENT, LOCATION
    entity_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    metric_value = Column(Numeric(10, 2), nullable=False)
    target_value = Column(Numeric(10, 2))
    variance = Column(Numeric(10, 2))
    variance_percentage = Column(Numeric(5, 2))
    notes = Column(Text)
    calculated_by = Column(String(50), default="SYSTEM")  # SYSTEM, MANUAL