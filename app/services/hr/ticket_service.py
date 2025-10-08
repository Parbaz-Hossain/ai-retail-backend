import logging
from typing import Optional, Dict, Any
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, desc, and_, or_
from sqlalchemy.orm import selectinload

from app.models.hr.ticket import Ticket
from app.models.hr.employee import Employee
from app.schemas.hr.ticket_schema import TicketCreate, TicketResponse, EmployeeTicketSummary

logger = logging.getLogger(__name__)

class TicketService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_ticket_no(self) -> str:
        """Generate unique ticket number in format: TKT-YYYYMMDD-XXX"""
        today = date.today().strftime("%Y%m%d")
        prefix = f"TKT-{today}-"
        
        # Get last ticket number for today
        result = await self.session.execute(
            select(Ticket.ticket_no)
            .where(Ticket.ticket_no.like(f"{prefix}%"))
            .order_by(Ticket.ticket_no.desc())
            .limit(1)
        )
        last_ticket = result.scalar_one_or_none()
        
        if last_ticket:
            # Extract sequence number and increment
            try:
                seq = int(last_ticket.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        
        return f"{prefix}{seq:04d}"
    
    async def create_ticket(self, data: TicketCreate) -> Ticket:
        """Create a new ticket for an employee"""
        try:
            # Validate employee exists
            emp_result = await self.session.execute(
                select(Employee).where(
                    Employee.id == data.employee_id,
                    Employee.is_active == True
                )
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            # Generate unique ticket number
            ticket_no = await self.generate_ticket_no()
            
            # Create ticket
            ticket = Ticket(
                ticket_no=ticket_no,
                employee_id=data.employee_id,
                ticket_type=data.ticket_type,
                deduction_amount=data.deduction_amount
            )
            
            self.session.add(ticket)
            await self.session.commit()
            await self.session.refresh(ticket, attribute_names=["employee"])
            
            logger.info(f"Ticket created: {ticket_no} for employee {employee.employee_id} - Type: {data.ticket_type}, Amount: {data.deduction_amount}")
            return ticket
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating ticket: {e}")
            raise HTTPException(status_code=500, detail="Failed to create ticket")
    
    async def get_all_tickets(
        self,
        page_index: int = 1,
        page_size: int = 100,
        employee_id: Optional[int] = None,
        ticket_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        department_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get tickets grouped by employee with pagination and filtering
        Returns summary for each employee with their tickets
        """
        try:
            # Build base query for employee IDs that have tickets
            ticket_query = select(Ticket.employee_id).distinct()
            
            conditions = []
            
            if employee_id:
                conditions.append(Ticket.employee_id == employee_id)
            
            if ticket_type:
                conditions.append(Ticket.ticket_type == ticket_type)
            
            if start_date:
                conditions.append(func.date(Ticket.created_at) >= start_date)
            
            if end_date:
                conditions.append(func.date(Ticket.created_at) <= end_date)
            
            if conditions:
                ticket_query = ticket_query.where(and_(*conditions))
            
            # Get all unique employee IDs with tickets
            employee_ids_result = await self.session.execute(ticket_query)
            all_employee_ids = [row[0] for row in employee_ids_result.all()]
            
            # Apply search filter on employees
            employee_conditions = [Employee.id.in_(all_employee_ids)] if all_employee_ids else [Employee.id.is_(None)]
            
            if search:
                search_pattern = f"%{search}%"
                employee_conditions.append(
                    or_(
                        Employee.first_name.ilike(search_pattern),
                        Employee.last_name.ilike(search_pattern),
                        Employee.employee_id.ilike(search_pattern),
                        Employee.email.ilike(search_pattern)
                    )
                )
            
            if department_id:
                employee_conditions.append(Employee.department_id == department_id)
            
            # Get total count of employees with tickets matching filters
            count_query = select(func.count(Employee.id)).where(and_(*employee_conditions))
            total_count = await self.session.scalar(count_query) or 0
            
            # Get paginated employee IDs
            skip = (page_index - 1) * page_size
            employee_query = (
                select(Employee.id)
                .where(and_(*employee_conditions))
                .order_by(Employee.first_name, Employee.last_name)
                .offset(skip)
                .limit(page_size)
            )
            
            paginated_employee_ids_result = await self.session.execute(employee_query)
            paginated_employee_ids = [row[0] for row in paginated_employee_ids_result.all()]
            
            # Build summary for each employee
            summaries = []
            
            for emp_id in paginated_employee_ids:
                # Get employee info
                emp_result = await self.session.execute(
                    select(Employee).where(Employee.id == emp_id)
                )
                employee = emp_result.scalar_one_or_none()
                
                if not employee:
                    continue
                
                # Get all tickets for this employee with applied filters
                ticket_conditions = [Ticket.employee_id == emp_id]
                
                if ticket_type:
                    ticket_conditions.append(Ticket.ticket_type == ticket_type)
                
                if start_date:
                    ticket_conditions.append(func.date(Ticket.created_at) >= start_date)
                
                if end_date:
                    ticket_conditions.append(func.date(Ticket.created_at) <= end_date)
                
                # Get tickets
                tickets_result = await self.session.execute(
                    select(Ticket)
                    .options(selectinload(Ticket.employee))
                    .where(and_(*ticket_conditions))
                    .order_by(Ticket.created_at.desc())
                )
                tickets = tickets_result.scalars().all()
                
                # Calculate summary statistics
                total_tickets = len(tickets)
                total_deduction = sum([t.deduction_amount for t in tickets])
                late_tickets = len([t for t in tickets if t.ticket_type == "LATE"])
                absent_tickets = len([t for t in tickets if t.ticket_type == "ABSENT"])
                early_leave_tickets = len([t for t in tickets if t.ticket_type == "EARLY_LEAVE"])
                other_tickets = total_tickets - late_tickets - absent_tickets - early_leave_tickets
                
                latest_ticket_date = tickets[0].created_at if tickets else None
                
                # Convert to response models (show only recent 5 tickets in summary)
                recent_tickets = [TicketResponse.model_validate(t, from_attributes=True) for t in tickets[:5]]
                
                summary = EmployeeTicketSummary(
                    employee_id=emp_id,
                    employee_info={
                        "id": employee.id,
                        "employee_id": employee.employee_id,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "email": employee.email,
                        "department_id": employee.department_id,
                        "position": employee.position
                    },
                    total_tickets=total_tickets,
                    total_deduction=total_deduction,
                    late_tickets=late_tickets,
                    absent_tickets=absent_tickets,
                    early_leave_tickets=early_leave_tickets,
                    other_tickets=other_tickets,
                    latest_ticket_date=latest_ticket_date,
                    tickets=recent_tickets
                )
                
                summaries.append(summary)
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count,
                "data": summaries
            }
            
        except Exception as e:
            logger.error(f"Error fetching grouped tickets: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch tickets")
    
    async def get_employee_tickets(
        self,
        employee_id: int,
        page_index: int = 1,
        page_size: int = 50,
        ticket_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get all tickets for a specific employee with pagination"""
        try:
            # Validate employee exists
            emp_result = await self.session.execute(
                select(Employee).where(Employee.id == employee_id)
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            # Build conditions
            conditions = [Ticket.employee_id == employee_id]
            
            if ticket_type:
                conditions.append(Ticket.ticket_type == ticket_type)
            
            if start_date:
                conditions.append(func.date(Ticket.created_at) >= start_date)
            
            if end_date:
                conditions.append(func.date(Ticket.created_at) <= end_date)
            
            # Get total count
            count_query = select(func.count(Ticket.id)).where(and_(*conditions))
            total_count = await self.session.scalar(count_query) or 0
            
            # Get paginated tickets
            skip = (page_index - 1) * page_size
            tickets_result = await self.session.execute(
                select(Ticket)
                .options(selectinload(Ticket.employee))
                .where(and_(*conditions))
                .order_by(Ticket.created_at.desc())
                .offset(skip)
                .limit(page_size)
            )
            tickets = tickets_result.scalars().all()
            
            # Calculate summary
            all_tickets_result = await self.session.execute(
                select(Ticket).where(and_(*conditions))
            )
            all_tickets = all_tickets_result.scalars().all()
            
            total_deduction = sum([t.deduction_amount for t in all_tickets])
            late_count = len([t for t in all_tickets if t.ticket_type == "LATE"])
            absent_count = len([t for t in all_tickets if t.ticket_type == "ABSENT"])
            early_leave_count = len([t for t in all_tickets if t.ticket_type == "EARLY_LEAVE"])
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count,
                "employee": {
                    "id": employee.id,
                    "employee_id": employee.employee_id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "email": employee.email,
                    "department_id": employee.department_id,
                    "position": employee.position
                },
                "summary": {
                    "total_tickets": total_count,
                    "total_deduction": total_deduction,
                    "late_tickets": late_count,
                    "absent_tickets": absent_count,
                    "early_leave_tickets": early_leave_count
                },
                "data": [TicketResponse.model_validate(t, from_attributes=True) for t in tickets]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching employee tickets: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch employee tickets")