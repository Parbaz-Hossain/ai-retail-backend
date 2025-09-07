# app/services/logistics/driver_service.py
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.models.logistics.driver import Driver
from app.models.hr.employee import Employee
from app.models.logistics.shipment import Shipment
from app.models.logistics.shipment_item import ShipmentItem
from app.schemas.common.pagination import PaginatedResponse
from app.schemas.logistics.driver_schema import DriverCreate, DriverUpdate, DriverResponse

logger = logging.getLogger(__name__)

class DriverService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_driver(self, driver_data: DriverCreate, user_id: int) -> Driver:
        """Create a new driver"""
        try:
            # Check if employee exists
            result = await self.session.execute(
                select(Employee).where(Employee.id == driver_data.employee_id)
            )
            employee = result.scalar_one_or_none()
            if not employee:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee not found"
                )

            # Check if driver already exists for this employee
            result = await self.session.execute(
                select(Driver).where(Driver.employee_id == driver_data.employee_id)
            )
            existing_driver = result.scalar_one_or_none()
            if existing_driver:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Driver record already exists for this employee"
                )

            # Check if license number is unique
            if driver_data.license_number:
                result = await self.session.execute(
                    select(Driver).where(Driver.license_number == driver_data.license_number)
                )
                existing_license = result.scalar_one_or_none()
                if existing_license:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="License number already exists"
                    )

            # Create driver
            driver = Driver(**driver_data.dict())
            driver.created_by = user_id
            self.session.add(driver)
            await self.session.commit()
            result = await self.session.execute(
                select(Driver)
                 .options(
                    selectinload(Driver.employee).selectinload(Employee.department),
                    selectinload(Driver.employee).selectinload(Employee.location),
                )
                .where(Driver.id == driver.id)
            )
            driver = result.scalar_one()
            logger.info(f"Driver created successfully with ID: {driver.id}")
            return DriverResponse.model_validate(driver, from_attributes=True)

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating driver: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create driver"
            )

    async def get_driver(self, driver_id: int) -> Optional[Driver]:
        """Get driver by ID"""
        try:
            result = await self.session.execute(
                select(Driver)
                 .options(
                    selectinload(Driver.employee).selectinload(Employee.department),
                    selectinload(Driver.employee).selectinload(Employee.location),
                )
                .where(Driver.id == driver_id, Driver.is_deleted == False)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting driver {driver_id}: {str(e)}")
            return None

    async def get_drivers(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get list of drivers with filters"""
        try:
            conditions = [Driver.is_deleted == False]

            if search:
                conditions.append(
                    or_(
                        Driver.license_number.ilike(f"%{search}%"),
                        Driver.phone.ilike(f"%{search}%")
                    )
                )

            if is_available is not None:
                conditions.append(Driver.is_available == is_available)

            if is_active is not None:
                conditions.append(Driver.is_active == is_active)

            # Count total first
            total = await self.session.scalar(
                select(func.count()).select_from(Driver).where(and_(*conditions))
            )

            # Calculate offset
            skip = (page_index - 1) * page_size

            # Build query with eager loads
            query = (
                select(Driver)
                .options(
                    selectinload(Driver.employee).selectinload(Employee.department),
                    selectinload(Driver.employee).selectinload(Employee.location),
                )
                .where(and_(*conditions))
                .offset(skip)
                .limit(page_size)
                .order_by(Driver.created_at.desc())
            )

            result = await self.session.execute(query)
            drivers = result.scalars().all()

            # Convert ORM → Pydantic
            driver_list = [
                DriverResponse.model_validate(d, from_attributes=True) for d in drivers
            ]

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": driver_list
            }

        except Exception as e:
            logger.error(f"Error getting drivers: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def update_driver(self, driver_id: int, driver_data: DriverUpdate, user_id: int) -> Optional[Driver]:
        """Update driver"""
        try:
            driver = await self.get_driver(driver_id)
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Driver not found"
                )

            # Check license number uniqueness if being updated
            if driver_data.license_number and driver_data.license_number != driver.license_number:
                result = await self.session.execute(
                    select(Driver).where(
                        Driver.license_number == driver_data.license_number,
                        Driver.id != driver_id
                    )
                )
                existing_license = result.scalar_one_or_none()
                if existing_license:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="License number already exists"
                    )

            # Update fields
            update_data = driver_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(driver, field, value)

            driver.updated_at = datetime.utcnow()
            driver.updated_by = user_id
            await self.session.commit()
            await self.session.refresh(driver)

            logger.info(f"Driver {driver_id} updated successfully")
            return driver

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating driver {driver_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update driver"
            )

    async def delete_driver(self, driver_id: int, user_id: int) -> bool:
        """Soft delete driver"""
        try:
            driver = await self.get_driver(driver_id)
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Driver not found"
                )

            # Check if driver has active shipments
            result = await self.session.execute(
                select(Shipment).where(
                    Shipment.driver_id == driver_id,
                    Shipment.status.in_(["READY_FOR_PICKUP", "PICKED_UP", "OUT_FOR_DELIVERY", "IN_TRANSIT"])
                )
            )
            active_shipments = result.scalars().all()
            if active_shipments:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete driver with active shipments"
                )

            driver.is_active = False
            driver.is_deleted = True
            driver.is_available = False
            await self.session.commit()

            logger.info(f"Driver {driver_id} deleted successfully")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting driver {driver_id}: {str(e)}")
            return False

    async def get_available_drivers(self) -> List[Driver]:
        """Get all available drivers"""
        try:
            result = await self.session.execute(
                select(Driver)
                .options(
                    selectinload(Driver.employee).selectinload(Employee.department),
                    selectinload(Driver.employee).selectinload(Employee.location),
                )
                .where(
                    Driver.is_available == True,
                    Driver.is_active == True,
                    Driver.is_deleted == False
                )
                .order_by(Driver.created_at.desc())
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting available drivers: {str(e)}")
            return []

    async def update_driver_availability(self, driver_id: int, is_available: bool, user_id: int) -> bool:
        """Update driver availability status"""
        try:
            driver = await self.get_driver(driver_id)
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Driver not found"
                )

            driver.is_available = is_available
            driver.updated_at = datetime.utcnow()
            await self.session.commit()

            logger.info(f"Driver {driver_id} availability updated to {is_available}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating driver availability: {str(e)}")
            return False

    async def get_driver_shipments(
        self, 
        driver_id: int, 
        page_index: int = 1, 
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get shipments for a driver with pagination"""
        try:
            # Base query
            query = select(Shipment).options(
                selectinload(Shipment.from_location),
                selectinload(Shipment.to_location),
                selectinload(Shipment.vehicle),
                selectinload(Shipment.driver)
                    .selectinload(Driver.employee)
                    .options(
                        selectinload(Employee.location),  
                        selectinload(Employee.department)
                    ),
                selectinload(Shipment.items).selectinload(ShipmentItem.item)
            ).where(Shipment.driver_id == driver_id)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0

            # Calculate offset and get paginated data
            skip = (page_index - 1) * page_size
            query = query.order_by(Shipment.created_at.desc()).offset(skip).limit(page_size)
            result = await self.session.execute(query)
            shipments = result.scalars().all()

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": shipments
            }

        except Exception as e:
            logger.error(f"Error getting driver shipments: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }


    async def get_license_expiring_soon(self, days_ahead: int = 30) -> List[Driver]:
        """Return drivers with license_expiry between today and today+days_ahead (inclusive)."""
        try:
            # keep it reasonable and predictable
            days = max(1, min(int(days_ahead), 365))
            end_date = date.today() + timedelta(days=days)

            stmt = (
                select(Driver)
                .options(
                    selectinload(Driver.employee).selectinload(Employee.department),
                    selectinload(Driver.employee).selectinload(Employee.location),
                )
                .where(
                    Driver.license_expiry.is_not(None),
                    # if license_expiry is DATE, this is fine; if TIMESTAMP, func.date() makes it safe
                    func.date(Driver.license_expiry) >= func.current_date(),
                    func.date(Driver.license_expiry) <= end_date,
                    Driver.is_active.is_(True),
                    Driver.is_deleted.is_(False),
                )
                .order_by(Driver.license_expiry.asc(), Driver.id.asc())
            )

            result = await self.session.execute(stmt)
            # unique() guards against duplicates when eager-loading collections
            return list(result.scalars().unique().all())

        except Exception as e:
            logger.error(f"Error checking license expiry: {e}")
            return []