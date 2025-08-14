from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
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
            # Check if holiday already exists for this date
            existing = self.db.query(Holiday).filter(
                Holiday.date == holiday_data.date,
                Holiday.is_active == True
            ).first()
            if existing:
                raise ValidationError(f"Holiday already exists for {holiday_data.date}")

            holiday = Holiday(**holiday_data.dict())
            
            self.db.add(holiday)
            self.db.commit()
            self.db.refresh(holiday)
            
            logger.info(f"Holiday created: {holiday.name} on {holiday.date} by user {current_user_id}")
            return holiday
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating holiday: {str(e)}")
            raise

    async def get_holidays(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> List[Holiday]:
        """Get holidays with filtering"""
        query = self.db.query(Holiday)
        
        if is_active is not None:
            query = query.filter(Holiday.is_active == is_active)
        
        if year:
            query = query.filter(Holiday.date.like(f"{year}-%"))
        
        if month and year:
            query = query.filter(Holiday.date.like(f"{year}-{month:02d}-%"))
        
        return query.order_by(Holiday.date).all()

    async def update_holiday(
        self,
        holiday_id: int,
        holiday_data: HolidayUpdate,
        current_user_id: int
    ) -> Holiday:
        """Update holiday"""
        holiday = self.db.query(Holiday).filter(
            Holiday.id == holiday_id,
            Holiday.is_active == True
        ).first()
        
        if not holiday:
            raise NotFoundError(f"Holiday with ID {holiday_id} not found")

        update_data = holiday_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(holiday, field, value)

        self.db.commit()
        self.db.refresh(holiday)
        
        logger.info(f"Holiday updated: {holiday.name} by user {current_user_id}")
        return holiday

    async def delete_holiday(self, holiday_id: int, current_user_id: int) -> bool:
        """Soft delete holiday"""
        holiday = self.db.query(Holiday).filter(
            Holiday.id == holiday_id,
            Holiday.is_active == True
        ).first()
        
        if not holiday:
            raise NotFoundError(f"Holiday with ID {holiday_id} not found")

        holiday.is_active = False
        self.db.commit()
        
        logger.info(f"Holiday deleted: {holiday.name} by user {current_user_id}")
        return True