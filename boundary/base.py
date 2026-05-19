from dataclasses import dataclass, field


@dataclass
class RuleProposal:
    rule_id: str
    operation: str
    score: float
    spans: list
    metadata: dict = field(default_factory=dict)


class BaseRule:
    rule_id = "base_rule"
    description = ""
    stage = "adjust"

    def applies_to(self, span, context):
        return True

    def propose(self, span, context):
        return None
