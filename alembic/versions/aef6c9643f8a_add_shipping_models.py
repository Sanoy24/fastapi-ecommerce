"""Add Shipping Models

Revision ID: aef6c9643f8a
Revises: 6002961bbcd8
Create Date: 2026-08-25 23:40:55.456576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aef6c9643f8a'
down_revision: Union[str, Sequence[str], None] = '6002961bbcd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('shipping_zones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('countries', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shipping_zones'))
    )
    op.create_table('shipping_methods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('carrier', sa.String(length=100), nullable=False),
        sa.Column('estimated_days_min', sa.Integer(), nullable=True),
        sa.Column('estimated_days_max', sa.Integer(), nullable=True),
        sa.Column('base_rate', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('per_kg_rate', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shipping_methods'))
    )
    op.create_table('shipping_rates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('method_id', sa.Integer(), nullable=False),
        sa.Column('base_rate_override', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('per_kg_rate_override', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.ForeignKeyConstraint(['method_id'], ['shipping_methods.id'], name=op.f('fk_shipping_rates_method_id_shipping_methods'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['zone_id'], ['shipping_zones.id'], name=op.f('fk_shipping_rates_zone_id_shipping_zones'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shipping_rates'))
    )

def downgrade() -> None:
    op.drop_table('shipping_rates')
    op.drop_table('shipping_methods')
    op.drop_table('shipping_zones')
