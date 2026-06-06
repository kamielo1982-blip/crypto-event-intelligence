# QA Report - 2026-06-06

Target: local MVP at `http://localhost:3000` and `http://localhost:8000`

## Result

- Final health: 96/100
- Ship readiness: ready for private MVP trial after setting real `.env` secrets
- Critical/high open issues: 0
- Medium open issues: 0

## Fixed During QA

- Fixed a high-severity `Coin Intelligence` blank screen caused by `lightweight-charts` receiving newest-first marker timestamps.
- Fixed a high-severity Python dependency audit finding by upgrading to `fastapi==0.136.3` and `starlette==1.0.1`.
- Removed insecure deployment defaults by requiring `.env` values for database URL, Postgres password, admin password, and session secret.

## Verification

- `npm --prefix frontend run build`: pass
- `PYTHONPATH=backend .venv/bin/python -m unittest discover backend/tests`: 14 tests pass
- `python3 -m compileall backend/app`: pass
- `docker compose --env-file .env.example config`: pass
- `npm --prefix frontend audit --audit-level=high`: found 0 vulnerabilities
- `.venv/bin/python -m pip_audit -r backend/requirements.txt`: no known vulnerabilities
- Browser E2E: login, Market Brief, Coin Intelligence, Event Feed filters, Data Health, mobile viewport all pass
- Runtime exceptions during E2E: 0
- Unauthenticated protected endpoints returned 401
- Client bundle secret scan found no OpenAI/API/session/database secret names or values

## Performance

- `GET /api/market/brief`: p95 8.35ms across 30 local iterations, target <= 800ms
- `GET /api/assets/BTC/overview`: p95 2.18ms across 30 local iterations, target <= 1500ms

## Notes

- Docker Compose config is valid, but full image build was inconclusive in this QA run because BuildKit stalled while loading base image metadata.
- On-chain and supply data are still partial/demo-backed in the MVP and surfaced as availability caveats.
- Favicon is not configured; this is cosmetic only.
