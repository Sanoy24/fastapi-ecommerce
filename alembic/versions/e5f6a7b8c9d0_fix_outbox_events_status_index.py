"""Fix outbox_events status index drift

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-12 00:00:00.000000

e71d0e330657 (add_auditlog_and_performance_indexes) created an index named
'ix_outbox_events_status' — the name SQLAlchemy's naming convention would
generate for the model's `status: Mapped[str] = mapped_column(...,
index=True)` single-column index — but gave it the wrong column list,
['status', 'created_at']. That's a copy-paste duplicate of
'ix_outbox_events_status_created' (created separately in the genesis
migration, matching the model's __table_args__ composite Index), not the
single-column index the name implies.

Net effect on any database that has run both migrations: two physically
identical (status, created_at) composite indexes under different names —
wasted disk space and extra write overhead maintaining both, on every
single insert or update to the table — and the actual single-column
`status` index the model has declared this whole time was never created
at all.

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_outbox_events_status', table_name='outbox_events')
    op.create_index('ix_outbox_events_status', 'outbox_events', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_outbox_events_status', table_name='outbox_events')
    op.create_index(
        'ix_outbox_events_status', 'outbox_events', ['status', 'created_at'], unique=False
    )
