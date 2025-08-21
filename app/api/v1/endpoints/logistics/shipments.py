# app/api/v1/endpoints/logistics/shipments.py
import logging
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.models.shared.enums import ShipmentStatus
from app.schemas.common.pagination import PaginatedResponse
from app.schemas.logistics.shipment_schema import (
    ShipmentCreate, ShipmentUpdate, ShipmentResponse,
    OTPVerificationRequest, ShipmentStatusUpdate,
    ShipmentAssignment, ShipmentTrackingResponse
)
from app.services.logistics.shipment_service import ShipmentService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_shipment(
    shipment_data: ShipmentCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new shipment"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.create_shipment(shipment_data, current_user.id)
        return shipment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating shipment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create shipment"
        )

@router.get("/", response_model=PaginatedResponse[ShipmentResponse])
async def get_shipments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by shipment number or reference type"),
    status: Optional[ShipmentStatus] = Query(None, description="Filter by shipment status"),
    from_location_id: Optional[int] = Query(None, description="Filter by source location"),
    to_location_id: Optional[int] = Query(None, description="Filter by destination location"),
    driver_id: Optional[int] = Query(None, description="Filter by assigned driver"),
    vehicle_id: Optional[int] = Query(None, description="Filter by assigned vehicle"),
    date_from: Optional[date] = Query(None, description="Filter shipments from this date"),
    date_to: Optional[date] = Query(None, description="Filter shipments until this date"),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get list of shipments with optional filters"""
    try:
        shipment_service = ShipmentService(session)
        shipments = await shipment_service.get_shipments(
            skip=skip,
            limit=limit,
            search=search,
            status=status,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            date_from=date_from,
            date_to=date_to
        )
        return shipments
    except Exception as e:
        logger.error(f"Error getting shipments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shipments"
        )

@router.get("/statistics")
async def get_shipment_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to calculate statistics for"),
    session: AsyncSession = Depends(get_async_session)
):
    """Get shipment statistics including completion rates, delivery times, and performance metrics"""
    try:
        shipment_service = ShipmentService(session)
        stats = await shipment_service.get_shipment_statistics(days)
        return stats
    except Exception as e:
        logger.error(f"Error getting shipment statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shipment statistics"
        )

@router.get("/driver/{driver_id}/active", response_model=List[ShipmentResponse])
async def get_active_shipments_by_driver(
    driver_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get active shipments assigned to a specific driver"""
    try:
        shipment_service = ShipmentService(session)
        shipments = await shipment_service.get_active_shipments_by_driver(driver_id)
        return shipments
    except Exception as e:
        logger.error(f"Error getting active shipments by driver: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active shipments"
        )

@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get detailed shipment information by ID"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.get_shipment(shipment_id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        return shipment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shipment {shipment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shipment"
        )

@router.put("/{shipment_id}", response_model=ShipmentResponse)
async def update_shipment(
    shipment_id: int,
    shipment_data: ShipmentUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update shipment details (only allowed for non-delivered/cancelled shipments)"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.update_shipment(shipment_id, shipment_data, current_user.id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        return shipment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shipment {shipment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update shipment"
        )

@router.patch("/{shipment_id}/assign")
async def assign_driver_vehicle(
    shipment_id: int,
    assignment_data: ShipmentAssignment,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Assign driver and/or vehicle to a shipment"""
    try:
        shipment_service = ShipmentService(session)
        success = await shipment_service.assign_driver_vehicle(
            shipment_id, assignment_data.driver_id, assignment_data.vehicle_id, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to assign driver/vehicle"
            )
        return {"message": "Driver and/or vehicle assigned successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning driver/vehicle: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign driver/vehicle"
        )

@router.patch("/{shipment_id}/status")
async def update_shipment_status(
    shipment_id: int,
    status_data: ShipmentStatusUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update shipment status with optional notes"""
    try:
        shipment_service = ShipmentService(session)
        success = await shipment_service.update_shipment_status(
            shipment_id, status_data.status, status_data.notes, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update shipment status"
            )
        return {"message": f"Shipment status updated to {status_data.status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shipment status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update shipment status"
        )

@router.post("/{shipment_id}/pickup/verify-otp")
async def verify_pickup_otp(
    shipment_id: int,
    otp_data: OTPVerificationRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Verify pickup OTP and update shipment to PICKED_UP status"""
    try:
        shipment_service = ShipmentService(session)
        success = await shipment_service.verify_pickup_otp(
            shipment_id, otp_data.otp, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP or shipment not ready for pickup"
            )
        return {"message": "Pickup OTP verified successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying pickup OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify pickup OTP"
        )

@router.post("/{shipment_id}/delivery/verify-otp")
async def verify_delivery_otp(
    shipment_id: int,
    otp_data: OTPVerificationRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Verify delivery OTP and complete shipment delivery"""
    try:
        shipment_service = ShipmentService(session)
        success = await shipment_service.verify_delivery_otp(
            shipment_id, otp_data.otp, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP or shipment not ready for delivery"
            )
        return {"message": "Delivery OTP verified successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying delivery OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify delivery OTP"
        )

@router.post("/{shipment_id}/cancel")
async def cancel_shipment(
    shipment_id: int,
    reason: str = Body(..., embed=True, description="Reason for cancellation"),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Cancel a shipment with reason"""
    try:
        shipment_service = ShipmentService(session)
        success = await shipment_service.cancel_shipment(
            shipment_id, reason, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to cancel shipment"
            )
        return {"message": "Shipment cancelled successfully", "reason": reason}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling shipment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel shipment"
        )

@router.get("/{shipment_id}/tracking", response_model=List[ShipmentTrackingResponse])
async def get_shipment_tracking(
    shipment_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get complete tracking history for a shipment"""
    try:
        shipment_service = ShipmentService(session)
        tracking = await shipment_service.get_shipment_tracking(shipment_id)
        return tracking
    except Exception as e:
        logger.error(f"Error getting shipment tracking: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shipment tracking"
        )

@router.get("/{shipment_id}/otp/pickup")
async def get_pickup_otp(
    shipment_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get pickup OTP for a shipment (for authorized users only)"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.get_shipment(shipment_id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        if shipment.status != ShipmentStatus.READY_FOR_PICKUP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment is not ready for pickup"
            )
        
        return {
            "shipment_id": shipment_id,
            "pickup_otp": shipment.pickup_otp,
            "status": shipment.status,
            "from_location": shipment.from_location.name if shipment.from_location else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pickup OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pickup OTP"
        )

@router.get("/{shipment_id}/otp/delivery")
async def get_delivery_otp(
    shipment_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get delivery OTP for a shipment (for authorized users only)"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.get_shipment(shipment_id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        if shipment.status not in [ShipmentStatus.PICKED_UP, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.IN_TRANSIT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment is not ready for delivery"
            )
        
        return {
            "shipment_id": shipment_id,
            "delivery_otp": shipment.delivery_otp,
            "status": shipment.status,
            "to_location": shipment.to_location.name if shipment.to_location else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting delivery OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve delivery OTP"
        )

@router.post("/{shipment_id}/regenerate-otp")
async def regenerate_shipment_otps(
    shipment_id: int,
    otp_type: str = Body(..., embed=True, regex="^(pickup|delivery|both)$"),
    session: AsyncSession = Depends(get_async_session)
):
    """Regenerate pickup and/or delivery OTP for a shipment"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.get_shipment(shipment_id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        # Only allow OTP regeneration for non-completed shipments
        if shipment.status in [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot regenerate OTP for completed or cancelled shipment"
            )
        
        new_otps = {}
        if otp_type in ["pickup", "both"]:
            if not shipment.pickup_otp_verified:
                shipment.pickup_otp = shipment_service.generate_otp()
                new_otps["pickup_otp"] = shipment.pickup_otp
        
        if otp_type in ["delivery", "both"]:
            if not shipment.delivery_otp_verified:
                shipment.delivery_otp = shipment_service.generate_otp()
                new_otps["delivery_otp"] = shipment.delivery_otp
        
        if not new_otps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OTP can be regenerated (already verified or invalid type)"
            )
        
        await session.commit()
        
        return {
            "message": f"OTP regenerated successfully for {otp_type}",
            "shipment_id": shipment_id,
            **new_otps
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error regenerating OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate OTP"
        )

@router.get("/status/{status}")
async def get_shipments_by_status(
    status: ShipmentStatus,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all shipments with a specific status"""
    try:
        shipment_service = ShipmentService(session)
        shipments = await shipment_service.get_shipments(
            skip=skip,
            limit=limit,
            status=status
        )
        return {
            "status": status,
            "count": len(shipments),
            "shipments": shipments
        }
    except Exception as e:
        logger.error(f"Error getting shipments by status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shipments by status"
        )

@router.get("/location/{location_id}/shipments")
async def get_shipments_by_location(
    location_id: int,
    location_type: str = Query("both", regex="^(from|to|both)$", description="Filter by source, destination, or both"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session)
):
    """Get shipments associated with a specific location"""
    try:
        shipment_service = ShipmentService(session)
        
        from_location_id = location_id if location_type in ["from", "both"] else None
        to_location_id = location_id if location_type in ["to", "both"] else None
        
        shipments = await shipment_service.get_shipments(
            skip=skip,
            limit=limit,
            from_location_id=from_location_id,
            to_location_id=to_location_id
        )
        
        return {
            "location_id": location_id,
            "location_type": location_type,
            "count": len(shipments),
            "shipments": shipments
        }
    except Exception as e:
        logger.error(f"Error getting shipments by location: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shipments by location"
        )

@router.post("/{shipment_id}/tracking/update")
async def add_tracking_update(
    shipment_id: int,
    location: Optional[str] = Body(None, description="Location description"),
    latitude: Optional[float] = Body(None, description="GPS latitude"),
    longitude: Optional[float] = Body(None, description="GPS longitude"),
    notes: Optional[str] = Body(None, description="Additional notes"),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Add a manual tracking update to a shipment"""
    try:
        shipment_service = ShipmentService(session)
        shipment = await shipment_service.get_shipment(shipment_id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        # Create tracking update
        await shipment_service._create_tracking_update(
            shipment_id=shipment_id,
            status=shipment.status,
            notes=notes or f"Manual tracking update by user {current_user.id}",
            user_id=current_user.id,
            location=location,
            latitude=latitude,
            longitude=longitude
        )
        
        return {
            "message": "Tracking update added successfully",
            "shipment_id": shipment_id,
            "location": location,
            "coordinates": {"latitude": latitude, "longitude": longitude} if latitude and longitude else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding tracking update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add tracking update"
        )

@router.get("/dashboard/summary")
async def get_logistics_dashboard_summary(
    session: AsyncSession = Depends(get_async_session)
):
    """Get logistics dashboard summary with key metrics"""
    try:
        shipment_service = ShipmentService(session)
        
        # Get statistics for different time periods
        daily_stats = await shipment_service.get_shipment_statistics(1)
        weekly_stats = await shipment_service.get_shipment_statistics(7)
        monthly_stats = await shipment_service.get_shipment_statistics(30)
        
        # Get current status counts
        active_shipments = await shipment_service.get_shipments(
            limit=1000,
            status=None
        )
        
        status_counts = {}
        for status in ShipmentStatus:
            count = len([s for s in active_shipments if s.status == status])
            status_counts[status.value] = count
        
        return {
            "daily_stats": daily_stats,
            "weekly_stats": weekly_stats,
            "monthly_stats": monthly_stats,
            "status_distribution": status_counts,
            "total_active_shipments": len(active_shipments),
            "summary": {
                "pending_pickup": status_counts.get("READY_FOR_PICKUP", 0),
                "in_transit": status_counts.get("IN_TRANSIT", 0) + status_counts.get("PICKED_UP", 0) + status_counts.get("OUT_FOR_DELIVERY", 0),
                "delivered_today": daily_stats.get("completed_shipments", 0),
                "completion_rate_monthly": monthly_stats.get("completion_rate", 0)
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard summary"
        )