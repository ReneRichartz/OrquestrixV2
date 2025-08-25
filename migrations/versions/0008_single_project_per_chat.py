"""single project per chat

Revision ID: 0008_single_project_per_chat
Revises: 0007_extend_worker_log
Create Date: 2025-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = '0008_single_project_per_chat'
down_revision = '0007_extend_worker_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('chat')]
    if 'project_id' not in cols:
        op.add_column('chat', sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=True))
    if 'project_chat' in insp.get_table_names():
        op.drop_table('project_chat')


def downgrade() -> None:
    # Recreate M2M table
    op.create_table(
        'project_chat',
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), primary_key=True),
        sa.Column('chat_id', sa.Integer(), sa.ForeignKey('chat.id'), primary_key=True),
    )
    op.drop_column('chat', 'project_id')
