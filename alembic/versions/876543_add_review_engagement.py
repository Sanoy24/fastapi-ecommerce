"""Add review engagement fields

Revision ID: 876543
Revises: 765432
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '876543'
down_revision = '765432'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reviews', sa.Column('helpful_votes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('reviews', sa.Column('unhelpful_votes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('reviews', sa.Column('report_count', sa.Integer(), nullable=False, server_default='0'))
    
    op.create_table(
        'review_votes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('is_helpful', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'user_id', name='uq_review_vote_user')
    )


def downgrade() -> None:
    op.drop_table('review_votes')
    op.drop_column('reviews', 'helpful_votes')
    op.drop_column('reviews', 'unhelpful_votes')
    op.drop_column('reviews', 'report_count')
