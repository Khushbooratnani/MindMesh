import tempfile
from pathlib import Path
import pytest

from app.database.migrations.runner import get_forward_migration_files, FORWARD_MIGRATION_PATTERN


def test_migration_runner_excludes_rollback_and_sorts_correctly():
    """Verify that rollback scripts are strictly excluded and forward files are sorted by version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "003_auth_and_locker.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "003_rollback_auth_and_locker.sql").write_text("DROP TABLE users;", encoding="utf-8")
        (tmp_path / "002_phase2.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "random_notes.txt").write_text("notes", encoding="utf-8")

        forward_files = get_forward_migration_files(tmp_path)
        filenames = [f.name for f in forward_files]

        assert "003_rollback_auth_and_locker.sql" not in filenames
        assert filenames == [
            "001_initial.sql",
            "002_phase2.sql",
            "003_auth_and_locker.sql",
        ]


def test_migration_runner_rejects_duplicate_versions():
    """Verify that duplicate migration version numbers raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "001_conflict.sql").write_text("SELECT 1;", encoding="utf-8")

        with pytest.raises(ValueError, match="Duplicate migration version '001' detected"):
            get_forward_migration_files(tmp_path)


def test_migration_runner_current_directory_check():
    """Verify the active migrations directory contains no duplicate versions and excludes rollback."""
    forward_files = get_forward_migration_files()
    filenames = [f.name for f in forward_files]

    assert "003_rollback_auth_and_locker.sql" not in filenames
    assert "001_initial_schema.sql" in filenames
    assert "002_phase2_schema.sql" in filenames
    assert "003_auth_and_locker.sql" in filenames
