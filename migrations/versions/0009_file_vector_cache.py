"""add file vector cache columns

Revision ID: 0009_file_vector_cache
Revises: 0008_single_project_per_chat
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_file_vector_cache'
down_revision = '0008_single_project_per_chat'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('file')]
    if 'in_vector_store' not in cols:
        op.add_column('file', sa.Column('in_vector_store', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.execute("UPDATE file SET in_vector_store = 0")
    if 'vector_store_ids_cache' not in cols:
        op.add_column('file', sa.Column('vector_store_ids_cache', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('file')]
    if 'vector_store_ids_cache' in cols:
        op.drop_column('file', 'vector_store_ids_cache')
    if 'in_vector_store' in cols:
        op.drop_column('file', 'in_vector_store')
