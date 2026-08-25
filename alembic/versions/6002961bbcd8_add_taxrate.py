"""Add TaxRate

Revision ID: 6002961bbcd8
Revises: 7c73165a6f5d
Create Date: 2026-08-25 23:39:00.436143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6002961bbcd8'
down_revision: Union[str, Sequence[str], None] = '7c73165a6f5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type if not exists
    tax_applies_to_enum = sa.Enum('all', 'category', 'region', name='tax_applies_to')
    
    op.create_table('tax_rates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('applies_to', tax_applies_to_enum, nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_tax_rates_category_id_categories'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tax_rates'))
    )

def downgrade() -> None:
    op.drop_table('tax_rates')
    sa.Enum(name='tax_applies_to').drop(op.get_bind(), checkfirst=True)
