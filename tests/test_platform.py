"""Tests for cross-platform compatibility (RHEL, Windows, macOS).

These tests are intentionally strict: they must FAIL if the codebase would break
on Windows, not merely pass on Linux. The original version of this file only
checked that pathlib was used and that no hardcoded paths appeared, which would
still pass on a codebase that was broken on Windows for other reasons.

The classes of real Windows breakage covered here:
  1. Text file I/O without an explicit encoding -> UnicodeDecodeError, because
     Windows defaults to cp1252 rather than UTF-8.
  2. Deprecated asyncio.get_event_loop() -> errors when no loop is running.
  3. POSIX-only imports (fcntl, pwd, termios, resource, ...) -> ImportError.
  4. os.path string concatenation instead of pathlib.
  5. Naive vs aware datetime arithmetic -> TypeError (this bit us in
     production: it silently disabled an escalation rule).
"""
import ast
import os
import sys
import platform
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _python_files():
    return sorted(APP_DIR.rglob("*.py"))


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
    assert "uploads" in str(uploads_dir)


def test_no_hardcoded_unix_paths():
    """Config source should not contain hardcoded Unix paths."""
    import inspect
    import app.config
    source = inspect.getsource(app.config)
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
    """Database path should be overridable via env var.

    Restores the original value with os.environ.pop() rather than assigning "".
    Setting the variable to an empty string is NOT the same as unsetting it --
    os.getenv(key, default) returns "" when the key exists but is empty, so
    leaving "" behind overrode the test database path for every later test that
    opened a connection (which is exactly what broke this file before).
    """
    import importlib
    import app.config

    original = os.environ.get("RESOLVEAI_DB")
    os.environ["RESOLVEAI_DB"] = str(tmp_path / "test.db")
    try:
        importlib.reload(app.config)
        assert str(tmp_path / "test.db") in str(app.config.DB_PATH)
    finally:
        if original is None:
            os.environ.pop("RESOLVEAI_DB", None)
        else:
            os.environ["RESOLVEAI_DB"] = original
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
    assert "app" in str(subdir)
    assert "routers" in str(subdir)


# ─── Windows-specific breakage classes ──────────────────────────────────────


def test_no_posix_only_module_imports():
    """No module may import a POSIX-only library, which fails on Windows."""
    posix_only = {
        "fcntl", "pwd", "grp", "termios", "resource", "crypt",
        "pty", "tty", "syslog", "posix", "nis", "spwd", "ossaudiodev",
    }
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in posix_only:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in posix_only:
                    offenders.append(f"{path.name}: from {node.module} import ...")
    assert not offenders, f"POSIX-only imports break Windows: {offenders}"


def test_text_file_io_declares_encoding():
    """Every text-mode open() must pass an explicit encoding.

    Windows defaults text-mode I/O to cp1252, so reading or writing UTF-8
    content (the i18n module holds Chinese, German and French strings) raises
    UnicodeDecodeError there while working fine on Linux. Binary mode ("rb"/"wb")
    is exempt because it performs no decoding.
    """
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open"):
                continue
            mode = None
            has_encoding = any(kw.arg == "encoding" for kw in node.keywords)
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if mode is not None and "b" in str(mode):
                continue  # binary mode: no decoding happens
            if not has_encoding:
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "open() in text mode without encoding= will fail on Windows (cp1252): "
        f"{offenders}"
    )


def test_no_deprecated_get_event_loop():
    """asyncio.get_event_loop() is deprecated and raises with no running loop.

    Use asyncio.get_running_loop() inside coroutines. Checked on the AST so that
    mentions in comments and docstrings (including the warning comment that
    explains this very rule) are not false positives.
    """
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_event_loop"
                and getattr(node.func.value, "id", "") == "asyncio"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        f"asyncio.get_event_loop() is deprecated; use get_running_loop(): {offenders}"
    )


def test_no_os_path_string_concatenation():
    """Paths must be built with pathlib, not os.path.join or manual joining."""
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        if "os.path.join(" in source:
            offenders.append(path.name)
    assert not offenders, f"Use pathlib instead of os.path.join: {offenders}"


# ─── Timezone handling (naive vs aware datetimes) ───────────────────────────


def test_parse_ts_handles_sqlite_naive_timestamp():
    """parse_ts must convert SQLite's naive format to an aware UTC datetime."""
    from app.config import parse_ts
    from datetime import timezone

    naive = parse_ts("2026-10-12 15:48:29")
    assert naive is not None
    assert naive.tzinfo is not None
    assert naive.utcoffset() == timezone.utc.utcoffset(None)


def test_parse_ts_handles_aware_iso_string():
    """parse_ts must accept the aware ISO format the app writes."""
    from app.config import parse_ts
    aware = parse_ts("2026-10-12T15:48:29+00:00")
    assert aware is not None
    assert aware.tzinfo is not None


def test_parse_ts_handles_zulu_and_none():
    """parse_ts must handle a trailing Z, None, and junk without raising."""
    from app.config import parse_ts
    assert parse_ts("2026-10-12T15:48:29Z") is not None
    assert parse_ts(None) is None
    assert parse_ts("") is None
    assert parse_ts("not a date") is None


def test_timestamps_are_comparable_across_formats():
    """A naive SQLite timestamp and an aware ISO timestamp must be subtractable."""
    from app.config import parse_ts
    from datetime import datetime, timezone

    a = parse_ts("2026-10-12 15:48:29")           # naive, from SQLite
    b = datetime.now(timezone.utc)                 # aware, from the app
    delta = (b - a).total_seconds()                # must not raise TypeError
    assert isinstance(delta, float)


def test_no_raw_fromisoformat_on_stored_timestamps():
    """Stored timestamps must be parsed with parse_ts, not datetime.fromisoformat.

    Mixing the two formats caused a real bug: an escalation rule silently never
    fired because a TypeError was swallowed by a broad except clause.
    """
    # config.parse_ts() is the single sanctioned place that calls
    # datetime.fromisoformat on a stored value; everything else must go through it.
    allowed = {"config.py"}
    offenders = []
    for path in _python_files():
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "fromisoformat"
                and getattr(node.func.value, "id", "") == "datetime"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "Use config.parse_ts() for stored timestamps (handles naive SQLite "
        f"values): {offenders}"
    )


@pytest.mark.asyncio
async def test_escalation_rule_3_fires_for_stale_ticket():
    """Escalation Rule 3 must actually escalate a 48h+ ticket with no reply.

    Regression test: this rule was dead because the datetime subtraction raised
    TypeError and the broad except swallowed it.
    """
    from app.database import get_db
    from app.escalation import check_escalation_rules

    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?)",
            ("Stale Cust", "stale@test.com"),
        )
        cid = cur.lastrowid
        # created_at in SQLite's naive format, 72 hours ago
        await db.execute(
            """INSERT INTO tickets
               (customer_id, subject, description, priority, status, created_at)
               VALUES (?, ?, ?, 'medium', 'open', datetime('now', '-72 hours'))""",
            (cid, "Stale ticket", "nobody replied"),
        )
        await db.commit()
        cur = await db.execute("SELECT id FROM tickets")
        tid = (await cur.fetchone())["id"]

    result = await check_escalation_rules(tid)
    assert result is not None, (
        "Rule 3 did not fire: a 72h-old open ticket with no agent reply should "
        "escalate to high"
    )
    assert result["new_priority"] == "high"


@pytest.mark.asyncio
async def test_email_created_ticket_has_sla_deadline():
    """Tickets created from email must get a real sla_due_at, like API ones."""
    from app.database import get_db
    from app.workers import _create_ticket_from_email

    await _create_ticket_from_email({
        "from": "newperson@example.com",
        "from_header": "New Person <newperson@example.com>",
        "subject": "Help me",
        "body": "I need assistance",
        "date": "",
        "message_id": "<x@y>",
    })
    async with get_db() as db:
        cur = await db.execute(
            "SELECT sla_due_at, created_at FROM tickets ORDER BY id DESC LIMIT 1"
        )
        row = dict(await cur.fetchone())
    assert row["sla_due_at"] is not None, "email-created ticket has no SLA deadline"
    assert row["created_at"] is not None

    from app.config import parse_ts
    assert parse_ts(row["sla_due_at"]) is not None
    assert parse_ts(row["created_at"]) is not None


# ─── Script / packaging checks ──────────────────────────────────────────────


def test_windows_scripts_exist_and_are_nonempty():
    """Both .bat scripts must exist for Windows users."""
    root = Path(__file__).resolve().parent.parent
    for name in ("setup.bat", "run.bat"):
        f = root / name
        assert f.exists(), f"{name} is missing"
        assert f.stat().st_size > 0, f"{name} is empty"


def test_unix_scripts_have_shebang_and_venv_guard():
    """Shell scripts need a shebang, and run.sh must not hard-fail on no venv."""
    root = Path(__file__).resolve().parent.parent
    for name in ("setup.sh", "run.sh"):
        text = (root / name).read_text(encoding="utf-8")
        assert text.startswith("#!"), f"{name} lacks a shebang"
    run_sh = (root / "run.sh").read_text(encoding="utf-8")
    assert "Scripts/activate" in run_sh, (
        "run.sh should handle the Windows venv layout (.venv/Scripts/activate) "
        "so it works under Git Bash"
    )


def test_requirements_have_no_platform_specific_pins():
    """No dependency may be pinned to a platform-specific build."""
    root = Path(__file__).resolve().parent.parent
    text = (root / "requirements.txt").read_text(encoding="utf-8")
    lowered = text.lower()
    for bad in ("win32", "manylinux", "macosx", "platform_system"):
        assert bad not in lowered, f"requirements.txt contains platform pin: {bad}"


def test_gitattributes_exists_and_pins_line_endings():
    """A .gitattributes must exist and pin per-extension line endings.

    Without it, a Windows checkout can end up with LF-only .bat files (which
    cmd.exe mishandles) or CRLF .sh files (which break the shebang with
    "bad interpreter: /bin/bash^M").
    """
    root = Path(__file__).resolve().parent.parent
    ga = root / ".gitattributes"
    assert ga.exists(), ".gitattributes is missing - line endings are not normalised"
    text = ga.read_text(encoding="utf-8")
    assert "*.bat" in text and "eol=crlf" in text, ".bat must be pinned to CRLF"
    assert "*.sh" in text and "eol=lf" in text, ".sh must be pinned to LF"


def test_bat_files_use_crlf_line_endings():
    """Windows batch files must use CRLF, not bare LF.

    cmd.exe is unreliable with LF-only batch files: multi-line blocks and
    labels can misbehave in ways that are hard to diagnose.
    """
    root = Path(__file__).resolve().parent.parent
    for name in ("setup.bat", "run.bat"):
        data = (root / name).read_bytes()
        assert b"\r\n" in data, f"{name} must use CRLF line endings for cmd.exe"
        # A bare LF that is not part of CRLF would indicate mixed endings.
        stripped = data.replace(b"\r\n", b"")
        assert b"\n" not in stripped, f"{name} has mixed line endings"


def test_shell_scripts_use_lf_line_endings():
    """Shell scripts must use LF; CRLF breaks the shebang on Linux."""
    root = Path(__file__).resolve().parent.parent
    for name in ("setup.sh", "run.sh"):
        data = (root / name).read_bytes()
        assert b"\r\n" not in data, (
            f"{name} contains CRLF - the shebang will fail on Linux/macOS "
            'with "bad interpreter"'
        )


def test_no_case_insensitive_filename_collisions():
    """No two tracked files may differ only by case.

    Windows filesystems are case-insensitive, so app/Foo.py and app/foo.py
    cannot coexist and a clone would fail or silently drop one.
    """
    import subprocess
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True
    ).stdout.splitlines()
    if not out:
        pytest.skip("not a git checkout")
    lowered = [f.lower() for f in out]
    dupes = {f for f in lowered if lowered.count(f) > 1}
    assert not dupes, f"files differing only by case break Windows: {sorted(dupes)}"


def test_no_windows_reserved_filenames():
    """No tracked file may use a Windows reserved device name."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True
    ).stdout.splitlines()
    if not out:
        pytest.skip("not a git checkout")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
        f"LPT{i}" for i in range(1, 10)
    }
    bad = []
    for f in out:
        stem = Path(f).name.split(".")[0].upper()
        if stem in reserved:
            bad.append(f)
    assert not bad, f"Windows reserved device names cannot be created: {bad}"


def test_no_windows_illegal_characters_in_filenames():
    """Filenames must not contain characters Windows forbids: : * ? " < > |"""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True
    ).stdout.splitlines()
    if not out:
        pytest.skip("not a git checkout")
    illegal = set(': * ? " < > |')
    bad = [f for f in out if any(ch in illegal for ch in f)]
    assert not bad, f"filenames contain characters illegal on Windows: {bad}"


def test_imports_are_case_exact():
    """Module imports must match the real filename's case.

    On Linux, `from .Models import X` would resolve to models.py; on Windows it
    would not, or would resolve to a different file. Check that every
    intra-package import names an existing module with exact case.
    """
    import re
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"^from\s+([.\w]+)\s+import\s", text, re.M):
            mod = m.group(1)
            if not mod.startswith("."):
                continue
            # Relative import: walk the dotted segments from the file's own
            # package directory. A multi-segment module like ".routers.kb"
            # lives at app/routers/kb.py, not app/kb.py.
            dots = len(mod) - len(mod.lstrip("."))
            parts = mod.lstrip(".").split(".") if mod.lstrip(".") else []
            if not parts:
                continue
            base = path.parent
            for _ in range(dots - 1):          # one dot = current package
                base = base.parent
            target = base.joinpath(*parts)
            if not (target.with_suffix(".py").exists() or (target / "__init__.py").exists()):
                offenders.append(f"{path.name}: from {mod} import ...")
    assert not offenders, (
        "imports reference modules that do not exist with that exact case "
        f"(would fail on Windows): {offenders}"
    )


# ─── Tunnel / reverse-proxy compatibility ───────────────────────────────────


def test_frontend_uses_relative_urls_only():
    """The frontend must not hardcode a host or port.

    When the app is reached through an SSH tunnel, a reverse proxy, or a
    different hostname, absolute URLs like http://localhost:8000/api/... would
    point the browser at the wrong machine and break the UI. All requests must
    be relative so they follow whatever address the browser used.
    """
    import re

    root = Path(__file__).resolve().parent.parent
    offenders = []
    for rel in ("app/static/js/app.js", "app/templates/index.html", "public/sw.js"):
        f = root / rel
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"https?://(localhost|127\.0\.0\.1|[\d.]+)(:\d+)?", text):
            offenders.append(f"{rel}: {m.group(0)}")
    assert not offenders, (
        "frontend hardcodes a host/port, which breaks access via a tunnel or "
        f"proxy: {offenders}"
    )


def test_websocket_url_derived_from_location():
    """The chat WebSocket URL must be built from location.host.

    A hardcoded ws://localhost:8000/... would fail whenever the page is served
    from a different origin (tunnel, proxy, or another host), silently breaking
    real-time chat.
    """
    root = Path(__file__).resolve().parent.parent
    js = (root / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "location.host" in js, (
        "app.js should build the WebSocket URL from location.host so it works "
        "through a tunnel or proxy"
    )
    assert "ws://localhost" not in js and "wss://localhost" not in js, (
        "app.js must not hardcode a WebSocket host"
    )


def test_served_html_uses_root_relative_asset_paths():
    """index.html asset references must be root-relative, not absolute URLs."""
    import re

    root = Path(__file__).resolve().parent.parent
    html = (root / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    for m in re.finditer(r'(?:src|href)="([^"]+)"', html):
        url = m.group(1)
        if url.startswith(("http://", "https://", "//")):
            raise AssertionError(f"absolute asset URL breaks tunnel access: {url}")
