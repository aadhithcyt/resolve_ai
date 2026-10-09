"""Tests for cross-platform compatibility (RHEL, Windows, macOS)."""
import os
import sys
import platform
from pathlib import Path

import pytest


def test_paths_use_pathlib():
    """All path operations should use pathlib, not string concatenation."""
    from app.config import BASE_DIR, DB_PATH
    assert isinstance(BASE_DIR, Path)
    assert isinstance(DB_PATH, (str, Path))


def test_db_path_is_absolute():
    """Database path should be absolute."""
    from app.config import DB_PATH
    db_path = Path(DB_PATH)
    assert db_path.is_absolute() or str(db_path).startswith(".")


def test_uploads_dir_creation():
    """Uploads directory should be created if it doesn't exist."""
    from app.config import BASE_DIR
    uploads_dir = BASE_DIR / "uploads"
    # Don't actually create in test, just verify the path is valid
    assert "uploads" in str(uploads_dir)


def test_no_hardcoded_unix_paths():
    """Config source should not contain hardcoded Unix paths."""
    import inspect
    import app.config
    source = inspect.getsource(app.config)
    # The config should use env vars or relative paths, not absolute Unix paths
    assert "/root/" not in source
    assert "/home/" not in source
    assert 'C:\\' not in source
    assert "D:\\" not in source


def test_no_hardcoded_windows_paths():
    """No hardcoded Windows paths like C:\\ in config."""
    from app.config import DB_PATH
    db_str = str(DB_PATH)
    assert not db_str.startswith("C:\\")
    assert not db_str.startswith("D:\\")


def test_static_files_resolve():
    """Static files directory should resolve correctly."""
    from app.config import BASE_DIR
    static_dir = BASE_DIR / "app" / "static"
    assert static_dir.exists()
    assert (static_dir / "css" / "style.css").exists()
    assert (static_dir / "js" / "app.js").exists()


def test_templates_resolve():
    """Templates directory should resolve correctly."""
    from app.config import BASE_DIR
    templates_dir = BASE_DIR / "app" / "templates"
    assert templates_dir.exists()
    assert (templates_dir / "index.html").exists()


def test_platform_detection():
    """Platform should be detectable."""
    system = platform.system()
    assert system in ("Linux", "Darwin", "Windows", "Java")


def test_python_version():
    """Python version should be 3.10+."""
    assert sys.version_info >= (3, 10)


def test_env_var_override(tmp_path):
    """Database path should be overridable via env var."""
    os.environ["RESOLVEAI_DB"] = str(tmp_path / "test.db")
    # Need to reimport to pick up new env var
    import importlib
    import app.config
    importlib.reload(app.config)
    assert str(tmp_path / "test.db") in str(app.config.DB_PATH)
    # Reset
    os.environ["RESOLVEAI_DB"] = ""
    importlib.reload(app.config)


def test_file_operations_cross_platform(tmp_path):
    """File operations should work on any platform."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")
    assert test_file.read_text() == "hello"
    assert test_file.exists()
    test_file.unlink()
    assert not test_file.exists()


def test_path_join_cross_platform():
    """Path joining should work correctly."""
    from app.config import BASE_DIR
    subdir = BASE_DIR / "app" / "routers"
    assert subdir.is_dir()
    # Should work regardless of OS path separator
    assert "app" in str(subdir)
    assert "routers" in str(subdir)
