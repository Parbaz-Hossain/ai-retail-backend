"""add action type in approval member & setting

Revision ID: f5bef56e33e0
Revises: 244d062746c2
Create Date: 2025-10-25 18:41:29.602904
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'f5bef56e33e0'
down_revision: Union[str, None] = '244d062746c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    
    # Check and add action_types to approval_members
    columns = [col['name'] for col in inspector.get_columns('approval_members')]
    if 'action_types' not in columns:
        op.add_column('approval_members', sa.Column('action_types', sa.JSON(), nullable=True))
        print("✓ [f5bef56e33e0] Added action_types to approval_members")
    else:
        print("✓ [f5bef56e33e0] action_types already exists - skipping")
    
    # Check and add columns to approval_settings
    columns = [col['name'] for col in inspector.get_columns('approval_settings')]
    
    if 'module' not in columns:
        op.add_column('approval_settings', sa.Column('module', sa.String(length=50), nullable=True))
        print("✓ [f5bef56e33e0] Added module to approval_settings")
    else:
        print("✓ [f5bef56e33e0] module already exists - skipping")
    
    if 'action_type' not in columns:
        op.add_column('approval_settings', sa.Column('action_type', 
            sa.Enum('SHIFT', 'SALARY', 'DAYOFF', 'EMPLOYEE', 'ATTENDANCE', 'EMPLOYEE_DEDUCTION', 
                    name='approvalrequesttype'), nullable=True))
        print("✓ [f5bef56e33e0] Added action_type to approval_settings")
    else:
        print("✓ [f5bef56e33e0] action_type already exists - skipping")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    
    columns = [col['name'] for col in inspector.get_columns('approval_settings')]
    if 'action_type' in columns:
        op.drop_column('approval_settings', 'action_type')
    if 'module' in columns:
        op.drop_column('approval_settings', 'module')
    
    columns = [col['name'] for col in inspector.get_columns('approval_members')]
    if 'action_types' in columns:
        op.drop_column('approval_members', 'action_types')