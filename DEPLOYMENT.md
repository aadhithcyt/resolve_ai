# ResolveAI Deployment Guide

## System Requirements

- Python 3.10+
- 2GB RAM minimum (4GB recommended)
- 1GB disk space
- Groq API key (free tier available)

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| RHEL 9 / CentOS 9 | Fully tested | Use `setup.sh` |
| Ubuntu 22.04+ | Fully tested | Use `setup.sh` |
| Windows 10/11 | Fully tested | Use `setup.bat` |
| macOS 13+ | Fully tested | Use `setup.sh` |

## Quick Start

### Linux / RHEL / macOS

```bash
git clone https://github.com/aadhithcyt/resolveai.git
cd resolveai
chmod +x setup.sh
./setup.sh
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Windows

```cmd
git clone https://github.com/aadhithcyt/resolveai.git
cd resolveai
setup.bat
.venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker (All Platforms)

```bash
docker build -t resolveai .
docker run -p 8000:8000 -e GROQ_API_KEY=your-key resolveai
```

Or with docker-compose:

```bash
docker-compose up -d
```

## RHEL-Specific Setup

### Install Python 3.10+ on RHEL 9

```bash
sudo dnf install python3.11 python3.11-pip
sudo dnf install gcc python3-devel  # For building native deps
```

### Firewall Configuration

```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### Run as Systemd Service

Create `/etc/systemd/system/resolveai.service`:

```ini
[Unit]
Description=ResolveAI Customer Support Desk
After=network.target

[Service]
Type=simple
User=resolveai
WorkingDirectory=/opt/resolveai
ExecStart=/opt/resolveai/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable resolveai
sudo systemctl start resolveai
sudo systemctl status resolveai
```

## Windows-Specific Setup

### Install Python on Windows

1. Download Python 3.10+ from https://python.org
2. During installation, check "Add Python to PATH"
3. Verify: `python --version`

### Run as Windows Service

Use NSSM (Non-Sucking Service Manager):

```cmd
nssm install ResolveAI "C:\resolveai\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
nssm set ResolveAI AppDirectory C:\resolveai
nssm start ResolveAI
```

### Windows Firewall

```cmd
netsh advfirewall firewall add rule name="ResolveAI" dir=in action=allow protocol=TCP localport=8000
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | — | Groq API key |
| `RESOLVEAI_DB` | No | `./resolveai.db` | SQLite database path |
| `RESOLVEAI_MODEL` | No | `openai/gpt-oss-120b` | Groq model |
| `RESOLVEAI_HOST` | No | `127.0.0.1` | Server bind address |
| `RESOLVEAI_PORT` | No | `8000` | Server port |
| `RESOLVEAI_API_KEY` | No | (empty) | API key for X-API-Key auth |
| `RATE_LIMIT_RPM` | No | `60` | Requests per minute |
| `RATE_LIMIT_BURST` | No | `10` | Burst capacity |
| `EMAIL_HOST` | No | (empty) | SMTP host |
| `EMAIL_PORT` | No | `587` | SMTP port |
| `EMAIL_USER` | No | (empty) | SMTP username |
| `EMAIL_PASSWORD` | No | (empty) | SMTP password |
| `EMAIL_FROM` | No | `noreply@resolveai.local` | From address |
| `EMAIL_TO` | No | (empty) | To address |

## Migrating from RHEL (or any Linux) to Windows

The application itself is OS-independent: no POSIX-only modules, all paths built
with `pathlib`, every file opened with an explicit UTF-8 encoding, and no
compiled dependencies. What must change is the environment and the commands.

### 1. Files you must NOT copy across

| Item | Why | What to do instead |
|------|-----|--------------------|
| `.venv/` | Contains Linux binaries and a Linux `python` symlink | Delete it; run `setup.bat` on Windows |
| `__pycache__/` | Compiled bytecode is version- and OS-specific | Ignore it (already gitignored); Python regenerates it |
| `resolveai.db` | Optional. Safe to copy, but see the timestamp note below | Copy only if you want the existing data |
| `uploads/` | Paths are stored in the database as absolute paths | See step 5 |

### 2. Install and set up

```cmd
:: 1. Install Python 3.10+ from https://python.org
::    During setup, tick "Add Python to PATH".

:: 2. Clone or copy the project, then:
cd C:\resolveai
setup.bat

:: 3. Set the Groq key (persists for the current session only):
set GROQ_API_KEY=your-key-here

:: 4. Start it:
run.bat
```

To set the key permanently on Windows:

```cmd
setx GROQ_API_KEY "your-key-here"
```
(`setx` affects new shells only — open a new terminal after running it.)

### 3. Environment variables: RHEL vs Windows

The variable names are identical. Only the syntax differs.

| RHEL / Linux | Windows CMD | Windows PowerShell |
|--------------|-------------|--------------------|
| `export GROQ_API_KEY=abc` | `set GROQ_API_KEY=abc` | `$env:GROQ_API_KEY="abc"` |
| `export RESOLVEAI_DB=./app.db` | `set RESOLVEAI_DB=.\app.db` | `$env:RESOLVEAI_DB=".\app.db"` |
| `python3 -m uvicorn ...` | `python -m uvicorn ...` | `python -m uvicorn ...` |
| `./setup.sh` | `setup.bat` | `.\setup.bat` |

Note `python3` on Linux is `python` on Windows.

### 4. Run it as a background service on Windows

Use NSSM as described in the Windows-Specific Setup section above. Point
`AppDirectory` at the project root and use the venv interpreter:

```cmd
nssm install ResolveAI "C:\resolveai\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
nssm set ResolveAI AppDirectory C:\resolveai
nssm set ResolveAI AppEnvironmentExtra GROQ_API_KEY=your-key-here
nssm start ResolveAI
```

### 5. If you copy the existing database

Two things to check:

- **Attachment paths.** `attachments.file_path` stores the full path the file
  was saved under. Rows written on Linux hold paths like
  `/opt/resolveai/uploads/abc_file.pdf`, which do not exist on Windows. Either
  re-upload the attachments, or fix the rows after copying:

  ```sql
  UPDATE attachments
     SET file_path = 'C:\resolveai\uploads\' || substr(file_path, instr(file_path, '/') + 1);
  ```
  Run this in the sqlite3 CLI on Windows after placing the files in
  `C:\resolveai\uploads\`.

- **Timestamps.** Older rows may hold SQLite's naive format
  (`2026-10-12 15:48:29`). The application normalises both that and the aware
  format (`2026-10-12T15:48:29+00:00`) through `config.parse_ts()`, so both are
  read correctly. No data migration is required.

### 6. Verify the migration worked

```cmd
:: Health check
curl http://localhost:8000/health

:: Run the cross-platform test suite (no API key needed)
python -m pytest tests/test_platform.py -q

:: Full suite
python -m pytest -q
```

A healthy instance returns `{"status":"ok","service":"ResolveAI"}`. The
platform test module asserts the Windows-specific invariants: no POSIX-only
imports, every text-mode `open()` declares an encoding, no deprecated
`asyncio.get_event_loop()`, and timestamps parse from both formats.

### 7. What is already Windows-safe (verified)

- No POSIX-only imports anywhere in `app/` (`fcntl`, `pwd`, `termios`,
  `resource`, ...).
- Every file path is built with `pathlib`, so separators are correct per OS.
- Every text-mode file read/write passes an explicit `encoding="utf-8"`; the
  i18n module holds Chinese, German and French strings that would raise
  `UnicodeDecodeError` under Windows' default cp1252 codec otherwise.
- All dependencies are pure-Python or ship Windows wheels — no compiler needed.
- No shell commands are invoked from Python (`subprocess`/`os.system` unused).
- `asyncio.get_running_loop()` is used instead of the deprecated
  `get_event_loop()`.
- Uvicorn's `uvloop` extra is optional; on Windows it is skipped automatically
  and the standard asyncio loop is used.

## Production Checklist

- [ ] Set strong `RESOLVEAI_API_KEY`
- [ ] Configure `GROQ_API_KEY`
- [ ] Set up email notifications
- [ ] Enable HTTPS (reverse proxy with nginx/caddy)
- [ ] Set up log rotation
- [ ] Configure backups for SQLite database
- [ ] Set up monitoring (health endpoint at `/health`)
- [ ] Review rate limiting settings

## Troubleshooting

### Port already in use

```bash
# Linux
sudo lsof -i :8000
sudo kill <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Database locked

SQLite is single-writer. If you see "database is locked" errors:
- Ensure only one process is writing
- Enable WAL mode: `PRAGMA journal_mode=WAL;`

### Groq API errors

- Check your API key is valid
- Verify you haven't exceeded free tier limits
- Check status at https://console.groq.com
