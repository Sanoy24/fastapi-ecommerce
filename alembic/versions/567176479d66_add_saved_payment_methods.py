"""Add saved_payment_methods and users.stripe_customer_id

Revision ID: 567176479d66
Revises: 35ed8fd469cf
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '567176479d66'
down_revision: Union[str, Sequence[str], None] = '35ed8fd469cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        op.f('uq_users_stripe_customer_id'), 'users', ['stripe_customer_id']
    )

    op.create_table(
        'saved_payment_methods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stripe_payment_method_id', sa.String(length=255), nullable=False),
        sa.Column('brand', sa.String(length=50), nullable=False),
        sa.Column('last4', sa.String(length=4), nullable=False),
        sa.Column('exp_month', sa.Integer(), nullable=False),
        sa.Column('exp_year', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_saved_payment_methods_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_saved_payment_methods')),
        sa.UniqueConstraint(
            'user_id', 'stripe_payment_method_id',
            name='uq_saved_payment_method_user_pm',
        ),
    )
    op.create_index(
        op.f('ix_saved_payment_methods_user_id'),
        'saved_payment_methods', ['user_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_payment_methods_user_id'), 'saved_payment_methods')
    op.drop_table('saved_payment_methods')
    op.drop_constraint(op.f('uq_users_stripe_customer_id'), 'users', type_='unique')
    op.drop_column('users', 'stripe_customer_id')
