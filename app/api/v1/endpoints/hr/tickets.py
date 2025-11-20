from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.services.hr.ticket_service import TicketService
from app.models.auth.user import User

router = APIRouter()

@router.get("/")
async def get_all_tickets(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    employee_id: Optional[int] = Query(None, description="Filter by specific employee"),
    ticket_type: Optional[str] = Query(None, description="Filter by ticket type (LATE, ABSENT, EARLY_LEAVE)"),
    start_date: Optional[date] = Query(None, description="Filter tickets from this date"),
    end_date: Optional[date] = Query(None, description="Filter tickets until this date"),
    search: Optional[str] = Query(None, description="Search by employee name, ID, or email"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all tickets with pagination and filtering.
    """
    service = TicketService(session)
    return await service.get_all_tickets(
        page_index=page_index,
        page_size=page_size,
        employee_id=employee_id,
        ticket_type=ticket_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
        user_id=current_user.id
    )

@router.get("/employee/{employee_id}")
async def get_employee_tickets(
    employee_id: int,
    page_index: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    ticket_type: Optional[str] = Query(None, description="Filter by ticket type (LATE, ABSENT, EARLY_LEAVE)"),
    start_date: Optional[date] = Query(None, description="Filter tickets from this date"),
    end_date: Optional[date] = Query(None, description="Filter tickets until this date"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all tickets for a specific employee with details and summary.
    """
    service = TicketService(session)
    return await service.get_employee_tickets(
        employee_id=employee_id,
        page_index=page_index,
        page_size=page_size,
        ticket_type=ticket_type,
        start_date=start_date,
        end_date=end_date
    )