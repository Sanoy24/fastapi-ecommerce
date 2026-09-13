"""Widen category columns and add brand filter + product attributes

Revision ID: 81a3400c512b
Revises: 923b4e2e6b7c
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81a3400c512b'
down_revision: Union[str, Sequence[str], None] = '923b4e2e6b7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # categories.name/slug/image_url were sized for the original narrow
    # single-department catalog (String(20)/String(20)/String(30)) — too
    # small for a general-merchandise store ("Home & Kitchen Appliances" is
    # 26 characters, and no real image URL fits in 30). Widened to match
    # the room Product's equivalent columns already have.
    op.alter_column('categories', 'name', existing_type=sa.String(length=20), type_=sa.String(length=100))
    op.alter_column('categories', 'slug', existing_type=sa.String(length=20), type_=sa.String(length=120))
    op.alter_column('categories', 'image_url', existing_type=sa.String(length=30), type_=sa.String(length=500))

    # Free-form spec data whose shape varies by category (RAM/screen size
    # for a laptop, material/care for apparel) — see Product.attributes,
    # which mirrors ProductVariant.attributes' existing JSON-blob convention.
    op.add_column('products', sa.Column('attributes', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'attributes')

    op.alter_column('categories', 'image_url', existing_type=sa.String(length=500), type_=sa.String(length=30))
    op.alter_column('categories', 'slug', existing_type=sa.String(length=120), type_=sa.String(length=20))
    op.alter_column('categories', 'name', existing_type=sa.String(length=100), type_=sa.String(length=20))
