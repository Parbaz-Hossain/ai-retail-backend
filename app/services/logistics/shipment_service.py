# app/services/logistics/shipment_service.py
import logging
import random
import string
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from app.models.hr.employee import Employee
from app.models.logistics.shipment import Shipment
from app.models.logistics.shipment_item import ShipmentItem
from app.models.logistics.shipment_tracking import ShipmentTracking
from app.models.logistics.driver import Driver
from app.models.logistics.vehicle import Vehicle
from app.models.organization.location import Location
from app.models.inventory.item import Item
from app.models.shared.enums import ShipmentStatus
from app.schemas.logistics.shipment_schema import (
    ShipmentCreate, ShipmentUpdate, ShipmentResponse,
    ShipmentItemCreate, OTPVerificationRequest
)

logger = logging.getLogger(__name__)

class ShipmentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def generate_shipment_number(self) -> str:
        """Generate unique shipment number"""
        prefix = "SHP"
        timestamp = datetime.now().strftime("%Y%m%d")
        random_suffix = ''.join(random.choices(string.digits, k=4))
        return f"{prefix}-{timestamp}-{random_suffix}"

    def generate_otp(self) -> str:
        """Generate 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))

    async def create_shipment(self, shipment_data: ShipmentCreate, user_id: int) -> Shipment:
        """Create a new shipment"""
        try:
            # Validate locations
            from_location = await self._validate_location(shipment_data.from_location_id)
            to_location = await self._validate_location(shipment_data.to_location_id)
            
            if shipment_data.from_location_id == shipment_data.to_location_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="From and To locations cannot be the same"
                )

            # Validate driver if provided
            if shipment_data.driver_id:
                await self._validate_driver(shipment_data.driver_id)

            # Validate vehicle if provided
            if shipment_data.vehicle_id:
                await self._validate_vehicle(shipment_data.vehicle_id)

            # Generate shipment number and OTPs
            shipment_number = self.generate_shipment_number()
            
            # Check uniqueness
            while await self._shipment_number_exists(shipment_number):
                shipment_number = self.generate_shipment_number()

            # Create shipment
            shipment_dict = shipment_data.dict(exclude={'items'})
            shipment = Shipment(
                **shipment_dict,
                shipment_number=shipment_number,
                pickup_otp=self.generate_otp(),
                delivery_otp=self.generate_otp(),
                created_by=user_id
            )
            
            self.session.add(shipment)
            await self.session.flush()

            # Add shipment items
            if shipment_data.items:
                total_weight = 0
                total_volume = 0
                
                for item_data in shipment_data.items:
                    # Validate item
                    await self._validate_item(item_data.item_id)
                    
                    shipment_item = ShipmentItem(
                        shipment_id=shipment.id,
                        **item_data.dict()
                    )
                    self.session.add(shipment_item)
                    
                    # Calculate totals
                    if item_data.weight:
                        total_weight += float(item_data.weight)
                    if item_data.volume:
                        total_volume += float(item_data.volume)

                shipment.total_weight = total_weight
                shipment.total_volume = total_volume

            await self.session.commit()
            result = await self.session.execute(
                select(Shipment)
                .options(
                    selectinload(Shipment.from_location),
                    selectinload(Shipment.to_location),
                    selectinload(Shipment.driver)
                        .selectinload(Driver.employee)
                        .selectinload(Employee.department),  
                    selectinload(Shipment.vehicle),
                    selectinload(Shipment.items)
                        .selectinload(ShipmentItem.item)     
                )
                .where(Shipment.id == shipment.id)
            )
            shipment = result.scalar_one()

            # Create initial tracking record
            await self._create_tracking_update(
                shipment.id,
                ShipmentStatus.READY_FOR_PICKUP,
                f"Shipment created and ready for pickup from {from_location.name}",
                user_id,
                from_location.name
            )

            logger.info(f"Shipment created successfully: {shipment.shipment_number}")
            return shipment

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating shipment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create shipment"
            )

    async def get_shipment(self, shipment_id: int) -> Optional[Shipment]:
        """Get shipment by ID with all related data"""
        try:
            result = await self.session.execute(
                select(Shipment)
                .options(
                    selectinload(Shipment.from_location),
                    selectinload(Shipment.to_location),
                    selectinload(Shipment.driver)
                        .selectinload(Driver.employee)
                        .selectinload(Employee.department),
                    selectinload(Shipment.vehicle),
                    selectinload(Shipment.items).selectinload(ShipmentItem.item),
                    selectinload(Shipment.tracking_updates)
                )
                .where(Shipment.id == shipment_id, Shipment.is_deleted == False)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting shipment {shipment_id}: {str(e)}")
            return None

    async def get_shipments(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        status: Optional[ShipmentStatus] = None,
        from_location_id: Optional[int] = None,
        to_location_id: Optional[int] = None,
        driver_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get list of shipments with filters"""
        try:
            query = select(Shipment).options(
                selectinload(Shipment.from_location),
                selectinload(Shipment.to_location),
                selectinload(Shipment.driver)
                    .selectinload(Driver.employee)
                    .selectinload(Employee.department),
                selectinload(Shipment.vehicle),
                selectinload(Shipment.items).selectinload(ShipmentItem.item)
            )
            
            # Apply filters
            conditions = [Shipment.is_deleted == False]
            
            if search:
                conditions.append(
                    or_(
                        Shipment.shipment_number.icontains(search),
                        Shipment.reference_type.icontains(search)
                    )
                )
            
            if status:
                conditions.append(Shipment.status == status)
                
            if from_location_id:
                conditions.append(Shipment.from_location_id == from_location_id)
                
            if to_location_id:
                conditions.append(Shipment.to_location_id == to_location_id)
                
            if driver_id:
                conditions.append(Shipment.driver_id == driver_id)
                
            if vehicle_id:
                conditions.append(Shipment.vehicle_id == vehicle_id)
                
            if date_from:
                conditions.append(Shipment.shipment_date >= date_from)
                
            if date_to:
                conditions.append(Shipment.shipment_date <= date_to)
            
            query = query.where(and_(*conditions))
            query = query.offset(skip).limit(limit).order_by(Shipment.created_at.desc())
            
            result = await self.session.execute(query)
            shipments = result.scalars().all()
            total_count = await self.session.execute(
                select(func.count(Shipment.id)).where(and_(*conditions))
            )

            return {
                "data": shipments,
                "total": total_count.scalar() or 0,
                "skip": skip,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error getting shipments: {str(e)}")
            return []

    async def update_shipment(self, shipment_id: int, shipment_data: ShipmentUpdate, user_id: int) -> Optional[Shipment]:
        """Update shipment"""
        try:
            shipment = await self.get_shipment(shipment_id)
            if not shipment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Shipment not found"
                )

            # Check if shipment can be updated
            if shipment.status in [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot update delivered or cancelled shipment"
                )

            # Validate new driver if provided
            if shipment_data.driver_id and shipment_data.driver_id != shipment.driver_id:
                await self._validate_driver(shipment_data.driver_id)

            # Validate new vehicle if provided
            if shipment_data.vehicle_id and shipment_data.vehicle_id != shipment.vehicle_id:
                await self._validate_vehicle(shipment_data.vehicle_id)

            # Update fields
            update_data = shipment_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(shipment, field, value)

            shipment.updated_at = datetime.utcnow()
            shipment.updated_by = user_id
            await self.session.commit()
            result = await self.session.execute(
                select(Shipment)
                .options(
                    selectinload(Shipment.from_location),
                    selectinload(Shipment.to_location),
                    selectinload(Shipment.driver)
                        .selectinload(Driver.employee)
                        .selectinload(Employee.department),  
                    selectinload(Shipment.driver)
                        .selectinload(Driver.employee)
                        .selectinload(Employee.location),
                    selectinload(Shipment.vehicle),
                    selectinload(Shipment.items)
                        .selectinload(ShipmentItem.item)     
                )
                .where(Shipment.id == shipment.id)
            )
            shipment = result.scalar_one()

            logger.info(f"Shipment {shipment_id} updated successfully")
            return shipment

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating shipment {shipment_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update shipment"
            )

    async def assign_driver_vehicle(self, shipment_id: int, driver_id: Optional[int], vehicle_id: Optional[int], user_id: int) -> bool:
        """Assign driver and vehicle to shipment"""
        try:
            shipment = await self.get_shipment(shipment_id)
            if not shipment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Shipment not found"
                )

            if shipment.status not in [ShipmentStatus.READY_FOR_PICKUP, ShipmentStatus.PICKED_UP]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only assign driver/vehicle to ready or picked up shipments"
                )

            # Validate and assign driver
            if driver_id:
                driver = await self._validate_driver(driver_id)
                if not driver.is_available:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Driver is not available"
                    )
                shipment.driver_id = driver_id

            # Validate and assign vehicle
            if vehicle_id:
                vehicle = await self._validate_vehicle(vehicle_id)
                if not vehicle.is_available:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vehicle is not available"
                    )
                shipment.vehicle_id = vehicle_id

            await self.session.commit()
            
            # Create tracking update
            await self._create_tracking_update(
                shipment_id,
                shipment.status,
                f"Driver and/or vehicle assigned to shipment",
                user_id
            )

            logger.info(f"Driver/Vehicle assigned to shipment {shipment_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error assigning driver/vehicle: {str(e)}")
            return False

    async def verify_pickup_otp(self, shipment_id: int, otp: str, user_id: int) -> bool:
        """Verify pickup OTP and update shipment status"""
        try:
            shipment = await self.get_shipment(shipment_id)
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

            if shipment.pickup_otp != otp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid OTP"
                )

            # Update shipment status
            shipment.status = ShipmentStatus.PICKED_UP
            shipment.pickup_otp_verified = True
            shipment.pickup_time = datetime.utcnow()
            shipment.updated_at = datetime.utcnow()

            # Mark driver and vehicle as unavailable
            if shipment.driver_id:
                await self._update_driver_availability(shipment.driver_id, False)
            if shipment.vehicle_id:
                await self._update_vehicle_availability(shipment.vehicle_id, False)

            await self.session.commit()

            # Create tracking update
            await self._create_tracking_update(
                shipment_id,
                ShipmentStatus.PICKED_UP,
                f"Shipment picked up from {shipment.from_location.name}",
                user_id,
                shipment.from_location.name
            )

            logger.info(f"Pickup OTP verified for shipment {shipment_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error verifying pickup OTP: {str(e)}")
            return False

    async def verify_delivery_otp(self, shipment_id: int, otp: str, user_id: int) -> bool:
        """Verify delivery OTP and complete shipment"""
        try:
            shipment = await self.get_shipment(shipment_id)
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

            if shipment.delivery_otp != otp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid OTP"
                )

            # Update shipment status
            shipment.status = ShipmentStatus.DELIVERED
            shipment.delivery_otp_verified = True
            shipment.delivery_time = datetime.utcnow()
            shipment.actual_delivery_date = datetime.utcnow()
            shipment.updated_at = datetime.utcnow()

            # Mark driver and vehicle as available
            if shipment.driver_id:
                await self._update_driver_availability(shipment.driver_id, True)
            if shipment.vehicle_id:
                await self._update_vehicle_availability(shipment.vehicle_id, True)

            await self.session.commit()

            # Create tracking update
            await self._create_tracking_update(
                shipment_id,
                ShipmentStatus.DELIVERED,
                f"Shipment delivered to {shipment.to_location.name}",
                user_id,
                shipment.to_location.name
            )

            logger.info(f"Delivery OTP verified for shipment {shipment_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error verifying delivery OTP: {str(e)}")
            return False

    async def update_shipment_status(self, shipment_id: int, status: ShipmentStatus, notes: Optional[str], user_id: int) -> bool:
        """Update shipment status"""
        try:
            shipment = await self.get_shipment(shipment_id)
            if not shipment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Shipment not found"
                )

            # Validate status transition
            if not self._is_valid_status_transition(shipment.status, status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status transition from {shipment.status} to {status}"
                )

            old_status = shipment.status
            shipment.status = status
            shipment.updated_at = datetime.utcnow()

            await self.session.commit()

            # Create tracking update
            await self._create_tracking_update(
                shipment_id,
                status,
                notes or f"Status updated from {old_status} to {status}",
                user_id
            )

            logger.info(f"Shipment {shipment_id} status updated to {status}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating shipment status: {str(e)}")
            return False

    async def cancel_shipment(self, shipment_id: int, reason: str, user_id: int) -> bool:
        """Cancel shipment"""
        try:
            shipment = await self.get_shipment(shipment_id)
            if not shipment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Shipment not found"
                )

            if shipment.status in [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot cancel delivered or already cancelled shipment"
                )

            shipment.status = ShipmentStatus.CANCELLED
            shipment.updated_at = datetime.utcnow()

            # Make driver and vehicle available if assigned
            if shipment.driver_id:
                await self._update_driver_availability(shipment.driver_id, True)
            if shipment.vehicle_id:
                await self._update_vehicle_availability(shipment.vehicle_id, True)

            await self.session.commit()

            # Create tracking update
            await self._create_tracking_update(
                shipment_id,
                ShipmentStatus.CANCELLED,
                f"Shipment cancelled. Reason: {reason}",
                user_id
            )

            logger.info(f"Shipment {shipment_id} cancelled")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cancelling shipment: {str(e)}")
            return False

    async def get_shipment_tracking(self, shipment_id: int) -> List[ShipmentTracking]:
        """Get shipment tracking history"""
        try:
            result = await self.session.execute(
                select(ShipmentTracking)
                .where(ShipmentTracking.shipment_id == shipment_id)
                .order_by(ShipmentTracking.timestamp.desc())
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting shipment tracking: {str(e)}")
            return []

    async def get_active_shipments_by_driver(self, driver_id: int) -> List[Shipment]:
        """Get active shipments for a driver"""
        try:
            result = await self.session.execute(
                select(Shipment)
                .options(
                     selectinload(Shipment.from_location),
                     selectinload(Shipment.to_location),
                     selectinload(Shipment.driver)
                        .selectinload(Driver.employee)
                        .selectinload(Employee.department),
                     selectinload(Shipment.vehicle),
                     selectinload(Shipment.items).selectinload(ShipmentItem.item)
                )
                .where(
                    Shipment.driver_id == driver_id,
                    Shipment.status.in_([
                        ShipmentStatus.READY_FOR_PICKUP,
                        ShipmentStatus.PICKED_UP,
                        ShipmentStatus.OUT_FOR_DELIVERY,
                        ShipmentStatus.IN_TRANSIT
                    ])
                )
                .order_by(Shipment.expected_delivery_date)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting active shipments by driver: {str(e)}")
            return []

    async def get_shipment_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get shipment statistics"""
        try:
            start_date = date.today() - timedelta(days=days)
            
            # Total shipments
            result = await self.session.execute(
                select(func.count(Shipment.id))
                .where(Shipment.shipment_date >= start_date)
            )
            total_shipments = result.scalar() or 0
            
            # Completed shipments
            result = await self.session.execute(
                select(func.count(Shipment.id))
                .where(
                    Shipment.shipment_date >= start_date,
                    Shipment.status == ShipmentStatus.DELIVERED
                )
            )
            completed_shipments = result.scalar() or 0
            
            # In-transit shipments
            result = await self.session.execute(
                select(func.count(Shipment.id))
                .where(
                    Shipment.status.in_([
                        ShipmentStatus.READY_FOR_PICKUP,
                        ShipmentStatus.PICKED_UP,
                        ShipmentStatus.OUT_FOR_DELIVERY,
                        ShipmentStatus.IN_TRANSIT
                    ])
                )
            )
            in_transit_shipments = result.scalar() or 0
            
            # Average delivery time (in hours)
            result = await self.session.execute(
                select(func.avg(
                    func.extract('epoch', Shipment.actual_delivery_date - Shipment.pickup_time) / 3600
                )).where(
                    Shipment.shipment_date >= start_date,
                    Shipment.status == ShipmentStatus.DELIVERED,
                    Shipment.pickup_time.isnot(None),
                    Shipment.actual_delivery_date.isnot(None)
                )
            )
            avg_delivery_time = result.scalar() or 0
            
            return {
                "total_shipments": total_shipments,
                "completed_shipments": completed_shipments,
                "in_transit_shipments": in_transit_shipments,
                "cancelled_shipments": total_shipments - completed_shipments - in_transit_shipments,
                "completion_rate": (completed_shipments / total_shipments * 100) if total_shipments > 0 else 0,
                "average_delivery_time_hours": round(float(avg_delivery_time), 2),
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting shipment statistics: {str(e)}")
            return {}

    # Helper methods
    async def _validate_location(self, location_id: int) -> Location:
        """Validate location exists and is active"""
        result = await self.session.execute(
            select(Location).where(
                Location.id == location_id,
                Location.is_active == True,
                Location.is_deleted == False
            )
        )
        location = result.scalar_one_or_none()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location with ID {location_id} not found"
            )
        return location

    async def _validate_driver(self, driver_id: int) -> Driver:
        """Validate driver exists and is active"""
        result = await self.session.execute(
            select(Driver).where(
                Driver.id == driver_id,
                Driver.is_active == True,
                Driver.is_deleted == False
            )
        )
        driver = result.scalar_one_or_none()
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver with ID {driver_id} not found"
            )
        return driver

    async def _validate_vehicle(self, vehicle_id: int) -> Vehicle:
        """Validate vehicle exists and is active"""
        result = await self.session.execute(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.is_active == True,
                Vehicle.is_deleted == False
            )
        )
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID {vehicle_id} not found"
            )
        return vehicle

    async def _validate_item(self, item_id: int) -> Item:
        """Validate item exists and is active"""
        result = await self.session.execute(
            select(Item).where(
                Item.id == item_id,
                Item.is_active == True,
                Item.is_deleted == False
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found"
            )
        return item

    async def _shipment_number_exists(self, shipment_number: str) -> bool:
        """Check if shipment number already exists"""
        result = await self.session.execute(
            select(Shipment).where(Shipment.shipment_number == shipment_number)
        )
        return result.scalar_one_or_none() is not None

    async def _create_tracking_update(self, shipment_id: int, 
                                      status: ShipmentStatus, notes: str, user_id: int, 
                                      location: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None):
        """Create shipment tracking update"""
        tracking = ShipmentTracking(
            shipment_id=shipment_id,
            status=status,
            notes=notes,
            timestamp=datetime.utcnow(),
            updated_by=user_id,
            location=location,
            latitude=latitude,
            longitude=longitude
        )
        self.session.add(tracking)
        await self.session.commit()

    async def _update_driver_availability(self, driver_id: int, is_available: bool):
        """Update driver availability"""
        await self.session.execute(
            update(Driver)
            .where(Driver.id == driver_id)
            .values(is_available=is_available, updated_at=datetime.utcnow())
        )

    async def _update_vehicle_availability(self, vehicle_id: int, is_available: bool):
        """Update vehicle availability"""
        await self.session.execute(
            update(Vehicle)
            .where(Vehicle.id == vehicle_id)
            .values(is_available=is_available, updated_at=datetime.utcnow())
        )

    def _is_valid_status_transition(self, current_status: ShipmentStatus, new_status: ShipmentStatus) -> bool:
        """Validate status transition"""
        valid_transitions = {
            ShipmentStatus.READY_FOR_PICKUP: [ShipmentStatus.PICKED_UP, ShipmentStatus.CANCELLED],
            ShipmentStatus.PICKED_UP: [ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED],
            ShipmentStatus.OUT_FOR_DELIVERY: [ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED],
            ShipmentStatus.IN_TRANSIT: [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED],
            ShipmentStatus.DELIVERED: [],  # Terminal state
            ShipmentStatus.CANCELLED: []   # Terminal state
        }
        
        return new_status in valid_transitions.get(current_status, [])