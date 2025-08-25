import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth.user import User
from app.services.engagement.faq_service import FAQService
from app.services.engagement.user_history_service import UserHistoryService
from app.schemas.engagement.faq_schema import (
    FAQCreate, FAQUpdate, FAQResponse, FAQListResponse
)
from app.models.shared.enums import HistoryActionType

router = APIRouter()
logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

@router.post("/", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
async def create_faq(
    data: FAQCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new FAQ"""
    try:
        faq_service = FAQService(session)
        history_service = UserHistoryService(session)
        
        faq = await faq_service.create_faq(data, current_user.id)
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.CREATE,
            resource_type="FAQ",
            resource_id=faq.id,
            title=f"Created FAQ: {data.question[:50]}...",
            description=f"Category: {data.category or 'General'}",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return faq
    except Exception as e:
        logger.error(f"Error creating FAQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating FAQ"
        )

@router.get("/", response_model=FAQListResponse)
async def get_faqs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's FAQs with pagination and filters"""
    try:
        faq_service = FAQService(session)
        
        faqs = await faq_service.get_user_faqs(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            search=search,
            category=category,
            is_active=is_active
        )
        
        total = await faq_service.count_user_faqs(
            user_id=current_user.id,
            search=search,
            category=category,
            is_active=is_active
        )
        
        return FAQListResponse(
            faqs=faqs,
            total=total,
            page=(skip // limit) + 1,
            limit=limit,
            has_next=(skip + limit) < total
        )
    except Exception as e:
        logger.error(f"Error getting FAQs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving FAQs"
        )

@router.get("/categories", response_model=List[str])
async def get_faq_categories(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's FAQ categories"""
    try:
        faq_service = FAQService(session)
        return await faq_service.get_categories(current_user.id)
    except Exception as e:
        logger.error(f"Error getting FAQ categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving categories"
        )

@router.get("/{faq_id}", response_model=FAQResponse)
async def get_faq(
    faq_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific FAQ by ID"""
    try:
        faq_service = FAQService(session)
        history_service = UserHistoryService(session)
        
        faq = await faq_service.get_faq(faq_id, current_user.id)
        if not faq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        # Increment view count
        await faq_service.increment_view_count(faq_id)
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.VIEW,
            resource_type="FAQ",
            resource_id=faq.id,
            title=f"Viewed FAQ: {faq.question[:50]}...",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return faq
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting FAQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving FAQ"
        )

@router.put("/{faq_id}", response_model=FAQResponse)
async def update_faq(
    faq_id: int,
    data: FAQUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update an existing FAQ"""
    try:
        faq_service = FAQService(session)
        history_service = UserHistoryService(session)
        
        faq = await faq_service.update_faq(faq_id, data, current_user.id)
        if not faq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.UPDATE,
            resource_type="FAQ",
            resource_id=faq.id,
            title=f"Updated FAQ: {faq.question[:50]}...",
            description=f"Category: {faq.category or 'General'}",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return faq
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating FAQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating FAQ"
        )

@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete an FAQ"""
    try:
        faq_service = FAQService(session)
        history_service = UserHistoryService(session)
        
        # Get FAQ first for logging
        faq = await faq_service.get_faq(faq_id, current_user.id)
        if not faq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        success = await faq_service.delete_faq(faq_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.DELETE,
            resource_type="FAQ",
            resource_id=faq_id,
            title=f"Deleted FAQ: {faq.question[:50]}...",
            description=f"Category: {faq.category or 'General'}",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting FAQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting FAQ"
        )