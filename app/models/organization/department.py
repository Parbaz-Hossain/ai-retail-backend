
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Department(BaseModel):
    __tablename__ = 'departments'
    
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # Relationships
    employees = relationship("Employee", back_populates="department")