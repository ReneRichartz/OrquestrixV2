"""extend worker_log with status and output files

Revision ID: 0007_extend_worker_log
Revises: 0006_add_worker_log
Create Date: 2025-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = '0007_extend_worker_log'
down_revision = '0006_add_worker_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: nur hinzufügen, falls Spalten fehlen (Schutz vor vorherigem create_all())
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('worker_log')]
    if 'run_status' not in cols:
        op.add_column('worker_log', sa.Column('run_status', sa.String(length=50), nullable=True))
    if 'output_file_ids' not in cols:
        op.add_column('worker_log', sa.Column('output_file_ids', sa.Text(), nullable=True))


def downgrade() -> None:
    # Ebenfalls defensiv droppen
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('worker_log')]
    if 'output_file_ids' in cols:
        op.drop_column('worker_log', 'output_file_ids')
    if 'run_status' in cols:
        op.drop_column('worker_log', 'run_status')
