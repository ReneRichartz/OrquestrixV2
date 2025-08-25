"""drop reasoning columns

Revision ID: 0005_drop_reasoning_columns
Revises: 0004_drop_temperature_columns
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_drop_reasoning_columns'
down_revision = '0004_drop_temperature_columns'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('chat') as batch_op:
        batch_op.drop_column('reasoning_effort')
        batch_op.drop_column('reasoning_summary')
    with op.batch_alter_table('chat_role') as batch_op:
        batch_op.drop_column('reasoning_effort')
        batch_op.drop_column('reasoning_summary')


def downgrade():
    with op.batch_alter_table('chat') as batch_op:
        batch_op.add_column(sa.Column('reasoning_effort', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('reasoning_summary', sa.String(length=20), nullable=True))
    with op.batch_alter_table('chat_role') as batch_op:
        batch_op.add_column(sa.Column('reasoning_effort', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('reasoning_summary', sa.String(length=20), nullable=True))
