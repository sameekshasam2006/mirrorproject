# MIRROR

MIRROR is a digital twin planning platform that helps users understand the impact of schedule decisions before they apply them.

## Project structure

- `frontend/` — React + Vite + Tailwind frontend
- `backend/` — FastAPI + SQLAlchemy backend

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev -- --host 0.0.0.0
```

## Environment variables

Update `.env` files with your local settings before running the app.

- The frontend uses `VITE_API_BASE`. For local development, `/api` is proxied
  to the backend at `http://localhost:8000`; set it to the public backend URL
  when building for production.
- The backend uses `APP_ENV`, `SECRET_KEY`, `DATABASE_URL`, and
  `FRONTEND_ORIGIN`. Production requires a random `SECRET_KEY` of at least 32
  characters and a persistent PostgreSQL `DATABASE_URL`.
- Password reset email requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL`. Configure these in the backend host;
  reset links are not returned by the API.
- `frontend/vercel.json` enables client-side route fallback. The root
  `render.yaml` configures a Render web service; its free plan sleeps when idle
  and has ephemeral disk, so the database must be external and persistent.

## Default login

Create a user via the registration page or use the API directly to create an account.

## Key features

- Secure auth flow
- Task management with validation
- Calendar timeline
- Rule-based what-if simulation engine
- Analytics summaries
- Notification storage and push-subscription endpoints
