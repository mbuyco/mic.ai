from enum import Enum

from pydantic import BaseModel, Field


class RuleType(str, Enum):
    KEYWORD = "keyword"
    PREFIX = "prefix"
    SCHEDULED = "scheduled"


class RuleAction(str, Enum):
    REPLY_TEXT = "reply_text"
    CALL_WEATHER = "call_weather"


class AgentRule(BaseModel):
    id: str
    agent_id: str
    rule_type: RuleType
    enabled: bool = True
    priority: int = 100
    keywords: list[str] = Field(default_factory=list)
    prefix: str | None = None
    action: RuleAction = RuleAction.REPLY_TEXT
    reply_text: str = ""


class IncomingMessage(BaseModel):
    message_id: str
    wa_id: str
    text: str
    is_voice: bool = False


class ConversationTurn(BaseModel):
    wa_id: str
    inbound_text: str
    outbound_text: str
    matched_rule_id: str | None = None


class WebhookEnvelope(BaseModel):
    object: str
    entry: list[dict]
