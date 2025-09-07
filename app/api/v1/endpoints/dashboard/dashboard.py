from datetime import date
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.services.dashboard.dashboard_service import DashboardService
from app.schemas.dashboard.dashboard_schema import DashboardResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=DashboardResponse)
async def get_dashboard_data(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Get comprehensive dashboard data including:
    - Purchase metrics (today's purchases, total orders, pending approvals)
    - Employee metrics (active employees, total employees)
    - Stock metrics (low stock items)
    - Salary metrics (individual status)
    - Po approvals (with status)
    - Shift information (current and next shifts)
    - Reorder request metrics (pending, approved, rejected counts)
    - Holiday information (today's and upcoming holidays)
    """
    try:
        dashboard_service = DashboardService(session)
        dashboard_data = await dashboard_service.get_dashboard_data()
        
        logger.info(f"Dashboard data retrieved successfully for user {current_user.id}")
        return dashboard_data

    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard data"
        )

@router.get("/purchase-report")
async def get_purchase_report(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get purchase report data"""
    try:
        dashboard_service = DashboardService(session)
        from datetime import date
        purchase_report = await dashboard_service.get_purchase_report()
        
        return {
            "data": purchase_report,
            "message": "Purchase reprot generated successfully"
        }

    except Exception as e:
        logger.error(f"Error retrieving purchase report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve purchase report"
        )

@router.get("/employee-report")
async def get_employee_report(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get employee report data"""
    try:
        dashboard_service = DashboardService(session)
        from datetime import date
        employee_report = await dashboard_service.get_employee_report(date.today())
        
        return {
            "data": employee_report,
            "message": "Employee report generated successfully"
        }

    except Exception as e:
        logger.error(f"Error retrieving employee report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve employee report"
        )

@router.get("/item_availability_report")
async def get_item_availability_report(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get item availability report data"""
    try:
        dashboard_service = DashboardService(session)
        stock_metrics = await dashboard_service.get_item_availability_report()
        
        return {
            "data": stock_metrics,
            "message": "Item availability report generated successfully"
        }

    except Exception as e:
        logger.error(f"Error retrieving item availability report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item availability report"
        )

@router.get("/logistics-summary")
async def get_logistics_summary(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get logistics-specific summary data (vehicles, drivers, shipments)"""
    try:
        dashboard_service = DashboardService(session)
        
        vehicle_metrics = await dashboard_service._get_vehicle_metrics()
        driver_metrics = await dashboard_service._get_driver_metrics()
        shipment_metrics = await dashboard_service._get_shipment_metrics()
        
        return {
            "data": {
                "vehicles": vehicle_metrics,
                "drivers": driver_metrics,
                "shipments": shipment_metrics
            },
            "message": "Logistics summary retrieved successfully"
        }

    except Exception as e:
        logger.error(f"Error retrieving logistics summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve logistics summary"
        )

@router.get("/attendance-summary")
async def get_attendance_summary(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get monthly attendance data"""
    try:
        dashboard_service = DashboardService(session)
        attendance_metrics = await dashboard_service._get_attendance_metrics(date.today())
        
        return {
            "data": attendance_metrics,
            "message": "Monthy attendance retrieved successfully"
        }

    except Exception as e:
        logger.error(f"Error retrieving monthly attendance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve monthly attendance data"
        )
    
@router.get("/salary-report")
async def get_yearly_salary_report(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get yearly salary report data"""
    try:
        dashboard_service = DashboardService(session)
        yearly_salary_report = await dashboard_service.get_yearly_salary_report()
        
        return {
            "data": yearly_salary_report,
            "message": "Yearly salary report generated successfully"
        }

    except Exception as e:
        logger.error(f"Error retrieving yearly salary report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve yearly salary report"
        )