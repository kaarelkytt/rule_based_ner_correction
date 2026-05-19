from .base import BaseRule, RuleProposal
from .common import (
    find_name_chain,
    find_start_flat_chain,
    is_continuation_token,
    is_name_like_token,
    is_start_token,
    replace_with_span,
)


ALLOWED_EXPAND_DEPRELS = {"flat", "compound", "nmod", "appos"}
FACILITY_LOCATION_HEADS = {
    "lennujaam",
    "lennuväli",
    "maantee",
    "piiripunkt",
    "plats",
    "provints",
    "puiestee",
    "rand",
    "staadion",
    "tänav",
    "tee",
    "väljak",
    "park",
    "klooster",
    "mõis",
    "kalmistu",
    "linn",
    "küla",
    "mägi",
    "talu",
}

QUOTE_TOKENS = {'"', "”", "“"}
ORG_ALLOWED_EXPAND_DEPRELS = {"nmod", "flat", "flat:name", "compound", "appos", "obj", "nsubj", "obl", "conj"}
ORG_BLOCKER_POS = {"J", "Z", "V", "D", "P"}
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


def is_valid_org_tail(token):
    return (
        token is not None
        and token.morph_pos not in ORG_BLOCKER_POS
        and token.deprel in ORG_ALLOWED_EXPAND_DEPRELS
        and token.lemma not in ROLE_LEMMAS
    )


class ExpandRightLocationFacilityHeadRule(BaseRule):
    rule_id = "laienda_loc_paremale_kohapea"
    description = "Laiendab ühesõnalist LOC märgendit kohatüübi või rajatise sõna võrra."
    stage = "adjust"

    def applies_to(self, span, context):
        return span.label == "LOC"

    def propose(self, span, context):
        if len(span.tokens) != 1:
            return None

        next_token = context.next_token(span)
        if next_token is None or next_token.lemma not in FACILITY_LOCATION_HEADS:
            return None

        next_form_parts = set((next_token.form or "").split())
        if "pl" in next_form_parts:
            return None

        current = span.tokens[0]
        syntax_link = (
            current.head == next_token.syntax_id
            or next_token.head == current.syntax_id
            or next_token.deprel in ALLOWED_EXPAND_DEPRELS
        )
        if not syntax_link:
            return None

        new_span = context.span_from_indices(span.label, span.start_i, span.end_i + 1)
        if new_span.root_count > 1:
            return None

        return replace_with_span(self.rule_id, 0.96, span, new_span)


class ExpandPersonRootChainRule(BaseRule):
    rule_id = "laienda_nime_root"
    description = "Laiendab ühetokenilist PER märgendit root + flat nimeahelaks."
    stage = "adjust"

    START_DEPRELS = {"root"}
    CONTINUATION_DEPRELS = {"flat"}
    NAME_POS = {"H", "Y"}
    BLOCKED_LABELS = {"LOC"}
    KEEP_SAME_CAPS = True
    SCORE = 0.99

    def applies_to(self, span, context):
        return span.label == "PER" and len(span.tokens) == 1

    def propose(self, span, context):
        token = span.tokens[0]
        starts_chain = is_start_token(token, context, self.START_DEPRELS, self.NAME_POS, self.BLOCKED_LABELS)
        continues_chain = is_continuation_token(
            token,
            context,
            self.CONTINUATION_DEPRELS,
            self.NAME_POS,
            self.BLOCKED_LABELS,
            reference_token=token,
            keep_same_caps=self.KEEP_SAME_CAPS,
        )
        if not (starts_chain or continues_chain):
            return None

        new_span = find_name_chain(
            span,
            context,
            self.START_DEPRELS,
            self.CONTINUATION_DEPRELS,
            self.NAME_POS,
            self.BLOCKED_LABELS,
            keep_same_caps=self.KEEP_SAME_CAPS,
        )
        if new_span is None:
            return None
        if new_span.start_i == span.start_i and new_span.end_i == span.end_i:
            return None

        return replace_with_span(self.rule_id, self.SCORE, span, new_span)


class ExpandLocNsubjFlatRule(BaseRule):
    rule_id = "laienda_loc_nsubj_flat"
    description = "Laiendab LOC märgendit nsubj/nsubj:cop + flat ahelaks."
    stage = "adjust"

    def applies_to(self, span, context):
        return span.label == "LOC"

    def propose(self, span, context):
        new_span = find_start_flat_chain(
            span=span,
            context=context,
            start_deprels={"nsubj", "nsubj:cop"},
            continuation_deprels={"flat"},
            name_pos={"H"},
            block_other_labels=True,
        )
        if new_span is None:
            return None
        if new_span.start_i == span.start_i and new_span.end_i == span.end_i:
            return None
        return RuleProposal(self.rule_id, "replace", 0.97, [new_span])


class ExpandRightPersonFlatRule(BaseRule):
    rule_id = "laienda_per_paremale_flat"
    description = "Laiendab PER märgendit paremale, kui järgmine token on flat-seoses nime osa."
    stage = "adjust"

    def applies_to(self, span, context):
        return span.label == "PER"

    def propose(self, span, context):
        next_token = context.next_token(span)
        if next_token is None or not is_name_like_token(next_token):
            return None
        if next_token.deprel != "flat":
            return None
        if not context.token_depends_on_span(next_token, span):
            return None

        next_entity = context.token_entity(next_token)
        if next_entity is not None:
            same_entity = next_entity.start_i == span.start_i and next_entity.end_i == span.end_i
            if not same_entity:
                return None

        new_span = context.span_from_indices(span.label, span.start_i, span.end_i + 1)
        return replace_with_span(self.rule_id, 0.985, span, new_span)


class TrimQuotedOrgRule(BaseRule):
    rule_id = "kahanda_org_jutumärgid"
    description = "Eemaldab ORG märgendi ümbert jutumärgid."
    stage = "adjust"

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
        return replace_with_span(self.rule_id, 0.98, span, new_span)


class ExpandRightGoverningBodyRule(BaseRule):
    rule_id = "laienda_org_paremale_juhtorgan"
    description = "Laiendab ORG märgendit paremale, kui järgneb tugev juhtorgani sõna."
    stage = "adjust"

    def applies_to(self, span, context):
        return span.label == "ORG"

    def propose(self, span, context):
        next_token = context.next_token(span)
        if not is_valid_org_tail(next_token):
            return None
        if next_token.lemma not in GOVERNING_BODY_HEADS:
            return None

        new_span = context.span_from_indices(span.label, span.start_i, span.end_i + 1)
        if new_span.root_count > 1:
            return None
        return replace_with_span(self.rule_id, 0.96, span, new_span)


class ExpandLeftCompanyPrefixRule(BaseRule):
    rule_id = "laienda_org_vasakule_firmavorm"
    description = "Laiendab ORG märgendit vasakule üle firmavormi alguse."
    stage = "adjust"
    
    COMPANY_PREFIX_TEXTS = {"AS", "OÜ", "MTÜ", "SA"}
    COMPANY_PREFIX_LEMMAS = {"aktsiaselts", "osaühing", "mittetulundusühing", "sihtasutus"}

    def applies_to(self, span, context):
        return span.label == "ORG"

    def propose(self, span, context):
        if span.start_i == 0:
            return None

        previous_token = context.tokens[span.start_i - 1]
        previous_upper = previous_token.text.upper()
        previous_lemma = (previous_token.lemma or "").lower()

        if previous_upper not in self.COMPANY_PREFIX_TEXTS and previous_lemma not in self.COMPANY_PREFIX_LEMMAS:
            return None
        if span.name_like_ratio < 0.5:
            return None

        new_span = context.span_from_indices(span.label, span.start_i - 1, span.end_i)
        if new_span.root_count > 2:
            return None
        return replace_with_span(self.rule_id, 0.985, span, new_span)
