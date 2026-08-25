"""Add AuditLog and Performance Indexes

Revision ID: e71d0e330657
Revises: 
Create Date: 2026-08-25 23:23:20.359397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e71d0e330657'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AuditLog table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], name=op.f('fk_audit_logs_admin_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_admin_user_id'), 'audit_logs', ['admin_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)

    # Performance Indexes
    op.create_index('ix_orders_user_id_status', 'orders', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_orderitems_order_id'), 'orderitems', ['order_id'], unique=False)
    op.create_index(op.f('ix_cartitems_cart_id'), 'cartitems', ['cart_id'], unique=False)
    op.create_index('ix_inventory_reservations_expires_product', 'inventory_reservations', ['expires_at', 'product_id'], unique=False)
    op.create_index(op.f('ix_inventory_reservations_product_id'), 'inventory_reservations', ['product_id'], unique=False)
    op.create_index(op.f('ix_inventory_reservations_expires_at'), 'inventory_reservations', ['expires_at'], unique=False)
    op.create_index('ix_products_status_category', 'products', ['status', 'category_id'], unique=False)
    op.create_index('ix_reviews_product_id_approved', 'reviews', ['product_id', 'is_approved'], unique=False)
    op.create_index('ix_outbox_events_status', 'outbox_events', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    # Drop Indexes
    op.drop_index('ix_outbox_events_status', table_name='outbox_events')
    op.drop_index('ix_reviews_product_id_approved', table_name='reviews')
    op.drop_index('ix_products_status_category', table_name='products')
    op.drop_index(op.f('ix_inventory_reservations_expires_at'), table_name='inventory_reservations')
    op.drop_index(op.f('ix_inventory_reservations_product_id'), table_name='inventory_reservations')
    op.drop_index('ix_inventory_reservations_expires_product', table_name='inventory_reservations')
    op.drop_index(op.f('ix_cartitems_cart_id'), table_name='cartitems')
    op.drop_index(op.f('ix_orderitems_order_id'), table_name='orderitems')
    op.drop_index('ix_orders_user_id_status', table_name='orders')

    # Drop AuditLog table
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_admin_user_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
