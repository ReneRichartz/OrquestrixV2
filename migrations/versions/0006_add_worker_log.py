"""add worker_log table

Revision ID: 0006_add_worker_log
Revises: 0005_drop_reasoning_columns
Create Date: 2025-08-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_add_worker_log'
down_revision = '0005_drop_reasoning_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schutz falls Tabelle durch create_all() bereits existiert
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if 'worker_log' not in insp.get_table_names():
        op.create_table(
            'worker_log',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('worker_id', sa.Integer(), sa.ForeignKey('worker.id'), nullable=False),
            sa.Column('input_text', sa.Text(), nullable=False),
            sa.Column('output_text', sa.Text(), nullable=True),
            sa.Column('openai_run_id', sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    op.drop_table('worker_log')
