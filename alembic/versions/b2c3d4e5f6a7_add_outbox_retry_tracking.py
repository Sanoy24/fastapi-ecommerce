"""Add retry tracking to outbox events

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'outbox_events',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'outbox_events',
        sa.Column('next_attempt_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('outbox_events', 'next_attempt_at')
    op.drop_column('outbox_events', 'retry_count')
