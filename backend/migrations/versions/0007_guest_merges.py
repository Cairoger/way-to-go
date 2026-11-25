"""Record authenticated guest account merges and original conflicting submissions."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_merges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "guest_id", sa.String(36), sa.ForeignKey("users.id"), unique=True, nullable=False
        ),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.CheckConstraint("guest_id <> account_id"),
    )
    op.create_index("ix_account_merges_account_id", "account_merges", ["account_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM account_merges LIMIT 1")).first():
        raise RuntimeError("已有訪客合併紀錄，移除帳號對應會影響既有分帳。請從升級前備份還原。")
    op.drop_table("account_merges")
