"""drop temperature columns

Revision ID: 0004_drop_temperature_columns
Revises: 0003_add_chat_roles
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_drop_temperature_columns'
down_revision = '0003_add_chat_roles'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('assistant') as batch_op:
        batch_op.drop_column('temperature')
    with op.batch_alter_table('chat_role') as batch_op:
        batch_op.drop_column('temperature')


def downgrade():
    with op.batch_alter_table('assistant') as batch_op:
        batch_op.add_column(sa.Column('temperature', sa.Float(), nullable=True))
    with op.batch_alter_table('chat_role') as batch_op:
        batch_op.add_column(sa.Column('temperature', sa.Float(), nullable=True))
