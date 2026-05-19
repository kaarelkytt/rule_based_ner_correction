from ..base import BaseMissingRule, MissingProposal
from ..common import is_title_case_name, is_upper_name, lower_key


LOCATION_LIKE_CASES = {"ill", "in", "el", "all", "ad", "abl", "ter"}
LOCATION_CONTEXT_LEMMAS = {
    "asuma",
    "elama",
    "järgnema",
    "lahkuma",
    "minema",
    "naasma",
    "reisima",
    "saabuma",
    "sõitma",
    "tulema",
}


class InsertLocativeProperLocationRule(BaseMissingRule):
    rule_id = "lisa_käändeline_koht"
    description = "Lisab puuduva LOC märgendi kohanimelaadsele sõnale kohakäändes."

    LEMMA_ALLOWLIST = {"lääs"}
    LEMMA_BLOCKLIST = {"facebook", "sierra"}
    SURFACE_BLOCKLIST = {"ametist", "sotsiaalhügienist", "vabadel"}

    def find(self, context, occupied):
        proposals = []
        for index, token in enumerate(context.tokens):
            if index in occupied:
                continue
            if token.xpostag != "H":
                continue
            if not (is_title_case_name(token.text) or is_upper_name(token.text)):
                continue
            lemma = lower_key(token)
            if token.lower in self.SURFACE_BLOCKLIST or lemma in self.LEMMA_BLOCKLIST:
                continue
            lemma_text = token.lemma or token.text
            if not (lemma_text[:1].isupper() or lemma in self.LEMMA_ALLOWLIST):
                continue
            form_parts = set((token.form or "").split())
            if not (form_parts & LOCATION_LIKE_CASES):
                continue
            previous = context.tokens[index - 1] if index > 0 else None
            next_token = context.tokens[index + 1] if index + 1 < len(context.tokens) else None
            head = context.by_syntax_id.get(token.head) if token.head not in {None, 0} else None
            if previous is not None and previous.xpostag == "H" and token.deprel in {"flat", "obl"}:
                continue
            if token.deprel == "root" and next_token is not None and next_token.lower in {"ja", "ning", "või"}:
                continue
            context_lemmas = {lower_key(item) for item in (previous, next_token, head) if item is not None}
            strong_context = bool(context_lemmas & LOCATION_CONTEXT_LEMMAS)
            boundary_context = (
                previous is None
                or previous.text in {".", "!", "?", ":", ",", ";", "(", '"', "“", "”"}
                or next_token is None
                or next_token.text in {".", "!", "?", ":", ",", ";", ")", '"', "“", "”"}
            )
            if not strong_context and not boundary_context:
                continue
            proposals.append(MissingProposal(self.rule_id, "LOC", index, index + 1, 0.93))
        return proposals
