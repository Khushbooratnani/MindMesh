import asyncio
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.connection.session import close_db_engine, create_async_engine_instance, get_async_engine
from app.database.models.base import Base

logger = logging.getLogger(__name__)


async def init_db_schema(engine: AsyncEngine | None = None) -> None:
    """Initialize or migrate the database schema.
    
    First runs raw SQL migrations if on PostgreSQL, or generates tables via
    SQLAlchemy metadata if on SQLite/testing.
    """
    target_engine = engine or get_async_engine()
    url_str = str(target_engine.url)

    if "sqlite" in url_str:
        # For SQLite in-memory / testing, create tables from Base metadata
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    # For PostgreSQL, execute SQL migration script
    migration_file = Path(__file__).parent / "001_initial_schema.sql"
    if migration_file.exists():
        sql_content = migration_file.read_text(encoding="utf-8")
        # Split statements by semicolon
        statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]
        async with target_engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    else:
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    print("Running MindMesh database schema initialization...")
    try:
        await init_db_schema()
        print("Database schema successfully initialized.")
    finally:
        await close_db_engine()


if __name__ == "__main__":
    asyncio.run(main())
