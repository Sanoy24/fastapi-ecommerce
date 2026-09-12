"""Add back_in_stock_subscriptions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'back_in_stock_subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_back_in_stock_subscriptions_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'],
            name=op.f('fk_back_in_stock_subscriptions_product_id_products'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['variant_id'], ['product_variants.id'],
            name=op.f('fk_back_in_stock_subscriptions_variant_id_product_variants'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_back_in_stock_subscriptions')),
        sa.UniqueConstraint(
            'user_id', 'product_id', 'variant_id',
            name='uq_back_in_stock_subscription',
        ),
    )
    op.create_index(
        op.f('ix_back_in_stock_subscriptions_product_id'),
        'back_in_stock_subscriptions', ['product_id'],
    )
    op.create_index(
        op.f('ix_back_in_stock_subscriptions_user_id'),
        'back_in_stock_subscriptions', ['user_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_back_in_stock_subscriptions_user_id'), 'back_in_stock_subscriptions')
    op.drop_index(op.f('ix_back_in_stock_subscriptions_product_id'), 'back_in_stock_subscriptions')
    op.drop_table('back_in_stock_subscriptions')
