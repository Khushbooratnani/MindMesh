import asyncio
import logging
from pathlib import Path
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.connection.session import close_db_engine, create_async_engine_instance, get_async_engine
from app.database.models.base import Base

logger = logging.getLogger(__name__)

FORWARD_MIGRATION_PATTERN = re.compile(r"^(\d{3})_([a-zA-Z0-9_\-]+)\.sql$")


def get_forward_migration_files(migrations_dir: Path | None = None) -> list[Path]:
    """Discover, filter, and validate forward migration SQL files.
    
    Guarantees:
    1. Rollback files (containing 'rollback' in name) are strictly excluded.
    2. Only files matching standard numeric prefix ('001_...', '002_...') are included.
    3. Duplicate migration versions are rejected with ValueError.
    4. Migration files are sorted strictly in ascending version order.
    """
    target_dir = migrations_dir or Path(__file__).parent
    all_sql_files = list(target_dir.glob("*.sql"))

    forward_files: list[tuple[int, str, Path]] = []
    seen_versions: dict[int, str] = {}

    for file in all_sql_files:
        name_lower = file.name.lower()
        if "rollback" in name_lower:
            logger.info("Excluding rollback script from forward migration runner: %s", file.name)
            continue

        match = FORWARD_MIGRATION_PATTERN.match(file.name)
        if not match:
            logger.warning("Ignoring non-standard SQL file in migrations directory: %s", file.name)
            continue

        version_num = int(match.group(1))
        version_str = match.group(1)

        if version_num in seen_versions:
            raise ValueError(
                f"Duplicate migration version '{version_str}' detected: "
                f"'{file.name}' conflicts with '{seen_versions[version_num]}'"
            )

        seen_versions[version_num] = file.name
        forward_files.append((version_num, version_str, file))

    forward_files.sort(key=lambda item: item[0])
    return [item[2] for item in forward_files]


async def init_db_schema(engine: AsyncEngine | None = None) -> None:
    """Initialize or migrate the database schema safely.
    
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

    # For PostgreSQL, execute forward SQL migration scripts with tracking table
    migrations_dir = Path(__file__).parent
    migration_files = get_forward_migration_files(migrations_dir)

    async with target_engine.begin() as conn:
        # 1. Ensure migration tracking table exists
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(32) PRIMARY KEY,
                    filename VARCHAR(256) NOT NULL,
                    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
                );
                """
            )
        )

        # 2. Query already applied migration versions
        result = await conn.execute(text("SELECT version FROM schema_migrations;"))
        applied_versions = {row[0] for row in result.fetchall()}

        # 3. Apply pending migrations in strict forward sequence
        for migration_file in migration_files:
            match = FORWARD_MIGRATION_PATTERN.match(migration_file.name)
            if not match:
                continue
            version = match.group(1)

            if version in applied_versions:
                logger.info("Migration %s already applied, skipping.", migration_file.name)
                continue

            logger.info("Applying migration: %s", migration_file.name)
            sql_content = migration_file.read_text(encoding="utf-8")
            statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

            for statement in statements:
                try:
                    await conn.execute(text(statement))
                except Exception as exc:
                    logger.error(
                        "Migration %s failed while executing statement:\n%s\nError: %s",
                        migration_file.name,
                        statement[:200],
                        exc,
                    )
                    raise

            # Record successfully applied migration
            await conn.execute(
                text(
                    "INSERT INTO schema_migrations (version, filename) VALUES (:version, :filename)"
                ),
                {"version": version, "filename": migration_file.name},
            )
            logger.info("Migration %s successfully recorded in schema_migrations.", migration_file.name)


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
