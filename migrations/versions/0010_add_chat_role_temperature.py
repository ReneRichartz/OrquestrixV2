"""add chat_role temperature column

Revision ID: 0010_add_chat_role_temperature
Revises: 0009_file_vector_cache
Create Date: 2025-08-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_add_chat_role_temperature'
down_revision = '0009_file_vector_cache'
branch_labels = None
depends_on = None

def upgrade():
    # Nur hinzufügen falls nicht vorhanden (idempotent Schutz für manuelle DBs)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('chat_role')]
    if 'temperature' not in cols:
        with op.batch_alter_table('chat_role') as batch_op:
            batch_op.add_column(sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'))
        # server_default entfernen damit zukünftige Inserts ORM Default nutzen können
        with op.batch_alter_table('chat_role') as batch_op:
            batch_op.alter_column('temperature', server_default=None)


def downgrade():
    with op.batch_alter_table('chat_role') as batch_op:
        batch_op.drop_column('temperature')
