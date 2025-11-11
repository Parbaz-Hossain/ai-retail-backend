import logging
from typing import List, Dict, Tuple, Optional
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

        logger.info(f"Processing refill for item: {item.name} (ID: {item_id}), Quantity: {refill_quantity}")

        raw_materials_used = []

        # Check if item has ingredients
        if item.has_ingredient and item.ingredients:
            # Calculate and process all raw materials recursively
            raw_materials = await self._calculate_raw_materials_recursive(
                item_id=item_id,
                quantity=refill_quantity
            )

            logger.info(f"Total raw materials calculated: {len(raw_materials)}")
            
            # Create OUTBOUND movements for each raw material and update stock
            for ingredient_item_id, total_qty, unit_type in raw_materials:
                # Get ingredient item name
                ingredient_item_result = await self.db.execute(
                    select(Item).where(Item.id == ingredient_item_id)
                )
                ingredient_item = ingredient_item_result.scalar_one()

                logger.info(
                    f"  - Deducting {ingredient_item.name}: {total_qty} {unit_type.value}"
                )

                movement_id = await self._create_outbound_movement(
                    ingredient_item_id=ingredient_item_id,
                    quantity=total_qty,
                    location_id=location_id,
                    current_user_id=current_user_id,
                    reference_type="REFILL_KITCHEN",
                    reference_id=item_id,
                    remarks=f"Used for refilling {item.name} (Qty: {refill_quantity})"
                )

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

        logger.info(f"Refill completed for {item.name}. Inbound movement ID: {inbound_movement_id}")

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
        aggregated_materials: Optional[Dict[int, Tuple[Decimal, str]]] = None,
        depth: int = 0
    ) -> List[Tuple[int, Decimal, str]]:
        """
        PROPERLY FIXED: Calculate raw materials with correct recursive logic.
        
        Key Principle: For each ingredient, calculate how much is needed based on
        the quantity we want to produce, then recursively break down compound ingredients.
        
        Example:
        - Royal Squad (5 plates) needs:
          * 500g Sugar per plate → 5 × 500g = 2,500g Sugar (direct)
          * 500g Chocolate Syrup per plate → 5 × 500g = 2,500g Chocolate Syrup (compound)
          * 1 Box per plate → 5 × 1 = 5 Boxes (direct)
          * 1 Lid per plate → 5 × 1 = 5 Lids (direct)
          * 500ml Milk per plate → 5 × 500ml = 2,500ml Milk (direct)
        
        - Then for 2,500g Chocolate Syrup:
          * Recipe: 200g Sugar + 1000g Cacao + 1000ml Milk (base = 2200g output)
          * Ratio: 2,500g / 2,200g = 1.136363636
          * Sugar needed: 200g × 1.136 = 227.27g
          * Cacao needed: 1000g × 1.136 = 1,136.36g
          * Milk needed: 1000ml × 1.136 = 1,136.36ml
        
        - Final totals:
          * Sugar: 2,500g (direct) + 227.27g (from syrup) = 2,727.27g
          * Cacao: 1,136.36g (from syrup)
          * Milk: 2,500ml (direct) + 1,136.36ml (from syrup) = 3,636.36ml
          * Boxes: 5 PCS
          * Lids: 5 PCS
        """
        if aggregated_materials is None:
            aggregated_materials = {}

        indent = "  " * depth
        logger.debug(f"{indent}[Depth {depth}] Calculating for item_id={item_id}, quantity={quantity}")

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
            logger.warning(f"{indent}Item {item_id} not found")
            return []

        logger.debug(
            f"{indent}Item: {item.name}, "
            f"has_ingredient={item.has_ingredient}, "
            f"ingredients_count={len(item.ingredients) if item.ingredients else 0}"
        )

        # If no ingredients, this is a raw material (shouldn't reach here in normal flow)
        if not item.has_ingredient or not item.ingredients:
            logger.debug(f"{indent}No ingredients for {item.name} - it's a raw material")
            return []

        # CRITICAL FIX: Different calculation strategies based on depth
        # 
        # DEPTH 0 (Parent level, e.g., Royal Squad):
        #   Use SIMPLE MULTIPLICATION: required_qty = quantity × ingredient.quantity
        #   Example: 5 plates × 500g/plate = 2,500g
        # 
        # DEPTH > 0 (Compound ingredient breakdown, e.g., Chocolate Syrup):
        #   Use RATIO-BASED SCALING: required_qty = (quantity / recipe_base) × ingredient.quantity
        #   Example: (2,500g needed / 2,200g recipe) × 200g sugar = 227.27g
        
        recipe_base = Decimal(0)
        
        # Calculate recipe base only if depth > 0 (we're breaking down a compound ingredient)
        if depth > 0:
            # Recipe base = sum of all ingredient quantities
            # (This represents the total output the recipe produces)
            for ing in item.ingredients:
                if ing.is_active:
                    recipe_base += ing.quantity
            
            logger.debug(
                f"{indent}[Depth {depth}] Recipe base for {item.name}: {recipe_base}"
            )
        
        # Process each ingredient in the recipe
        for ingredient in item.ingredients:
            if not ingredient.is_active:
                logger.debug(f"{indent}Skipping inactive ingredient")
                continue

            ingredient_item = ingredient.ingredient_item
            
            # Calculate required quantity based on depth
            if depth == 0:
                # Top level: Simple multiplication
                required_qty = quantity * ingredient.quantity
                
                logger.debug(
                    f"{indent}[Depth 0 - Simple] {ingredient_item.name}\n"
                    f"{indent}  Formula: {quantity} × {ingredient.quantity} = {required_qty} {ingredient.unit_type.value}"
                )
            else:
                # Compound breakdown: Ratio-based scaling
                if recipe_base > 0:
                    ratio = quantity / recipe_base
                    required_qty = ingredient.quantity * ratio
                    
                    logger.debug(
                        f"{indent}[Depth {depth} - Ratio] {ingredient_item.name}\n"
                        f"{indent}  Amount needed: {quantity}\n"
                        f"{indent}  Recipe base: {recipe_base}\n"
                        f"{indent}  Ratio: {ratio}\n"
                        f"{indent}  Formula: {ingredient.quantity} × {ratio} = {required_qty} {ingredient.unit_type.value}"
                    )
                else:
                    # Fallback (shouldn't happen)
                    required_qty = ingredient.quantity * quantity
                    logger.warning(
                        f"{indent}WARNING: recipe_base is 0 at depth {depth}, using direct multiplication!"
                    )
            
            logger.debug(
                f"{indent}  Ingredient: {ingredient_item.name}, "
                f"Required: {required_qty} {ingredient.unit_type.value}, "
                f"Has sub-ingredients: {ingredient_item.has_ingredient}"
            )

            # Check if this ingredient has sub-ingredients (compound ingredient)
            if ingredient_item.has_ingredient:
                logger.debug(
                    f"{indent}  -> {ingredient_item.name} is compound, recursing..."
                )
                
                # Recurse to break down this compound ingredient
                # Pass the required quantity - the recursion will handle scaling its sub-ingredients
                await self._calculate_raw_materials_recursive(
                    item_id=ingredient_item.id,
                    quantity=required_qty,
                    aggregated_materials=aggregated_materials,
                    depth=depth + 1
                )
            else:
                # This is a raw material - add to aggregates
                logger.debug(
                    f"{indent}  -> {ingredient_item.name} is raw material, aggregating"
                )
                
                if ingredient_item.id in aggregated_materials:
                    # Aggregate quantities (must be same unit type)
                    existing_qty, existing_unit = aggregated_materials[ingredient_item.id]
                    new_qty = existing_qty + required_qty
                    
                    logger.debug(
                        f"{indent}     Aggregating: {existing_qty} + {required_qty} = {new_qty}"
                    )
                    
                    aggregated_materials[ingredient_item.id] = (new_qty, existing_unit)
                else:
                    logger.debug(
                        f"{indent}     Adding new: {required_qty} {ingredient.unit_type.value}"
                    )
                    
                    aggregated_materials[ingredient_item.id] = (
                        required_qty,
                        ingredient.unit_type
                    )

        # Return results only at top level
        if depth == 0:
            result = [
                (item_id, qty, unit_type) 
                for item_id, (qty, unit_type) in aggregated_materials.items()
            ]
            
            logger.info(f"Calculation complete: {len(result)} raw materials")
            for mat_id, mat_qty, mat_unit in result:
                item_result = await self.db.execute(
                    select(Item).where(Item.id == mat_id)
                )
                mat_item = item_result.scalar_one()
                logger.info(f"  - {mat_item.name}: {mat_qty} {mat_unit.value}")
            
            return result
        
        return []

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

        logger.debug(
            f"Creating OUTBOUND movement: {ingredient_item.name}, "
            f"Qty: {quantity}, Unit Cost: {unit_cost}, Total Cost: {total_cost}"
        )

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

        logger.debug(
            f"Creating INBOUND movement: {item.name}, "
            f"Qty: {quantity}, Unit Cost: {unit_cost}, Total Cost: {total_cost}"
        )

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

            logger.info(
                f"Validating stock for {refill_item.item_id}, "
                f"found {len(raw_materials)} raw materials"
            )

            # Check stock availability for each raw material
            for ingredient_item_id, required_qty, unit_type in raw_materials:
                stock_level = await self.stock_level_service.get_stock_level_by_item_location(
                    item_id=ingredient_item_id,
                    location_id=refill_request.location_id
                )

                available = stock_level.available_stock if stock_level else Decimal(0)
                
                logger.debug(
                    f"  Stock check - Item ID {ingredient_item_id}: "
                    f"Required={required_qty}, Available={available}"
                )

                if not stock_level or available < required_qty:
                    # Get item name
                    item_result = await self.db.execute(
                        select(Item).where(Item.id == ingredient_item_id)
                    )
                    item = item_result.scalar_one()

                    shortage = required_qty - available
                    
                    logger.warning(
                        f"  INSUFFICIENT STOCK: {item.name} - "
                        f"Required: {required_qty}, Available: {available}, "
                        f"Shortage: {shortage}"
                    )

                    insufficient_items[ingredient_item_id] = {
                        'item_id': ingredient_item_id,
                        'item_name': item.name,
                        'required': float(required_qty),
                        'available': float(available),
                        'shortage': float(shortage),
                        'unit_type': unit_type.value
                    }

        return insufficient_items