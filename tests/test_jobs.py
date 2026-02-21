from datetime import datetime, timedelta, timezone

from app.db import SessionLocal, engine
from app.db_models import Base, UserAgentBindingRow
from app.jobs import process_inbound_message, send_outbound_message
from app.models import AgentRule, IncomingMessage, RuleAction, RuleType
from app.queue import InMemoryJobQueue
from app.repository import Repository


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_process_inbound_enqueues_outbound() -> None:
    queue = InMemoryJobQueue()
    with SessionLocal() as session:
        repo = Repository(session)
        repo.bind_user_agent("15550000001", "agent-1")
        repo.upsert_rule(
            AgentRule(
                id="rule-1",
                agent_id="agent-1",
                rule_type=RuleType.KEYWORD,
                keywords=["weather"],
                action=RuleAction.REPLY_TEXT,
                reply_text="Sunny today",
                priority=1,
            )
        )
        session.commit()

    with SessionLocal() as session:
        repo = Repository(session)
        ok = process_inbound_message(
            repo,
            queue,
            IncomingMessage(
                message_id="wamid.1",
                wa_id="15550000001",
                text="michael: weather please",
            ).model_dump(),
        )
        session.commit()

    assert ok is True
    assert len(queue.items) == 1
    assert queue.items[0].job_type == "outbound.send_text"
    assert queue.items[0].payload["body"] == "Sunny today"


def test_outbound_uses_template_when_out_of_window(monkeypatch) -> None:
    calls: dict[str, str | None] = {"text": None, "template": None}

    async def fake_send_text(wa_id: str, text: str) -> str:
        calls["text"] = f"{wa_id}:{text}"
        return "text-id"

    async def fake_send_template(wa_id: str, template_name: str) -> str:
        calls["template"] = f"{wa_id}:{template_name}"
        return "tpl-id"

    monkeypatch.setattr("app.jobs.wa_client.send_text", fake_send_text)
    monkeypatch.setattr("app.jobs.wa_client.send_template", fake_send_template)

    with SessionLocal() as session:
        session.add(
            UserAgentBindingRow(
                wa_id="15550000002",
                agent_id="agent-1",
                last_inbound_at=datetime.now(timezone.utc) - timedelta(hours=30),
            )
        )
        session.commit()

    with SessionLocal() as session:
        repo = Repository(session)
        import asyncio

        asyncio.run(
            send_outbound_message(
                repo,
                {
                    "idempotency_key": "reply:wamid.2",
                    "wa_id": "15550000002",
                    "body": "Hello",
                    "template_name": None,
                },
            )
        )
        session.commit()

    assert calls["text"] is None
    assert calls["template"] == "15550000002:out_of_window_default"
