from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.approval.approval_request import ApprovalRequest
from app.models.hr.employee import Employee
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.salary_service import SalaryService
from app.services.hr.deduction_service import DeductionService
from app.services.approval.approval_service import ApprovalService
from app.models.shared.enums import ApprovalRequestType, ApprovalStatus
from app.schemas.hr.salary_schema import SalaryCreate, SalaryUpdate, SalaryResponse, SalaryPaymentUpdate
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
    
    # Check if approval system is enabled
    if await approval_service.is_approval_enabled():
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
    Note: When approval is enabled, individual requests are created for each employee
    """
    approval_service = ApprovalService(session)
    salary_service = SalaryService(session)
    
    # Check if approval system is enabled
    if await approval_service.is_approval_enabled():
        # Get all employees that match the criteria        
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
                # Log error but continue
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

# @router.post("/approval/{approval_id}/execute", response_model=SalaryResponse)
# async def execute_approved_salary(
#     approval_id: int,
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     Execute an approved salary generation (called after all approvals)
#     """
#     approval_service = ApprovalService(session)
#     salary_service = SalaryService(session)
    
#     # Get the approval request
#     approval_request = await approval_service.get_approval_request(approval_id)
    
#     if not approval_request:
#         raise HTTPException(status_code=404, detail="Approval request not found")
    
#     if approval_request.status != ApprovalStatus.APPROVED:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Cannot execute. Request status is {approval_request.status.value}"
#         )
    
#     # Check if already executed
#     if approval_request.reference_id:
#         raise HTTPException(status_code=400, detail="This request has already been executed")
    
#     request_data = approval_request.request_data
#     employee_id = request_data["employee_id"]
#     salary_month = date.fromisoformat(request_data["salary_month"])
    
#     # Generate the salary
#     salary = await salary_service.generate_monthly_salary(
#         employee_id, salary_month, current_user.id
#     )
    
#     # Update approval request with reference    
#     await session.execute(
#         update(ApprovalRequest)
#         .where(ApprovalRequest.id == approval_id)
#         .values(reference_id=salary.id)
#     )
#     await session.commit()
    
#     return salary

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
    """Get employee salary history with pagination and deduction details"""
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
    """Get salary reports for management with deduction breakdown"""
    service = SalaryService(session)
    return await service.get_salary_reports(month, year, location_id, department_id)

@router.get("/{salary_id}/deductions")
async def get_salary_deduction_details(
    salary_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get detailed deduction breakdown for a salary"""
    service = SalaryService(session)
    salary = await service.get_salary_with_deduction_details(salary_id)
    if not salary:
        raise HTTPException(status_code=404, detail="Salary not found")
    
    deduction_breakdown = []
    for deduction in salary.deduction_details:
        deduction_breakdown.append({
            "id": deduction.id,
            "type_name": deduction.deduction_type.name if deduction.deduction_type else "Unknown",
            "amount": float(deduction.deducted_amount),
            "employee_deduction_id": deduction.employee_deduction_id,
            "is_auto_calculated": deduction.deduction_type.is_auto_calculated if deduction.deduction_type else False
        })
    
    return {
        "salary_id": salary.id,
        "employee_id": salary.employee_id,
        "salary_month": salary.salary_month,
        "total_deductions": float(salary.total_deductions),
        "deduction_breakdown": deduction_breakdown
    }

@router.put("/{salary_id}/recalculate-deductions", response_model=SalaryResponse)
async def recalculate_salary_deductions(
    salary_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Recalculate deductions for an existing salary"""
    service = SalaryService(session)
    return await service.recalculate_salary_deductions(salary_id, current_user.id)

@router.get("/preview-deductions/{employee_id}")
async def preview_salary_deductions(
    employee_id: int,
    salary_month: date = Query(..., description="Salary month in YYYY-MM-dd format"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Preview deductions for an employee before generating salary"""
    deduction_service = DeductionService(session)
    total_deduction, deduction_details = await deduction_service.calculate_monthly_deductions(
        employee_id, salary_month
    )
    
    return {
        "employee_id": employee_id,
        "salary_month": salary_month,
        "total_deduction": float(total_deduction),
        "deduction_breakdown": [
            {
                "type_name": detail.get('type_name'),
                "amount": float(detail['amount']),
                "is_auto_calculated": detail.get('auto_calculated', False),
                "employee_deduction_id": detail.get('employee_deduction_id')
            }
            for detail in deduction_details
        ]
    }