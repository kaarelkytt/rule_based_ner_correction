from .base import BaseRule, RuleProposal, BaseSplitDisconnectedEntityTreeRule


QUOTE_TOKENS = {'"', "”", "“"}
ALLOWED_EXPAND_DEPRELS = {"nmod", "flat", "flat:name", "compound", "appos", "obj", "nsubj", "obl", "conj"}
BLOCKER_POS = {"J", "Z", "V", "D", "P"}
GOVERNING_BODY_HEADS = {
    "fraktsioon",
    "julgeolekunõukogu",
    "nõukogu",
    "parlamendifraktsioon",
    "taksokomisjon",
    "vanematekogu",
    "volikogu",
}
ROLE_LEMMAS = {
    "aseesimees",
    "direktor",
    "esimees",
    "eestkõneleja",
    "juht",
    "juhataja",
    "korrapidaja",
    "leitnant",
    "liige",
    "peadirektor",
    "pressiesindaja",
    "president",
}


def _valid_next_token(token):
    return (
        token is not None
        and token.morph_pos not in BLOCKER_POS
        and token.deprel in ALLOWED_EXPAND_DEPRELS
        and token.lemma not in ROLE_LEMMAS
    )


class SplitDisconnectedOrgTreeRule(BaseSplitDisconnectedEntityTreeRule):
    rule_id = "lahuta_mittesidus_org_puu"
    description = "Lahutab mittesidusa ORG nimeüksuse."

    LABEL = "ORG"
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = {
        ("H", "S"),
        ("S", "S"),
        ("H", "Y"),
        ("A", "S"),
        ("Y", "H"),
        ("H", "H", "Y"),
    }

    DO_NOT_SPLIT_DEPREL_PATTERNS = {
        ("appos", "flat", "nmod"),
    }

    TRIM_EDGE_DEPRELS = {"cc"}
    TRIM_EDGE_POS = {"J", "O"}


class TrimQuotedNameRule(BaseRule):
    rule_id = "kahanda_org_jutumärgid"
    description = "Eemaldab ORG märgendi ümbert jutumärgid."

    def applies_to(self, span, context):
        return span.label == "ORG"

    def propose(self, span, context):
        start_i = span.start_i
        end_i = span.end_i
        changed = False
        while start_i < end_i and context.tokens[start_i].text in QUOTE_TOKENS:
            start_i += 1
            changed = True
        while end_i > start_i and context.tokens[end_i - 1].text in QUOTE_TOKENS:
            end_i -= 1
            changed = True

        if not changed:
            return None
        new_span = context.span_from_indices(span.label, start_i, end_i)
        return RuleProposal(self.rule_id, "replace", 0.98, [new_span], {"from": span.text, "to": new_span.text})


class ExpandRightGoverningBodyRule(BaseRule):
    rule_id = "laienda_org_paremale_juhtorgan"
    description = "Laiendab ORG märgendit paremale, kui järgneb tugev juhtorgani sõna."

    def applies_to(self, span, context):
        return span.label == "ORG"

    def propose(self, span, context):
        next_token = context.next_token(span)
        if not _valid_next_token(next_token):
            return None
        if next_token.lemma not in GOVERNING_BODY_HEADS:
            return None
        new_span = context.span_from_indices(span.label, span.start_i, span.end_i + 1)
        if new_span.root_count > 1:
            return None
        return RuleProposal(self.rule_id, "replace", 0.96, [new_span], {"from": span.text, "to": new_span.text})


class ExpandLeftCompanyPrefixRule(BaseRule):
    rule_id = "laienda_org_vasakule_firmavorm"
    description = "Laiendab ORG märgendit vasakule üle firmavormi alguse."

    COMPANY_PREFIX_TEXTS = {"AS", "OU", "OÜ", "MTU", "MTÜ", "SA"}
    COMPANY_PREFIX_LEMMAS = {"aktsiaselts", "osaühing", "mittetulundusühing", "sihtasutus"}


    def applies_to(self, span, context):
        return span.label == "ORG"

    def propose(self, span, context):
        if span.start_i == 0:
            return None
        prev_token = context.tokens[span.start_i - 1]
        prev_upper = prev_token.text.upper()
        prev_lemma = (prev_token.lemma or "").lower()
        if prev_upper not in self.COMPANY_PREFIX_TEXTS and prev_lemma not in self.COMPANY_PREFIX_LEMMAS:
            return None
        if span.name_like_ratio < 0.5:
            return None
        new_span = context.span_from_indices(span.label, span.start_i - 1, span.end_i)
        if new_span.root_count > 2:
            return None
        return RuleProposal(self.rule_id, "replace", 0.985, [new_span], {"from": span.text, "to": new_span.text})


class SplitCoordinatedLocationRule(BaseRule):
    rule_id = "jaga_koordineeritud_loc"
    description = "Jagab kaheks koordineeritud LOC märgendi nagu Põlva- ja Hiiumaal."

    def applies_to(self, span, context):
        return span.label == "LOC" and len(span.tokens) >= 3

    def propose(self, span, context):
        conj_offset = None
        for offset, token in enumerate(span.tokens):
            if token.lower == "ja":
                conj_offset = offset
                break
        if conj_offset is None or conj_offset == 0 or conj_offset == len(span.tokens) - 1:
            return None

        left_tokens = span.tokens[:conj_offset]
        if not any(token.text == "-" or token.text.endswith("-") for token in left_tokens):
            return None

        right = span.tokens[conj_offset + 1]
        if "ill" in (right.form or "").split():
            return None

        left_span = context.span_from_indices(span.label, span.start_i, span.start_i + conj_offset)
        right_span = context.span_from_indices(span.label, span.start_i + conj_offset + 1, span.end_i)
        if not left_span.tokens or not right_span.tokens:
            return None
        if left_span.name_like_ratio < 0.5 or right_span.name_like_ratio < 0.5:
            return None

        return RuleProposal(self.rule_id, "split", 0.97, [left_span, right_span], {"from": span.text, "parts": [left_span.text, right_span.text]})
