# Installation Guide

## Requirements

- Python 3.11 or newer
- Git
- Network access to Sleeper for live synchronization; an existing cache supports degraded offline startup

## Windows PowerShell

```powershell
git clone https://github.com/Richarddavis47/dtos.git
cd dtos
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.validation.validate_release
.\.venv\Scripts\python.exe -m uvicorn dtos_app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Keep `.venv`, cache files, and credentials outside version control.

## First startup

DTOS loads `DTOS_CACHE_FILE`, attempts a Sleeper synchronization, and serves cached data if synchronization fails. With neither live nor cached data, data-dependent routes return HTTP 503 while health endpoints remain available.
