"""Restore individual planner records and retain activity time zones."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itinerary_items", sa.Column("timezone", sa.String(64)))
    op.add_column("itinerary_items", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_table(
        "entity_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "resource_id", "version"),
    )
    op.create_index("ix_entity_revisions_trip_id", "entity_revisions", ["trip_id"])


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM itinerary_items WHERE deleted_at IS NOT NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError("請先復原回收區活動，再降版以保留資料狀態。")
    op.drop_table("entity_revisions")
    op.drop_column("itinerary_items", "deleted_at")
    op.drop_column("itinerary_items", "timezone")
