# app/services/logistics/vehicle_service.py
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.models.logistics.vehicle import Vehicle
from app.models.logistics.shipment import Shipment
from app.schemas.logistics.vehicle_schema import VehicleCreate, VehicleUpdate, VehicleResponse

logger = logging.getLogger(__name__)

class VehicleService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_vehicle(self, vehicle_data: VehicleCreate, user_id: int) -> Vehicle:
        """Create a new vehicle"""
        try:
            # Check if vehicle number is unique
            result = await self.session.execute(
                select(Vehicle).where(Vehicle.vehicle_number == vehicle_data.vehicle_number)
            )
            existing_vehicle = result.scalar_one_or_none()
            if existing_vehicle:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vehicle number already exists"
                )

            # Create vehicle
            vehicle = Vehicle(**vehicle_data.dict())
            vehicle.created_by = user_id            
            self.session.add(vehicle)
            await self.session.commit()
            await self.session.refresh(vehicle)

            logger.info(f"Vehicle created successfully with ID: {vehicle.id}")
            return vehicle

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating vehicle: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create vehicle"
            )

    async def get_vehicle(self, vehicle_id: int) -> Optional[Vehicle]:
        """Get vehicle by ID"""
        try:
            result = await self.session.execute(
                select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.is_deleted == False)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting vehicle {vehicle_id}: {str(e)}")
            return None

    async def get_vehicles(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get list of vehicles with filters"""
        try:
            query = select(Vehicle)
            
            # Apply filters
            conditions = [Vehicle.is_deleted == False]
            
            if search:
                conditions.append(
                    or_(
                        Vehicle.vehicle_number.icontains(search),
                        Vehicle.model.icontains(search),
                        Vehicle.vehicle_type.icontains(search)
                    )
                )
            
            if vehicle_type:
                conditions.append(Vehicle.vehicle_type == vehicle_type)
                
            if is_available is not None:
                conditions.append(Vehicle.is_available == is_available)
                
            if is_active is not None:
                conditions.append(Vehicle.is_active == is_active)
            
            query = query.where(and_(*conditions))
            query = query.offset(skip).limit(limit).order_by(Vehicle.created_at.desc())
            
            result = await self.session.execute(query)
            vehicles = result.scalars().all()
            total = await self.session.scalar(
                select(func.count()).select_from(Vehicle).where(and_(*conditions))
            )

            return {
                "data": vehicles,
                "total": total,
                "skip": skip,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error getting vehicles: {str(e)}")
            return []

    async def update_vehicle(self, vehicle_id: int, vehicle_data: VehicleUpdate, user_id: int) -> Optional[Vehicle]:
        """Update vehicle"""
        try:
            vehicle = await self.get_vehicle(vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found"
                )

            # Check vehicle number uniqueness if being updated
            if vehicle_data.vehicle_number and vehicle_data.vehicle_number != vehicle.vehicle_number:
                result = await self.session.execute(
                    select(Vehicle).where(
                        Vehicle.vehicle_number == vehicle_data.vehicle_number,
                        Vehicle.id != vehicle_id
                    )
                )
                existing_vehicle = result.scalar_one_or_none()
                if existing_vehicle:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vehicle number already exists"
                    )

            # Update fields
            update_data = vehicle_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(vehicle, field, value)

            vehicle.updated_at = datetime.utcnow()
            vehicle.updated_by = user_id
            await self.session.commit()
            await self.session.refresh(vehicle)

            logger.info(f"Vehicle {vehicle_id} updated successfully")
            return vehicle

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating vehicle {vehicle_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update vehicle"
            )

    async def delete_vehicle(self, vehicle_id: int, user_id: int) -> bool:
        """Soft delete vehicle"""
        try:
            vehicle = await self.get_vehicle(vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found"
                )

            # Check if vehicle has active shipments
            result = await self.session.execute(
                select(Shipment).where(
                    Shipment.vehicle_id == vehicle_id,
                    Shipment.status.in_(["READY_FOR_PICKUP", "PICKED_UP", "OUT_FOR_DELIVERY", "IN_TRANSIT"])
                )
            )
            active_shipments = result.scalars().all()
            if active_shipments:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete vehicle with active shipments"
                )

            vehicle.is_active = False
            vehicle.is_deleted = True
            await self.session.commit()

            logger.info(f"Vehicle {vehicle_id} deleted successfully")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting vehicle {vehicle_id}: {str(e)}")
            return False

    async def get_available_vehicles(self, min_capacity_weight: Optional[float] = None) -> List[Vehicle]:
        """Get all available vehicles"""
        try:
            conditions = [
                Vehicle.is_available == True,
                Vehicle.is_active == True,
                Vehicle.is_deleted == False
            ]
            
            if min_capacity_weight:
                conditions.append(Vehicle.capacity_weight >= min_capacity_weight)
            
            result = await self.session.execute(
                select(Vehicle)
                .where(and_(*conditions))
                .order_by(Vehicle.capacity_weight.desc())
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting available vehicles: {str(e)}")
            return []

    async def update_vehicle_availability(self, vehicle_id: int, is_available: bool, user_id: int) -> bool:
        """Update vehicle availability status"""
        try:
            vehicle = await self.get_vehicle(vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found"
                )

            vehicle.is_available = is_available
            vehicle.updated_at = datetime.utcnow()
            await self.session.commit()

            logger.info(f"Vehicle {vehicle_id} availability updated to {is_available}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating vehicle availability: {str(e)}")
            return False

    async def update_vehicle_mileage(self, vehicle_id: int, new_mileage: int, user_id: int) -> bool:
        """Update vehicle mileage"""
        try:
            vehicle = await self.get_vehicle(vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found"
                )

            if new_mileage < vehicle.current_mileage:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New mileage cannot be less than current mileage"
                )

            vehicle.current_mileage = new_mileage
            vehicle.updated_at = datetime.utcnow()
            await self.session.commit()

            logger.info(f"Vehicle {vehicle_id} mileage updated to {new_mileage}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating vehicle mileage: {str(e)}")
            return False

    async def get_vehicles_needing_maintenance(self) -> List[Vehicle]:
        """Get vehicles that need maintenance"""
        try:
            today = date.today()
            
            result = await self.session.execute(
                select(Vehicle).where(
                    Vehicle.next_maintenance_date <= today,
                    Vehicle.is_active == True,
                    Vehicle.is_deleted == False
                )
                .order_by(Vehicle.next_maintenance_date)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting vehicles needing maintenance: {str(e)}")
            return []

    async def check_vehicle_documents_expiry(self, days_ahead: int = 30) -> List[Vehicle]:
        """Get vehicles with documents expiring soon"""
        try:
            expiry_date = date.today() + timedelta(days=days_ahead)
            today = date.today()
            
            result = await self.session.execute(
                select(Vehicle).where(
                    or_(
                        and_(
                            Vehicle.registration_expiry <= expiry_date,
                            Vehicle.registration_expiry >= today
                        ),
                        and_(
                            Vehicle.insurance_expiry <= expiry_date,
                            Vehicle.insurance_expiry >= today
                        )
                    ),
                    Vehicle.is_active == True,
                    Vehicle.is_deleted == False
                )
                .order_by(Vehicle.registration_expiry, Vehicle.insurance_expiry)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error checking vehicle documents expiry: {str(e)}")
            return []

    async def get_vehicle_utilization_stats(self, vehicle_id: int, days: int = 30) -> Dict[str, Any]:
        """Get vehicle utilization statistics"""
        try:
            start_date = date.today() - timedelta(days=days)
            
            # Get total shipments
            result = await self.session.execute(
                select(func.count(Shipment.id))
                .where(
                    Shipment.vehicle_id == vehicle_id,
                    Shipment.shipment_date >= start_date
                )
            )
            total_shipments = result.scalar() or 0
            
            # Get completed shipments
            result = await self.session.execute(
                select(func.count(Shipment.id))
                .where(
                    Shipment.vehicle_id == vehicle_id,
                    Shipment.shipment_date >= start_date,
                    Shipment.status == "DELIVERED"
                )
            )
            completed_shipments = result.scalar() or 0
            
            # Get total distance and fuel cost
            result = await self.session.execute(
                select(
                    func.sum(Shipment.distance_km),
                    func.sum(Shipment.fuel_cost)
                ).where(
                    Shipment.vehicle_id == vehicle_id,
                    Shipment.shipment_date >= start_date,
                    Shipment.status == "DELIVERED"
                )
            )
            distance_fuel = result.first()
            total_distance = distance_fuel[0] or 0
            total_fuel_cost = distance_fuel[1] or 0
            
            return {
                "total_shipments": total_shipments,
                "completed_shipments": completed_shipments,
                "completion_rate": (completed_shipments / total_shipments * 100) if total_shipments > 0 else 0,
                "total_distance_km": float(total_distance),
                "total_fuel_cost": float(total_fuel_cost),
                "average_distance_per_shipment": float(total_distance / completed_shipments) if completed_shipments > 0 else 0,
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting vehicle utilization stats: {str(e)}")
            return {
                "total_shipments": 0,
                "completed_shipments": 0,
                "completion_rate": 0,
                "total_distance_km": 0,
                "total_fuel_cost": 0,
                "average_distance_per_shipment": 0,
                "period_days": days
            }