from .base import BaseMissingRule, MissingProposal
from .common import *


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


class InsertLocativeProperLocationRule(BaseMissingRule):
    rule_id = "lisa_käändeline_koht"
    description = "Lisab puuduva LOC märgendi kohanimelaadsele sõnale kohakäändes."

    LEMMA_ALLOWLIST = {"lääs"}
    LEMMA_BLOCKLIST = {"facebook", "sierra"}
    SURFACE_BLOCKLIST = {"ametist", "sotsiaalhügienist", "vabadel"}

    def find(self, context, occupied):
        proposals = []
        for i, token in enumerate(context.tokens):
            if i in occupied:
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
            prev = context.tokens[i - 1] if i > 0 else None
            next_token = context.tokens[i + 1] if i + 1 < len(context.tokens) else None
            head = context.by_syntax_id.get(token.head) if token.head not in {None, 0} else None
            if prev is not None and prev.xpostag == "H" and token.deprel in {"flat", "obl"}:
                continue
            if token.deprel == "root" and next_token is not None and next_token.lower in {"ja", "ning", "või"}:
                continue
            context_lemmas = {lower_key(item) for item in (prev, next_token, head) if item is not None}
            strong_context = bool(context_lemmas & LOCATION_CONTEXT_LEMMAS)
            boundary_context = (
                prev is None
                or prev.text in {".", "!", "?", ":", ",", ";", "(", '"', "“", "”"}
                or next_token is None
                or next_token.text in {".", "!", "?", ":", ",", ";", ")", '"', "“", "”"}
            )
            if not strong_context and not boundary_context:
                continue
            proposals.append(MissingProposal(self.rule_id, "LOC", i, i + 1, 0.93))
        return proposals


class InsertProperLocationHeadPhraseRule(BaseMissingRule):
    rule_id = "lisa_kohafraas"
    description = "Lisab puuduva LOC fraasi kohanime ja kohatüübi sõnast."

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied or i + 1 in occupied:
                continue
            first = context.tokens[i]
            head = context.tokens[i + 1]
            if lower_key(head) not in LOCATION_HEAD_PHRASE_HEADS:
                continue
            if not (is_title_case_name(first.text) or first.xpostag == "H" or "-" in first.text):
                continue
            if first.morph_pos not in {"H", "S", "Y"} or head.morph_pos not in {"S", "H"}:
                continue
            span = context.span_from_indices("LOC", i, i + 2)
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
            proposals.append(MissingProposal(self.rule_id, "LOC", i, i + 2, 0.90))
        return proposals
