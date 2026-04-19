# Bifrost Backend

FastAPI backend for Bifrost — Asgard Aerospace's internal operating system.

Target deployment: `api.bifrost-dev.asgardaerospace.com`

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.x + Alembic
- PostgreSQL
- Pydantic v2 (+ pydantic-settings)

## Layout

```
backend/
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── core/
│   │   ├── config.py        # Settings (env vars)
│   │   └── database.py      # Engine / session
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   └── api/
│       ├── router.py        # Root API router
│       └── routes/          # Endpoint modules
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Setup

### 1. Create virtual environment and install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# edit .env with real DATABASE_URL and JWT_SECRET_KEY
```

Required env vars:

- `DATABASE_URL` — e.g. `postgresql+psycopg2://bifrost:bifrost@localhost:5432/bifrost`
- `JWT_SECRET_KEY` — any secure random string
- `CORS_ORIGINS` — comma-separated list of allowed frontend origins

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Run the server (local dev)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the API docs: http://localhost:8000/api/v1/docs

## Alembic

Generate a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Deployment

Structured for deployment behind `api.bifrost-dev.asgardaerospace.com`. All
configuration is supplied via environment variables — no hardcoded values.

Run with a production ASGI server, e.g.:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
