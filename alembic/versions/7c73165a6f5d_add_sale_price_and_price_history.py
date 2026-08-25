"""Add Sale Price and Price History

Revision ID: 7c73165a6f5d
Revises: e71d0e330657
Create Date: 2026-08-25 23:36:19.816066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c73165a6f5d'
down_revision: Union[str, Sequence[str], None] = 'e71d0e330657'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to products
    op.add_column('products', sa.Column('sale_price', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('products', sa.Column('sale_starts_at', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('sale_ends_at', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('compare_at_price', sa.Numeric(precision=10, scale=2), nullable=True))

    # Create price_history table
    op.create_table('price_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('old_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('new_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], name=op.f('fk_price_history_changed_by_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_price_history_product_id_products'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_price_history'))
    )
    op.create_index(op.f('ix_price_history_changed_at'), 'price_history', ['changed_at'], unique=False)
    op.create_index(op.f('ix_price_history_product_id'), 'price_history', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_price_history_product_id'), table_name='price_history')
    op.drop_index(op.f('ix_price_history_changed_at'), table_name='price_history')
    op.drop_table('price_history')
    
    op.drop_column('products', 'compare_at_price')
    op.drop_column('products', 'sale_ends_at')
    op.drop_column('products', 'sale_starts_at')
    op.drop_column('products', 'sale_price')
