# MIRROR

MIRROR is a digital twin planning platform that helps users understand the impact of schedule decisions before they apply them.

## Project structure

- `frontend/` — React + Vite + Tailwind frontend
- `backend/` — FastAPI + SQLAlchemy backend

## Quick start

The backend creates `backend/mirror.db` automatically when no database URL is
configured. After installing the backend and frontend dependencies below, the
recommended way to start both is from the project root:

```powershell
npm run dev
```

This starts the backend first and waits for its `/health` endpoint before
starting Vite, preventing API proxy requests during backend startup. To run them
separately instead, use **two PowerShell windows** and start the backend first.

### Backend (PowerShell)

```powershell
Set-Location backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (PowerShell)

```powershell
Set-Location frontend
npm install
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

Open `http://localhost:5173`, register an account, and add tasks from the Tasks
page. The What-If Simulator compares plans without changing saved tasks; approve
the recommended or selected alternative plan to update the task list and
calendar. The simulator uses the working hours in user preferences and otherwise
defaults to 09:00–17:00.

### Tests

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest
Set-Location ..\frontend
npm run build
npm run lint
```

## Environment variables

Update `.env` files with your local settings before running the app.

- The frontend uses `VITE_API_BASE=/api`. Vite proxies `/api` to the local
  backend at `http://localhost:8000`.
- The backend uses local SQLite and allows requests from the frontend at
  `http://localhost:5173`. No deployment configuration is required.
- Password reset email requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL`. These settings can be left empty for
  local development; reset links are not returned by the API.

## Default login

Create a user via the registration page or use the API directly to create an account.

## Key features

- Secure auth flow
- Task management with validation
- Calendar timeline
- Rule-based what-if simulation engine
- Analytics summaries
- Notification storage and push-subscription endpoints
