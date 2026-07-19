"""Application startup and shutdown

Handles database initialization, schema migration (auto-add-column), event discovery, and bootstrap.
"""

from loguru import logger
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session

from app.db.session import engine
from app.core.events import discover_event_handlers
from app.bootstrap import discover_and_run_initializers


def _auto_add_missing_columns():
    """Auto-add missing columns to existing tables.

    Only adds columns that have a server_default set, as these can be safely
    backfilled with ALTER TABLE ... DEFAULT ... on existing rows.
    """
    inspector = inspect(engine)

    for table_name, table in SQLModel.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue

        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        model_columns = set(table.columns.keys())
        missing = model_columns - existing_columns

        if not missing:
            continue

        for col_name in missing:
            column = table.columns[col_name]
            server_default = column.server_default

            if server_default is None and not column.nullable:
                logger.warning(
                    f"[Schema Migration] Skipping non-nullable column '{col_name}' on table '{table_name}' "
                    f"(no server_default set). Add a server_default to the model or use a migration."
                )
                continue

            col_type = column.type.compile(engine.dialect)
            nullable_str = "" if column.nullable else " NOT NULL"
            default_str = f" DEFAULT {server_default.arg}" if server_default is not None else ""

            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{nullable_str}{default_str}"

            try:
                with engine.connect() as conn:
                    conn.execute(text(alter_sql))
                    conn.commit()
                logger.info(f"[Schema Migration] Added column '{col_name}' to table '{table_name}'")
            except Exception as e:
                logger.error(f"[Schema Migration] Failed to add column '{col_name}' to table '{table_name}': {e}")


def startup():
    """Application startup sequence.

    1. Create all database tables (if they don't exist)
    2. Auto-add missing columns to existing tables
    3. Discover event handlers
    4. Run bootstrap initializers (prompts, card types, knowledge base, workflows, etc.)
    """
    logger.info("=" * 60)
    logger.info("Novel Forge backend starting up...")
    logger.info("=" * 60)

    # 1. Create tables
    logger.info("[Startup] Creating database tables...")
    SQLModel.metadata.create_all(engine)

    # 2. Auto-add missing columns
    logger.info("[Startup] Checking for missing columns...")
    _auto_add_missing_columns()

    # 3. Discover event handlers
    logger.info("[Startup] Discovering event handlers...")
    discover_event_handlers()

    # 4. Run bootstrap initializers
    logger.info("[Startup] Running bootstrap initializers...")
    with Session(engine) as session:
        discover_and_run_initializers(session)

    logger.info("[Startup] Startup complete.")


def shutdown():
    """Application shutdown sequence."""
    logger.info("=" * 60)
    logger.info("Novel Forge backend shutting down...")
    logger.info("=" * 60)

    try:
        engine.dispose()
    except Exception as e:
        logger.error(f"[Shutdown] Error disposing engine: {e}")

    logger.info("[Shutdown] Shutdown complete.")
