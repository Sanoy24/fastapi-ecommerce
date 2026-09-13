"""Add oauth_accounts and make users.password_hash nullable

Revision ID: 9435916d3638
Revises: 567176479d66
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9435916d3638'
down_revision: Union[str, Sequence[str], None] = '567176479d66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=True)

    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_oauth_accounts_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth_accounts')),
        sa.UniqueConstraint(
            'provider', 'provider_user_id',
            name='uq_oauth_account_provider_identity',
        ),
        sa.UniqueConstraint(
            'user_id', 'provider',
            name='uq_oauth_account_user_provider',
        ),
    )
    op.create_index(
        op.f('ix_oauth_accounts_user_id'),
        'oauth_accounts', ['user_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_oauth_accounts_user_id'), 'oauth_accounts')
    op.drop_table('oauth_accounts')
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=False)
