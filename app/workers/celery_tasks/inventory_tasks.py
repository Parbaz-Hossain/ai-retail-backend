from celery import current_task
import logging
from app.core.celery_app import celery_app
from app.services.inventory.stock_service import StockService
from app.services.email.email_service import EmailService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def check_low_stock_alerts(self):
    """Check for low stock items and send alerts"""
    try:
        logger.info("🔍 Checking for low stock items...")
        
        stock_service = StockService()
        email_service = EmailService()
        
        # Get low stock items
        low_stock_items = stock_service.get_low_stock_items_sync()
        
        if low_stock_items:
            logger.warning(f"⚠️ Found {len(low_stock_items)} low stock items")
            
            # Send email alert
            email_service.send_low_stock_alert(low_stock_items)
            
            # Create automatic reorder requests for critical items
            critical_items = [item for item in low_stock_items if item.current_stock == 0]
            if critical_items:
                logger.critical(f"🚨 {len(critical_items)} items are out of stock!")
                # Auto-create reorder requests
                # Implementation would go here
        
        return {
            "status": "completed",
            "low_stock_count": len(low_stock_items),
            "message": f"Processed {len(low_stock_items)} low stock items"
        }
        
    except Exception as e:
        logger.error(f"❌ Error in low stock check: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)

@celery_app.task(bind=True)
def process_inventory_count(self, inventory_count_id: int):
    """Process inventory count adjustments"""
    try:
        logger.info(f"📊 Processing inventory count {inventory_count_id}")
        
        # Implementation for processing inventory count
        # This would typically involve:
        # 1. Calculate variances
        # 2. Create stock adjustments
        # 3. Update stock levels
        # 4. Generate reports
        
        return {
            "status": "completed",
            "inventory_count_id": inventory_count_id,
            "message": "Inventory count processed successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing inventory count: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)