from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class Fingerprint(BaseModel):
    __tablename__ = 'fingerprints'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    finger_index = Column(Integer, nullable=False)  # 1-10 for left/right fingers
    template_data = Column(LargeBinary, nullable=False)  # Encrypted fingerprint template
    template_hash = Column(String(255), nullable=False, unique=True)  # Hash for quick lookup
    quality_score = Column(Integer, default=0)  # 0-100 quality score
    enrollment_attempts = Column(Integer, default=1)
    device_id = Column(String(100))  # Device used for enrollment
    device_info = Column(Text)  # Additional device information
    is_primary = Column(Boolean, default=False)  # Primary finger for employee
    is_active = Column(Boolean, default=True)
    enrolled_by = Column(Integer)  # User ID who enrolled
    last_verified = Column(DateTime(timezone=True))
    verification_count = Column(Integer, default=0)
    
    # Relationships
    employee = relationship("Employee", back_populates="fingerprints")
