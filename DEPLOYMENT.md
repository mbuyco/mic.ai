# Deployment

This repo runs a FastAPI API service plus a worker and scheduler, backed by Postgres and Redis. The API exposes `/health` and `/webhook` and must be reachable over HTTPS for Meta/WhatsApp webhooks.

## Deployment Recommendation

Default recommendation: deploy on Render with three services (api, worker, scheduler) plus managed Postgres and managed Redis.

Why this default:

- Lower ops burden than VM self-hosting
- Matches this app's multi-process model (not serverless-only)
- Lets you keep only the api public while worker/scheduler stay private
- Simple health checks and env var management in one place

## Architecture Snapshot

- api: FastAPI app (container port 8000; compose maps to 8001)
- worker: `python -m app.worker`
- scheduler: `python -m app.scheduler`
- postgres: Postgres 16
- redis: Redis 7

## Implementation Plan and Progress Checklist

Progress legend: `[x]` complete, `[ ]` pending.

1. Discovery and deployment decision
- [x] Confirm runtime model, ports, and required endpoints.
- [x] Choose default deployment path (Render + managed DB/Redis).
- [x] Publish deployment runbook (`DEPLOYMENT.md`).
- [x] Add Render Blueprint file (`render.yaml`) for api/worker/scheduler + Postgres + Redis.

2. Infrastructure provisioning
- [ ] Provision Postgres and Redis.
- [ ] Record and validate `MICAI_DATABASE_URL` and `MICAI_REDIS_URL`.

3. Secret management
- [ ] Generate strong production secrets and tokens.
- [ ] Configure platform secret storage for api/worker/scheduler.
- [ ] Ensure no dev defaults are used in production.

4. Service deployment
- [ ] Deploy api with public HTTPS ingress.
- [ ] Deploy worker and scheduler as private/background services.
- [ ] Configure api health check to `GET /health`.

5. WhatsApp webhook wiring
- [ ] Set callback URL to `https://<domain>/webhook`.
- [ ] Set verify token to `MICAI_WHATSAPP_VERIFY_TOKEN`.
- [ ] Validate inbound flow end-to-end (webhook -> queue -> worker).

6. Security hardening before internet exposure
- [ ] Implement `X-Hub-Signature-256` verification for `POST /webhook`.
- [ ] Restrict `/admin/*` behind allowlist, VPN, or gateway.
- [ ] Add rate limits and body-size limits at edge/platform.

7. Outbound activation and rollback safety
- [ ] Keep `MICAI_OUTBOUND_REPLY_ENABLED=false` during bring-up.
- [ ] Enable outbound only after hardening and successful webhook tests.
- [ ] Define rollback: disable outbound and rotate secrets if anomalies occur.

## Required Endpoints

- `GET /health`
- `GET /webhook` (Meta verification)
- `POST /webhook` (inbound messages)

## Secrets and Environment

Use `MICAI_`-prefixed env vars (or secret files in `/run/secrets`). Do not deploy with dev defaults.

Required:

- `MICAI_DATABASE_URL`
- `MICAI_REDIS_URL`
- `MICAI_ADMIN_API_KEY` or `MICAI_ADMIN_API_KEY_FILE`
- `MICAI_WHATSAPP_VERIFY_TOKEN` or `MICAI_WHATSAPP_VERIFY_TOKEN_FILE`
- `MICAI_WHATSAPP_ACCESS_TOKEN` or `MICAI_WHATSAPP_ACCESS_TOKEN_FILE`
- `MICAI_WHATSAPP_PHONE_NUMBER_ID` or `MICAI_WHATSAPP_PHONE_NUMBER_ID_FILE`

Recommended:

- `MICAI_OUTBOUND_REPLY_ENABLED=true` only when ready to send real messages
- `MICAI_REQUIRE_INVOKE_PREFIX=true`
- `MICAI_INVOKE_PREFIXES=michael:,@michael,/ask`

## Render Deployment (Default Path)

This app requires three long-running processes from the same codebase. On Render, deploy one Web Service (api) and two Background Workers (worker, scheduler).

### 1) Prerequisites

- A Render account connected to this Git repo
- WhatsApp Cloud credentials ready
- Postgres and Redis connection URLs (or let `render.yaml` provision them)

You can deploy either with manual service creation or with the Blueprint in `render.yaml`.

### 1.1) Fast path with Blueprint

1. In Render Dashboard, create a new Blueprint and select this repository.
2. Render will detect `render.yaml` and propose resources:
   - web service: `micai-api`
   - workers: `micai-worker`, `micai-scheduler`
   - key value: `micai-redis`
   - postgres: `micai-postgres`
3. During initial sync, provide values for `sync: false` vars:
   - `MICAI_WHATSAPP_VERIFY_TOKEN`
   - `MICAI_WHATSAPP_ACCESS_TOKEN`
   - `MICAI_WHATSAPP_PHONE_NUMBER_ID`
4. Complete Blueprint apply and wait for services to become healthy.

### 1.2) Immediate operator steps (do these now)

- [ ] Open Render Dashboard -> New -> Blueprint -> select this repo.
- [ ] Confirm resources from `render.yaml` are detected.
- [ ] Enter values for required secret vars when prompted.
- [ ] Apply Blueprint and wait for all services to become `Live`.
- [ ] Copy the api URL (for example `https://micai-api.onrender.com`).

### 2) Provision data services (if not using Blueprint-managed data)

Pick one of the following:

- Use Render Postgres + Render Redis
- Or external providers (for example Neon + Upstash)

Copy values into:

- `MICAI_DATABASE_URL`
- `MICAI_REDIS_URL`

### 3) Create the api service (Web Service)

- Environment: Docker
- Root: repo root
- Build: default Docker build from `Dockerfile`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Health check path: `/health`
- Public URL: enabled (HTTPS)

### 4) Create worker and scheduler (Background Workers)

Create two Background Worker services from the same repo/image:

- worker start command: `python -m app.worker`
- scheduler start command: `python -m app.scheduler`

Do not expose public ingress for these workers.

### 5) Configure environment variables (all services)

Set the same required `MICAI_` variables on api, worker, and scheduler.

Minimum required values:

- `MICAI_DATABASE_URL`
- `MICAI_REDIS_URL`
- `MICAI_ADMIN_API_KEY`
- `MICAI_WHATSAPP_VERIFY_TOKEN`
- `MICAI_WHATSAPP_ACCESS_TOKEN`
- `MICAI_WHATSAPP_PHONE_NUMBER_ID`

Safety defaults during bring-up:

- `MICAI_APP_ENV=prod`
- `MICAI_OUTBOUND_REPLY_ENABLED=false`

### 6) Verify deployment

- Confirm `https://<render-api-domain>/health` returns `{"status":"ok"}`
- Check Render logs for api, worker, and scheduler boot success
- Confirm scheduler is enqueueing and worker is polling without crash loops

You can run:

```bash
bin/render-verify https://<render-api-domain> "$MICAI_WHATSAPP_VERIFY_TOKEN"
```

If this fails, check service logs in this order:

1. `micai-api`
2. `micai-worker`
3. `micai-scheduler`

### 7) Configure Meta webhook

- Callback URL: `https://<render-api-domain>/webhook`
- Verify token: exactly `MICAI_WHATSAPP_VERIFY_TOKEN`
- Subscribe to message events

After webhook config, send a test message and confirm the api receives it and worker processes it.

## Render Env Reference

Use `render.env.example` as a source of required keys and safe bring-up defaults.

### 8) Cutover and rollback plan

- Enable outbound only after webhook validation: set `MICAI_OUTBOUND_REPLY_ENABLED=true`
- Rollback if anomalies: set `MICAI_OUTBOUND_REPLY_ENABLED=false`, rotate secrets, and disable webhook subscriptions until stable

## Managed Hosting (Alternative)

If not using Render, use Railway or Fly.io with the same process model (api + worker + scheduler) and identical env var requirements.

## Local + Podman Compose

1. Initialize secrets:

```bash
bin/init-secrets
```

2. Edit `secrets/*` with real values (one value per file).
3. Start the stack:

```bash
bin/up
```

4. Verify health:

```bash
bin/health
```

The API will be available at `http://localhost:8001` and the webhook endpoint is `http://localhost:8001/webhook`.

## Local + ngrok (for webhook testing)

Start the local API (via compose or `uvicorn`), then:

```bash
ngrok http 8001
```

Use the ngrok HTTPS URL as the callback URL in Meta. Example: `https://<subdomain>.ngrok-free.app/webhook`.

Note on stable URLs: free ngrok URLs change on each restart. For stable webhook URLs, use a reserved ngrok domain or a paid plan with a fixed subdomain, otherwise you must update the Meta webhook URL after each restart.

## Meta/WhatsApp Webhook Setup

1. In the Meta App Dashboard, configure the WhatsApp webhook callback URL:
   - `https://<domain>/webhook`
2. Set the Verify Token to the same value as `MICAI_WHATSAPP_VERIFY_TOKEN`.
3. Subscribe to message events.
4. Send a test message and confirm it reaches `/webhook` and shows as processed in logs.

## Security Notes (Mitigations Required for Internet Exposure)

- Webhook signature verification is not implemented. Add `X-Hub-Signature-256` validation using your Meta app secret before production exposure.
- Do not expose `/admin/*` publicly. Keep it behind an allowlist, VPN, or gateway, and use a strong `MICAI_ADMIN_API_KEY`.
- Replace all dev defaults (verify token, access token, phone id) before deployment.
- Keep `MICAI_OUTBOUND_REPLY_ENABLED=false` until you are ready to incur WhatsApp costs.
