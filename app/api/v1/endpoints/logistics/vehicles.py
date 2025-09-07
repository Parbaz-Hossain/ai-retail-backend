import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.schemas.common.pagination import PaginatedResponse
from app.schemas.logistics.vehicle_schema import VehicleCreate, VehicleUpdate, VehicleResponse
from app.services.logistics.vehicle_service import VehicleService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new vehicle"""
    try:
        vehicle_service = VehicleService(session)
        vehicle = await vehicle_service.create_vehicle(vehicle_data, current_user.id)
        return vehicle
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vehicle: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create vehicle"
        )

@router.get("/", response_model=PaginatedResponse[VehicleResponse])
async def get_vehicles(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    is_available: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get list of vehicles with optional filters"""
    try:
        vehicle_service = VehicleService(session)
        vehicles = await vehicle_service.get_vehicles(
            page_index=page_index,
            page_size=page_size,
            search=search,
            vehicle_type=vehicle_type,
            is_available=is_available,
            is_active=is_active
        )
        return vehicles
    except Exception as e:
        logger.error(f"Error getting vehicles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vehicles"
        )
    
@router.get("/available", response_model=List[VehicleResponse])
async def get_available_vehicles(
    min_capacity_weight: Optional[float] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all available vehicles"""
    try:
        vehicle_service = VehicleService(session)
        vehicles = await vehicle_service.get_available_vehicles(min_capacity_weight)
        return vehicles
    except Exception as e:
        logger.error(f"Error getting available vehicles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available vehicles"
        )

@router.get("/maintenance-due", response_model=List[VehicleResponse])
async def get_vehicles_needing_maintenance(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get vehicles that need maintenance"""
    try:
        vehicle_service = VehicleService(session)
        vehicles = await vehicle_service.get_vehicles_needing_maintenance()
        return vehicles
    except Exception as e:
        logger.error(f"Error getting vehicles needing maintenance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vehicles needing maintenance"
        )

@router.get("/documents-expiry", response_model=List[VehicleResponse])
async def get_vehicles_documents_expiry(
    days_ahead: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get vehicles with documents expiring soon"""
    try:
        vehicle_service = VehicleService(session)
        vehicles = await vehicle_service.check_vehicle_documents_expiry(days_ahead)
        return vehicles
    except Exception as e:
        logger.error(f"Error checking vehicle documents expiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check vehicle documents expiry"
        )

@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get vehicle by ID"""
    try:
        vehicle_service = VehicleService(session)
        vehicle = await vehicle_service.get_vehicle(vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        return vehicle
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vehicle {vehicle_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vehicle"
        )

@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: int,
    vehicle_data: VehicleUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update vehicle"""
    try:
        vehicle_service = VehicleService(session)
        vehicle = await vehicle_service.update_vehicle(vehicle_id, vehicle_data, current_user.id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        return vehicle
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vehicle {vehicle_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update vehicle"
        )

@router.delete("/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete vehicle"""
    try:
        vehicle_service = VehicleService(session)
        success = await vehicle_service.delete_vehicle(vehicle_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        return {"message": "Vehicle deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vehicle {vehicle_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete vehicle"
        )

@router.patch("/{vehicle_id}/availability")
async def update_vehicle_availability(
    vehicle_id: int,
    is_available: bool,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update vehicle availability status"""
    try:
        vehicle_service = VehicleService(session)
        success = await vehicle_service.update_vehicle_availability(
            vehicle_id, is_available, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        return {
            "message": f"Vehicle availability updated to {'available' if is_available else 'unavailable'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vehicle availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update vehicle availability"
        )

@router.patch("/{vehicle_id}/mileage")
async def update_vehicle_mileage(
    vehicle_id: int,
    new_mileage: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update vehicle mileage"""
    try:
        vehicle_service = VehicleService(session)
        success = await vehicle_service.update_vehicle_mileage(
            vehicle_id, new_mileage, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        return {"message": f"Vehicle mileage updated to {new_mileage}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vehicle mileage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update vehicle mileage"
        )

@router.get("/{vehicle_id}/utilization")
async def get_vehicle_utilization_stats(
    vehicle_id: int,
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get vehicle utilization statistics"""
    try:
        vehicle_service = VehicleService(session)
        stats = await vehicle_service.get_vehicle_utilization_stats(vehicle_id, days)
        return stats
    except Exception as e:
        logger.error(f"Error getting vehicle utilization stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vehicle utilization statistics"
        )