"""Add email column to profiles table

Revision ID: add_email_profiles
Revises: d1fb8bfc5380
Create Date: 2025-12-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_email_profiles'
down_revision: Union[str, Sequence[str], None] = 'd1fb8bfc5380'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email column to profiles table."""
    op.add_column('profiles', sa.Column('email', sa.String(255), nullable=True))
    op.create_index('ix_profiles_email', 'profiles', ['email'])

    # Mavjud profillar uchun emailni users jadvalidan nusxalash
    op.execute("""
        UPDATE profiles
        SET email = users.email
        FROM users
        WHERE profiles.user_id = users.id
    """)


def downgrade() -> None:
    """Remove email column from profiles table."""
    op.drop_index('ix_profiles_email', table_name='profiles')
    op.drop_column('profiles', 'email')
