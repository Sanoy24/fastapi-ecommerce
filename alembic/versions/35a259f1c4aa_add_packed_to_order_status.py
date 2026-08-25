"""Add packed to order status

Revision ID: 35a259f1c4aa
Revises: a40c41319686
Create Date: 2026-08-26 00:02:32.887269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35a259f1c4aa'
down_revision: Union[str, Sequence[str], None] = 'a40c41319686'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This requires autocommit since ADD VALUE cannot be executed in a transaction block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'packed'")

def downgrade() -> None:
    pass
