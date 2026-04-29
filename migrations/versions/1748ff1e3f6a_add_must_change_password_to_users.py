"""add must_change_password to users

Revision ID: 1748ff1e3f6a
Revises: 08e592e19ef3
Create Date: 2026-04-30 01:10:31.139109

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1748ff1e3f6a'
down_revision = '08e592e19ef3'
branch_labels = None
depends_on = None


def upgrade():
    # Add column as nullable first so existing rows don't violate NOT NULL
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'must_change_password', sa.Boolean(), nullable=True
        ))

    # Backfill: existing users already have a password — no need to force change
    op.execute("UPDATE users SET must_change_password = FALSE WHERE must_change_password IS NULL")

    # Now tighten to NOT NULL with server_default so future rows are safe
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'must_change_password',
            nullable=False,
            server_default=sa.text('FALSE')
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('must_change_password')
