# Web Health Monitor (MVP + Dashboard)

Backend + simple dashboard:
- Add URLs to monitor
- Background scheduler checks every minute
- Store results in SQLite (`monitor.db`)
- Dashboard page: list monitors, latest status, add/edit/enable/disable, manual run

## 1) Setup

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

pip install -r requirements.txt
```

## 2) Run

```bash
uvicorn app:app --reload
```

## 3) Open Dashboard
- Dashboard: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs

## 4) Tips
- If you add a monitor then want an instant check (no waiting 1 minute):
  - Click **Run checks now** in dashboard
  - Or call POST `/run-once`

