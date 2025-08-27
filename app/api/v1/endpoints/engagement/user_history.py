import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth.user import User
from app.schemas.common.pagination import PaginatedResponseNew
from app.services.engagement.user_history_service import UserHistoryService
from app.schemas.engagement.user_history_schema import (
    UserHistoryResponse, UserHistoryListResponse, UserHistoryStats
)
from app.models.shared.enums import HistoryActionType

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=PaginatedResponseNew[UserHistoryResponse])
async def get_user_history(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    action_type: Optional[HistoryActionType] = Query(None),
    resource_type: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    is_archived: Optional[bool] = Query(False),
    session_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's history with pagination and filters"""
    try:
        history_service = UserHistoryService(session)
        
        histories = await history_service.get_user_histories(
            user_id=current_user.id,
            page_index=page_index,
            page_size=page_size,
            action_type=action_type,
            resource_type=resource_type,
            is_favorite=is_favorite,
            is_archived=is_archived,
            session_id=session_id
        )
        
        return histories
    
    except Exception as e:
        logger.error(f"Error getting user history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving history"
        )

@router.get("/stats", response_model=UserHistoryStats)
async def get_user_stats(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's activity statistics"""
    try:
        history_service = UserHistoryService(session)
        stats = await history_service.get_user_stats(current_user.id)
        return UserHistoryStats(**stats)
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving statistics"
        )

@router.put("/{history_id}/favorite", status_code=status.HTTP_200_OK)
async def toggle_favorite(
    history_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Toggle favorite status of a history item"""
    try:
        history_service = UserHistoryService(session)
        success = await history_service.toggle_favorite(history_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="History item not found"
            )
        return {"message": "Favorite status toggled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating favorite status"
        )

@router.put("/{history_id}/archive", status_code=status.HTTP_200_OK)
async def archive_history(
    history_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Archive a history item"""
    try:
        history_service = UserHistoryService(session)
        success = await history_service.archive_history(history_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="History item not found"
            )
        return {"message": "History item archived successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error archiving history item"
        )

@router.get("/session/{session_id}", response_model=UserHistoryListResponse)
async def get_session_history(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get history for a specific session (useful for chat context)"""
    try:
        history_service = UserHistoryService(session)
        
        histories = await history_service.get_user_histories(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            session_id=session_id,
            is_archived=False
        )
        
        total = await history_service.count_user_histories(
            user_id=current_user.id,
            session_id=session_id,
            is_archived=False
        )
        
        return UserHistoryListResponse(
            histories=histories,
            total=total,
            page=(skip // limit) + 1,
            limit=limit,
            has_next=(skip + limit) < total
        )
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving session history"
        )