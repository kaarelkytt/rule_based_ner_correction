from .base import BaseRule, RuleProposal, BaseSplitDisconnectedEntityTreeRule

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


def is_all_caps_token(token):
    return token is not None and token.text.isupper()


def caps_matches(token, reference_token, keep_same_caps):
    if not keep_same_caps:
        return True

    return is_all_caps_token(token) == is_all_caps_token(reference_token)

def token_is_blocked(token, context, block_labels):
    return (
        token is not None
        and context.token_entity_label(token) in block_labels
    )


def is_start_token(token, context, start_deprels, name_pos, block_labels):
    return (
        token is not None
        and token.morph_pos in name_pos
        and token.deprel in start_deprels
        and not token_is_blocked(token, context, block_labels)
    )


def is_continuation_token(
    token,
    context,
    cont_deprels,
    name_pos,
    block_labels,
    reference_token=None,
    keep_same_caps=False,
):
    return (
        token is not None
        and token.morph_pos in name_pos
        and token.deprel in cont_deprels
        and not token_is_blocked(token, context, block_labels)
        and (
            reference_token is None
            or caps_matches(token, reference_token, keep_same_caps)
        )
    )


def find_name_chain(
    span,
    context,
    start_deprels,
    cont_deprels,
    name_pos,
    block_labels,
    keep_same_caps=False,
):
    reference_token = span.tokens[0]

    start_i = span.start_i
    end_i = span.end_i

    while start_i > 0:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        prev_token = context.prev_token(candidate)

        if not is_continuation_token(
            prev_token,
            context,
            cont_deprels,
            name_pos,
            block_labels,
            reference_token=reference_token,
            keep_same_caps=keep_same_caps,
        ):
            break

        start_i -= 1

    candidate = context.span_from_indices(span.label, start_i, end_i)
    first_token = candidate.tokens[0]

    if not is_start_token(
        first_token,
        context,
        start_deprels,
        name_pos,
        block_labels,
    ):
        prev_token = context.prev_token(candidate)

        if not is_start_token(
            prev_token,
            context,
            start_deprels,
            name_pos,
            block_labels,
        ):
            return None

        if not caps_matches(prev_token, reference_token, keep_same_caps):
            return None

        start_i -= 1

    while True:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        next_token = context.next_token(candidate)

        if not is_continuation_token(
            next_token,
            context,
            cont_deprels,
            name_pos,
            block_labels,
            reference_token=reference_token,
            keep_same_caps=keep_same_caps,
        ):
            break

        end_i += 1

    new_span = context.span_from_indices(span.label, start_i, end_i)

    if not is_start_token(
        new_span.tokens[0],
        context,
        start_deprels,
        name_pos,
        block_labels,
    ):
        return None

    if not any(
        is_continuation_token(
            t,
            context,
            cont_deprels,
            name_pos,
            block_labels,
            reference_token=reference_token,
            keep_same_caps=keep_same_caps,
        )
        for t in new_span.tokens[1:]
    ):
        return None

    return new_span


def token_entity_label_or_none(context, token):
    if token is None:
        return None
    return context.token_entity_label(token)


def is_allowed_name_token(token, name_pos):
    return (
        token is not None
        and token.morph_pos in name_pos
    )


def is_flat_token(token, cont_deprels, name_pos):
    return (
        is_allowed_name_token(token, name_pos)
        and token.deprel in cont_deprels
    )


def has_blocking_entity(context, token, current_label, block_other_labels=True):
    label = token_entity_label_or_none(context, token)

    if label is None:
        return False

    if block_other_labels and label != current_label:
        return True

    return False


def find_start_flat_chain(
    span,
    context,
    start_deprels,
    cont_deprels={"flat"},
    name_pos={"H", "Y"},
    block_other_labels=True,
):
    start_i = span.start_i
    end_i = span.end_i

    while start_i > 0:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        prev_token = context.prev_token(candidate)
        prev_i = start_i - 1

        if not is_flat_token(prev_token, cont_deprels, name_pos):
            break

        if not (span.start_i <= prev_i < span.end_i):
            if has_blocking_entity(context, prev_token, span.label, block_other_labels):
                break

        start_i -= 1

    candidate = context.span_from_indices(span.label, start_i, end_i)
    first_token = candidate.tokens[0]

    if not is_start_token(first_token, start_deprels, name_pos):
        prev_token = context.prev_token(candidate)
        prev_i = start_i - 1

        if not is_start_token(prev_token, start_deprels, name_pos):
            return None

        if not (span.start_i <= prev_i < span.end_i):
            if has_blocking_entity(context, prev_token, span.label, block_other_labels):
                return None

        start_i -= 1

    while True:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        next_token = context.next_token(candidate)
        next_i = end_i

        if not is_flat_token(next_token, cont_deprels, name_pos):
            break

        if not (span.start_i <= next_i < span.end_i):
            if has_blocking_entity(context, next_token, span.label, block_other_labels):
                break

        end_i += 1

    new_span = context.span_from_indices(span.label, start_i, end_i)

    if len(new_span.tokens) < 2:
        return None

    if not is_start_token(new_span.tokens[0], start_deprels, name_pos):
        return None

    if not all(is_flat_token(token, cont_deprels, name_pos) for token in new_span.tokens[1:]):
        return None

    return new_span


class SplitDisconnectedLocTreeRule(BaseSplitDisconnectedEntityTreeRule):
    rule_id = "lahuta_mittesidus_loc_puu"
    description = "Lahutab mittesidusa LOC nimeüksuse."

    LABEL = "LOC"
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = {
        ("H", "S"),
        ("S", "S"),
        ("H", "Y"),
        ("A", "S"),
    }

    DO_NOT_SPLIT_DEPREL_PATTERNS = set()

    TRIM_EDGE_DEPRELS = {"cc"}
    TRIM_EDGE_POS = {"J", "O"}


class ExpandRightLocationFacilityHeadRule(BaseRule):
    rule_id = "laienda_loc_paremale_kohapea"
    description = "Laiendab ühesõnalist LOC märgendit kohatüübi või rajatise sõna võrra."

    def applies_to(self, span, context):
        return span.label == "LOC"

    def propose(self, span, context):
        if len(span.tokens) != 1:
            return None

        next_token = context.next_token(span)
        if next_token is None:
            return None
        if next_token.lemma not in FACILITY_LOCATION_HEADS:
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

        return RuleProposal(self.rule_id, "replace", 0.96, [new_span], {"from": span.text, "to": new_span.text})
    

class ExpandPersonRootChainRule(BaseRule):
    rule_id = 'laienda_nime_root'
    description = 'Laiendab ühe-tokenilist PER üksust root + flat* nimeahelaks.'

    START_DEPRELS = {'root'}
    CONT_DEPRELS = {'flat'}
    NAME_POS = {'H', 'Y'}
    BLOCK_LABELS = {'LOC'}
    KEEP_SAME_CAPS = True
    SCORE = 0.99

    def applies_to(self, span, context):
        return span.label == 'PER' and len(span.tokens) == 1

    def propose(self, span, context):
        token = span.tokens[0]

        if not (
            is_start_token(token, context, self.START_DEPRELS, self.NAME_POS, self.BLOCK_LABELS)
            or is_continuation_token(
                token,
                context,
                self.CONT_DEPRELS,
                self.NAME_POS,
                self.BLOCK_LABELS,
                reference_token=token,
                keep_same_caps=self.KEEP_SAME_CAPS,
            )
        ):
            return None

        new_span = find_name_chain(
            span,
            context,
            self.START_DEPRELS,
            self.CONT_DEPRELS,
            self.NAME_POS,
            self.BLOCK_LABELS,
            keep_same_caps=self.KEEP_SAME_CAPS,
        )

        if new_span is None:
            return None

        if new_span.start_i == span.start_i and new_span.end_i == span.end_i:
            return None

        return RuleProposal(
            rule_id=self.rule_id,
            operation='replace',
            score=self.SCORE,
            spans=[new_span],
            metadata={'from': span.text, 'to': new_span.text},
        )
    

class ExpandLocNsubjFlatRule(BaseRule):
    rule_id = "laienda_loc_nsubj_flat"
    description = "Laiendab LOC märgendit nsubj/nsubj:cop + flat* ahelaks."

    def applies_to(self, span, context):
        return span.label == "LOC"

    def propose(self, span, context):
        new_span = find_start_flat_chain(
            span=span,
            context=context,
            start_deprels={"nsubj", "nsubj:cop"},
            cont_deprels={"flat"},
            name_pos={"H"},
            block_other_labels=True,
        )

        if new_span is None:
            return None

        if new_span.start_i == span.start_i and new_span.end_i == span.end_i:
            return None

        return RuleProposal(
            rule_id=self.rule_id,
            operation="replace",
            score=0.97,
            spans=[new_span],
        )