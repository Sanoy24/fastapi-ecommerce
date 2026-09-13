"""Add subscriptions

Revision ID: 1ed67c1278d3
Revises: 9435916d3638
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ed67c1278d3'
down_revision: Union[str, Sequence[str], None] = '9435916d3638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column(
            'interval', sa.Enum('weekly', 'biweekly', 'monthly', name='subscription_interval'),
            nullable=False,
        ),
        sa.Column('saved_payment_method_id', sa.Integer(), nullable=False),
        sa.Column('shipping_address_id', sa.Integer(), nullable=False),
        sa.Column('billing_address_id', sa.Integer(), nullable=False),
        sa.Column(
            'status', sa.Enum('active', 'paused', 'past_due', 'cancelled', name='subscription_status'),
            nullable=False,
        ),
        sa.Column('next_billing_date', sa.DateTime(), nullable=False),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('last_payment_error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_subscriptions_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'],
            name=op.f('fk_subscriptions_product_id_products'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['variant_id'], ['product_variants.id'],
            name=op.f('fk_subscriptions_variant_id_product_variants'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['saved_payment_method_id'], ['saved_payment_methods.id'],
            name=op.f('fk_subscriptions_saved_payment_method_id_saved_payment_methods'),
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['shipping_address_id'], ['addresses.id'],
            name=op.f('fk_subscriptions_shipping_address_id_addresses'),
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['billing_address_id'], ['addresses.id'],
            name=op.f('fk_subscriptions_billing_address_id_addresses'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_subscriptions')),
    )
    op.create_index(
        op.f('ix_subscriptions_user_id_status'),
        'subscriptions', ['user_id', 'status'],
    )
    op.create_index(
        op.f('ix_subscriptions_next_billing_date'),
        'subscriptions', ['next_billing_date'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_subscriptions_next_billing_date'), 'subscriptions')
    op.drop_index(op.f('ix_subscriptions_user_id_status'), 'subscriptions')
    op.drop_table('subscriptions')
    op.execute('DROP TYPE IF EXISTS subscription_status')
    op.execute('DROP TYPE IF EXISTS subscription_interval')
