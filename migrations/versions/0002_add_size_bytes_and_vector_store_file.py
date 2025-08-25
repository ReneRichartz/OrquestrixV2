"""add size_bytes and vector_store_file

Revision ID: 0002_add_size_bytes_and_vector_store_file
Revises: 0001_initial
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_add_size_bytes_and_vector_store_file'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('file', schema=None) as batch_op:
        batch_op.add_column(sa.Column('size_bytes', sa.Integer(), nullable=True))
    op.create_table('vector_store_file',
        sa.Column('vector_store_id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['file.id'], ),
        sa.ForeignKeyConstraint(['vector_store_id'], ['vector_store.id'], ),
        sa.PrimaryKeyConstraint('vector_store_id', 'file_id')
    )

def downgrade():
    op.drop_table('vector_store_file')
    with op.batch_alter_table('file', schema=None) as batch_op:
        batch_op.drop_column('size_bytes')