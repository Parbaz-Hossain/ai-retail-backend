import logging
from typing import List, Dict, Tuple
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_
from datetime import datetime

from app.models.inventory.item import Item
from app.models.inventory.item_ingredient import ItemIngredient
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.stock_movement import StockMovement
from app.models.shared.enums import StockMovementType
from app.schemas.inventory.refill_kitchen_schema import (
    RefillKitchenRequest, 
    RefillKitchenResponse,
    RefillItemResult,
    RawMaterialUsage
)
from app.core.exceptions import NotFoundError, ValidationError
from app.services.inventory.stock_level_service import StockLevelService

logger = logging.getLogger(__name__)

class RefillKitchenService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_level_service = StockLevelService(db)

    async def refill_kitchen_items(
        self, 
        refill_request: RefillKitchenRequest,
        current_user_id: int
    ) -> RefillKitchenResponse:
        """
        Main method to refill kitchen items with proper ingredient handling
        """
        try:
            # Validate location exists
            from app.models.organization.location import Location
            location_result = await self.db.execute(
                select(Location).where(Location.id == refill_request.location_id)
            )
            location = location_result.scalar_one_or_none()
            if not location:
                raise NotFoundError(f"Location with id {refill_request.location_id} not found")

            refill_results = []

            # Process each item to refill
            for refill_item in refill_request.items:
                result = await self._process_single_refill_item(
                    item_id=refill_item.item_id,
                    refill_quantity=refill_item.quantity,
                    location_id=refill_request.location_id,
                    current_user_id=current_user_id,
                    remarks=refill_request.remarks
                )
                refill_results.append(result)

            await self.db.commit()

            return RefillKitchenResponse(
                location_id=refill_request.location_id,
                total_items_refilled=len(refill_results),
                refill_results=refill_results,
                message="Kitchen refill completed successfully",
                refilled_at=datetime.utcnow()
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Refill kitchen error: {str(e)}")
            raise

    async def _process_single_refill_item(
        self,
        item_id: int,
        refill_quantity: Decimal,
        location_id: int,
        current_user_id: int,
        remarks: str = None
    ) -> RefillItemResult:
        """
        Process a single item refill with recursive ingredient handling
        """
        # Get the item with its ingredients
        item_result = await self.db.execute(
            select(Item)
            .options(
                selectinload(Item.ingredients).selectinload(ItemIngredient.ingredient_item)
            )
            .where(and_(Item.id == item_id, Item.is_active == True))
        )
        item = item_result.scalar_one_or_none()
        
        if not item:
            raise NotFoundError(f"Item with id {item_id} not found")

        raw_materials_used = []

        # Check if item has ingredients
        if item.has_ingredient and item.ingredients:
            # Calculate and process all raw materials recursively
            raw_materials = await self._calculate_raw_materials_recursive(
                item_id=item_id,
                quantity=refill_quantity
            )

            # Create OUTBOUND movements for each raw material and update stock
            for ingredient_item_id, total_qty, unit_type in raw_materials:
                movement_id = await self._create_outbound_movement(
                    ingredient_item_id=ingredient_item_id,
                    quantity=total_qty,
                    location_id=location_id,
                    current_user_id=current_user_id,
                    reference_type="REFILL_KITCHEN",
                    reference_id=item_id,
                    remarks=f"Used for refilling {item.name} (Qty: {refill_quantity})"
                )

                # Get ingredient item name
                ingredient_item_result = await self.db.execute(
                    select(Item).where(Item.id == ingredient_item_id)
                )
                ingredient_item = ingredient_item_result.scalar_one()

                raw_materials_used.append(RawMaterialUsage(
                    ingredient_item_id=ingredient_item_id,
                    ingredient_item_name=ingredient_item.name,
                    total_quantity=total_qty,
                    unit_type=unit_type.value,
                    stock_movement_id=movement_id
                ))

        # Create INBOUND movement for the refilled item and update stock
        inbound_movement_id = await self._create_inbound_movement(
            item_id=item_id,
            quantity=refill_quantity,
            location_id=location_id,
            current_user_id=current_user_id,
            reference_type="REFILL_KITCHEN",
            remarks=remarks or f"Kitchen refill: {item.name}"
        )

        return RefillItemResult(
            item_id=item_id,
            item_name=item.name,
            refill_quantity=refill_quantity,
            raw_materials_used=raw_materials_used,
            inbound_movement_id=inbound_movement_id
        )

    async def _calculate_raw_materials_recursive(
        self,
        item_id: int,
        quantity: Decimal,
        aggregated_materials: Dict[int, Tuple[Decimal, str]] = None
    ) -> List[Tuple[int, Decimal, str]]:
        """
        Recursively calculate all raw materials needed.
        Returns list of (ingredient_item_id, total_quantity, unit_type)
        
        This handles the case where an ingredient itself has sub-ingredients.
        """
        if aggregated_materials is None:
            aggregated_materials = {}

        # Get item with its ingredients
        item_result = await self.db.execute(
            select(Item)
            .options(
                selectinload(Item.ingredients).selectinload(ItemIngredient.ingredient_item)
            )
            .where(and_(Item.id == item_id, Item.is_active == True))
        )
        item = item_result.scalar_one_or_none()

        if not item:
            return []

        # Process each ingredient
        for ingredient in item.ingredients:
            if not ingredient.is_active:
                continue

            ingredient_item = ingredient.ingredient_item
            required_qty = ingredient.quantity * quantity

            # Check if this ingredient itself has sub-ingredients
            if ingredient_item.has_ingredient:
                # Recursive call to get sub-ingredients
                await self._calculate_raw_materials_recursive(
                    item_id=ingredient_item.id,
                    quantity=required_qty,
                    aggregated_materials=aggregated_materials
                )
            else:
                # This is a raw material (leaf node), add to aggregated materials
                if ingredient_item.id in aggregated_materials:
                    # Aggregate quantities for the same ingredient
                    existing_qty, unit_type = aggregated_materials[ingredient_item.id]
                    aggregated_materials[ingredient_item.id] = (
                        existing_qty + required_qty,
                        unit_type
                    )
                else:
                    aggregated_materials[ingredient_item.id] = (
                        required_qty,
                        ingredient.unit_type
                    )

        # Convert to list format
        return [
            (item_id, qty, unit_type) 
            for item_id, (qty, unit_type) in aggregated_materials.items()
        ]

    async def _create_outbound_movement(
        self,
        ingredient_item_id: int,
        quantity: Decimal,
        location_id: int,
        current_user_id: int,
        reference_type: str,
        reference_id: int = None,
        remarks: str = None
    ) -> int:
        """
        Create OUTBOUND stock movement for raw material and update stock level
        """
        # Get ingredient item details for unit cost
        ingredient_result = await self.db.execute(
            select(Item).where(Item.id == ingredient_item_id)
        )
        ingredient_item = ingredient_result.scalar_one()

        # Calculate total cost
        unit_cost = ingredient_item.unit_cost or Decimal(0)
        total_cost = unit_cost * quantity

        # Create OUTBOUND movement
        movement = StockMovement(
            item_id=ingredient_item_id,
            location_id=location_id,
            movement_type=StockMovementType.OUTBOUND,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            remarks=remarks,
            performed_by=current_user_id,
            movement_date=datetime.utcnow(),
            created_by=current_user_id
        )

        self.db.add(movement)
        await self.db.flush()

        # Update stock level (decrease)
        await self.stock_level_service.adjust_stock(
            item_id=ingredient_item_id,
            location_id=location_id,
            quantity_change=-quantity,  # Negative for outbound
            reason=f"Refill Kitchen - OUTBOUND: {remarks or 'Raw material usage'}",
            current_user_id=current_user_id
        )

        return movement.id

    async def _create_inbound_movement(
        self,
        item_id: int,
        quantity: Decimal,
        location_id: int,
        current_user_id: int,
        reference_type: str,
        remarks: str = None
    ) -> int:
        """
        Create INBOUND stock movement for refilled item and update stock level
        """
        # Get item details for unit cost
        item_result = await self.db.execute(
            select(Item).where(Item.id == item_id)
        )
        item = item_result.scalar_one()

        # Calculate total cost
        unit_cost = item.unit_cost or Decimal(0)
        total_cost = unit_cost * quantity

        # Create INBOUND movement
        movement = StockMovement(
            item_id=item_id,
            location_id=location_id,
            movement_type=StockMovementType.INBOUND,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference_type=reference_type,
            remarks=remarks,
            performed_by=current_user_id,
            movement_date=datetime.utcnow(),
            created_by=current_user_id
        )

        self.db.add(movement)
        await self.db.flush()

        # Update stock level (increase)
        await self.stock_level_service.adjust_stock(
            item_id=item_id,
            location_id=location_id,
            quantity_change=quantity,  # Positive for inbound
            reason=f"Refill Kitchen - INBOUND: {remarks or 'Prepared item'}",
            current_user_id=current_user_id
        )

        return movement.id

    async def validate_sufficient_stock(
        self,
        refill_request: RefillKitchenRequest
    ) -> Dict[int, Dict[str, any]]:
        """
        Validate if there's sufficient stock for all raw materials needed.
        Returns dict of insufficient items with details.
        """
        insufficient_items = {}

        for refill_item in refill_request.items:
            # Calculate raw materials needed
            raw_materials = await self._calculate_raw_materials_recursive(
                item_id=refill_item.item_id,
                quantity=refill_item.quantity
            )

            # Check stock availability for each raw material
            for ingredient_item_id, required_qty, unit_type in raw_materials:
                stock_level = await self.stock_level_service.get_stock_level_by_item_location(
                    item_id=ingredient_item_id,
                    location_id=refill_request.location_id
                )

                if not stock_level or stock_level.available_stock < required_qty:
                    available = stock_level.available_stock if stock_level else Decimal(0)
                    
                    # Get item name
                    item_result = await self.db.execute(
                        select(Item).where(Item.id == ingredient_item_id)
                    )
                    item = item_result.scalar_one()

                    insufficient_items[ingredient_item_id] = {
                        'item_id': ingredient_item_id,
                        'item_name': item.name,
                        'required': float(required_qty),
                        'available': float(available),
                        'shortage': float(required_qty - available),
                        'unit_type': unit_type.value
                    }

        return insufficient_items