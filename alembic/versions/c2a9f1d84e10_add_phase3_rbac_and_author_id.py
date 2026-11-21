"""add_phase3_rbac_and_author_id

Revision ID: c2a9f1d84e10
Revises: bf7044d6278f
Create Date: 2026-11-21 19:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c2a9f1d84e10'
down_revision: Union[str, Sequence[str], None] = 'bf7044d6278f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 3 workspace_blog_assignments table and articles.author_id column."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Create workspace_blog_assignments if not exists
    if 'workspace_blog_assignments' not in existing_tables:
        op.create_table(
            'workspace_blog_assignments',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('membership_id', sa.String(length=36), nullable=False),
            sa.Column('blog_id', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['membership_id'], ['workspace_memberships.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_workspace_blog_assignments_blog_id', 'workspace_blog_assignments', ['blog_id'], unique=False)
        op.create_index('ix_workspace_blog_assignments_membership_id', 'workspace_blog_assignments', ['membership_id'], unique=False)
        op.create_index('uq_membership_blog', 'workspace_blog_assignments', ['membership_id', 'blog_id'], unique=True)

    # 2. Add author_id column to articles if missing
    if 'articles' in existing_tables:
        article_cols = [c['name'] for c in inspector.get_columns('articles')]
        if 'author_id' not in article_cols:
            op.add_column('articles', sa.Column('author_id', sa.String(length=36), nullable=True))
            op.create_index('ix_articles_author_id', 'articles', ['author_id'], unique=False)


def downgrade() -> None:
    """Revert Phase 3 RBAC additions."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'articles' in existing_tables:
        article_cols = [c['name'] for c in inspector.get_columns('articles')]
        if 'author_id' in article_cols:
            op.drop_index('ix_articles_author_id', table_name='articles')
            op.drop_column('articles', 'author_id')

    if 'workspace_blog_assignments' in existing_tables:
        op.drop_index('uq_membership_blog', table_name='workspace_blog_assignments')
        op.drop_index('ix_workspace_blog_assignments_membership_id', table_name='workspace_blog_assignments')
        op.drop_index('ix_workspace_blog_assignments_blog_id', table_name='workspace_blog_assignments')
        op.drop_table('workspace_blog_assignments')
