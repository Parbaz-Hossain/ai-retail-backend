"""
Auto-executor for approved requests
This service automatically executes approved requests when all members have approved
"""
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.approval.approval_request import ApprovalRequest
from app.models.hr.user_shift import UserShift
from app.models.shared.enums import ApprovalRequestType, ApprovalStatus
from app.services.hr.shift_service import ShiftService
from app.services.hr.salary_service import SalaryService
from app.services.hr.offday_service import OffdayService
from app.schemas.hr.shift_schema import UserShiftCreate, UserShiftUpdate
from app.schemas.hr.offday_schema import OffdayCreate, OffdayBulkCreate
from app.utils.date_time_serializer import deserialize_dates

logger = logging.getLogger(__name__)

class ApprovalAutoExecutor:
    """
    Automatically executes approved requests
    Call this after an approval response is processed
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def execute_if_fully_approved(self, approval_request_id: int, user_id: int):
        """
        Check if request is fully approved and execute it
        """
        try:
            # Get the approval request
            result = await self.session.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == approval_request_id)
            )
            approval_request = result.scalar_one_or_none()
            
            if not approval_request:
                logger.error(f"Approval request {approval_request_id} not found")
                return False
            
            # Check if status is APPROVED
            if approval_request.status != ApprovalStatus.APPROVED:
                logger.info(
                    f"Request {approval_request_id} not yet fully approved. "
                    f"Status: {approval_request.status.value}"
                )
                return False
            
            # Check if already executed
            if approval_request.reference_id:
                logger.info(f"Request {approval_request_id} already executed")
                return True
            
            # Deserialize dates in request_data from ISO format strings back to date objects
            deserialized_data = deserialize_dates(approval_request.request_data)

            # Execute based on request type
            if approval_request.request_type == ApprovalRequestType.SHIFT:
                await self._execute_shift_request(approval_request, deserialized_data, user_id)
            elif approval_request.request_type == ApprovalRequestType.SALARY:
                await self._execute_salary_request(approval_request, deserialized_data, user_id)
            elif approval_request.request_type == ApprovalRequestType.DAYOFF:
                await self._execute_offday_request(approval_request, deserialized_data, user_id)
            
            logger.info(f"Successfully executed approval request {approval_request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing approval request {approval_request_id}: {e}")
            return False
        
    # region ============== HR Execution Methods ==============

    async def _execute_shift_request(self, approval_request: ApprovalRequest, request_data: dict, user_id: int):
        """Execute an approved shift request"""
        shift_service = ShiftService(self.session)
        
        if "user_shift_id" in request_data:
            # This is an update
            user_shift_id = request_data.pop("user_shift_id")
            shift_update = UserShiftUpdate(**request_data)
            await shift_service.update_user_shift(user_shift_id, shift_update, user_id)
            
            # Update approval request with reference
            approval_request.reference_id = user_shift_id
        else:
            # This is a new assignment
            logger.info(f"Assigning new shift with data: {request_data}")
            shift_create = UserShiftCreate(**request_data)
            result = await shift_service.assign_shift_to_employee(shift_create, user_id)
            
            # Update approval request with reference
            approval_request.reference_id = result.id
        
        await self.session.commit()
        logger.info(f"Executed shift request {approval_request.id}")
    
    async def _execute_salary_request(self, approval_request: ApprovalRequest, request_data: dict, user_id: int):
        """Execute an approved salary request"""
        try:
            salary_service = SalaryService(self.session)
            
            employee_id = request_data["employee_id"]
            salary_month = request_data["salary_month"]
            
            # Generate the salary
            logger.info(f"Generating salary for employee {employee_id} for month {salary_month}")
            salary = await salary_service.generate_monthly_salary(employee_id, salary_month, user_id)
            
            # Update approval request with reference
            approval_request.reference_id = salary.id
            
            await self.session.commit()
            logger.info(f"Executed salary request {approval_request.id}")
        except Exception as e:
            logger.error(f"Error executing salary request {approval_request.id}: {e}")
            raise
    
    async def _execute_offday_request(self, approval_request: ApprovalRequest, request_data: dict, user_id: int):
        """Execute an approved offday request"""
        offday_service = OffdayService(self.session)
        
        # Check if this is bulk or single offday
        if "offday_dates" in request_data:
            # Bulk offdays            
            bulk_create = OffdayBulkCreate(**request_data)
            result = await offday_service.create_bulk_offdays(bulk_create, user_id)
            
            # For bulk, store the count
            approval_request.reference_id = result.total_offdays
        else:
            # Single offday
            if "offday_id" in request_data:
                # This is an update
                offday_id = request_data.pop("offday_id")
                
                from app.schemas.hr.offday_schema import OffdayUpdate
                offday_update = OffdayUpdate(**request_data)
                result = await offday_service.update_offday(offday_id, offday_update, user_id)
                
                approval_request.reference_id = offday_id
            else:
                # This is a new creation
                offday_create = OffdayCreate(**request_data)
                result = await offday_service.create_offday(offday_create, user_id)
                
                approval_request.reference_id = result.id
        
        await self.session.commit()
        logger.info(f"Executed offday request {approval_request.id}")

    # endregion