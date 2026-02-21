from fastapi.testclient import TestClient

from app.db import engine
from app.db_models import Base
from app.main import app
from app.models import AgentRule, RuleAction, RuleType
from app.queue import InMemoryJobQueue
from app.runtime import runtime

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    runtime.set_test_queue(InMemoryJobQueue())


def test_webhook_processes_message_once() -> None:
    client.post(
        "/admin/bind/15550000001/agent-1",
        headers={"x-admin-key": "dev-admin-key"},
    )
    client.post(
        "/admin/rules",
        json=AgentRule(
            id="rule-1",
            agent_id="agent-1",
            rule_type=RuleType.KEYWORD,
            keywords=["weather"],
            action=RuleAction.REPLY_TEXT,
            reply_text="Sunny today",
            priority=1,
        ).model_dump(mode="json"),
        headers={"x-admin-key": "dev-admin-key"},
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "15550000001"}],
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "type": "text",
                                    "text": {"body": "michael: weather please"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }

    first = client.post("/webhook", json=payload)
    second = client.post("/webhook", json=payload)

    assert first.status_code == 200
    assert first.json()["processed"] == 1
    assert second.status_code == 200
    assert second.json()["processed"] == 0
    assert isinstance(runtime.queue, InMemoryJobQueue)
    assert len(runtime.queue.items) == 1
    assert runtime.queue.items[0].job_type == "inbound.process_message"
