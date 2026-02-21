from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Query

from app.config import settings
from app.models import AgentRule, IncomingMessage, WebhookEnvelope
from app.runtime import runtime

app = FastAPI(title="mic.ai WhatsApp MVP", version="0.1.0")


@app.on_event("startup")
async def startup_event() -> None:
    runtime.initialize()


def _extract_messages(envelope: WebhookEnvelope) -> list[IncomingMessage]:
    messages: list[IncomingMessage] = []
    for entry in envelope.entry:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = value.get("contacts", [])
            default_wa_id = contacts[0].get("wa_id") if contacts else ""

            for msg in value.get("messages", []):
                message_type = msg.get("type", "")
                wa_id = default_wa_id or msg.get("from", "")
                text = ""
                if message_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif message_type == "audio":
                    text = "voice note"

                if not wa_id:
                    continue

                messages.append(
                    IncomingMessage(
                        message_id=msg.get("id", ""),
                        wa_id=wa_id,
                        text=text,
                        is_voice=message_type == "audio",
                    )
                )
    return [m for m in messages if m.message_id and m.text]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    challenge: str = Query(alias="hub.challenge"),
    verify_token: str = Query(alias="hub.verify_token"),
) -> str:
    if mode != "subscribe" or verify_token != settings.whatsapp_verify_token:
        raise HTTPException(status_code=403, detail="Invalid verification token")
    return challenge


@app.post("/webhook")
async def inbound_webhook(envelope: WebhookEnvelope) -> dict[str, int | str]:
    processed = 0
    with runtime.repo_scope() as repo:
        for message in _extract_messages(envelope):
            claimed = repo.claim_inbound_message(message.message_id, message.wa_id, message.text)
            if not claimed:
                continue
            runtime.queue.enqueue("inbound.process_message", message.model_dump())
            processed += 1
    return {"status": "accepted", "processed": processed}


def _require_admin_key(key: str | None) -> None:
    if key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/admin/rules")
async def upsert_rule(rule: AgentRule, x_admin_key: str | None = Header(default=None)) -> dict[str, str]:
    _require_admin_key(x_admin_key)
    with runtime.repo_scope() as repo:
        repo.upsert_rule(rule)
    return {"status": "ok", "rule_id": rule.id}


@app.post("/admin/bind/{wa_id}/{agent_id}")
async def bind_agent(
    wa_id: str,
    agent_id: str,
    x_admin_key: str | None = Header(default=None),
) -> dict[str, str]:
    _require_admin_key(x_admin_key)
    with runtime.repo_scope() as repo:
        repo.bind_user_agent(wa_id, agent_id)
    return {"status": "ok", "wa_id": wa_id, "agent_id": agent_id}
