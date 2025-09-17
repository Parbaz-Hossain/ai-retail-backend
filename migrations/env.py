import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, make_url
from sqlalchemy import pool
from alembic import context

# Add your model imports here
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.models.base import Base
from app.models.ai import ai_interaction, automation_log, automation_rule
from app.models.alerts import alert, notification_queue
from app.models.auth import audit_log, permission, refresh_token, role_permission, role, user_role, user
from app.models.communication import email_log, whatsapp_log
from app.models.hr import attendance, employee, holiday, salary, shift_type, user_shift, offday, deduction
from app. models.inventory import category, inventory_count_item, inventory_count, item, reorder_request_item, reorder_request, stock_analytics, stock_level, stock_movement, stock_type, transfer_item, transfer
from app.models.logistics import driver, shipment_item, shipment_tracking, shipment, vehicle
from app.models.organization import department, location
from app.models.purchase import goods_receipt_item, goods_receipt, item_supplier, purchase_order_item, purchase_order, supplier
from app.models.system import file_upload, performance_metrics, qr_code, system_setting
from app.models.engagement import faq, user_history, chat
from app.models.biometric import fingerprint
from app.models.task import task_type, task, task_comment, task_attachment, task_assignment
from app.core.config import settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from settings
if not config.get_main_option("sqlalchemy.url"):
    database_url = settings.DATABASE_URL.replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", str(make_url(database_url)))

print("🔍 Alembic is using DB URL:", config.get_main_option("sqlalchemy.url"))


target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Safety check for production environment
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    if environment == "production":
        print("🚨 PRODUCTION ENVIRONMENT DETECTED")
        if "downgrade" in sys.argv:
            raise RuntimeError("🚫 Downgrades are blocked in production!")
        try:
            revision = context.get_revision_argument()
            print("Migration target:", revision)
        except Exception:
            pass
        
        # Prevent accidental downgrades in production
        if context.is_offline_mode():
            raise RuntimeError("Offline migrations not allowed in production!")
            
        # Get current and target revisions
        # current_rev = context.get_current_revision()
        # target_rev = context.get_revision_argument()
        
        # if target_rev and current_rev and target_rev < current_rev:
        #     raise RuntimeError(
        #         f"🚨 DOWNGRADE PREVENTED: Cannot downgrade from {current_rev} to {target_rev} in production!"
        #     )
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()