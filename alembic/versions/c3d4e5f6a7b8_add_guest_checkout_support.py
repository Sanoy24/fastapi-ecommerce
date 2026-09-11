"""Add guest checkout support

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- orders: allow a guest order (no user_id, no Address rows) ---
    op.add_column('orders', sa.Column('guest_email', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_orders_guest_email'), 'orders', ['guest_email'])

    op.alter_column('orders', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('orders', 'shipping_address_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('orders', 'billing_address_id', existing_type=sa.Integer(), nullable=True)

    # Note: the constraint_name argument is run through the naming
    # convention (ck_%(table_name)s_%(constraint_name)s) same as the model
    # declaration — passing the already-prefixed name here would double it
    # up into ck_orders_ck_orders_...; confirmed against a live database
    # before settling on this form.
    op.create_check_constraint(
        'user_or_guest_email',
        'orders',
        'user_id IS NOT NULL OR guest_email IS NOT NULL',
    )

    # --- inventory_reservations: release by order, not by user ---
    # user_id == order.user_id was the release filter used by
    # PaymentService and OrderService.cancel_order. For a guest order
    # (user_id NULL), that filter becomes "user_id IS NULL" — matching
    # every other guest order's reservations too, not just this one's.
    # order_id is the correct, order-scoped filter; user_id becomes
    # informational only (nullable, since guest reservations have none).
    op.add_column('inventory_reservations', sa.Column('order_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_inventory_reservations_order_id'), 'inventory_reservations', ['order_id']
    )
    op.create_foreign_key(
        op.f('fk_inventory_reservations_order_id_orders'),
        'inventory_reservations', 'orders', ['order_id'], ['id'], ondelete='CASCADE'
    )
    op.alter_column('inventory_reservations', 'user_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column('inventory_reservations', 'user_id', existing_type=sa.Integer(), nullable=False)
    op.drop_constraint(
        op.f('fk_inventory_reservations_order_id_orders'),
        'inventory_reservations', type_='foreignkey'
    )
    op.drop_index(op.f('ix_inventory_reservations_order_id'), 'inventory_reservations')
    op.drop_column('inventory_reservations', 'order_id')

    op.drop_constraint(op.f('ck_orders_user_or_guest_email'), 'orders', type_='check')
    op.alter_column('orders', 'billing_address_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('orders', 'shipping_address_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('orders', 'user_id', existing_type=sa.Integer(), nullable=False)
    op.drop_index(op.f('ix_orders_guest_email'), 'orders')
    op.drop_column('orders', 'guest_email')
