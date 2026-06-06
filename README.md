# Crypto Event Intelligence MVP

Private dashboard for crypto swing traders who need to connect price moves with news,
market, on-chain, and supply signals without turning the product into an auto-trading
system.

## Stack

- Backend/API: FastAPI + SQLAlchemy + PostgreSQL
- Worker: Python scheduler process
- Frontend: React + Vite + TypeScript + Tailwind CSS + lightweight-charts
- Deployment: Docker Compose

## Quick Start

1. Copy the environment template and replace every `replace-with-*` value.

```bash
cp .env.example .env
```

2. Start the stack.

```bash
docker compose up --build
```

3. Open the dashboard.

```text
http://localhost:3000
```

The login comes from your `.env`:

- username: `admin`
- password: the value you set in `ADMIN_PASSWORD`

Do not use the template placeholder passwords with real data.

## Local Backend Checks

The repository includes pure Python unit tests that do not require installed FastAPI
dependencies:

```bash
PYTHONPATH=backend python3 -m unittest discover backend/tests
python3 -m compileall backend/app
```

## Data Policy

- This product is an interpretation aid, not financial advice.
- AI output must present cause candidates, evidence, caveats, and confidence.
- API keys are server-side only. Never expose them in the frontend.
- Missing data is distinct from zero data and should be shown as unavailable.
