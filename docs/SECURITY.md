# Security Notes

## Authentication

- The MVP uses a single admin account configured through environment variables.
- Sessions are HMAC-signed and stored in an HTTP-only cookie named
  `crypto_intel_session`.
- Set `SESSION_SECRET` to a long random value before any real deployment.
- Set `SESSION_COOKIE_SECURE=true` when serving over HTTPS.

## Secret Handling

- API keys, OpenAI keys, and database credentials must stay in `.env` or the
  server/worker environment.
- Frontend code must not reference `OPENAI_API_KEY`, exchange credentials, raw
  OAuth data, Telegram tokens, or private logs.
- `.env` is ignored by git.

## AI Input Boundary

- AI interpretation receives structured `signal_events`, evidence URLs, and
  caveats only.
- Raw HTML, article bodies, user prompt-like text, and untrusted commands should
  not be passed directly into AI prompts.
- Output parsing rejects trading advice language such as buy/sell calls,
  definitive causality, or return prediction phrasing.

## External Data

- Free sources can be incomplete, delayed, rate-limited, or unavailable.
- Demo fallback data is explicitly labeled as `demo_fallback`.
- On-chain and supply availability must be displayed as partial or unavailable
  until real adapters are implemented per chain.

## Deployment Checklist

- Change `ADMIN_PASSWORD`.
- Change `SESSION_SECRET`.
- Keep `SESSION_COOKIE_SECURE=true` behind HTTPS.
- Restrict network access to the private dashboard.
- Review client bundle for accidental secret strings before deployment.
