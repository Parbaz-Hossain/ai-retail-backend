from sqlalchemy import Column, Integer, Boolean, Text, ForeignKey, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import OffdayType

class Offday(BaseModel):
    __tablename__ = 'offdays'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    offday_date = Column(Date, nullable=False)
    offday_type = Column(SQLEnum(OffdayType), nullable=False, default=OffdayType.WEEKEND)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    employee = relationship("Employee", back_populates="offdays")
    