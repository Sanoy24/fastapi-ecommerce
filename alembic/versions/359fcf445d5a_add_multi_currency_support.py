"""Add multi-currency support

Revision ID: 359fcf445d5a
Revises: 1ed67c1278d3
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '359fcf445d5a'
down_revision: Union[str, Sequence[str], None] = '1ed67c1278d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'currencies',
        sa.Column('code', sa.String(length=3), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=5), nullable=False),
        sa.Column('exchange_rate_to_base', sa.Numeric(12, 6), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('code', name=op.f('pk_currencies')),
    )

    # The base currency must exist before any FK referencing it can be
    # backfilled onto existing carts/orders/payments below.
    op.execute(
        "INSERT INTO currencies (code, name, symbol, exchange_rate_to_base, is_active, created_at, updated_at) "
        "VALUES ('USD', 'US Dollar', '$', 1, true, now(), now())"
    )

    op.add_column('carts', sa.Column('currency_code', sa.String(length=3), nullable=True))
    op.create_foreign_key(
        op.f('fk_carts_currency_code_currencies'), 'carts', 'currencies',
        ['currency_code'], ['code'], ondelete='SET NULL',
    )

    # Every existing order predates multi-currency, so backfilling as
    # base-currency-at-a-1:1-rate is simply the truth, not an approximation.
    op.add_column(
        'orders',
        sa.Column('currency_code', sa.String(length=3), nullable=False, server_default='USD'),
    )
    op.add_column(
        'orders',
        sa.Column('exchange_rate_at_purchase', sa.Numeric(12, 6), nullable=False, server_default='1'),
    )
    op.create_foreign_key(
        op.f('fk_orders_currency_code_currencies'), 'orders', 'currencies',
        ['currency_code'], ['code'], ondelete='RESTRICT',
    )

    op.add_column(
        'payments',
        sa.Column('currency_code', sa.String(length=3), nullable=False, server_default='USD'),
    )
    op.create_foreign_key(
        op.f('fk_payments_currency_code_currencies'), 'payments', 'currencies',
        ['currency_code'], ['code'], ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('fk_payments_currency_code_currencies'), 'payments', type_='foreignkey')
    op.drop_column('payments', 'currency_code')

    op.drop_constraint(op.f('fk_orders_currency_code_currencies'), 'orders', type_='foreignkey')
    op.drop_column('orders', 'exchange_rate_at_purchase')
    op.drop_column('orders', 'currency_code')

    op.drop_constraint(op.f('fk_carts_currency_code_currencies'), 'carts', type_='foreignkey')
    op.drop_column('carts', 'currency_code')

    op.drop_table('currencies')
