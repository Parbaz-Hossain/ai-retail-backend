from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class QRCode(BaseModel):
    __tablename__ = 'qr_codes'
    
    qr_code = Column(String(255), unique=True, nullable=False)
    qr_code_image = Column(String(500))  # File path to QR image
    entity_type = Column(String(50), nullable=False)  # ITEM, STOCK_LEVEL, LOCATION
    entity_id = Column(Integer, nullable=False)
    data_payload = Column(JSON)  # JSON data encoded in QR
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer)  # User ID