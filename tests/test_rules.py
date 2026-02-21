from app.models import AgentRule, RuleAction, RuleType
from app.rules import match_rule


def test_prefix_rule_matches_first() -> None:
    rules = [
        AgentRule(
            id="r1",
            agent_id="a1",
            rule_type=RuleType.PREFIX,
            prefix="michael:",
            action=RuleAction.REPLY_TEXT,
            reply_text="Hi",
            priority=1,
        ),
        AgentRule(
            id="r2",
            agent_id="a1",
            rule_type=RuleType.KEYWORD,
            keywords=["weather"],
            action=RuleAction.REPLY_TEXT,
            reply_text="Weather",
            priority=10,
        ),
    ]

    rule = match_rule("michael: what is weather", rules)
    assert rule is not None
    assert rule.id == "r1"


def test_keyword_rule_matches_contains() -> None:
    rules = [
        AgentRule(
            id="r2",
            agent_id="a1",
            rule_type=RuleType.KEYWORD,
            keywords=["weather"],
            action=RuleAction.REPLY_TEXT,
            reply_text="Weather",
        )
    ]
    rule = match_rule("Can you share weather now?", rules)
    assert rule is not None
    assert rule.id == "r2"
