# Deployment

This repo is deployed as a Dockerized multi-service stack:

- `api` (FastAPI)
- `worker` (`python -m app.worker`)
- `scheduler` (`python -m app.scheduler`)
- `postgres` (state)
- `redis` (queue)

For WhatsApp webhooks, the `api` service must be reachable via HTTPS.

## Implementation Plan and Checklist

Progress legend: `[x]` complete, `[ ]` pending.

1. Planning and scope
- [x] Focus deployment strategy on Dockerized hosting (remove Render-specific path).
- [x] Keep one public entrypoint (`api`), keep worker/scheduler private.

2. Repository deployment assets
- [x] Keep Docker runtime centered on `compose.yml`.
- [x] Add deployment verification helper: `bin/deploy-verify`.
- [x] Remove Render-specific files and references.

3. Host provisioning (operator)
- [ ] Provision a Linux VM with Docker Engine + Docker Compose plugin.
- [ ] Attach a public domain to the host.
- [ ] Open firewall for `80` and `443`.

4. Secrets and config (operator)
- [ ] Run `bin/init-secrets`.
- [ ] Fill `secrets/*` with real production values (no dev defaults).
- [ ] Keep `MICAI_OUTBOUND_REPLY_ENABLED=false` during bring-up.

5. Deploy stack (operator)
- [ ] Start services with `bin/up`.
- [ ] Confirm all containers healthy (`api`, `worker`, `scheduler`, `postgres`, `redis`).
- [ ] Verify local health with `bin/health`.

6. HTTPS reverse proxy (operator)
- [ ] Configure Caddy or nginx to terminate TLS for your domain.
- [ ] Proxy requests to `api` (`localhost:8001` on host).
- [ ] Restrict public access to `/admin/*`.

7. WhatsApp webhook wiring (operator)
- [ ] Set callback URL to `https://<your-domain>/webhook`.
- [ ] Set verify token to `MICAI_WHATSAPP_VERIFY_TOKEN`.
- [ ] Validate verification + health with `bin/deploy-verify`.
- [ ] Send test message and confirm queue/worker processing in logs.

8. Security hardening before enabling outbound
- [ ] Implement webhook signature verification (`X-Hub-Signature-256`) in app code.
- [ ] Add request rate limits and body-size limits at proxy layer.
- [ ] Rotate secrets if any non-production value was ever exposed.

9. Outbound activation and rollback
- [ ] Enable `MICAI_OUTBOUND_REPLY_ENABLED=true` only after hardening.
- [ ] Define rollback: disable outbound, rotate secrets, pause webhook subscription.

## Runtime Commands

Initialize and start:

```bash
bin/init-secrets
bin/up
```

Check health locally:

```bash
bin/health
```

Logs:

```bash
bin/logs
bin/logs api
bin/logs worker
bin/logs scheduler
```

Stop stack:

```bash
bin/down
```

## Required Endpoints

- `GET /health`
- `GET /webhook` (Meta verification)
- `POST /webhook` (inbound WhatsApp)

## Required Environment Variables

Use either direct vars or `_FILE` variants:

- `MICAI_DATABASE_URL`
- `MICAI_REDIS_URL`
- `MICAI_ADMIN_API_KEY` or `MICAI_ADMIN_API_KEY_FILE`
- `MICAI_WHATSAPP_VERIFY_TOKEN` or `MICAI_WHATSAPP_VERIFY_TOKEN_FILE`
- `MICAI_WHATSAPP_ACCESS_TOKEN` or `MICAI_WHATSAPP_ACCESS_TOKEN_FILE`
- `MICAI_WHATSAPP_PHONE_NUMBER_ID` or `MICAI_WHATSAPP_PHONE_NUMBER_ID_FILE`

Recommended bring-up defaults:

- `MICAI_APP_ENV=prod`
- `MICAI_OUTBOUND_REPLY_ENABLED=false`
- `MICAI_REQUIRE_INVOKE_PREFIX=true`

## HTTPS Reverse Proxy Notes

- Point your domain to the VM.
- Terminate TLS at the proxy.
- Forward traffic to `http://127.0.0.1:8001`.
- Do not expose `/admin/*` publicly.

## Webhook Validation

From your machine:

```bash
bin/deploy-verify https://<your-domain> "$MICAI_WHATSAPP_VERIFY_TOKEN"
```

Then in Meta Dashboard:

1. Callback URL: `https://<your-domain>/webhook`
2. Verify token: exact value of `MICAI_WHATSAPP_VERIFY_TOKEN`
3. Subscribe to message events

## Local Tunnel Option (temporary)

If you are not ready for a VM/domain yet:

```bash
bin/up
ngrok http 8001
```

Use `https://<ngrok-domain>/webhook` as callback URL. Free ngrok domains rotate on restart.
