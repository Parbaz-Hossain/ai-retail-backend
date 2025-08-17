from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import date

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
        year: Optional[int] = None,
        month: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> List[Holiday]:
        """Retrieve holidays with optional filters"""
        stmt = select(Holiday)

        if is_active is not None:
            stmt = stmt.where(Holiday.is_active == is_active)

        if year and month:
            stmt = stmt.where(Holiday.date.like(f"{year}-{month:02d}-%"))
        elif year:
            stmt = stmt.where(Holiday.date.like(f"{year}-%"))

        result = await self.db.execute(stmt.order_by(Holiday.date))
        return result.scalars().all()

    async def update_holiday(self, holiday_id: int, holiday_data: HolidayUpdate, current_user_id: int) -> Holiday:
        """Update a holiday record"""
        result = await self.db.execute(
            select(Holiday).where(
                Holiday.id == holiday_id,
                Holiday.is_active == True
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
                Holiday.id == holiday_id,
                Holiday.is_active == True
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
