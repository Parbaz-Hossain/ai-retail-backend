from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.hr.employee import Employee
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.salary_service import SalaryService
from app.services.approval.approval_service import ApprovalService
from app.models.shared.enums import ApprovalRequestType
from app.schemas.hr.salary_schema import SalaryDetailedResponse, SalaryPaymentUpdate, SalaryResponse
from app.models.auth.user import User

router = APIRouter()

@router.post("/generate/{employee_id}")
async def generate_employee_salary(
    employee_id: int,
    salary_month: date = Query(..., description="Salary month in YYYY-MM-dd format"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Generate salary for a specific employee - goes through approval if enabled
    """
    approval_service = ApprovalService(session)
    salary_service = SalaryService(session)
    
    # Check if approval system is enabled for HR.SALARY
    if await approval_service.is_approval_enabled("HR", ApprovalRequestType.SALARY):
        # Create approval request
        request_data = {
            "employee_id": employee_id,
            "salary_month": salary_month.isoformat()
        }
        
        approval_request = await approval_service.create_approval_request(
            request_type=ApprovalRequestType.SALARY,
            employee_id=employee_id,
            request_data=request_data,
            requested_by=current_user.id,
            module="HR",
            remarks=f"Salary generation request for {salary_month.strftime('%B %Y')}"
        )
        
        return {
            "message": "Salary generation sent for approval",
            "approval_request_id": approval_request.id,
            "status": "pending_approval",
            "approval_request": approval_request
        }
    else:
        # Direct generation without approval
        salary = await salary_service.generate_monthly_salary(
            employee_id, salary_month, current_user.id
        )
        return {
            "message": "Salary generated successfully",
            "status": "completed",
            "data": salary
        }

@router.post("/generate-bulk")
async def generate_bulk_salary(
    background_tasks: BackgroundTasks,
    salary_month: date = Query(..., description="Salary month in YYYY-MM-dd format"),
    location_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Generate salary for multiple employees - goes through approval if enabled
    """
    approval_service = ApprovalService(session)
    salary_service = SalaryService(session)
    
    # Check if approval system is enabled for HR.SALARY
    if await approval_service.is_approval_enabled("HR", ApprovalRequestType.SALARY):
        # Get all employees that match criteria        
        query = select(Employee).where(Employee.is_active == True)
        
        if location_id:
            query = query.where(Employee.location_id == location_id)
        if department_id:
            query = query.where(Employee.department_id == department_id)
        
        result = await session.execute(query)
        employees = result.scalars().all()
        
        # Create approval requests for each employee
        approval_requests = []
        for emp in employees:
            try:
                request_data = {
                    "employee_id": emp.id,
                    "salary_month": salary_month.isoformat(),
                    "bulk_generation": True
                }
                
                approval_request = await approval_service.create_approval_request(
                    request_type=ApprovalRequestType.SALARY,
                    employee_id=emp.id,
                    request_data=request_data,
                    requested_by=current_user.id,
                    module="HR",
                    remarks=f"Bulk salary generation for {salary_month.strftime('%B %Y')}"
                )
                approval_requests.append(approval_request.id)
            except Exception as e:
                pass
        
        return {
            "message": f"Bulk salary generation sent for approval ({len(approval_requests)} requests created)",
            "approval_request_ids": approval_requests,
            "status": "pending_approval",
            "total_employees": len(employees),
            "requests_created": len(approval_requests)
        }
    else:
        # Direct bulk generation without approval
        async def bulk_salary_task():
            return await salary_service.generate_bulk_salary(
                salary_month, location_id, department_id, current_user.id
            )
        
        background_tasks.add_task(bulk_salary_task)
        return {
            "message": "Bulk salary generation started in background",
            "status": "processing"
        }

@router.put("/{salary_id}/mark-paid", response_model=SalaryResponse)
async def mark_salary_paid(
    salary_id: int,
    payment_data: SalaryPaymentUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Mark salary as paid"""
    service = SalaryService(session)
    return await service.mark_salary_paid(
        salary_id,
        payment_data.payment_date,
        payment_data.payment_method,
        payment_data.payment_reference,
        current_user.id
    )

@router.get("/employee/{employee_id}", response_model=PaginatedResponse[SalaryResponse])
async def get_employee_salaries(
    employee_id: int,
    page_index: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee salary history with pagination"""
    service = SalaryService(session)
    return await service.get_employee_salaries(
        employee_id=employee_id,
        page_index=page_index,
        page_size=page_size,
        year=year
    )

@router.get("/reports")
async def get_salary_reports(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    location_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get salary reports for management"""
    service = SalaryService(session)
    return await service.get_salary_reports(month, year, location_id, department_id)

@router.get("/", response_model=PaginatedResponse[SalaryDetailedResponse])
async def get_all_salaries(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
    location_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    payment_status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of all employee salaries with filters"""
    service = SalaryService(session)
    return await service.get_all_salaries(
        page_index=page_index,
        page_size=page_size,
        month=month,
        year=year,
        location_id=location_id,
        department_id=department_id,
        payment_status=payment_status
    )