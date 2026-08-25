"""Add MFA fields

Revision ID: a40c41319686
Revises: 59ff5edac949
Create Date: 2026-08-25 23:58:56.788498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a40c41319686'
down_revision: Union[str, Sequence[str], None] = '59ff5edac949'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('totp_secret', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), server_default='0', nullable=False))

def downgrade() -> None:
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'totp_secret')
