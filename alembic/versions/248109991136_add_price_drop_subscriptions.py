"""Add price_drop_subscriptions

Revision ID: 248109991136
Revises: 00e06bbcd509
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '248109991136'
down_revision: Union[str, Sequence[str], None] = '00e06bbcd509'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_drop_subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('subscribed_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('target_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_price_drop_subscriptions_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'],
            name=op.f('fk_price_drop_subscriptions_product_id_products'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_price_drop_subscriptions')),
        sa.UniqueConstraint(
            'user_id', 'product_id',
            name='uq_price_drop_subscription',
        ),
    )
    op.create_index(
        op.f('ix_price_drop_subscriptions_product_id'),
        'price_drop_subscriptions', ['product_id'],
    )
    op.create_index(
        op.f('ix_price_drop_subscriptions_user_id'),
        'price_drop_subscriptions', ['user_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_price_drop_subscriptions_user_id'), 'price_drop_subscriptions')
    op.drop_index(op.f('ix_price_drop_subscriptions_product_id'), 'price_drop_subscriptions')
    op.drop_table('price_drop_subscriptions')
