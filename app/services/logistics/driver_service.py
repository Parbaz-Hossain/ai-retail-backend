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
            await self.session.refresh(driver)

            logger.info(f"Driver created successfully with ID: {driver.id}")
            return driver

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
                .options(selectinload(Driver.employee))
                .where(Driver.id == driver_id, Driver.is_deleted == False)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting driver {driver_id}: {str(e)}")
            return None

    async def get_drivers(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get list of drivers with filters"""
        try:
            query = select(Driver).options(selectinload(Driver.employee))
            
            # Apply filters
            conditions = [Driver.is_deleted == False]
            
            if search:
                conditions.append(
                    or_(
                        Driver.license_number.icontains(search),
                        Driver.phone.icontains(search)
                    )
                )
            
            if is_available is not None:
                conditions.append(Driver.is_available == is_available)
                
            if is_active is not None:
                conditions.append(Driver.is_active == is_active)
            
            query = query.where(and_(*conditions))
            query = query.offset(skip).limit(limit).order_by(Driver.created_at.desc())

            # Get total count
            total = await self.session.scalar(select(func.count()).select_from(Driver).where(and_(*conditions)))            
            result = await self.session.execute(query)
            drivers = result.scalars().all()

            return {
                "data": drivers,
                "total": total,
                "skip": skip,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error getting drivers: {str(e)}")
            return []

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
                .options(selectinload(Driver.employee))
                .where(
                    Driver.is_available == True,
                    Driver.is_active == True,
                    Driver.is_deleted == False
                )
                .order_by(Driver.employee.has(Employee.first_name))
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

    async def get_driver_shipments(self, driver_id: int, limit: int = 10) -> List[Shipment]:
        """Get recent shipments for a driver"""
        try:
            result = await self.session.execute(
                select(Shipment)
                .where(Shipment.driver_id == driver_id)
                .order_by(Shipment.created_at.desc())
                .limit(limit)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting driver shipments: {str(e)}")
            return []

    async def check_license_expiry(self, days_ahead: int = 30) -> List[Driver]:
        """Get drivers with licenses expiring soon"""
        try:
            expiry_date = date.today() + timedelta(days=days_ahead)
            
            result = await self.session.execute(
                select(Driver)
                .options(selectinload(Driver.employee))
                .where(
                    Driver.license_expiry <= expiry_date,
                    Driver.license_expiry >= date.today(),
                    Driver.is_active == True,
                    Driver.is_deleted == False
                )
                .order_by(Driver.license_expiry)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error checking license expiry: {str(e)}")
            return []