from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func
from app.models.inventory.stock_analytics import StockAnalytics
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.stock_movement import StockMovement
from app.models.organization.location import Location
from app.models.shared.enums import StockMovementType
from datetime import datetime, date, timedelta

class StockAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_inventory_dashboard(self, location_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive inventory dashboard data"""
        # Total items and stock value
        stock_query = select(
            func.count(StockLevel.id).label('total_items'),
            func.sum(StockLevel.current_stock * Item.unit_cost).label('total_value'),
            func.sum(StockLevel.current_stock).label('total_quantity'),
            func.sum(StockLevel.reserved_stock).label('total_reserved')
        ).join(Item).where(Item.is_active == True)
        
        if location_id:
            stock_query = stock_query.where(StockLevel.location_id == location_id)
            
        stock_result = await self.db.execute(stock_query)
        stock_data = stock_result.first()

        # Low stock items
        low_stock_query = select(func.count(StockLevel.id)).join(Item).where(
            and_(
                Item.is_active == True,
                StockLevel.current_stock <= Item.reorder_point,
                Item.reorder_point > 0
            )
        )
        
        if location_id:
            low_stock_query = low_stock_query.where(StockLevel.location_id == location_id)
            
        low_stock_result = await self.db.execute(low_stock_query)
        low_stock_count = low_stock_result.scalar()

        # Out of stock items
        out_of_stock_query = select(func.count(StockLevel.id)).join(Item).where(
            and_(
                Item.is_active == True,
                StockLevel.current_stock == 0
            )
        )
        
        if location_id:
            out_of_stock_query = out_of_stock_query.where(StockLevel.location_id == location_id)
            
        out_of_stock_result = await self.db.execute(out_of_stock_query)
        out_of_stock_count = out_of_stock_result.scalar()

        # Recent movements (last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        movement_query = select(
            StockMovement.movement_type,
            func.count(StockMovement.id).label('count'),
            func.sum(StockMovement.quantity).label('total_quantity')
        ).where(
            StockMovement.movement_date >= thirty_days_ago
        ).group_by(StockMovement.movement_type)
        
        if location_id:
            movement_query = movement_query.where(StockMovement.location_id == location_id)
            
        movement_result = await self.db.execute(movement_query)
        movement_data = {row.movement_type.value: {
            'count': row.count,
            'quantity': float(row.total_quantity)
        } for row in movement_result.all()}

        return {
            'overview': {
                'total_items': stock_data.total_items or 0,
                'total_value': float(stock_data.total_value or 0),
                'total_quantity': float(stock_data.total_quantity or 0),
                'total_reserved': float(stock_data.total_reserved or 0),
                'low_stock_items': low_stock_count or 0,
                'out_of_stock_items': out_of_stock_count or 0
            },
            'recent_movements': movement_data,
            'generated_at': datetime.utcnow().isoformat()
        }

    async def get_turnover_analysis(
        self, 
        location_id: Optional[int] = None,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """Calculate inventory turnover rates"""
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()

        # Get outbound movements in the period
        outbound_query = select(
            StockMovement.item_id,
            func.sum(StockMovement.quantity).label('total_outbound'),
            func.avg(StockLevel.current_stock).label('avg_stock')
        ).join(StockLevel, StockLevel.item_id == StockMovement.item_id).where(
            and_(
                StockMovement.movement_type == StockMovementType.OUTBOUND,
                StockMovement.movement_date >= start_date,
                StockMovement.movement_date <= end_date
            )
        ).group_by(StockMovement.item_id, StockLevel.current_stock)
        
        if location_id:
            outbound_query = outbound_query.where(
                and_(
                    StockMovement.location_id == location_id,
                    StockLevel.location_id == location_id
                )
            )

        result = await self.db.execute(outbound_query)
        turnover_data = []
        
        for row in result.all():
            if row.avg_stock and row.avg_stock > 0:
                # Calculate turnover rate (outbound quantity / average stock)
                days_in_period = (end_date - start_date).days
                turnover_rate = (row.total_outbound / row.avg_stock) * (365 / days_in_period)
                
                # Get item details
                item_result = await self.db.execute(
                    select(Item).where(Item.id == row.item_id)
                )
                item = item_result.scalar_one_or_none()
                
                if item:
                    turnover_data.append({
                        'item_id': row.item_id,
                        'item_name': item.name,
                        'item_code': item.item_code,
                        'total_outbound': float(row.total_outbound),
                        'avg_stock': float(row.avg_stock),
                        'turnover_rate': float(turnover_rate),
                        'turnover_category': self._classify_turnover(turnover_rate)
                    })

        # Sort by turnover rate
        turnover_data.sort(key=lambda x: x['turnover_rate'], reverse=True)

        return {
            'analysis_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'turnover_analysis': turnover_data,
            'summary': {
                'total_items_analyzed': len(turnover_data),
                'fast_moving': len([x for x in turnover_data if x['turnover_category'] == 'FAST']),
                'medium_moving': len([x for x in turnover_data if x['turnover_category'] == 'MEDIUM']),
                'slow_moving': len([x for x in turnover_data if x['turnover_category'] == 'SLOW'])
            }
        }

    def _classify_turnover(self, turnover_rate: float) -> str:
        """Classify turnover rate"""
        if turnover_rate >= 6:  # More than 6 times per year
            return "FAST"
        elif turnover_rate >= 2:  # 2-6 times per year
            return "MEDIUM"
        else:  # Less than 2 times per year
            return "SLOW"

    async def get_stock_valuation(
        self,
        location_id: Optional[int] = None,
        valuation_date: date = None
    ) -> Dict[str, Any]:
        """Get current stock valuation"""
        if not valuation_date:
            valuation_date = date.today()

        # Build explicit query
        valuation_query = (
            select(
                Item.id,
                Item.name,
                Item.item_code,
                Item.unit_cost,
                StockLevel.current_stock,
                (StockLevel.current_stock * Item.unit_cost).label("total_value"),
                Location.name.label("location_name"),
            )
            .select_from(Item)
            .join(StockLevel, StockLevel.item_id == Item.id)
            .join(Location, Location.id == StockLevel.location_id)
            .where(
                and_(
                    Item.is_active.is_(True),
                    StockLevel.current_stock > 0,
                    Item.unit_cost.isnot(None),
                )
            )
        )

        if location_id:
            valuation_query = valuation_query.where(StockLevel.location_id == location_id)

        result = await self.db.execute(valuation_query)

        valuation_data = []
        total_value = 0.0

        for row in result.all():
            item_value = float(row.current_stock * (row.unit_cost or 0))
            total_value += item_value

            valuation_data.append({
                "item_id": row.id,
                "item_name": row.name,
                "item_code": row.item_code,
                "unit_cost": float(row.unit_cost or 0),
                "current_stock": float(row.current_stock),
                "total_value": item_value,
                "location_name": row.location_name if not location_id else None,
            })

        # Sort by total value descending
        valuation_data.sort(key=lambda x: x["total_value"], reverse=True)

        return {
            "valuation_date": valuation_date.isoformat(),
            "total_stock_value": total_value,
            "item_count": len(valuation_data),
            "items": valuation_data,
            "top_10_by_value": valuation_data[:10],
        }
    
    async def get_stock_aging_analysis(self, location_id: Optional[int] = None) -> Dict[str, Any]:
        """Analyze stock aging based on last movement dates"""
        # This is a simplified version - in a real system, you'd track batch dates
        aging_query = select(
            Item.id,
            Item.name,
            Item.item_code,
            StockLevel.current_stock,
            func.max(StockMovement.movement_date).label('last_movement_date')
        ).join(StockLevel).outerjoin(StockMovement, and_(
            StockMovement.item_id == Item.id,
            StockMovement.location_id == StockLevel.location_id
        )).where(
            and_(
                Item.is_active == True,
                StockLevel.current_stock > 0
            )
        ).group_by(Item.id, Item.name, Item.item_code, StockLevel.current_stock)
        
        if location_id:
            aging_query = aging_query.where(StockLevel.location_id == location_id)

        result = await self.db.execute(aging_query)
        
        aging_data = []
        today = date.today()
        
        for row in result.all():
            last_movement = row.last_movement_date.date() if row.last_movement_date else None
            days_since_movement = (today - last_movement).days if last_movement else None
            
            aging_category = "UNKNOWN"
            if days_since_movement is not None:
                if days_since_movement <= 30:
                    aging_category = "0-30_DAYS"
                elif days_since_movement <= 60:
                    aging_category = "31-60_DAYS"
                elif days_since_movement <= 90:
                    aging_category = "61-90_DAYS"
                else:
                    aging_category = "90+_DAYS"
            
            aging_data.append({
                'item_id': row.id,
                'item_name': row.name,
                'item_code': row.item_code,
                'current_stock': float(row.current_stock),
                'last_movement_date': last_movement.isoformat() if last_movement else None,
                'days_since_movement': days_since_movement,
                'aging_category': aging_category
            })

        # Group by aging category
        aging_summary = {}
        for item in aging_data:
            category = item['aging_category']
            if category not in aging_summary:
                aging_summary[category] = {'count': 0, 'total_stock': 0}
            aging_summary[category]['count'] += 1
            aging_summary[category]['total_stock'] += item['current_stock']

        return {
            'analysis_date': today.isoformat(),
            'aging_summary': aging_summary,
            'detailed_aging': aging_data
        }

    async def get_movement_trends(
        self, 
        location_id: Optional[int] = None,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """Get stock movement trends over time"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        # Daily movement trends
        daily_query = select(
            func.date(StockMovement.movement_date).label('movement_date'),
            StockMovement.movement_type,
            func.sum(StockMovement.quantity).label('total_quantity'),
            func.count(StockMovement.id).label('movement_count')
        ).where(
            and_(
                StockMovement.movement_date >= start_date,
                StockMovement.movement_date <= end_date
            )
        ).group_by(
            func.date(StockMovement.movement_date),
            StockMovement.movement_type
        ).order_by(func.date(StockMovement.movement_date))
        
        if location_id:
            daily_query = daily_query.where(StockMovement.location_id == location_id)

        result = await self.db.execute(daily_query)
        
        daily_trends = {}
        for row in result.all():
            date_str = row.movement_date.isoformat()
            movement_type = row.movement_type.value
            
            if date_str not in daily_trends:
                daily_trends[date_str] = {}
            
            daily_trends[date_str][movement_type] = {
                'quantity': float(row.total_quantity),
                'count': row.movement_count
            }

        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'daily_trends': daily_trends
        }

    async def generate_daily_analytics(self, analytics_date: date, location_id: Optional[int] = None) -> int:
        """Generate daily stock analytics records"""
        # This would typically be run as a daily job
        # Get all items with stock levels
        items_query = select(Item, StockLevel).join(StockLevel).where(
            Item.is_active == True
        )
        
        if location_id:
            items_query = items_query.where(StockLevel.location_id == location_id)

        items_result = await self.db.execute(items_query)
        
        records_created = 0
        for item, stock_level in items_result.all():
            # Check if record already exists
            existing = await self.db.execute(
                select(StockAnalytics).where(and_(
                    StockAnalytics.item_id == item.id,
                    StockAnalytics.location_id == stock_level.location_id,
                    StockAnalytics.date == analytics_date
                ))
            )
            
            if existing.scalar_one_or_none():
                continue  # Skip if already exists

            # Calculate daily movements
            movements_result = await self.db.execute(
                select(
                    func.sum(
                        func.case((StockMovement.movement_type == StockMovementType.INBOUND, StockMovement.quantity), else_=0)
                    ).label('inbound'),
                    func.sum(
                        func.case((StockMovement.movement_type == StockMovementType.OUTBOUND, StockMovement.quantity), else_=0)
                    ).label('outbound'),
                    func.sum(
                        func.case((StockMovement.movement_type == StockMovementType.TRANSFER, StockMovement.quantity), else_=0)
                    ).label('transfers'),
                    func.sum(
                        func.case((StockMovement.movement_type == StockMovementType.ADJUSTMENT, StockMovement.quantity), else_=0)
                    ).label('adjustments'),
                    func.sum(
                        func.case((StockMovement.movement_type.in_([StockMovementType.WASTE, StockMovementType.DAMAGE]), StockMovement.quantity), else_=0)
                    ).label('waste')
                ).where(and_(
                    StockMovement.item_id == item.id,
                    StockMovement.location_id == stock_level.location_id,
                    func.date(StockMovement.movement_date) == analytics_date
                ))
            )
            
            movements = movements_result.first()

            # Calculate stock value
            stock_value = stock_level.current_stock * (item.unit_cost or 0)

            # Create analytics record
            analytics_record = StockAnalytics(
                item_id=item.id,
                location_id=stock_level.location_id,
                date=analytics_date,
                opening_stock=stock_level.current_stock,  # Simplified - should be calculated
                closing_stock=stock_level.current_stock,
                total_inbound=movements.inbound or 0,
                total_outbound=movements.outbound or 0,
                total_transfers_in=0,  # Would need more complex calculation
                total_transfers_out=0,
                total_adjustments=movements.adjustments or 0,
                total_waste=movements.waste or 0,
                stock_value=stock_value,
                created_by=1,  # System user
                updated_by=1
            )
            
            self.db.add(analytics_record)
            records_created += 1

        await self.db.commit()
        return records_created
