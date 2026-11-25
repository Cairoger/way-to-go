"""Retain removed original places for scheduled references and revision history."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("places", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM places WHERE deleted_at IS NOT NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError("已有移除的原始景點，請從升級前備份還原以保留移除狀態。")
    op.drop_column("places", "deleted_at")
