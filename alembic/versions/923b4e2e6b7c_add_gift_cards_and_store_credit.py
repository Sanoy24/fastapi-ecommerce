"""Add gift cards and store credit

Revision ID: 923b4e2e6b7c
Revises: 69bda0ccf50c
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '923b4e2e6b7c'
down_revision: Union[str, Sequence[str], None] = '69bda0ccf50c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every existing user/order/cart predates gift cards, so backfilling a
    # balance/applied amount of 0 is simply the truth, not an approximation.
    op.add_column('users', sa.Column('store_credit_balance', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('carts', sa.Column('store_credit_applied', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('store_credit_applied', sa.Numeric(10, 2), nullable=False, server_default='0'))

    op.create_table(
        'gift_cards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('value', sa.Numeric(10, 2), nullable=False),
        sa.Column('is_redeemed', sa.Boolean(), nullable=False),
        sa.Column('redeemed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['redeemed_by_user_id'], ['users.id'],
            name=op.f('fk_gift_cards_redeemed_by_user_id_users'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['created_by'], ['users.id'],
            name=op.f('fk_gift_cards_created_by_users'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_gift_cards')),
    )
    op.create_index(op.f('ix_gift_cards_code'), 'gift_cards', ['code'], unique=True)

    op.create_table(
        'store_credit_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('gift_card_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_store_credit_transactions_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['order_id'], ['orders.id'],
            name=op.f('fk_store_credit_transactions_order_id_orders'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['gift_card_id'], ['gift_cards.id'],
            name=op.f('fk_store_credit_transactions_gift_card_id_gift_cards'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_store_credit_transactions')),
    )
    op.create_index(
        op.f('ix_store_credit_transactions_user_id_created_at'),
        'store_credit_transactions', ['user_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_store_credit_transactions_user_id_created_at'), 'store_credit_transactions')
    op.drop_table('store_credit_transactions')

    op.drop_index(op.f('ix_gift_cards_code'), 'gift_cards')
    op.drop_table('gift_cards')

    op.drop_column('orders', 'store_credit_applied')
    op.drop_column('carts', 'store_credit_applied')
    op.drop_column('users', 'store_credit_balance')
