from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.models import ConversationTurn, IncomingMessage
from app.queue import JobQueue
from app.repository import Repository
from app.rules import match_rule, normalize
from app.whatsapp import wa_client


def _fallback_reply(text: str) -> str:
    return f"I heard: {text}. I can help with weather or reminders."


def _is_invoked(text: str) -> bool:
    if not settings.require_invoke_prefix:
        return True
    candidate = normalize(text)
    for prefix in settings.invoke_prefixes.split(","):
        if candidate.startswith(normalize(prefix)):
            return True
    return False


@dataclass
class OutboundCommand:
    idempotency_key: str
    wa_id: str
    body: str
    template_name: str | None = None


def process_inbound_message(repo: Repository, queue: JobQueue, payload: dict) -> bool:
    message = IncomingMessage.model_validate(payload)
    repo.touch_user_inbound(message.wa_id)
    if not _is_invoked(message.text):
        return False

    rules = repo.get_rules_for_user(message.wa_id)
    matched_rule = match_rule(message.text, rules)
    outbound = matched_rule.reply_text if matched_rule and matched_rule.reply_text else _fallback_reply(message.text)

    turn = ConversationTurn(
        wa_id=message.wa_id,
        inbound_text=message.text,
        outbound_text=outbound,
        matched_rule_id=matched_rule.id if matched_rule else None,
    )
    repo.save_turn(turn)

    queue.enqueue(
        "outbound.send_text",
        OutboundCommand(
            idempotency_key=f"reply:{message.message_id}",
            wa_id=message.wa_id,
            body=outbound,
        ).__dict__,
    )
    return True


async def send_outbound_message(repo: Repository, payload: dict) -> bool:
    command = OutboundCommand(**payload)
    if not repo.try_start_outbound_send(
        idempotency_key=command.idempotency_key,
        wa_id=command.wa_id,
        body=command.body,
        template_name=command.template_name,
    ):
        return False

    try:
        provider_id: str | None
        if command.template_name:
            provider_id = await wa_client.send_template(command.wa_id, command.template_name)
        elif repo.can_send_freeform(command.wa_id, settings.freeform_window_hours):
            provider_id = await wa_client.send_text(command.wa_id, command.body)
        else:
            provider_id = await wa_client.send_template(command.wa_id, "out_of_window_default")
        repo.mark_outbound_sent(command.idempotency_key, provider_message_id=provider_id)
    except Exception as exc:
        repo.mark_outbound_failed(command.idempotency_key, str(exc))
        raise
    return True


def enqueue_due_schedules(repo: Repository, queue: JobQueue) -> int:
    due = repo.list_due_schedules()
    count = 0
    for schedule in due:
        queue.enqueue(
            "outbound.send_text",
            OutboundCommand(
                idempotency_key=f"schedule:{schedule.id}:{int(schedule.next_run_at.timestamp())}",
                wa_id=schedule.wa_id,
                body=schedule.message_text,
                template_name=schedule.template_name,
            ).__dict__,
        )
        repo.advance_schedule(schedule)
        count += 1
    return count
