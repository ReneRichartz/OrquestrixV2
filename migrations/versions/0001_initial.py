"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # This represents the original tables before new features
    pass

def downgrade():
    pass