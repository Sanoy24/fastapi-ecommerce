"""Add ProductRelation

Revision ID: 59ff5edac949
Revises: aef6c9643f8a
Create Date: 2026-08-25 23:43:15.984184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59ff5edac949'
down_revision: Union[str, Sequence[str], None] = 'aef6c9643f8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    product_relation_type_enum = sa.Enum('similar', 'frequently_bought_together', 'accessory', name='product_relation_type')
    
    op.create_table('product_relations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('related_product_id', sa.Integer(), nullable=False),
        sa.Column('relation_type', product_relation_type_enum, nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_relations_product_id_products'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_product_id'], ['products.id'], name=op.f('fk_product_relations_related_product_id_products'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_relations'))
    )

def downgrade() -> None:
    op.drop_table('product_relations')
    sa.Enum(name='product_relation_type').drop(op.get_bind(), checkfirst=True)
