import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.schemas.common.pagination import PaginatedResponse
from app.schemas.logistics.driver_schema import DriverCreate, DriverUpdate, DriverResponse
from app.services.logistics.driver_service import DriverService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def create_driver(
    driver_data: DriverCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new driver"""
    try:
        driver_service = DriverService(session)
        driver = await driver_service.create_driver(driver_data, current_user.id)
        return driver
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create driver"
        )

@router.get("/", response_model=PaginatedResponse[DriverResponse])
async def get_drivers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    is_available: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get list of drivers with optional filters"""
    try:
        driver_service = DriverService(session)
        drivers = await driver_service.get_drivers(
            skip=skip,
            limit=limit,
            search=search,
            is_available=is_available,
            is_active=is_active
        )
        return drivers
    except Exception as e:
        logger.error(f"Error getting drivers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve drivers"
        )

@router.get("/available", response_model=List[DriverResponse])
async def get_available_drivers(
    session: AsyncSession = Depends(get_async_session)
):
    """Get all available drivers"""
    try:
        driver_service = DriverService(session)
        drivers = await driver_service.get_available_drivers()
        return drivers
    except Exception as e:
        logger.error(f"Error getting available drivers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available drivers"
        )

@router.get("/license-expiry", response_model=List[DriverResponse])
async def get_drivers_license_expiry(
    days_ahead: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session)
):
    """Get drivers with licenses expiring soon"""
    try:
        driver_service = DriverService(session)
        drivers = await driver_service.check_license_expiry(days_ahead)
        return drivers
    except Exception as e:
        logger.error(f"Error checking license expiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check license expiry"
        )

@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get driver by ID"""
    try:
        driver_service = DriverService(session)
        driver = await driver_service.get_driver(driver_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        return driver
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver {driver_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve driver"
        )

@router.put("/{driver_id}", response_model=DriverResponse)
async def update_driver(
    driver_id: int,
    driver_data: DriverUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update driver"""
    try:
        driver_service = DriverService(session)
        driver = await driver_service.update_driver(driver_id, driver_data, current_user.id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        return driver
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver {driver_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update driver"
        )

@router.delete("/{driver_id}")
async def delete_driver(
    driver_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete driver"""
    try:
        driver_service = DriverService(session)
        success = await driver_service.delete_driver(driver_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        return {"message": "Driver deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting driver {driver_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete driver"
        )

@router.patch("/{driver_id}/availability")
async def update_driver_availability(
    driver_id: int,
    is_available: bool,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update driver availability status"""
    try:
        driver_service = DriverService(session)
        success = await driver_service.update_driver_availability(
            driver_id, is_available, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        return {
            "message": f"Driver availability updated to {'available' if is_available else 'unavailable'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update driver availability"
        )

@router.get("/{driver_id}/shipments")
async def get_driver_shipments(
    driver_id: int,
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session)
):
    """Get recent shipments for a driver"""
    try:
        driver_service = DriverService(session)
        shipments = await driver_service.get_driver_shipments(driver_id, limit)
        return shipments
    except Exception as e:
        logger.error(f"Error getting driver shipments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve driver shipments"
        )