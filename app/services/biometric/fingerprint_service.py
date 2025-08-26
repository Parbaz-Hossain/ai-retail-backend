import logging
import hashlib
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.biometric.fingerprint import Fingerprint
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.shared.enums import AttendanceStatus
from app.schemas.biometric.fingerprint_schema import (
    FingerprintEnrollRequest, FingerprintVerifyRequest, 
    FingerprintEnrollResponse, FingerprintVerifyResponse
)

logger = logging.getLogger(__name__)

class FingerprintService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.finger_names = {
            1: "Left Thumb", 2: "Left Index", 3: "Left Middle", 
            4: "Left Ring", 5: "Left Little", 6: "Right Thumb",
            7: "Right Index", 8: "Right Middle", 9: "Right Ring", 10: "Right Little"
        }

    def _generate_template_hash(self, template_data: str, employee_id: int, finger_index: int) -> str:
        """Generate unique hash for fingerprint template"""
        combined = f"{template_data}_{employee_id}_{finger_index}_{datetime.utcnow().isoformat()}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _encrypt_template(self, template_data: str) -> bytes:
        """Encrypt template data before storing"""
        # In production, use proper encryption like AES
        # For now, we'll use base64 encoding as placeholder
        try:
            return base64.b64decode(template_data)
        except Exception as e:
            raise ValueError(f"Invalid template data: {str(e)}")

    def _decrypt_template(self, encrypted_data: bytes) -> str:
        """Decrypt template data for verification"""
        try:
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Error decrypting template: {e}")
            return ""

    def _calculate_match_score(self, template1: str, template2: str) -> float:
        """Calculate fingerprint match score (0-100)"""
        # This is a simplified matching algorithm
        # In production, use proper biometric matching algorithms
        try:
            # Simple byte comparison for demo
            data1 = base64.b64decode(template1)
            data2 = base64.b64decode(template2)
            
            if len(data1) != len(data2):
                return 0.0
            
            matches = sum(1 for a, b in zip(data1, data2) if a == b)
            score = (matches / len(data1)) * 100
            
            return round(score, 2)
        except Exception as e:
            logger.error(f"Error calculating match score: {e}")
            return 0.0

    # ---------- Enrollment ----------
    async def enroll_fingerprint(self, request: FingerprintEnrollRequest, enrolled_by: int) -> FingerprintEnrollResponse:
        """Enroll a new fingerprint for an employee"""
        try:
            # Validate employee exists and is active
            emp_result = await self.session.execute(
                select(Employee).where(
                    Employee.id == request.employee_id,
                    Employee.is_active == True
                )
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee not found or inactive"
                )

            # Check if fingerprint already exists for this finger
            existing_result = await self.session.execute(
                select(Fingerprint).where(
                    Fingerprint.employee_id == request.employee_id,
                    Fingerprint.finger_index == request.finger_index,
                    Fingerprint.is_active == True
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Fingerprint already enrolled for {self.finger_names[request.finger_index]}"
                )

            # Encrypt template data
            encrypted_template = self._encrypt_template(request.template_data)
            template_hash = self._generate_template_hash(
                request.template_data, request.employee_id, request.finger_index
            )

            # If this is marked as primary, unset other primary fingerprints
            if request.is_primary:
                await self.session.execute(
                    select(Fingerprint).where(
                        Fingerprint.employee_id == request.employee_id,
                        Fingerprint.is_primary == True
                    )
                )
                # Update existing primary fingerprints
                primary_fps = await self.session.execute(
                    select(Fingerprint).where(
                        Fingerprint.employee_id == request.employee_id,
                        Fingerprint.is_primary == True,
                        Fingerprint.is_active == True
                    )
                )
                for fp in primary_fps.scalars().all():
                    fp.is_primary = False

            # Create fingerprint record
            fingerprint = Fingerprint(
                employee_id=request.employee_id,
                finger_index=request.finger_index,
                template_data=encrypted_template,
                template_hash=template_hash,
                quality_score=request.quality_score or 0,
                device_id=request.device_id,
                device_info=request.device_info,
                is_primary=request.is_primary,
                enrolled_by=enrolled_by,
                enrollment_attempts=1
            )

            self.session.add(fingerprint)
            await self.session.commit()
            await self.session.refresh(fingerprint)

            logger.info(f"Fingerprint enrolled: Employee {employee.employee_id}, Finger {request.finger_index}")

            return FingerprintEnrollResponse(
                id=fingerprint.id,
                employee_id=fingerprint.employee_id,
                finger_index=fingerprint.finger_index,
                finger_name=self.finger_names[fingerprint.finger_index],
                quality_score=fingerprint.quality_score,
                template_hash=fingerprint.template_hash,
                is_primary=fingerprint.is_primary,
                enrollment_attempts=fingerprint.enrollment_attempts,
                device_id=fingerprint.device_id,
                enrolled_at=fingerprint.created_at,
                employee_name=f"{employee.first_name} {employee.last_name}",
                employee_code=employee.employee_id
            )

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error enrolling fingerprint: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enroll fingerprint"
            )

    # ---------- Verification ----------
    async def verify_fingerprint(self, request: FingerprintVerifyRequest) -> FingerprintVerifyResponse:
        """Verify fingerprint and optionally mark attendance"""
        try:
            # Get all active fingerprints
            fp_result = await self.session.execute(
                select(Fingerprint)
                .options(selectinload(Fingerprint.employee))
                .where(Fingerprint.is_active == True)
                .order_by(Fingerprint.is_primary.desc())  # Check primary fingers first
            )
            fingerprints = fp_result.scalars().all()

            best_match = None
            best_score = 0.0
            threshold = 80.0  # Minimum match score threshold

            # Find best matching fingerprint
            for fp in fingerprints:
                if not fp.employee or not fp.employee.is_active:
                    continue

                stored_template = self._decrypt_template(fp.template_data)
                if not stored_template:
                    continue

                match_score = self._calculate_match_score(request.template_data, stored_template)
                
                if match_score > best_score and match_score >= threshold:
                    best_match = fp
                    best_score = match_score

            if not best_match:
                return FingerprintVerifyResponse(
                    success=False,
                    message="Fingerprint not recognized"
                )

            # Update verification stats
            best_match.last_verified = datetime.utcnow()
            best_match.verification_count += 1

            # Mark attendance if requested
            # attendance_marked = False
            # attendance_id = None
            
            # if request.attendance_date:
            #     attendance_id = await self._mark_attendance(
            #         best_match.employee_id, 
            #         request.attendance_date,
            #         request.device_id
            #     )
            #     attendance_marked = attendance_id is not None

            await self.session.commit()

            logger.info(f"Fingerprint verified: Employee {best_match.employee.employee_id}, Score: {best_score}")

            return FingerprintVerifyResponse(
                success=True,
                employee_id=best_match.employee_id,
                employee_name=f"{best_match.employee.first_name} {best_match.employee.last_name}",
                employee_code=best_match.employee.employee_id,
                finger_index=best_match.finger_index,
                finger_name=self.finger_names[best_match.finger_index],
                match_score=best_score,
                verification_time=datetime.utcnow(),
                # attendance_marked=attendance_marked,
                # attendance_id=attendance_id,
                message="Fingerprint verified successfully"
            )

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error verifying fingerprint: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify fingerprint"
            )

    async def _mark_attendance(self, employee_id: int, attendance_date: datetime, device_id: Optional[str]) -> Optional[int]:
        """Mark attendance for verified employee"""
        try:
            from app.services.hr.attendance_service import AttendanceService
            attendance_service = AttendanceService(self.session)

            # Check existing attendance for today
            today = attendance_date.date()
            existing_result = await self.session.execute(
                select(Attendance).where(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date == today
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing and existing.check_out_time:
                # Already complete attendance for today
                return None

            # Import the attendance schema
            from app.schemas.hr.attendance_schema import AttendanceCreate

            if existing and not existing.check_out_time:
                # Check out
                attendance_data = AttendanceCreate(
                    employee_id=employee_id,
                    attendance_date=today,
                    check_out_time=attendance_date,
                    bio_check_out=True
                )
            else:
                # Check in
                attendance_data = AttendanceCreate(
                    employee_id=employee_id,
                    attendance_date=today,
                    check_in_time=attendance_date,
                    bio_check_in=True
                )

            result = await attendance_service.mark_attendance(attendance_data)
            return result.id

        except Exception as e:
            logger.error(f"Error marking attendance: {e}")
            return None

    # ---------- Management ----------
    async def get_employee_fingerprints(self, employee_id: int) -> List[Dict[str, Any]]:
        """Get all fingerprints for an employee"""
        try:
            result = await self.session.execute(
                select(Fingerprint)
                .options(selectinload(Fingerprint.employee))
                .where(
                    Fingerprint.employee_id == employee_id,
                    Fingerprint.is_active == True
                )
                .order_by(Fingerprint.finger_index)
            )
            fingerprints = result.scalars().all()

            return [
                {
                    "id": fp.id,
                    "finger_index": fp.finger_index,
                    "finger_name": self.finger_names[fp.finger_index],
                    "quality_score": fp.quality_score,
                    "is_primary": fp.is_primary,
                    "last_verified": fp.last_verified,
                    "verification_count": fp.verification_count,
                    "enrolled_at": fp.created_at
                }
                for fp in fingerprints
            ]

        except Exception as e:
            logger.error(f"Error getting employee fingerprints: {e}")
            return []

    async def delete_fingerprint(self, fingerprint_id: int, user_id: int) -> bool:
        """Delete (deactivate) a fingerprint"""
        try:
            result = await self.session.execute(
                select(Fingerprint).where(Fingerprint.id == fingerprint_id)
            )
            fingerprint = result.scalar_one_or_none()
            
            if not fingerprint:
                return False

            fingerprint.is_active = False
            fingerprint.is_deleted = True
            fingerprint.updated_at = datetime.utcnow()
            
            await self.session.commit()
            logger.info(f"Fingerprint deleted: ID {fingerprint_id} by user {user_id}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting fingerprint: {e}")
            return False

    async def get_verification_stats(self, employee_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """Get fingerprint verification statistics"""
        try:
            from datetime import timedelta
            since_date = datetime.utcnow() - timedelta(days=days)

            query = select(
                func.count(Fingerprint.id).label('total_fingerprints'),
                func.sum(Fingerprint.verification_count).label('total_verifications'),
                func.avg(Fingerprint.quality_score).label('avg_quality')
            ).where(Fingerprint.is_active == True)

            if employee_id:
                query = query.where(Fingerprint.employee_id == employee_id)

            result = await self.session.execute(query)
            stats = result.first()

            return {
                "total_fingerprints": stats.total_fingerprints or 0,
                "total_verifications": stats.total_verifications or 0,
                "average_quality": round(float(stats.avg_quality or 0), 2),
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting verification stats: {e}")
            return {
                "total_fingerprints": 0,
                "total_verifications": 0,
                "average_quality": 0,
                "period_days": days
            }