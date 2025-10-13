import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from fastapi import HTTPException, status

from app.models.approval.approval_member import ApprovalMember
from app.models.approval.approval_request import ApprovalRequest
from app.models.approval.approval_response import ApprovalResponse
from app.models.approval.approval_settings import ApprovalSettings
from app.models.hr.employee import Employee
from app.models.shared.enums import (
    ApprovalRequestType, ApprovalStatus, ApprovalResponseStatus
)
from app.schemas.approval.approval_member_schema import ApprovalMemberCreate, ApprovalMemberResponse, ApprovalMemberUpdate, ApprovalMembersByModule
from app.schemas.approval.approval_request_schema import ApprovalRequestCreate, ApprovalRequestResponse
from app.services.communication.whatsapp_service import WhatsAppClient
from app.services.approval.approval_auto_executor import ApprovalAutoExecutor
from app.utils.date_time_serializer import serialize_dates

logger = logging.getLogger(__name__)

class ApprovalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.whatsapp_client = WhatsAppClient()

    # region ========== Approval Settings ==========

    async def get_approval_settings(self) -> Dict[str, Any]:
        """Get current approval system settings"""
        result = await self.session.execute(
            select(ApprovalSettings).where(ApprovalSettings.id == 1)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Create default settings if not exists
            settings = ApprovalSettings(id=1, is_enabled=False, updated_by=1)
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
        
        return {
            "id": settings.id,
            "is_enabled": settings.is_enabled,
            "updated_at": settings.updated_at
        }

    async def update_approval_settings(self, is_enabled: bool, user_id: int) -> Dict[str, Any]:
        """Enable or disable approval system"""
        result = await self.session.execute(
            select(ApprovalSettings).where(ApprovalSettings.id == 1)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = ApprovalSettings(id=1, is_enabled=is_enabled, updated_by=user_id)
            self.session.add(settings)
        else:
            settings.is_enabled = is_enabled
            settings.updated_by = user_id
            settings.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        await self.session.refresh(settings)
        
        logger.info(f"Approval system {'enabled' if is_enabled else 'disabled'} by user {user_id}")
        return {
            "id": settings.id,
            "is_enabled": settings.is_enabled,
            "updated_at": settings.updated_at
        }

    async def is_approval_enabled(self) -> bool:
        """Check if approval system is enabled"""
        settings = await self.get_approval_settings()
        return settings["is_enabled"]
    
    # endregion

    # region ========== Approval Members ==========

    async def add_approval_member(self, data: ApprovalMemberCreate, added_by: int) -> ApprovalMemberResponse:
        """Add a new approval member for specific module"""
        try:
            # Validate employee exists and is active
            emp_result = await self.session.execute(
                select(Employee).where(
                    Employee.id == data.employee_id,
                    Employee.is_active == True
                )
            )
            employee = emp_result.scalar_one_or_none()
            
            if not employee:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee not found or inactive"
                )
            
            # Check if already a member for this module with overlapping action types
            existing_result = await self.session.execute(
                select(ApprovalMember).where(
                    ApprovalMember.employee_id == data.employee_id,
                    ApprovalMember.module == data.module,
                    ApprovalMember.is_active == True
                )
            )
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Employee is already an approval member for {data.module}"
                )
            
            # Create approval member
            approval_member = ApprovalMember(
                employee_id=data.employee_id,
                module=data.module,
                added_by=added_by,
                created_by=added_by
            )
            self.session.add(approval_member)
            await self.session.commit()
            await self.session.refresh(approval_member, attribute_names=["employee"])
            
            logger.info(
                f"Approval member added: Employee {data.employee_id} for {data.module} by user {added_by}"
            )
            return ApprovalMemberResponse.model_validate(approval_member, from_attributes=True)
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error adding approval member: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error adding approval member"
            )

    async def update_approval_member(
        self, 
        member_id: int, 
        data: ApprovalMemberUpdate, 
        updated_by: int
    ) -> ApprovalMemberResponse:
        """Update approval member's module or active status"""
        try:
            result = await self.session.execute(
                select(ApprovalMember)
                .options(selectinload(ApprovalMember.employee))
                .where(ApprovalMember.id == member_id)
            )
            member = result.scalar_one_or_none()
            
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Approval member not found"
                )
            
            # Update fields
            if data.module is not None:
                member.module = data.module
            if data.is_active is not None:
                member.is_active = data.is_active
            
            await self.session.commit()
            await self.session.refresh(member)
            
            logger.info(f"Approval member {member_id} updated by user {updated_by}")
            return ApprovalMemberResponse.model_validate(member, from_attributes=True)
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating approval member: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating approval member"
            )

    async def remove_approval_member(self, member_id: int, removed_by: int) -> bool:
        """Remove an approval member and their pending responses"""
        try:
            result = await self.session.execute(
                select(ApprovalMember).where(ApprovalMember.id == member_id)
            )
            member = result.scalar_one_or_none()
            
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Approval member not found"
                )
            
            # Delete all pending approval responses for this member
            await self.session.execute(
                delete(ApprovalResponse).where(
                    ApprovalResponse.approval_member_id == member_id,
                    ApprovalResponse.status == ApprovalResponseStatus.PENDING
                )
            )
            
            # Delete the member
            await self.session.delete(member)
            await self.session.commit()
            
            logger.info(f"Approval member {member_id} removed by user {removed_by}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error removing approval member: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error removing approval member"
            )

    async def get_approval_members(
        self,  
        page_index: int = 1,
        page_size: int = 100,
        module: Optional[str] = None,
        is_active: Optional[bool] = True
    ) -> Dict[str, Any]:
        """Get paginated approval members filtered by module and/or active status"""
        try:
            conditions = []
            if is_active is not None:
                conditions.append(ApprovalMember.is_active == is_active)
            if module:
                conditions.append(ApprovalMember.module == module.upper())

            # Get total count
            total_count = await self.session.scalar(
                select(func.count(ApprovalMember.id)).where(*conditions)
            )

            skip = (page_index - 1) * page_size

            result = await self.session.execute(
                select(ApprovalMember)
                .options(selectinload(ApprovalMember.employee))
                .where(*conditions)
                .order_by(ApprovalMember.module, ApprovalMember.created_at.desc())
                .offset(skip)
                .limit(page_size)
            )
            members = result.scalars().all()

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": [
                    ApprovalMemberResponse.model_validate(member, from_attributes=True)
                    for member in members
                ]
            }
        except Exception as e:
            logger.error(f"Error getting approval members: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_approval_members_by_module(self) -> Dict[str, ApprovalMembersByModule]:
        """Get approval members grouped by module"""
        try:
            result = await self.session.execute(
                select(ApprovalMember)
                .options(selectinload(ApprovalMember.employee))
                .where(ApprovalMember.is_active == True)
                .order_by(ApprovalMember.module, ApprovalMember.created_at.desc())
            )
            members = result.scalars().all()
            
            # Group by module
            grouped = {}
            for member in members:
                module = member.module
                if module not in grouped:
                    grouped[module] = []
                grouped[module].append(
                    ApprovalMemberResponse.model_validate(member, from_attributes=True)
                )
            
            # Convert to response format
            response = {}
            for module, member_list in grouped.items():
                response[module] = ApprovalMembersByModule(
                    module=module,
                    members=member_list,
                    total=len(member_list)
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting members by module: {e}")
            return {}
    
    # endregion

    # region ========== Approval Requests ==========

    async def create_approval_request(
        self,
        request_type: ApprovalRequestType,
        employee_id: int,
        request_data: Dict[str, Any],
        requested_by: int,
        module: str, 
        remarks: Optional[str] = None,
    ) -> ApprovalRequestResponse:
        """
        Create a new approval request and notify members
        NOW FILTERS MEMBERS BY MODULE AND ACTION TYPE
        """
        try:
            # Check if approval system is enabled
            if not await self.is_approval_enabled():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Approval system is not enabled"
                )
            
            # Serialize dates in request_data to ISO format strings
            serialized_request_data = serialize_dates(request_data)
            
            # Get approval members for this specific module and action type
            members_result = await self.session.execute(
                select(ApprovalMember)
                .options(selectinload(ApprovalMember.employee))
                .where(
                    ApprovalMember.is_active == True,
                    ApprovalMember.module == module.upper()
                )
            )
            all_members = members_result.scalars().all()
            
            if not all_members:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No approval members configured for {module}"
                )
            
            # Create approval request
            approval_request = ApprovalRequest(
                request_type=request_type,
                employee_id=employee_id,
                requested_by=requested_by,
                request_data=serialized_request_data,
                remarks=remarks,
                status=ApprovalStatus.PENDING
            )
            self.session.add(approval_request)
            await self.session.flush()
            
            # Create approval responses for each member
            for member in all_members:
                response = ApprovalResponse(
                    approval_request_id=approval_request.id,
                    approval_member_id=member.id,
                    status=ApprovalResponseStatus.PENDING
                )
                self.session.add(response)
            
            await self.session.commit()
            await self.session.refresh(
                approval_request,
                attribute_names=["employee", "approval_responses"]
            )
            
            # Send WhatsApp notifications to all members
            await self._notify_approval_members(all_members, request_type, approval_request.id)
            
            logger.info(
                f"Approval request created: Type={request_type}, Module={module}, "
                f"Employee={employee_id}, RequestID={approval_request.id}, "
                f"Members={len(all_members)}"
            )
            
            return ApprovalRequestResponse.model_validate(
                approval_request,
                from_attributes=True
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating approval request: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating approval request"
            )

    async def process_approval_response(
        self,
        request_id: int,
        member_employee_id: int,
        action: str,
        user_id: int,
        comments: Optional[str] = None
    ) -> ApprovalRequestResponse:
        """Process an approval or rejection from a member"""
        try:
            # Get the approval request with all relationships
            result = await self.session.execute(
                select(ApprovalRequest)
                .options(   
                    joinedload(ApprovalRequest.employee),
                    selectinload(ApprovalRequest.approval_responses)
                    .joinedload(ApprovalResponse.approval_member)
                    .joinedload(ApprovalMember.employee)
                )
                .where(ApprovalRequest.id == request_id)
            )
            request = result.scalar_one_or_none()
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Approval request not found"
                )
            
            if request.status != ApprovalStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Request is already {request.status.value}"
                )
            
            # Find the member's response
            member_response = None
            for response in request.approval_responses:
                if response.approval_member.employee_id == member_employee_id:
                    member_response = response
                    break
            
            logger.info(f"Member response found: {member_response} member_employee_id={member_employee_id}")
            if not member_response:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to approve this request"
                )
            
            if member_response.status != ApprovalResponseStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You have already responded to this request"
                )
            
            # Update the response
            if action.lower() == "approve":
                member_response.status = ApprovalResponseStatus.APPROVED
            elif action.lower() == "reject":
                member_response.status = ApprovalResponseStatus.REJECTED
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid action. Must be 'approve' or 'reject'"
                )
            
            member_response.comments = comments
            member_response.responded_at = datetime.now(timezone.utc)
            
            # Check if all members have responded
            all_responses = request.approval_responses
            pending_count = sum(
                1 for r in all_responses
                if r.status == ApprovalResponseStatus.PENDING
            )
            
            # If any rejection, mark request as rejected
            if member_response.status == ApprovalResponseStatus.REJECTED:
                request.status = ApprovalStatus.REJECTED
                request.rejected_at = datetime.now(timezone.utc)
                logger.info(f"Approval request {request_id} rejected by member {member_employee_id}")
            
            # If all approved, mark request as approved
            elif pending_count == 0:
                all_approved = all(
                    r.status == ApprovalResponseStatus.APPROVED
                    for r in all_responses
                )
                
                if all_approved:
                    request.status = ApprovalStatus.APPROVED
                    request.approved_at = datetime.now(timezone.utc)
                    logger.info(f"Approval request {request_id} fully approved")
            
            await self.session.commit()
                       
            # Auto-execute if fully approved
            if request.status == ApprovalStatus.APPROVED:
                executor = ApprovalAutoExecutor(self.session)
                await executor.execute_if_fully_approved(request_id, user_id)

                result = await self.session.execute(
                select(ApprovalRequest)
                .options(
                    selectinload(ApprovalRequest.employee),
                    selectinload(ApprovalRequest.approval_responses)
                    .selectinload(ApprovalResponse.approval_member)
                    .selectinload(ApprovalMember.employee)
                    )
                    .where(ApprovalRequest.id == request_id)
                )

                request = result.scalar_one_or_none()
            else: 
                await self.session.refresh(request, attribute_names=["updated_at"])
            
            return ApprovalRequestResponse.model_validate(request, from_attributes=True)
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error processing approval response: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing approval response"
            )

    async def get_pending_approvals_for_member(
        self,
        member_employee_id: int
    ) -> List[ApprovalRequestResponse]:
        """Get all pending approval requests for a specific member"""
        try:
            # First get the approval member
            member_result = await self.session.execute(
                select(ApprovalMember).where(
                    ApprovalMember.employee_id == member_employee_id,
                    ApprovalMember.is_active == True
                )
            )
            member = member_result.scalar_one_or_none()
            
            if not member:
                return []
            
            # Get all pending requests where this member hasn't responded
            result = await self.session.execute(
                select(ApprovalRequest)
                .join(ApprovalResponse)
                .options(
                    selectinload(ApprovalRequest.employee),
                    selectinload(ApprovalRequest.approval_responses)
                    .selectinload(ApprovalResponse.approval_member)
                    .selectinload(ApprovalMember.employee)
                )
                .where(
                    ApprovalRequest.status == ApprovalStatus.PENDING,
                    ApprovalResponse.approval_member_id == member.id,
                    ApprovalResponse.status == ApprovalResponseStatus.PENDING
                )
                .order_by(ApprovalRequest.created_at.desc())
            )
            
            requests = result.scalars().unique().all()
            
            return [
                ApprovalRequestResponse.model_validate(req, from_attributes=True)
                for req in requests
            ]
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {e}")
            return []

    async def get_all_approval_requests(
        self,
        status: Optional[ApprovalStatus] = None,
        request_type: Optional[ApprovalRequestType] = None,
        page_index: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """Get paginated approval requests with filtering"""
        try:
            conditions = []
            
            if status:
                conditions.append(ApprovalRequest.status == status)
            if request_type:
                conditions.append(ApprovalRequest.request_type == request_type)
            
            # Get total count
            total_count = await self.session.scalar(
                select(func.count(ApprovalRequest.id)).where(*conditions)
            )
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            result = await self.session.execute(
                select(ApprovalRequest)
                .options(
                    selectinload(ApprovalRequest.employee),
                    selectinload(ApprovalRequest.approval_responses)
                    .selectinload(ApprovalResponse.approval_member)
                    .selectinload(ApprovalMember.employee)
                )
                .where(*conditions)
                .order_by(ApprovalRequest.created_at.desc())
                .offset(skip)
                .limit(page_size)
            )
            
            requests = result.scalars().unique().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": [
                    ApprovalRequestResponse.model_validate(req, from_attributes=True)
                    for req in requests
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting approval requests: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_approval_request(self, request_id: int) -> Optional[ApprovalRequestResponse]:
        """Get a specific approval request"""
        try:
            result = await self.session.execute(
                select(ApprovalRequest)
                .options(
                    selectinload(ApprovalRequest.employee),
                    selectinload(ApprovalRequest.approval_responses)
                    .selectinload(ApprovalResponse.approval_member)
                    .selectinload(ApprovalMember.employee)
                )
                .where(ApprovalRequest.id == request_id)
            )
            request = result.scalar_one_or_none()
            
            if request:
                return ApprovalRequestResponse.model_validate(request, from_attributes=True)
            return None
            
        except Exception as e:
            logger.error(f"Error getting approval request: {e}")
            return None

    # endregion

    # ========== WhatsApp Notifications ==========
    async def _notify_approval_members(
        self,
        members: List[ApprovalMember],
        request_type: ApprovalRequestType,
        request_id: int
    ):
        """Send WhatsApp notifications to approval members"""
        try:
            for member in members:
                if member.employee and member.employee.phone:
                    message = (
                        f"Dear {member.employee.first_name},\n\n"
                        f"You have a new approval request to review.\n\n"
                        f"Type: {request_type.value}\n"
                        f"Request ID: {request_id}\n\n"
                        f"Please login to the system to approve or reject this request."
                    )
                    
                    await self.whatsapp_client.send(
                        phone=member.employee.phone,
                        body=message
                    )
                    
                    logger.info(
                        f"WhatsApp notification sent to {member.employee.phone} "
                        f"for request {request_id}"
                    )
                    
        except Exception as e:
            # Don't fail the whole process if WhatsApp fails
            logger.error(f"Error sending WhatsApp notifications: {e}")