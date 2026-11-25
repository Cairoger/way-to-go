from alembic import context

from app import (  # noqa: F401
    availability_models,
    decisions_models,
    file_models,
    finance_models,
    merge_models,
    notice_models,
    planning_models,
    preparation_models,
)
from app.core import get_engine
from app.models import Base


def run():
    if context.is_offline_mode():
        context.configure(url=get_engine().url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        with get_engine().connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()


run()
