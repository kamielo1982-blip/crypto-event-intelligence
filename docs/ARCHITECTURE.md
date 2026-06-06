# Crypto Event Intelligence MVP Architecture

## Objective

Help a swing trader identify plausible cause candidates behind top crypto price
moves within 5 minutes. The product is not an auto-trading system and does not
produce buy/sell instructions.

## Runtime Layout

- `frontend`: React/Vite private dashboard served by Nginx.
- `api`: FastAPI app with cookie-based admin authentication.
- `worker`: Python scheduler that collects data at KST 09:00, 15:00, and 21:00.
- `postgres`: PostgreSQL database for normalized snapshots, raw payloads, source
  health, signals, and cached interpretations.

## Core Tables

- `assets`: investable assets and separately grouped stablecoins.
- `collection_runs`: one row per scheduled or manual collection execution.
- `market_snapshots`: price, market cap, volume, and supply values from market APIs.
- `news_items`: deduplicated news records with related symbols and source URLs.
- `onchain_snapshots`: partial MVP on-chain metrics with availability flags.
- `supply_snapshots`: circulating/total/max supply and mint/burn placeholders.
- `signal_events`: structured market, news, on-chain, and supply signals.
- `ai_interpretations`: cached cause candidates generated from structured signals.
- `source_health`: latest source success/failure status for the Data Health screen.

## Data Flow

1. Worker creates a `collection_runs` row.
2. Market and news adapters try free data sources first.
3. If a source fails and demo fallback is enabled, deterministic demo rows are
   stored with `demo_fallback` source labels.
4. On-chain and supply rows are stored as partial MVP availability.
5. Signal Engine compares current and previous snapshots.
6. AI Interpreter receives only structured signals, evidence links, and caveats.
7. Dashboard APIs serve cached brief, detail, feed, and source health views.

## API Surface

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/assets`
- `GET /api/market/brief`
- `GET /api/assets/{symbol}/overview`
- `GET /api/assets/{symbol}/signals`
- `GET /api/events`
- `GET /api/health/sources`
- `POST /api/admin/collection-runs`
- `POST /api/admin/interpretations/regenerate`

## Measurable MVP Gates

- A user can move from login to Market Brief, coin detail, evidence links, and
  filtered event feed without changing tools.
- `GET /api/market/brief` target p95: under 800 ms with indexed snapshot data.
- `GET /api/assets/{symbol}/overview` target p95: under 1.5 seconds for 80
  snapshots and 40 signals.
- Source Health must distinguish unavailable data from zero values.
- AI text must avoid buy/sell advice, definitive causality, and return forecasts.
