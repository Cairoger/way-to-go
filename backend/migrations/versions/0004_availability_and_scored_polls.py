"""Add member availability, rating ballots, and ranked ballots."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def replace_mode_check(expanded: bool):
    db = op.get_bind()
    expr = (
        "mode IN ('single','multiple','rating','ranked')"
        if expanded
        else "mode IN ('single','multiple')"
    )
    old_name = "poll_rounds_mode_check" if expanded else "ck_poll_round_mode"
    new_name = "ck_poll_round_mode" if expanded else "poll_rounds_mode_check"
    if db.dialect.name == "postgresql":
        op.drop_constraint(old_name, "poll_rounds", type_="check")
        op.create_check_constraint(new_name, "poll_rounds", expr)
        return
    # SQLite must rebuild this FK parent. Keep its existing options, ballots and kind check.
    with op.get_context().autocommit_block():
        db.exec_driver_sql("PRAGMA foreign_keys=OFF")
        db.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with op.batch_alter_table("poll_rounds", recreate="always") as batch:
                for constraint in sa.inspect(db).get_check_constraints("poll_rounds"):
                    if constraint["name"]:
                        batch.drop_constraint(constraint["name"], type_="check")
                batch.create_check_constraint("ck_poll_round_kind", "kind IN ('place','date')")
                batch.create_check_constraint(new_name, expr)
            if db.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise RuntimeError("投票輪次資料參照有誤")
            db.exec_driver_sql("COMMIT")
        except Exception:
            db.exec_driver_sql("ROLLBACK")
            raise
        finally:
            db.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    replace_mode_check(True)
    op.add_column(
        "ballot_choices",
        sa.Column(
            "value",
            sa.Integer(),
            sa.CheckConstraint("value BETWEEN 1 AND 5", name="ck_ballot_choice_value"),
        ),
    )
    op.add_column(
        "ballot_choices",
        sa.Column(
            "rank",
            sa.Integer(),
            sa.CheckConstraint("rank BETWEEN 1 AND 60", name="ck_ballot_choice_rank"),
        ),
    )
    op.create_table(
        "availability_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_availability_order"),
        sa.CheckConstraint("status IN ('yes','maybe','no')", name="ck_availability_status"),
        sa.CheckConstraint("version >= 1", name="ck_availability_version"),
    )
    op.create_index(
        "ix_availability_member_dates",
        "availability_entries",
        ["trip_id", "user_id", "start_date", "end_date"],
    )


def downgrade():
    db = op.get_bind()
    if db.scalar(
        sa.text("SELECT 1 FROM poll_rounds WHERE mode IN ('rating','ranked') LIMIT 1")
    ) or (db.scalar(sa.text("SELECT 1 FROM availability_entries LIMIT 1"))):
        raise RuntimeError("請先匯出並移除日期標記、評分與排序投票，再降版。")
    replace_mode_check(False)
    op.drop_table("availability_entries")
    op.drop_column("ballot_choices", "rank")
    op.drop_column("ballot_choices", "value")
