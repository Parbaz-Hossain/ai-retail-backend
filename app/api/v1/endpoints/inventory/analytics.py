from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from datetime import date, timedelta
from app.core.database import get_async_session
from app.services.inventory.stock_analytics_service import StockAnalyticsService

router = APIRouter()

@router.get("/dashboard")
async def get_inventory_dashboard(
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """Get comprehensive inventory dashboard data"""
    service = StockAnalyticsService(db)
    dashboard = await service.get_inventory_dashboard(location_id)
    return dashboard

@router.get("/turnover-analysis")
async def get_turnover_analysis(
    location_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """Get inventory turnover analysis"""
    service = StockAnalyticsService(db)
    
    if not start_date:
        start_date = date.today() - timedelta(days=90)
    if not end_date:
        end_date = date.today()
        
    analysis = await service.get_turnover_analysis(location_id, start_date, end_date)
    return analysis

@router.get("/stock-valuation")
async def get_stock_valuation(
    location_id: Optional[int] = Query(None),
    valuation_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """Get current stock valuation"""
    service = StockAnalyticsService(db)
    
    if not valuation_date:
        valuation_date = date.today()
        
    valuation = await service.get_stock_valuation(location_id, valuation_date)
    return valuation

@router.get("/aging-analysis")
async def get_stock_aging_analysis(
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """Get stock aging analysis"""
    service = StockAnalyticsService(db)
    aging = await service.get_stock_aging_analysis(location_id)
    return aging

@router.get("/movement-trends")
async def get_movement_trends(
    location_id: Optional[int] = Query(None),
    period_days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """Get stock movement trends"""
    service = StockAnalyticsService(db)
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)
    
    trends = await service.get_movement_trends(location_id, start_date, end_date)
    return trends

@router.post("/generate-daily-analytics")
async def generate_daily_analytics(
    analytics_date: Optional[date] = Query(None),
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """Generate daily stock analytics data"""
    service = StockAnalyticsService(db)
    
    if not analytics_date:
        analytics_date = date.today() - timedelta(days=1)  # Previous day
        
    result = await service.generate_daily_analytics(analytics_date, location_id)
    return {"message": f"Generated analytics for {analytics_date}", "records_created": result} 
