"""Trip budgets, multi-party expenses and settlement records."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "budgets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=12), nullable=False),
        sa.Column("target", sa.String(length=80), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("scope IN ('trip','personal','category')"),
        sa.CheckConstraint("amount_minor > 0"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "scope", "target"),
    )
    op.create_index(op.f("ix_budgets_trip_id"), "budgets", ["trip_id"], unique=False)
    op.create_table(
        "exchange_rate_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("source_currency", sa.String(length=3), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_exchange_rate_snapshots_trip_id"),
        "exchange_rate_snapshots",
        ["trip_id"],
        unique=False,
    )
    op.create_table(
        "finance_ledgers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id"),
    )
    op.create_table(
        "settlements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("from_user_id", sa.String(length=36), nullable=False),
        sa.Column("to_user_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_minor > 0 AND from_user_id <> to_user_id"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["from_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_settlements_trip_id"), "settlements", ["trip_id"], unique=False)
    op.create_table(
        "expenses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("split_mode", sa.String(length=10), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("base_minor", sa.BigInteger(), nullable=False),
        sa.Column("rate_id", sa.String(length=36), nullable=False),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('actual','estimate')"),
        sa.CheckConstraint("split_mode IN ('equal','custom','ratio')"),
        sa.CheckConstraint("amount_minor > 0 AND base_minor >= 0"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rate_id"],
            ["exchange_rate_snapshots.id"],
        ),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expenses_trip_id"), "expenses", ["trip_id"], unique=False)
    op.create_table(
        "expense_payers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("expense_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("base_minor", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expense_id", "user_id"),
    )
    op.create_index(
        op.f("ix_expense_payers_expense_id"), "expense_payers", ["expense_id"], unique=False
    )
    op.create_table(
        "expense_splits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("expense_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("base_minor", sa.BigInteger(), nullable=False),
        sa.Column("weight", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expense_id", "user_id"),
    )
    op.create_index(
        op.f("ix_expense_splits_expense_id"), "expense_splits", ["expense_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_expense_splits_expense_id"), table_name="expense_splits")
    op.drop_table("expense_splits")
    op.drop_index(op.f("ix_expense_payers_expense_id"), table_name="expense_payers")
    op.drop_table("expense_payers")
    op.drop_index(op.f("ix_expenses_trip_id"), table_name="expenses")
    op.drop_table("expenses")
    op.drop_index(op.f("ix_settlements_trip_id"), table_name="settlements")
    op.drop_table("settlements")
    op.drop_table("finance_ledgers")
    op.drop_index(op.f("ix_exchange_rate_snapshots_trip_id"), table_name="exchange_rate_snapshots")
    op.drop_table("exchange_rate_snapshots")
    op.drop_index(op.f("ix_budgets_trip_id"), table_name="budgets")
    op.drop_table("budgets")
