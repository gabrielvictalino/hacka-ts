from alembic import context
from app.db import get_engine

if context.is_offline_mode():
    from app.config import get_settings

    context.configure(url=get_settings().database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
