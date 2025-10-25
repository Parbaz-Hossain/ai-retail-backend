"""rename_offday_to_dayoff_in_approval_request_type

Revision ID: 935675deff8e
Revises: d86da62d7802
Create Date: 2025-10-23 19:11:27.911745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '935675deff8e'
down_revision: Union[str, None] = 'd86da62d7802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Add the new enum value 'DAYOFF' to the existing enum type
    connection = op.get_bind()
    
    # We need to commit this change before we can use the new value
    connection.execute(sa.text("ALTER TYPE approvalrequesttype ADD VALUE IF NOT EXISTS 'DAYOFF'"))
    # connection.commit()
    
    # Step 2: Now update existing data (now 'DAYOFF' is a valid value and committed)
    op.execute("""
        UPDATE approval_requests 
        SET request_type = 'DAYOFF' 
        WHERE request_type = 'OFFDAY'
    """)
    
    # Step 3: Convert column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE approval_requests 
        ALTER COLUMN request_type TYPE VARCHAR(50)
    """)
    
    # Step 4: Drop the old enum type
    op.execute("DROP TYPE approvalrequesttype")
    
    # Step 5: Create the new enum type without 'OFFDAY'
    op.execute("""
        CREATE TYPE approvalrequesttype AS ENUM ('SHIFT', 'SALARY', 'DAYOFF')
    """)
    
    # Step 6: Convert the column back to enum type
    op.execute("""
        ALTER TABLE approval_requests 
        ALTER COLUMN request_type TYPE approvalrequesttype 
        USING request_type::approvalrequesttype
    """)


def downgrade():
    # Step 1: Convert to VARCHAR
    op.execute("""
        ALTER TABLE approval_requests 
        ALTER COLUMN request_type TYPE VARCHAR(50)
    """)
    
    # Step 2: Drop the current enum type
    op.execute("DROP TYPE approvalrequesttype")
    
    # Step 3: Recreate enum with 'OFFDAY'
    op.execute("""
        CREATE TYPE approvalrequesttype AS ENUM ('SHIFT', 'SALARY', 'OFFDAY')
    """)
    
    # Step 4: Convert back to enum
    op.execute("""
        ALTER TABLE approval_requests 
        ALTER COLUMN request_type TYPE approvalrequesttype 
        USING request_type::approvalrequesttype
    """)
    
    # Step 5: Update data back to 'OFFDAY'
    op.execute("""
        UPDATE approval_requests 
        SET request_type = 'OFFDAY' 
        WHERE request_type = 'DAYOFF'
    """)