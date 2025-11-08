import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload

from app.models.inventory.order import Order
from app.models.inventory.order_product import OrderProduct
from app.models.inventory.product import Product
from app.models.inventory.product_item import ProductItem
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.stock_movement import StockMovement
from app.models.organization.location import Location
from app.models.shared.enums import StockMovementType
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class FoodicsOrderService:
    def __init__(self, db: AsyncSession, foodics_api_token: str):
        self.db = db
        self.api_token = foodics_api_token
        self.base_url = "https://api.foodics.com/v5"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    async def fetch_and_save_orders(self, location_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch new orders from Foodics and save them to database.
        Similar to FetchAndSaveNewOrdersAsyncChatGPT in C# code.
        """
        try:
            # Get locations to sync
            if location_id:
                location_result = await self.db.execute(
                    select(Location).where(
                        and_(
                            Location.id == location_id,
                            Location.is_active == True,
                            Location.foodics_guid.isnot(None)
                        )
                    )
                )
                locations = [location_result.scalar_one_or_none()]
                if not locations[0]:
                    return {
                        "success": False,
                        "message": "Location not found or doesn't have Foodics integration",
                        "orders_synced": 0,
                        "errors": []
                    }
            else:
                location_result = await self.db.execute(
                    select(Location).where(
                        and_(
                            Location.is_active == True,
                            Location.foodics_guid.isnot(None)
                        )
                    )
                )
                locations = location_result.scalars().all()
            
            total_orders_synced = 0
            errors = []
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                for location in locations:
                    try:
                        orders_synced = await self._sync_location_orders(
                            client, location
                        )
                        total_orders_synced += orders_synced
                        logger.info(f"Synced {orders_synced} orders for location {location.name}")
                    except Exception as e:
                        error_msg = f"Error syncing location {location.name}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            
            return {
                "success": True,
                "message": f"Successfully synced orders from {len(locations)} location(s)",
                "orders_synced": total_orders_synced,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error in fetch_and_save_orders: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "orders_synced": 0,
                "errors": [str(e)]
            }
    
    async def _sync_location_orders(
        self, 
        client: httpx.AsyncClient, 
        location: Location
    ) -> int:
        """Sync orders for a specific location"""
        
        # Get last synced order reference
        last_order_result = await self.db.execute(
            select(Order.reference)
            .where(Order.location_id == location.id)
            .order_by(desc(Order.reference))
            .limit(1)
        )
        last_order_reference = last_order_result.scalar_one_or_none() or 0
        
        # Get pagination info
        metadata_url = (
            f"{self.base_url}/orders?"
            f"sort=reference&"
            f"filter[reference_after]={last_order_reference}&"
            f"filter[branch_id]={location.foodics_guid}"
        )
        
        metadata_response = await client.get(metadata_url, headers=self.headers)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        
        total_pages = metadata.get("meta", {}).get("last_page", 0)
        
        if total_pages == 0:
            return 0
        
        orders_synced = 0
        rate_limit = 30  # Process in batches
        
        for page in range(1, total_pages + 1):
            try:
                # Fetch orders page
                orders_url = (
                    f"{self.base_url}/orders?"
                    f"sort=reference&"
                    f"include=products.product&"
                    f"filter[reference_after]={last_order_reference}&"
                    f"filter[branch_id]={location.foodics_guid}&"
                    f"page={page}"
                )
                
                response = await client.get(orders_url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                orders_data = data.get("data", [])
                if not orders_data:
                    continue
                
                # Process orders
                for order_data in orders_data:
                    await self._process_order(order_data, location)
                    orders_synced += 1
                
                # Commit in batches
                if page % rate_limit == 0 or page == total_pages:
                    await self.db.commit()
                    await asyncio.sleep(1)  # Rate limiting
                    
            except Exception as e:
                logger.error(f"Error processing page {page}: {str(e)}")
                await self.db.rollback()
                raise
        
        return orders_synced
    
    async def _process_order(self, order_data: Dict[str, Any], location: Location):
        """Process a single order from Foodics"""
        
        # Check if order already exists
        existing_order = await self.db.execute(
            select(Order).where(
                Order.foodics_guid == UUID(order_data["id"])
            )
        )
        if existing_order.scalar_one_or_none():
            return  # Skip if already processed
        
        # Parse dates with timezone adjustment (+3 hours as in C# code)
        def parse_date(date_str: Optional[str], add_hours: int = 0) -> Optional[datetime]:
            if not date_str:
                return None
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if add_hours:
                    dt = dt + timedelta(hours=add_hours)
                return dt
            except:
                return None
        
        # Create order
        order = Order(
            foodics_guid=UUID(order_data["id"]),
            app_id=UUID(order_data.get("app_id")) if order_data.get("app_id") else None,
            promotion_id=UUID(order_data.get("promotion_id")) if order_data.get("promotion_id") else None,
            order_number=f"FD-{order_data['reference']}",
            reference=order_data.get("reference", 0),
            reference_x=order_data.get("reference_x"),
            check_number=order_data.get("check_number", 0),
            order_type=order_data.get("type", 0),
            source=order_data.get("source", 0),
            status=order_data.get("status", 0),
            delivery_status=order_data.get("delivery_status"),
            guests=order_data.get("guests", 0),
            discount_type=order_data.get("discount_type"),
            subtotal_price=Decimal(str(order_data.get("subtotal_price", 0))),
            discount_amount=Decimal(str(order_data.get("discount_amount", 0))),
            rounding_amount=Decimal(str(order_data.get("rounding_amount", 0))),
            total_price=Decimal(str(order_data.get("total_price", 0))),
            tax_exclusive_discount_amount=Decimal(str(order_data.get("tax_exclusive_discount_amount", 0))),
            kitchen_notes=order_data.get("kitchen_notes"),
            customer_notes=order_data.get("customer_notes"),
            business_date=datetime.fromisoformat(order_data["business_date"]).date() if order_data.get("business_date") else datetime.now().date(),
            opened_at=parse_date(order_data.get("opened_at"), 3),
            accepted_at=parse_date(order_data.get("accepted_at")),
            due_at=parse_date(order_data.get("due_at")),
            driver_assigned_at=parse_date(order_data.get("driver_assigned_at")),
            dispatched_at=parse_date(order_data.get("dispatched_at")),
            driver_collected_at=parse_date(order_data.get("driver_collected_at")),
            delivered_at=parse_date(order_data.get("delivered_at")),
            closed_at=parse_date(order_data.get("closed_at"), 3),
            location_id=location.id
        )
        
        self.db.add(order)
        await self.db.flush()  # Get order.id
        
        # Process order products
        products_data = order_data.get("products", [])
        for product_data in products_data:
            await self._process_order_product(
                product_data, 
                order, 
                location
            )
    
    async def _process_order_product(
        self, 
        product_data: Dict[str, Any], 
        order: Order, 
        location: Location
    ):
        """Process a single order product and deduct inventory"""
        
        product_info = product_data.get("product", {})
        if not product_info:
            return
        
        foodics_product_guid = UUID(product_info["id"])
        quantity = Decimal(str(product_data.get("quantity", 0)))
        
        # Find matching product in our system
        product_result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.product_items).selectinload(ProductItem.item))
            .where(Product.product_guid == foodics_product_guid)
        )
        product = product_result.scalar_one_or_none()
        
        # Create order product record
        order_product = OrderProduct(
            order_id=order.id,
            product_id=product.id if product else None,
            foodics_product_guid=foodics_product_guid,
            product_name=product_info.get("name", "Unknown Product"),
            quantity=quantity,
            unit_price=Decimal(str(product_data.get("unit_price", 0))),
            total_price=Decimal(str(product_data.get("total_price", 0))),
            discount_amount=Decimal(str(product_data.get("discount_amount", 0)))
        )
        
        self.db.add(order_product)
        
        # Deduct inventory if order is not cancelled (status != 7)
        if order.status != 7 and product:
            await self._deduct_inventory(product, quantity, location, order)
    
    async def _deduct_inventory(
        self, 
        product: Product, 
        quantity: Decimal, 
        location: Location, 
        order: Order
    ):
        """
        Deduct inventory for product items (ingredients).
        Similar to the C# code's inventory deduction logic.
        """
        
        for product_item in product.product_items:
            if not product_item.item:
                continue
            
            # Calculate total quantity to deduct
            # quantity = number of products ordered
            # product_item.quantity = amount of ingredient per product
            total_deduction = product_item.quantity * quantity
            
            # Get stock level for this item at this location
            stock_result = await self.db.execute(
                select(StockLevel).where(
                    and_(
                        StockLevel.item_id == product_item.item_id,
                        StockLevel.location_id == location.id
                    )
                )
            )
            stock_level = stock_result.scalar_one_or_none()
            
            if not stock_level:
                logger.warning(
                    f"No stock level found for item {product_item.item.name} "
                    f"at location {location.name}"
                )
                continue
            
            # Record stock movement (OUTBOUND)
            stock_movement = StockMovement(
                item_id=product_item.item_id,
                location_id=location.id,
                movement_type=StockMovementType.OUTBOUND,
                quantity=total_deduction,
                unit_cost=product_item.item.unit_cost,
                total_cost=product_item.item.unit_cost * total_deduction if product_item.item.unit_cost else None,
                reference_type="ORDER",
                reference_id=order.id,
                remarks=f"Deducted for order {order.order_number} - Product: {product.name}",
                performed_by=None  # System generated
            )
            
            self.db.add(stock_movement)
            
            # Update stock level
            stock_level.current_stock -= total_deduction
            stock_level.available_stock = stock_level.current_stock - stock_level.reserved_stock
            
            # Optional: Check if below minimum and send alert
            if (stock_level.current_stock < stock_level.par_level_min and 
                stock_level.par_level_min > 0):
                logger.warning(
                    f"Low stock alert: {product_item.item.name} at {location.name} "
                    f"is below minimum level ({stock_level.current_stock} < {stock_level.par_level_min})"
                )
                # You could implement notification logic here
    
    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """Get order with all relationships"""
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.location),
                selectinload(Order.order_products).selectinload(OrderProduct.product)
            )
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def get_orders(
        self,
        page_index: int = 1,
        page_size: int = 100,
        location_id: Optional[int] = None,
        status: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get orders with pagination and filters"""
        
        query = select(Order).options(
            selectinload(Order.location),
            selectinload(Order.order_products).selectinload(OrderProduct.product)
        )
        
        filters = []
        
        if location_id:
            filters.append(Order.location_id == location_id)
        
        if status is not None:
            filters.append(Order.status == status)
        
        if start_date:
            filters.append(Order.business_date >= start_date.date())
        
        if end_date:
            filters.append(Order.business_date <= end_date.date())
        
        if filters:
            query = query.where(and_(*filters))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated data
        query = query.order_by(desc(Order.created_at))
        skip = (page_index - 1) * page_size
        query = query.offset(skip).limit(page_size)
        
        result = await self.db.execute(query)
        orders = result.scalars().unique().all()
        
        return {
            "page_index": page_index,
            "page_size": page_size,
            "count": total,
            "data": orders
        }