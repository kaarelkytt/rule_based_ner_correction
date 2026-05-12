from .base import BaseRule, RuleProposal, BaseSplitDisconnectedEntityTreeRule

def _is_title_case_name(text):
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    return text[:1].isupper()

def _is_name_like_token(token):
    if token is None:
        return False
    return token.xpostag == "H" or _is_title_case_name(token.text)


class SplitDisconnectedPerTreeRule(BaseSplitDisconnectedEntityTreeRule):
    rule_id = "poolita_mittesidus_per_puu"
    description = "Lahutab mittesidusa PER nimeüksuse."

    LABEL = "PER"
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = {
        ("H", "S"),
        ("H", "O"),
        ("H", "H", "O"),
    }

    DO_NOT_SPLIT_DEPREL_PATTERNS = set()

    TRIM_EDGE_DEPRELS = {"cc"}
    TRIM_EDGE_POS = {"J"}


class ExpandRightPersonFlatRule(BaseRule):
    rule_id = "laienda_per_paremale_flat"
    description = "Laiendab PER märgendit paremale, kui süntaksis on selge flat-seos."

    def applies_to(self, span, context):
        return span.label == "PER"

    def propose(self, span, context):
        next_token = context.next_token(span)
        if next_token is None:
            return None
        if not _is_name_like_token(next_token):
            return None
        if next_token.deprel != "flat":
            return None
        if not context.token_depends_on_span(next_token, span):
            return None
        if "ner" in context.text.layers:
            for annotation in context.text["ner"]:
                other = context.span_from_annotation(annotation)
                if other is None:
                    continue
                if other.start_i == span.start_i and other.end_i == span.end_i:
                    continue
                if other.start_i <= next_token.index < other.end_i:
                    return None

        new_span = context.span_from_indices(span.label, span.start_i, span.end_i + 1)
        return RuleProposal(self.rule_id, "replace", 0.985, [new_span], {"from": span.text, "to": new_span.text})
