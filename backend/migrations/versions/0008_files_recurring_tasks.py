"""Transactional file content, related readers and recurring task progress."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def ident():
    return sa.Column("id", sa.String(36), primary_key=True)


def fk(name, target, cascade=False):
    return sa.Column(
        name,
        sa.String(36),
        sa.ForeignKey(target, ondelete="CASCADE" if cascade else None),
        nullable=False,
    )


def upgrade():
    op.create_table(
        "files",
        ident(),
        fk("trip_id", "trips.id", True),
        fk("owner_id", "users.id"),
        sa.Column("filename", sa.String(180), nullable=False),
        sa.Column("mime", sa.String(127), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("private", sa.Boolean, nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column("preview_text", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("size > 0 AND version >= 1"),
    )
    op.create_index("ix_files_trip_id", "files", ["trip_id"])
    op.create_table(
        "file_permissions",
        ident(),
        fk("file_id", "files.id", True),
        fk("user_id", "users.id"),
        sa.UniqueConstraint("file_id", "user_id"),
    )
    op.create_index("ix_file_permissions_file_id", "file_permissions", ["file_id"])
    op.create_table(
        "file_links",
        ident(),
        fk("file_id", "files.id", True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.UniqueConstraint("file_id", "kind", "target_id"),
    )
    for column in ("file_id", "target_id"):
        op.create_index("ix_file_links_" + column, "file_links", [column])
    op.add_column(
        "tasks", sa.Column("recurrence", sa.String(12), nullable=False, server_default="none")
    )
    op.add_column("tasks", sa.Column("period", sa.Integer, nullable=False, server_default="1"))
    op.create_table(
        "task_occurrences",
        ident(),
        fk("task_id", "tasks.id", True),
        sa.Column("period", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("progress", sa.JSON, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "period"),
    )
    op.create_index("ix_task_occurrences_task_id", "task_occurrences", ["task_id"])


def downgrade():
    op.drop_table("task_occurrences")
    op.drop_column("tasks", "period")
    op.drop_column("tasks", "recurrence")
    op.drop_table("file_links")
    op.drop_table("file_permissions")
    op.drop_table("files")
