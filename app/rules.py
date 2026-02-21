from app.models import AgentRule, RuleType


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def match_rule(text: str, rules: list[AgentRule]) -> AgentRule | None:
    candidate = normalize(text)
    for rule in rules:
        if rule.rule_type == RuleType.PREFIX and rule.prefix:
            if candidate.startswith(normalize(rule.prefix)):
                return rule
        if rule.rule_type == RuleType.KEYWORD and rule.keywords:
            lowered = [normalize(k) for k in rule.keywords]
            if any(keyword in candidate for keyword in lowered):
                return rule
    return None
