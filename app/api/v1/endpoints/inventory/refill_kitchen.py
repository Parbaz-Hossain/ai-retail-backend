import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.core.exceptions import NotFoundError, ValidationError
from app.models.auth.user import User
from app.schemas.inventory.refill_kitchen_schema import (
    RefillKitchenRequest,
    RefillKitchenResponse
)
from app.services.inventory.refill_kitchen_service import RefillKitchenService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/refill", response_model=RefillKitchenResponse, status_code=status.HTTP_201_CREATED)
async def refill_kitchen_items(
    refill_request: RefillKitchenRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Refill kitchen items by:
    1. Calculating raw materials needed (recursively handling nested ingredients)
    2. Creating OUTBOUND movements for raw materials and updating stock levels
    3. Creating INBOUND movements for prepared items and updating stock levels
    
    Example request:
    {
        "location_id": 1,
        "items": [
            {"item_id": 1, "quantity": 16},
            {"item_id": 2, "quantity": 8},
            {"item_id": 3, "quantity": 5},
            {"item_id": 4, "quantity": 12}
        ],
        "remarks": "Daily kitchen refill"
    }
    """
    try:
        service = RefillKitchenService(db)
        
        # Optional: Validate sufficient stock before processing
        insufficient_stock = await service.validate_sufficient_stock(refill_request)
        if insufficient_stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Insufficient stock for refill operation",
                    "insufficient_items": insufficient_stock
                }
            )
        
        # Process the refill
        result = await service.refill_kitchen_items(refill_request, current_user.id)
        return result
        
    except HTTPException:
        # Re-raise HTTPException so FastAPI can handle it properly
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Refill kitchen error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process kitchen refill"
        )
