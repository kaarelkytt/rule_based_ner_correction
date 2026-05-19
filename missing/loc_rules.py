from .base import BaseMissingRule, MissingProposal
from .common import is_title_case_name, lower_key


LOCATION_HEAD_PHRASE_HEADS = {
    "kalmistu",
    "lennujaam",
    "mägi",
    "mõis",
    "järv",
    "paisjärv",
    "plats",
    "rand",
    "staadion",
    "talu",
    "tänav",
    "tee",
    "maantee",
}


class InsertProperLocationHeadPhraseRule(BaseMissingRule):
    rule_id = "lisa_kohafraas"
    description = "Lisab puuduva LOC fraasi kohanime ja kohatüübi sõnast."

    def find(self, context, occupied):
        proposals = []
        for start_i in range(len(context.tokens) - 1):
            if start_i in occupied or start_i + 1 in occupied:
                continue

            first = context.tokens[start_i]
            head = context.tokens[start_i + 1]

            if lower_key(head) not in LOCATION_HEAD_PHRASE_HEADS:
                continue
            if not (is_title_case_name(first.text) or first.xpostag == "H" or "-" in first.text):
                continue
            if first.morph_pos not in {"H", "S", "Y"} or head.morph_pos not in {"S", "H"}:
                continue

            span = context.span_from_indices("LOC", start_i, start_i + 2)
            if span.root_count > 2:
                continue

            linked = (
                first.head == head.syntax_id
                or head.head == first.syntax_id
                or first.deprel in {"flat", "nmod", "appos", "obl"}
                or head.deprel in {"flat", "nmod", "appos", "obl"}
            )
            if not linked:
                continue

            proposals.append(MissingProposal(self.rule_id, "LOC", start_i, start_i + 2, 0.90))
        return proposals
