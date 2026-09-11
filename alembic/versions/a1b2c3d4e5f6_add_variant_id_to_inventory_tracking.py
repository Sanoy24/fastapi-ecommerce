"""Add variant_id to inventory reservations and transactions

Revision ID: a1b2c3d4e5f6
Revises: 876543
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '876543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inventory_reservations', sa.Column('variant_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_inventory_reservations_variant_id'), 'inventory_reservations', ['variant_id']
    )
    op.create_foreign_key(
        op.f('fk_inventory_reservations_variant_id_product_variants'),
        'inventory_reservations', 'product_variants', ['variant_id'], ['id'], ondelete='CASCADE'
    )

    op.add_column('inventory_transactions', sa.Column('variant_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f('fk_inventory_transactions_variant_id_product_variants'),
        'inventory_transactions', 'product_variants', ['variant_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_inventory_transactions_variant_id_product_variants'),
        'inventory_transactions', type_='foreignkey'
    )
    op.drop_column('inventory_transactions', 'variant_id')

    op.drop_constraint(
        op.f('fk_inventory_reservations_variant_id_product_variants'),
        'inventory_reservations', type_='foreignkey'
    )
    op.drop_index(op.f('ix_inventory_reservations_variant_id'), 'inventory_reservations')
    op.drop_column('inventory_reservations', 'variant_id')
