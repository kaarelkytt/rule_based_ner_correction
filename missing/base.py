from dataclasses import dataclass, field


@dataclass
class MissingProposal:
    rule_id: str
    label: str
    start_i: int
    end_i: int
    score: float
    metadata: dict = field(default_factory=dict)


class BaseMissingRule:
    rule_id = "base_missing_rule"
    description = ""

    def find(self, context, occupied):
        return []
