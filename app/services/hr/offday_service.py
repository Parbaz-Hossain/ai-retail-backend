from typing import Any, Dict, List, Optional
from sqlalchemy import func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from datetime import date, datetime

from app.models.hr.offday import Offday
from app.models.hr.employee import Employee
from app.schemas.hr.offday_schema import (
    OffdayCreate, OffdayBulkCreate, OffdayUpdate, 
    OffdayResponse, OffdayListResponse
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger

class OffdayService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_offday(self, offday_data: OffdayCreate, current_user_id: int) -> OffdayResponse:
        """Create a single offday"""
        try:
            # Validate employee exists
            emp_result = await self.db.execute(
                select(Employee).where(Employee.id == offday_data.employee_id, Employee.is_active == True)
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                raise ValidationError("Employee not found")

            # Check if offday already exists for this date
            existing = await self.db.execute(
                select(Offday).where(
                    Offday.employee_id == offday_data.employee_id,
                    Offday.offday_date == offday_data.offday_date,
                    Offday.is_active == True
                )
            )
            if existing.scalar_one_or_none():
                raise ValidationError(f"Offday already exists for {offday_data.offday_date}")

            # Create new offday
            offday = Offday(**offday_data.dict())
            self.db.add(offday)
            await self.db.commit()
            await self.db.refresh(offday, attribute_names=["employee"])

            logger.info(f"offday created for employee {offday_data.employee_id} on {offday_data.offday_date} by user {current_user_id}")
            return OffdayResponse.model_validate(offday, from_attributes=True)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating offday: {str(e)}")
            raise

    async def create_bulk_offdays(self, bulk_data: OffdayBulkCreate, current_user_id: int) -> OffdayListResponse:
        """Create multiple offdays for an employee in a month"""
        try:
            # Validate employee exists
            emp_result = await self.db.execute(
                select(Employee).where(Employee.id == bulk_data.employee_id, Employee.is_active == True)
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                raise ValidationError("Employee not found")

            # Delete existing offdays for this employee/month to avoid duplicates
            await self.db.execute(
                delete(Offday).where(
                    Offday.employee_id == bulk_data.employee_id,
                    Offday.year == bulk_data.year,
                    Offday.month == bulk_data.month
                )
            )

            # Create new offdays
            offdays = []
            for offday_date in bulk_data.offday_dates:
                # Validate date belongs to the specified month/year
                if offday_date.year != bulk_data.year or offday_date.month != bulk_data.month:
                    raise ValidationError(f"Date {offday_date} doesn't belong to {bulk_data.year}-{bulk_data.month}")

                offday = Offday(
                    employee_id=bulk_data.employee_id,
                    year=bulk_data.year,
                    month=bulk_data.month,
                    offday_date=offday_date,
                    offday_type=bulk_data.offday_type,
                    description=bulk_data.description
                )
                self.db.add(offday)
                offdays.append(offday)

            await self.db.commit()

            # Refresh and return response
            for offday in offdays:
                await self.db.refresh(offday, attribute_names=["employee"])

            logger.info(f"Bulk offdays created for employee {bulk_data.employee_id} - {len(offdays)} days in {bulk_data.year}-{bulk_data.month}")
            
            return OffdayListResponse(
                employee_id=bulk_data.employee_id,
                year=bulk_data.year,
                month=bulk_data.month,
                offdays=[OffdayResponse.model_validate(offday, from_attributes=True) for offday in offdays],
                total_offdays=len(offdays)
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating bulk offdays: {str(e)}")
            raise

    async def get_employee_offdays(self, employee_id: int, year: int, month: int) -> OffdayListResponse:
        """Get all offdays for an employee in a specific month"""
        try:
            result = await self.db.execute(
                select(Offday)
                .options(selectinload(Offday.employee))
                .where(
                    Offday.employee_id == employee_id,
                    Offday.year == year,
                    Offday.month == month,
                    Offday.is_active == True
                )
                .order_by(Offday.offday_date)
            )
            offdays = result.scalars().all()

            return OffdayListResponse(
                employee_id=employee_id,
                year=year,
                month=month,
                offdays=[OffdayResponse.model_validate(offday, from_attributes=True) for offday in offdays],
                total_offdays=len(offdays)
            )

        except Exception as e:
            logger.error(f"Error getting employee offdays: {e}")
            return OffdayListResponse(
                employee_id=employee_id,
                year=year,
                month=month,
                offdays=[],
                total_offdays=0
            )

    async def get_all_offdays(
        self,
        page_index: int = 1,
        page_size: int = 100,
        employee_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get paginated offdays with filtering"""
        try:
            conditions = [Offday.is_active == True]
            
            if employee_id:
                conditions.append(Offday.employee_id == employee_id)
            if year:
                conditions.append(Offday.year == year)
            if month:
                conditions.append(Offday.month == month)

            # Get total count
            total_count = await self.db.scalar(
                select(func.count(Offday.id)).where(*conditions)
            )

            # Calculate offset
            skip = (page_index - 1) * page_size

            # Get paginated data
            offdays = await self.db.scalars(
                select(Offday)
                .options(selectinload(Offday.employee))
                .where(*conditions)
                .order_by(Offday.offday_date.desc())
                .offset(skip)
                .limit(page_size)
            )

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": offdays.all()
            }

        except Exception as e:
            logger.error(f"Error getting offdays: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def update_offday(self, offday_id: int, offday_data: OffdayUpdate, current_user_id: int) -> OffdayResponse:
        """Update a offday"""
        result = await self.db.execute(
            select(Offday)
            .options(selectinload(Offday.employee))
            .where(Offday.id == offday_id, Offday.is_active == True)
        )
        offday = result.scalars().first()

        if not offday:
            raise NotFoundError(f" offday with ID {offday_id} not found")

        update_data = offday_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(offday, field, value)

        # Update year/month if date is changed
        if offday_data.offday_date:
            offday.year = offday_data.offday_date.year
            offday.month = offday_data.offday_date.month

        await self.db.commit()
        await self.db.refresh(offday)

        logger.info(f"offday updated: ID {offday_id} by user {current_user_id}")
        return OffdayResponse.model_validate(offday, from_attributes=True)

    async def delete_offday(self, offday_id: int, current_user_id: int) -> bool:
        """Permanently delete an offday (hard delete)"""
        result = await self.db.execute(
            select(Offday).where(Offday.id == offday_id)
        )
        offday = result.scalars().first()
        
        if not offday:
            raise NotFoundError(f"offday with ID {offday_id} not found")

        await self.db.delete(offday)
        await self.db.commit()

        logger.info(f"offday hard deleted: ID {offday_id} by user {current_user_id}")
        return True

    async def delete_employee_month_offdays(self, employee_id: int, year: int, month: int, current_user_id: int) -> bool:
        """Delete all offdays for an employee in a specific month"""
        await self.db.execute(
            delete(Offday).where(
                Offday.employee_id == employee_id,
                Offday.year == year,
                Offday.month == month
            )
        )
        await self.db.commit()

        logger.info(f"All offdays deleted for employee {employee_id} in {year}-{month} by user {current_user_id}")
        return True

    async def is_employee_offday(self, employee_id: int, check_date: date) -> bool:
        """Check if a specific date is an offday for an employee"""
        try:
            result = await self.db.execute(
                select(Offday).where(
                    Offday.employee_id == employee_id,
                    Offday.offday_date == check_date,
                    Offday.is_active == True
                )
            )
            return result.scalar_one_or_none() is not None
        except Exception:
            return False