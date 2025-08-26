# app/schemas/biometric/fingerprint_schema.py
from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
from enum import IntEnum

class FingerIndex(IntEnum):
    """Finger index mapping"""
    LEFT_THUMB = 1
    LEFT_INDEX = 2
    LEFT_MIDDLE = 3
    LEFT_RING = 4
    LEFT_LITTLE = 5
    RIGHT_THUMB = 6
    RIGHT_INDEX = 7
    RIGHT_MIDDLE = 8
    RIGHT_RING = 9
    RIGHT_LITTLE = 10

class FingerprintEnrollRequest(BaseModel):
    employee_id: int
    finger_index: int = Field(..., ge=1, le=10, description="Finger index (1-10)")
    template_data: str = Field(..., description="Base64 encoded fingerprint template")
    quality_score: Optional[int] = Field(0, ge=0, le=100)
    device_id: Optional[str] = Field(None, max_length=100)
    device_info: Optional[str] = None
    is_primary: bool = False

    @validator('finger_index')
    def validate_finger_index(cls, v):
        if v not in range(1, 11):
            raise ValueError('Finger index must be between 1 and 10')
        return v

    @validator('template_data')
    def validate_template_data(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Template data is required and must be valid')
        # Basic base64 validation
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('Template data must be valid base64 encoded')
        return v

class FingerprintVerifyRequest(BaseModel):
    template_data: str = Field(..., description="Base64 encoded fingerprint template to verify")
    device_id: Optional[str] = Field(None, max_length=100)
    location_id: Optional[int] = None
    
    @validator('template_data')
    def validate_template_data(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Template data is required for verification')
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('Template data must be valid base64 encoded')
        return v

class FingerprintEnrollResponse(BaseModel):
    id: int
    employee_id: int
    finger_index: int
    finger_name: str
    quality_score: int
    template_hash: str
    is_primary: bool
    enrollment_attempts: int
    device_id: Optional[str]
    enrolled_at: datetime
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None

    class Config:
        from_attributes = True

class FingerprintVerifyResponse(BaseModel):
    success: bool
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    finger_index: Optional[int] = None
    finger_name: Optional[str] = None
    match_score: Optional[float] = None
    verification_time: Optional[datetime] = None
    message: Optional[str] = None

class FingerprintListResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_code: str
    finger_index: int
    finger_name: str
    quality_score: int
    is_primary: bool
    is_active: bool
    last_verified: Optional[datetime]
    verification_count: int
    enrolled_at: datetime

    class Config:
        from_attributes = True

class FingerprintBulkEnrollRequest(BaseModel):
    employee_id: int
    fingerprints: List[FingerprintEnrollRequest]
    
    @validator('fingerprints')
    def validate_fingerprints(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one fingerprint is required')
        if len(v) > 10:
            raise ValueError('Maximum 10 fingerprints allowed per employee')
        
        # Check for duplicate finger indexes
        finger_indexes = [fp.finger_index for fp in v]
        if len(finger_indexes) != len(set(finger_indexes)):
            raise ValueError('Duplicate finger indexes not allowed')
        
        return v

class BiometricDeviceStatus(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    location_id: Optional[int] = None
    is_online: Optional[bool] = None
    last_heartbeat: Optional[datetime] = None
    total_enrollments: Optional[int] = None
    total_verifications: Optional[int] = None