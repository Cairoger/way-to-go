"""Version existing and new profiles for conditional nickname updates."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("users", "version")
