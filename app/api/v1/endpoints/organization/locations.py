from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.organization.location_service import LocationService
from app.schemas.organization.location_schema import LocationCreate, LocationUpdate, LocationResponse
from app.models.auth.user import User

router = APIRouter()

@router.post("/", response_model=LocationResponse)
async def create_location(
    location: LocationCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("location", "create"))
):
    """Create a new location"""
    service = LocationService(session)
    return await service.create_location(location, current_user.id)

@router.get("/", response_model=PaginatedResponse[LocationResponse])
async def get_locations(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    location_type: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all locations with filtering"""
    service = LocationService(session)
    return await service.get_locations(
        page_index=page_index, 
        page_size=page_size, 
        location_type=location_type, 
        city=city, 
        is_active=is_active, 
        search=search
    )

@router.get("/branches", response_model=List[LocationResponse])
async def get_branches(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all active branches"""
    service = LocationService(session)
    return await service.get_branches()

@router.get("/warehouses", response_model=List[LocationResponse])
async def get_warehouses(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all active warehouses"""
    service = LocationService(session)
    return await service.get_warehouses()

@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get location by ID"""
    service = LocationService(session)
    location = await service.get_location(location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return location

@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    location: LocationUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("location", "update"))
):
    """Update location"""
    service = LocationService(session)
    return await service.update_location(location_id, location, current_user.id)

@router.delete("/{location_id}")
async def delete_location(
    location_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("location", "delete"))
):
    """Delete location"""
    service = LocationService(session)
    result = await service.delete_location(location_id, current_user.id)
    return {"message": "Location deleted successfully", "success": result}