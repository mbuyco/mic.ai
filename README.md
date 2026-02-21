# mic.ai

`mic.ai` is a WhatsApp-first agent platform MVP. Users create agents with persona and trigger rules, then interact through a WhatsApp Business number.

## Current MVP Focus

- WhatsApp inbound webhook handling with DB-backed idempotency
- Agent trigger engine for keyword/prefix logic
- Redis-backed queue and worker processing
- Scheduler loop for due recurring messages
- Template gating for out-of-window sends (24h customer care window)
- Cost-first defaults: outbound API calls disabled in local dev

## Current Architecture

- **FastAPI service** (`app/main.py`) for webhook and admin endpoints
- **Postgres repository** (`app/repository.py`) for rules, dedupe, turns, schedules, send ledger
- **Redis queue** (`app/queue.py`) for asynchronous job delivery
- **Worker** (`app/worker.py`) for inbound processing and outbound sends
- **Scheduler** (`app/scheduler.py`) for due recurring dispatch
- **Job handlers** (`app/jobs.py`) for processing, gating, and send flow
- **WhatsApp client** (`app/whatsapp.py`) Cloud API sender with outbound safety switch

## WhatsApp-only Behavior Notes

- WhatsApp does not provide Slack-style bot mention semantics for this MVP.
- `@michael` is treated as plain text and can be matched as a keyword/prefix.
- Scheduled/recurring messages outside the 24h window must use approved templates (template pathway is next step).

## Containerized Setup (Podman)

This project is configured to run with container-managed config and secrets.

Requirements:

- Podman 5+
- `podman compose` or `podman-compose`

Quick start:

```bash
bin/init-secrets
```

Then edit the values in `secrets/*` (one value per file).

Start stack:

```bash
bin/up
```

Alternative command:

```bash
bin/compose up --build
```

Convenience scripts:

- `bin/init-secrets` create local secret files with safe defaults/placeholders
- `bin/ensure-secrets-perms` normalize secret file permissions for rootless Podman
- `bin/up` start stack in detached mode (`--foreground` to stream output)
- `bin/down` stop and remove containers
- `bin/logs` stream logs (`bin/logs api` for one service)
- `bin/health` check API health endpoint

API is exposed on `http://localhost:8001`.

Notes:

- `compose.yml` runs 3 processes: `api` (FastAPI), `worker`, and `scheduler`, plus `postgres` + `redis`.
- Outbound sends are disabled by default (`MICAI_OUTBOUND_REPLY_ENABLED=false`) to avoid accidental costs.
- Do not commit `secrets/*`.

Fedora/SELinux note:

- Secrets are mounted with `:z` in `compose.yml` so multiple containers can share `/run/secrets` on SELinux-enforcing hosts.
- `bin/up` automatically normalizes secret file permissions to avoid rootless Podman read errors.

## Environment Variables

All variables use prefix `MICAI_`.

- `MICAI_WHATSAPP_VERIFY_TOKEN` webhook verification token (fallback if no `_FILE`)
- `MICAI_WHATSAPP_ACCESS_TOKEN` Cloud API token (fallback if no `_FILE`)
- `MICAI_WHATSAPP_PHONE_NUMBER_ID` Cloud API phone number id (fallback if no `_FILE`)
- `MICAI_DATABASE_URL` SQLAlchemy database URL (`postgresql+psycopg://...` recommended)
- `MICAI_REDIS_URL` Redis URL for queue transport
- `MICAI_ADMIN_API_KEY` required for `/admin/*` endpoints (fallback if no `_FILE`)
- `MICAI_OUTBOUND_REPLY_ENABLED` set `true` to enable real outbound sends
- `MICAI_REQUIRE_INVOKE_PREFIX` require trigger prefix to reduce spam/cost
- `MICAI_INVOKE_PREFIXES` comma-separated prefixes (default `michael:,@michael,/ask`)
- `MICAI_FREEFORM_WINDOW_HOURS` WhatsApp freeform window (default `24`)

Preferred in containers (`compose.yml` uses these):

- `MICAI_ADMIN_API_KEY_FILE=/run/secrets/admin_api_key`
- `MICAI_WHATSAPP_VERIFY_TOKEN_FILE=/run/secrets/whatsapp_verify_token`
- `MICAI_WHATSAPP_ACCESS_TOKEN_FILE=/run/secrets/whatsapp_access_token`
- `MICAI_WHATSAPP_PHONE_NUMBER_ID_FILE=/run/secrets/whatsapp_phone_number_id`

## API Endpoints (Current)

- `GET /health`
- `GET /webhook` WhatsApp verification endpoint
- `POST /webhook` inbound WhatsApp events
- `POST /admin/rules` upsert agent rule
- `POST /admin/bind/{wa_id}/{agent_id}` bind WhatsApp user to agent

Admin endpoints require `x-admin-key` header.

## Local Development (No Containers)

Requirements:

- Python 3.11+
- Postgres + Redis (or run them via containers and run only the API locally)

Setup + run:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"

# provide env vars (or export *_FILE equivalents)
export MICAI_DATABASE_URL='postgresql+psycopg://...'
export MICAI_REDIS_URL='redis://localhost:6379/0'
export MICAI_ADMIN_API_KEY='...'

uvicorn app.main:app --reload --port 8001
```

Run background processors (separate terminals):

```bash
python -m app.worker
python -m app.scheduler
```

## Tests

```bash
python -m pytest
```

## Next Execution Milestones

1. Add proper migration workflow (Alembic)
2. Add reminder/weather tool execution path and strict allowlist
3. Implement retry policy with jitter and dead-letter handling
4. Add STT pipeline for voice notes and optional TTS feature flag
5. Add dashboards/alerts for queue lag, send failures, and dedupe conflicts
