import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.organization.location import Location
from app.models.hr.employee import Employee
from app.schemas.organization.location_schema import LocationCreate, LocationUpdate
from app.services.auth.user_service import UserService

logger = logging.getLogger(__name__)


class LocationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)

    # ---------- Getters ----------
    async def get_location(self, location_id: int) -> Optional[Location]:
        try:
            result = await self.session.execute(
                select(Location).where(
                    Location.id == location_id,
                    Location.is_active == True
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting location {location_id}: {e}")
            return None

    # ---------- Create / Update / Delete ----------
    async def create_location(self, data: LocationCreate, current_user_id: int) -> Location:
        try:
            location = Location(**data.dict())
            self.session.add(location)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(location)
            logger.info(f"Location created: {location.name} ({location.location_type}) by user {current_user_id}")
            return location
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating location: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating location")

    async def update_location(self, location_id: int, data: LocationUpdate, current_user_id: int) -> Location:
        try:
            location = await self.get_location(location_id)
            if not location:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

            for field, value in data.dict(exclude_unset=True).items():
                setattr(location, field, value)

            # if you track timestamps
            if hasattr(location, "updated_at"):
                location.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(location)
            logger.info(f"Location updated: {location.name} by user {current_user_id}")
            return location
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating location {location_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating location")

    async def delete_location(self, location_id: int, current_user_id: int) -> bool:
        try:
            location = await self.get_location(location_id)
            if not location:
                return False

            # block delete if active employees exist
            count_result = await self.session.execute(
                select(func.count()).select_from(Employee).where(
                    Employee.location_id == location_id,
                    Employee.is_active == True
                )
            )
            if int(count_result.scalar() or 0) > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete location. It has active employees"
                )

            location.is_active = False
            location.is_deleted = True
            if hasattr(location, "updated_at"):
                location.updated_at = datetime.utcnow()

            await self.session.commit()
            logger.info(f"Location deleted (soft): {location.name} by user {current_user_id}")
            return True
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting location {location_id}: {e}")
            return False

    # ---------- Listing & Counting ----------
    async def get_locations(
        self,
        page_index: int = 1,
        page_size: int = 100,
        location_type: Optional[str] = None,
        city: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get locations with pagination"""
        try:
            query = select(Location)
            if is_active is not None:
                query = query.where(Location.is_active == is_active)
            if location_type:
                query = query.where(Location.location_type == location_type)
            if city:
                query = query.where(Location.city.ilike(f"%{city}%"))
            if search:
                like = f"%{search}%"
                query = query.where(
                    or_(
                        Location.name.ilike(like),
                        Location.address.ilike(like),
                        Location.city.ilike(like)
                    )
                )

            # Location manager restriction
            role_name = await self.user_service.get_specific_role_name_by_user(user_id,"location_manager")
            if role_name:
                loc_res = await self.session.execute(
                        select(Location).where(Location.manager_id == user_id)
                    )
                loc = loc_res.scalar_one_or_none()
                if loc:
                    query = query.where(Location.id == loc.id)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0
            
            # Calculate offset and get data
            skip = (page_index - 1) * page_size
            result = await self.session.execute(query.offset(skip).limit(page_size))
            locations = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": locations
            }
        except Exception as e:
            logger.error(f"Error getting locations: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }
    
    async def count_locations(
        self,
        location_type: Optional[str] = None,
        city: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> int:
        try:
            query = select(func.count(Location.id))
            if is_active is not None:
                query = query.where(Location.is_active == is_active)
            if location_type:
                query = query.where(Location.location_type == location_type)
            if city:
                query = query.where(Location.city.ilike(f"%{city}%"))
            if search:
                like = f"%{search}%"
                query = query.where(
                    or_(
                        Location.name.ilike(like),
                        Location.address.ilike(like),
                        Location.city.ilike(like)
                    )
                )
            result = await self.session.execute(query)
            return int(result.scalar() or 0)
        except Exception as e:
            logger.error(f"Error counting locations: {e}")
            return 0

    # ---------- Quick helpers ----------
    async def get_branches(self) -> List[Location]:
        try:
            result = await self.session.execute(
                select(Location).where(
                    Location.location_type == "BRANCH",
                    Location.is_active == True
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting branches: {e}")
            return []

    async def get_warehouses(self) -> List[Location]:
        try:
            result = await self.session.execute(
                select(Location).where(
                    Location.location_type == "WAREHOUSE",
                    Location.is_active == True
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting warehouses: {e}")
            return []
