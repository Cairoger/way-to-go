"""Allow an independent identity for the opt-in local test account."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def replace_check(allow_local: bool):
    expression = (
        "account_type in ('google','guest','local_test')"
        if allow_local
        else "account_type in ('google','guest')"
    )
    name = "ck_users_account_type"
    if op.get_bind().dialect.name == "postgresql":
        # PostgreSQL generated users_account_type_check for the unnamed check in 0001.
        op.drop_constraint(
            "users_account_type_check" if allow_local else name, "users", type_="check"
        )
        op.create_check_constraint(
            name if allow_local else "users_account_type_check", "users", expression
        )
        return
    # SQLite requires a table rebuild for changed CHECK constraints. The users table
    # is referenced by existing trips and sessions, so suspend FK checks around the
    # rebuild and validate all references before committing it.
    with op.get_context().autocommit_block():
        db = op.get_bind()
        db.exec_driver_sql("PRAGMA foreign_keys=OFF")
        db.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            # Alembic excludes unnamed checks during the rebuild, including 0001's.
            with op.batch_alter_table("users", recreate="always") as batch:
                for check in sa.inspect(db).get_check_constraints("users"):
                    if check["name"] and "account_type" in check["sqltext"]:
                        batch.drop_constraint(check["name"], type_="check")
                batch.create_check_constraint(
                    name if allow_local else "users_account_type_check", expression
                )
            if db.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise RuntimeError("users 表重建後發現參照錯誤")
            db.exec_driver_sql("COMMIT")
        except Exception:
            db.exec_driver_sql("ROLLBACK")
            raise
        finally:
            db.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    replace_check(True)


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM users WHERE account_type='local_test' LIMIT 1"))
        .first()
    ):
        raise RuntimeError("仍有本機測試帳號，無法移除該帳號類型。")
    replace_check(False)
