"""Add last activity to cart

Revision ID: 765432
Revises: 654321
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '765432'
down_revision = '654321'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('carts', sa.Column('last_activity_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))


def downgrade() -> None:
    op.drop_column('carts', 'last_activity_at')
