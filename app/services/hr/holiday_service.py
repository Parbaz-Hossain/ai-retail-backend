from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import date, timedelta

from app.models.hr.holiday import Holiday
from app.schemas.hr.holiday_schema import HolidayCreate, HolidayUpdate
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger

class HolidayService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_holiday(self, holiday_data: HolidayCreate, current_user_id: int) -> Holiday:
        """Create a new holiday"""
        try:
            result = await self.db.execute(
                select(Holiday).where(
                    Holiday.date == holiday_data.date,
                    Holiday.is_active == True
                )
            )
            existing = result.scalars().first()
            if existing:
                raise ValidationError(f"Holiday already exists for {holiday_data.date}")

            holiday = Holiday(**holiday_data.dict())
            self.db.add(holiday)
            await self.db.commit()
            await self.db.refresh(holiday)

            logger.info(f"Holiday created: {holiday.name} on {holiday.date} by user {current_user_id}")
            return holiday

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating holiday: {str(e)}")
            raise

    async def get_holidays(
        self,
        page_index: int = 1,
        page_size: int = 100,
        year: Optional[int] = None,
        month: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Retrieve holidays with pagination and optional filters"""
        try:
            conditions = []

            if is_active is not None:
                conditions.append(Holiday.is_active == is_active)

            if year and month:
                # Calculate start and end dates for the specific month
                start_date = date(year, month, 1)
                if month == 12:
                    end_date = date(year, 12, 31)
                else:
                    next_month = date(year, month + 1, 1)
                    end_date = next_month - timedelta(days=1)
                conditions.append(Holiday.date >= start_date)
                conditions.append(Holiday.date <= end_date)
            elif year:
                # Filter by year only
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)
                conditions.append(Holiday.date >= start_date)
                conditions.append(Holiday.date <= end_date)

            # Get total count
            total_count = await self.db.scalar(
                select(func.count(Holiday.id)).where(*conditions)
            )

            # Calculate offset
            skip = (page_index - 1) * page_size

            # Get paginated data
            holidays = await self.db.scalars(
                select(Holiday)
                .where(*conditions)
                .order_by(Holiday.date.desc())
                .offset(skip)
                .limit(page_size)
            )

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": holidays.all()
            }

        except Exception as e:
            logger.error(f"Error getting holidays: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }
    
    async def get_holiday(self, holiday_id: int) -> Optional[Holiday]:
        try:
            result = await self.db.execute(
                select(Holiday).where(
                    Holiday.id == holiday_id,
                    Holiday.is_active == True
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting location {holiday_id}: {e}")
            return None

    async def update_holiday(self, holiday_id: int, holiday_data: HolidayUpdate, current_user_id: int) -> Holiday:
        """Update a holiday record"""
        result = await self.db.execute(
            select(Holiday).where(
                Holiday.id == holiday_id,
                Holiday.is_deleted == False
            )
        )
        holiday = result.scalars().first()

        if not holiday:
            raise NotFoundError(f"Holiday with ID {holiday_id} not found")

        update_data = holiday_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(holiday, field, value)

        await self.db.commit()
        await self.db.refresh(holiday)

        logger.info(f"Holiday updated: {holiday.name} by user {current_user_id}")
        return holiday

    async def delete_holiday(self, holiday_id: int, current_user_id: int) -> bool:
        """Soft delete a holiday"""
        result = await self.db.execute(
            select(Holiday).where(
                Holiday.id == holiday_id
            )
        )
        holiday = result.scalars().first()
        if not holiday:
            raise NotFoundError(f"Holiday with ID {holiday_id} not found")

        holiday.is_active = False
        holiday.is_deleted = True
        await self.db.commit()

        logger.info(f"Holiday deleted: {holiday.name} by user {current_user_id}")
        return True
