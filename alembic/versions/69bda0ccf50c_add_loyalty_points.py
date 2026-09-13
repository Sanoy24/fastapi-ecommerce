"""Add loyalty points

Revision ID: 69bda0ccf50c
Revises: 359fcf445d5a
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69bda0ccf50c'
down_revision: Union[str, Sequence[str], None] = '359fcf445d5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every existing user/order/cart predates loyalty points, so
    # backfilling a balance/redeemed/earned count of 0 is simply the truth,
    # not an approximation.
    op.add_column('users', sa.Column('loyalty_points_balance', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('carts', sa.Column('points_redeemed', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('points_redeemed', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('points_earned', sa.Integer(), nullable=False, server_default='0'))

    op.create_table(
        'loyalty_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_loyalty_transactions_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['order_id'], ['orders.id'],
            name=op.f('fk_loyalty_transactions_order_id_orders'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_loyalty_transactions')),
    )
    op.create_index(
        op.f('ix_loyalty_transactions_user_id_created_at'),
        'loyalty_transactions', ['user_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_loyalty_transactions_user_id_created_at'), 'loyalty_transactions')
    op.drop_table('loyalty_transactions')

    op.drop_column('orders', 'points_earned')
    op.drop_column('orders', 'points_redeemed')
    op.drop_column('carts', 'points_redeemed')
    op.drop_column('users', 'loyalty_points_balance')
