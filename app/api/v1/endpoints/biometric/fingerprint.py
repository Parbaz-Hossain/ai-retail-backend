import logging
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth.user import User
from app.services.biometric.fingerprint_service import FingerprintService
from app.services.engagement.user_history_service import UserHistoryService
from app.schemas.biometric.fingerprint_schema import (
    FingerprintEnrollRequest, FingerprintVerifyRequest,
    FingerprintEnrollResponse, FingerprintVerifyResponse,
    FingerprintBulkEnrollRequest, BiometricDeviceStatus
)
from app.models.shared.enums import HistoryActionType

router = APIRouter()
logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

@router.post("/enroll", response_model=FingerprintEnrollResponse, status_code=status.HTTP_201_CREATED)
async def enroll_fingerprint(
    enroll_data: FingerprintEnrollRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Enroll a new fingerprint for an employee"""
    try:
        fingerprint_service = FingerprintService(session)
        history_service = UserHistoryService(session)
        
        result = await fingerprint_service.enroll_fingerprint(enroll_data, current_user.id)
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.CREATE,
            resource_type="FINGERPRINT",
            resource_id=result.id,
            title=f"Enrolled fingerprint: {result.finger_name}",
            description=f"Employee: {result.employee_name} ({result.employee_code}), Quality: {result.quality_score}%",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return result
    except Exception as e:
        logger.error(f"Error enrolling fingerprint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enroll fingerprint"
        )

@router.post("/verify", response_model=FingerprintVerifyResponse)
async def verify_fingerprint(
    verify_data: FingerprintVerifyRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Verify fingerprint"""
    try:
        fingerprint_service = FingerprintService(session)
        
        result = await fingerprint_service.verify_fingerprint(verify_data)
        
        # Log verification attempt (no user required for verification)
        if result.success:
            logger.info(f"Fingerprint verified: Employee {result.employee_code}, Score: {result.match_score}")
        else:
            logger.warning(f"Fingerprint verification failed from {get_client_ip(request)}")
        
        return result
    except Exception as e:
        logger.error(f"Error verifying fingerprint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify fingerprint"
        )

@router.get("/employee/{employee_id}", response_model=List[Any])
async def get_employee_fingerprints(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all fingerprints for a specific employee"""
    try:
        fingerprint_service = FingerprintService(session)
        fingerprints = await fingerprint_service.get_employee_fingerprints(employee_id)
        return fingerprints
    except Exception as e:
        logger.error(f"Error getting employee fingerprints: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve employee fingerprints"
        )

@router.delete("/{fingerprint_id}")
async def delete_fingerprint(
    fingerprint_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete (deactivate) a fingerprint"""
    try:
        fingerprint_service = FingerprintService(session)
        history_service = UserHistoryService(session)
        
        success = await fingerprint_service.delete_fingerprint(fingerprint_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fingerprint not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.DELETE,
            resource_type="FINGERPRINT",
            resource_id=fingerprint_id,
            title="Deleted fingerprint",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return {"message": "Fingerprint deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting fingerprint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete fingerprint"
        )

@router.post("/bulk-enroll", response_model=List[FingerprintEnrollResponse])
async def bulk_enroll_fingerprints(
    bulk_data: FingerprintBulkEnrollRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Bulk enroll multiple fingerprints for an employee"""
    try:
        fingerprint_service = FingerprintService(session)
        history_service = UserHistoryService(session)
        
        results = []
        errors = []
        
        for fp_data in bulk_data.fingerprints:
            try:
                # Ensure employee_id matches
                fp_data.employee_id = bulk_data.employee_id
                result = await fingerprint_service.enroll_fingerprint(fp_data, current_user.id)
                results.append(result)
            except Exception as e:
                errors.append(f"Finger {fp_data.finger_index}: {str(e)}")
                continue
        
        if results:
            # Log to history
            await history_service.log_action(
                user_id=current_user.id,
                action_type=HistoryActionType.CREATE,
                resource_type="FINGERPRINT_BULK",
                title=f"Bulk enrolled {len(results)} fingerprints",
                description=f"Employee ID: {bulk_data.employee_id}, Successful: {len(results)}, Errors: {len(errors)}",
                metadata={"successful_count": len(results), "error_count": len(errors), "errors": errors[:5]},
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent")
            )
        
        if errors:
            logger.warning(f"Bulk enrollment partially failed: {errors}")
        
        return results
    except Exception as e:
        logger.error(f"Error in bulk fingerprint enrollment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk enroll fingerprints"
        )

@router.get("/stats")
async def get_fingerprint_stats(
    employee_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get fingerprint verification statistics"""
    try:
        fingerprint_service = FingerprintService(session)
        stats = await fingerprint_service.get_verification_stats(employee_id, days)
        return stats
    except Exception as e:
        logger.error(f"Error getting fingerprint stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve fingerprint statistics"
        )