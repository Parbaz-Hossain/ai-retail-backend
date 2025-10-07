from sqlalchemy import Column, Integer,ForeignKey, Numeric, String
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class Ticket(BaseModel):
    __tablename__ = 'tickets'
    
    ticket_no = Column(String(50), unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    ticket_type = Column(String(50), nullable=False)
    deduction_amount = Column(Numeric(10, 2), default=0)
    
    # Relationships
    employee = relationship("Employee", back_populates="tickets")