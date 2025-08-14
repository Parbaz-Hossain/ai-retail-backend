from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_
from app.models.organization.location import Location
from app.models.hr.employee import Employee
from app.schemas.organization.location_schema import LocationCreate, LocationUpdate, LocationResponse
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger

class LocationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_location(self, location_data: LocationCreate, current_user_id: int) -> Location:
        """Create a new location (branch or warehouse)"""
        try:
            location = Location(**location_data.dict())
            
            self.db.add(location)
            self.db.commit()
            self.db.refresh(location)
            
            logger.info(f"Location created: {location.name} ({location.location_type}) by user {current_user_id}")
            return location
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating location: {str(e)}")
            raise

    async def get_location(self, location_id: int) -> Location:
        """Get location by ID"""
        location = self.db.query(Location).filter(
            Location.id == location_id,
            Location.is_active == True
        ).first()
        
        if not location:
            raise NotFoundError(f"Location with ID {location_id} not found")
        
        return location

    async def get_locations(
        self,
        skip: int = 0,
        limit: int = 100,
        location_type: Optional[str] = None,
        city: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> List[Location]:
        """Get all locations with filtering"""
        query = self.db.query(Location)
        
        if is_active is not None:
            query = query.filter(Location.is_active == is_active)
        
        if location_type:
            query = query.filter(Location.location_type == location_type)
        
        if city:
            query = query.filter(Location.city.ilike(f"%{city}%"))
        
        if search:
            query = query.filter(
                or_(
                    Location.name.ilike(f"%{search}%"),
                    Location.address.ilike(f"%{search}%"),
                    Location.city.ilike(f"%{search}%")
                )
            )
        
        return query.offset(skip).limit(limit).all()

    async def update_location(
        self,
        location_id: int,
        location_data: LocationUpdate,
        current_user_id: int
    ) -> Location:
        """Update location"""
        location = await self.get_location(location_id)
        
        update_data = location_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(location, field, value)

        self.db.commit()
        self.db.refresh(location)
        
        logger.info(f"Location updated: {location.name} by user {current_user_id}")
        return location

    async def delete_location(self, location_id: int, current_user_id: int) -> bool:
        """Soft delete location"""
        location = await self.get_location(location_id)
        
        # Check if location has active employees
        active_employees = self.db.query(Employee).filter(
            Employee.location_id == location_id,
            Employee.is_active == True
        ).count()
        
        if active_employees > 0:
            raise ValidationError(f"Cannot delete location. It has {active_employees} active employees")

        location.is_active = False
        self.db.commit()
        
        logger.info(f"Location deleted: {location.name} by user {current_user_id}")
        return True

    async def get_branches(self) -> List[Location]:
        """Get all active branches"""
        return self.db.query(Location).filter(
            Location.location_type == "BRANCH",
            Location.is_active == True
        ).all()

    async def get_warehouses(self) -> List[Location]:
        """Get all active warehouses"""
        return self.db.query(Location).filter(
            Location.location_type == "WAREHOUSE",
            Location.is_active == True
        ).all()