"""Add promotions

Revision ID: 654321
Revises: 
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '654321'
down_revision = '35a259f1c4aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'promotions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.Enum('buy_x_get_y', 'free_shipping', 'percentage_on_category', name='promotion_type'), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('rewards', sa.JSON(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('promotions')
    op.execute('DROP TYPE promotion_type')
