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
git clone https://github.com/YOUR_USERNAME/resolveai.git
cd resolveai
chmod +x setup.sh
./setup.sh
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Windows

```cmd
git clone https://github.com/YOUR_USERNAME/resolveai.git
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
