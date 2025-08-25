"""add chat roles

Revision ID: 0003_add_chat_roles
Revises: 0002_add_size_bytes_and_vector_store_file
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_add_chat_roles'
down_revision = '0002_add_size_bytes_and_vector_store_file'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'chat_role',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False, server_default='gpt-4.5'),
        sa.Column('reasoning_effort', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('reasoning_summary', sa.String(length=20), nullable=False, server_default='auto'),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table('chat') as batch_op:
        batch_op.add_column(sa.Column('chat_role_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_chat_chat_role', 'chat_role', ['chat_role_id'], ['id'])

def downgrade():
    with op.batch_alter_table('chat') as batch_op:
        batch_op.drop_constraint('fk_chat_chat_role', type_='foreignkey')
        batch_op.drop_column('chat_role_id')
    op.drop_table('chat_role')