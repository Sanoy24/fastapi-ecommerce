"""Add product_relations.is_auto_generated

Revision ID: 00e06bbcd509
Revises: f6a7b8c9d0e1
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00e06bbcd509'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'product_relations',
        sa.Column(
            'is_auto_generated', sa.Boolean(), nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    op.drop_column('product_relations', 'is_auto_generated')
