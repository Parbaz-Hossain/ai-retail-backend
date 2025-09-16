import logging
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.employee_service import EmployeeService
from app.schemas.hr.employee_schema import EmployeeCreateForm, EmployeeUpdateForm, EmployeeResponse
from app.models.auth.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=EmployeeResponse)
async def create_employee(
    employee_form: EmployeeCreateForm = Depends(),
    profile_image: UploadFile = File(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new employee with optional profile image"""
    try:
        # Convert form to schema
        employee_create = employee_form.to_employee_create()
        
        service = EmployeeService(session)
        
        # Create employee first
        new_employee = await service.create_employee(employee_create, current_user.id)
        
        # Handle image upload if provided
        if profile_image:
            from app.utils.file_handler import FileUploadService
            file_service = FileUploadService()
            
            # Upload image with employee ID
            image_path = await file_service.save_image(profile_image, "employees", new_employee.id)
            
            # Update employee with image path
            new_employee.profile_image = image_path            
            await session.commit()
            await session.refresh(new_employee, attribute_names=["department", "location", "updated_at"])
        
        return new_employee
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create employee error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create employee"
        )

@router.get("/", response_model=PaginatedResponse[EmployeeResponse])
async def get_employees(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    is_manager: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all employees with filtering and pagination"""
    service = EmployeeService(session)
    return await service.get_employees(
        page_index=page_index,
        page_size=page_size,
        department_id=department_id,
        location_id=location_id,
        is_manager=is_manager,
        is_active=is_active,
        search=search
    )

@router.get("/managers", response_model=List[EmployeeResponse])
async def get_managers(
    location_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all managers"""
    service = EmployeeService(session)
    return await service.get_managers(location_id)

@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee by ID"""
    service = EmployeeService(session)
    employee = await service.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    employee_form: EmployeeUpdateForm = Depends(),
    profile_image: UploadFile = File(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update employee with optional profile image"""
    try:
        service = EmployeeService(session)
        
        # Convert form to schema
        employee_update = employee_form.to_employee_update()
        
        # Update employee first
        updated_employee = await service.update_employee(employee_id, employee_update, current_user.id)
        
        # Handle image upload if provided
        if profile_image:
            from app.utils.file_handler import FileUploadService
            file_service = FileUploadService()
            
            # Upload image with employee ID
            image_path = await file_service.save_image(profile_image, "employees", updated_employee.id)
            
            # Update employee with image path
            updated_employee.profile_image = image_path
            await session.commit()
            await session.refresh(updated_employee, attribute_names=["department", "location", "updated_at"])
        
        return updated_employee
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update employee error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update employee"
        )
    
@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
   session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete employee"""
    service = EmployeeService(session)
    result = await service.delete_employee(employee_id, current_user.id)
    return {"message": "Employee deleted successfully", "success": result}