import logging
import sys
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def log_user_action(user_id: int, action: str, entity: str, entity_id: Any = None):
    """Log user actions for audit trail"""
    logger.info(f"User {user_id} performed {action} on {entity} {entity_id or ''}")
