from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_models import (
    AgentRuleRow,
    ConversationTurnRow,
    InboundDedupRow,
    OutboundSendRow,
    ScheduleRow,
    UserAgentBindingRow,
)
from app.models import AgentRule, ConversationTurn, RuleAction, RuleType


def _keywords_to_csv(keywords: list[str]) -> str:
    return "|".join(k.strip() for k in keywords if k.strip())


def _csv_to_keywords(value: str) -> list[str]:
    if not value:
        return []
    return [k for k in value.split("|") if k]


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def claim_inbound_message(self, message_id: str, wa_id: str, text: str) -> bool:
        try:
            with self.session.begin_nested():
                row = InboundDedupRow(message_id=message_id, wa_id=wa_id, text=text)
                self.session.add(row)
                self.session.flush()
        except IntegrityError:
            return False
        return True

    def upsert_rule(self, rule: AgentRule) -> None:
        row = self.session.get(AgentRuleRow, rule.id)
        if row is None:
            row = AgentRuleRow(id=rule.id)
            self.session.add(row)
        row.agent_id = rule.agent_id
        row.rule_type = rule.rule_type.value
        row.enabled = rule.enabled
        row.priority = rule.priority
        row.keywords_csv = _keywords_to_csv(rule.keywords)
        row.prefix = rule.prefix
        row.action = rule.action.value
        row.reply_text = rule.reply_text

    def bind_user_agent(self, wa_id: str, agent_id: str) -> None:
        row = self.session.get(UserAgentBindingRow, wa_id)
        if row is None:
            row = UserAgentBindingRow(wa_id=wa_id, agent_id=agent_id)
            self.session.add(row)
            return
        row.agent_id = agent_id

    def touch_user_inbound(self, wa_id: str, now: datetime | None = None) -> None:
        timestamp = now or datetime.now(timezone.utc)
        row = self.session.get(UserAgentBindingRow, wa_id)
        if row is None:
            row = UserAgentBindingRow(wa_id=wa_id, last_inbound_at=timestamp)
            self.session.add(row)
            return
        row.last_inbound_at = timestamp

    def get_rules_for_user(self, wa_id: str) -> list[AgentRule]:
        binding = self.session.get(UserAgentBindingRow, wa_id)
        agent_id = binding.agent_id if binding else "default-agent"
        stmt = (
            select(AgentRuleRow)
            .where(AgentRuleRow.agent_id == agent_id)
            .where(AgentRuleRow.enabled.is_(True))
            .order_by(AgentRuleRow.priority.asc())
        )
        rows = self.session.execute(stmt).scalars().all()
        return [
            AgentRule(
                id=row.id,
                agent_id=row.agent_id,
                rule_type=RuleType(row.rule_type),
                enabled=row.enabled,
                priority=row.priority,
                keywords=_csv_to_keywords(row.keywords_csv),
                prefix=row.prefix,
                action=RuleAction(row.action),
                reply_text=row.reply_text,
            )
            for row in rows
        ]

    def save_turn(self, turn: ConversationTurn) -> None:
        self.session.add(
            ConversationTurnRow(
                wa_id=turn.wa_id,
                inbound_text=turn.inbound_text,
                outbound_text=turn.outbound_text,
                matched_rule_id=turn.matched_rule_id,
            )
        )

    def get_last_inbound_at(self, wa_id: str) -> datetime | None:
        row = self.session.get(UserAgentBindingRow, wa_id)
        return row.last_inbound_at if row else None

    def can_send_freeform(self, wa_id: str, window_hours: int, now: datetime | None = None) -> bool:
        last_inbound = self.get_last_inbound_at(wa_id)
        if last_inbound is None:
            return False
        if last_inbound.tzinfo is None:
            last_inbound = last_inbound.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return (current - last_inbound) <= timedelta(hours=window_hours)

    def try_start_outbound_send(
        self, idempotency_key: str, wa_id: str, body: str, template_name: str | None
    ) -> bool:
        try:
            with self.session.begin_nested():
                row = OutboundSendRow(
                    idempotency_key=idempotency_key,
                    wa_id=wa_id,
                    body=body,
                    template_name=template_name,
                    status="sending",
                    attempts=1,
                )
                self.session.add(row)
                self.session.flush()
        except IntegrityError:
            return False
        return True

    def mark_outbound_sent(self, idempotency_key: str, provider_message_id: str | None = None) -> None:
        row = self.session.get(OutboundSendRow, idempotency_key)
        if row is None:
            return
        row.status = "sent"
        row.provider_message_id = provider_message_id
        row.last_error = None

    def mark_outbound_failed(self, idempotency_key: str, error: str) -> None:
        row = self.session.get(OutboundSendRow, idempotency_key)
        if row is None:
            return
        row.status = "failed"
        row.last_error = error

    def list_due_schedules(self, now: datetime | None = None) -> list[ScheduleRow]:
        current = now or datetime.now(timezone.utc)
        stmt = (
            select(ScheduleRow)
            .where(ScheduleRow.enabled.is_(True))
            .where(ScheduleRow.next_run_at <= current)
            .order_by(ScheduleRow.next_run_at.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def advance_schedule(self, schedule: ScheduleRow) -> None:
        schedule.next_run_at = schedule.next_run_at + timedelta(minutes=schedule.interval_minutes)
