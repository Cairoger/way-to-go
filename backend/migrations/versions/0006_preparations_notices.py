"""Tasks, bookings and mention notifications."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("mentions", sa.Boolean(), nullable=False),
        sa.Column("push", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_hash"),
    )
    op.create_index(
        op.f("ix_push_subscriptions_session_id"), "push_subscriptions", ["session_id"], unique=False
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("comment_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "comment_id"),
    )
    op.create_index(op.f("ix_notifications_trip_id"), "notifications", ["trip_id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("website", sa.Text(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("stay", sa.JSON(), nullable=True),
        sa.Column("item_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('flight','stay')"),
        sa.CheckConstraint("status IN ('planned','booked','cancelled')"),
        sa.CheckConstraint("price IS NULL OR price >= 0"),
        sa.CheckConstraint("version >= 1"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["item_id"], ["itinerary_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_trip_id"), "bookings", ["trip_id"], unique=False)
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("place_id", sa.String(length=36), nullable=True),
        sa.Column("item_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority IN ('low','normal','high')"),
        sa.CheckConstraint("scope IN ('shared','personal')"),
        sa.CheckConstraint("version >= 1"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["item_id"], ["itinerary_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_trip_id"), "tasks", ["trip_id"], unique=False)
    op.create_table(
        "task_assignees",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.CheckConstraint("state IN ('todo','doing','done')"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "user_id"),
    )
    op.create_index(op.f("ix_task_assignees_task_id"), "task_assignees", ["task_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_task_assignees_task_id"), table_name="task_assignees")
    op.drop_table("task_assignees")
    op.drop_index(op.f("ix_tasks_trip_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_bookings_trip_id"), table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_trip_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_push_subscriptions_session_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_table("notification_preferences")
