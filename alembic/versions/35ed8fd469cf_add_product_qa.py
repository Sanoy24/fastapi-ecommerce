"""Add product_questions and product_answers

Revision ID: 35ed8fd469cf
Revises: 248109991136
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35ed8fd469cf'
down_revision: Union[str, Sequence[str], None] = '248109991136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_questions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'],
            name=op.f('fk_product_questions_product_id_products'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_product_questions_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_questions')),
    )
    op.create_index(
        op.f('ix_product_questions_product_id'),
        'product_questions', ['product_id'],
    )

    op.create_table(
        'product_answers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['question_id'], ['product_questions.id'],
            name=op.f('fk_product_answers_question_id_product_questions'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_product_answers_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_answers')),
    )
    op.create_index(
        op.f('ix_product_answers_question_id'),
        'product_answers', ['question_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_product_answers_question_id'), 'product_answers')
    op.drop_table('product_answers')
    op.drop_index(op.f('ix_product_questions_product_id'), 'product_questions')
    op.drop_table('product_questions')
