from .base import RuleProposal


ALLOWED_NAME_POS = {"H", "Y"}


def is_title_case_name(text):
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    return text[:1].isupper()


def is_name_like_token(token):
    if token is None:
        return False
    return token.xpostag == "H" or is_title_case_name(token.text)


def is_all_caps_token(token):
    return token is not None and token.text.isupper()


def caps_match(token, reference_token, keep_same_caps):
    if not keep_same_caps:
        return True
    return is_all_caps_token(token) == is_all_caps_token(reference_token)


def token_entity_label(context, token):
    if token is None:
        return None
    return context.token_entity_label(token)


def is_blocked_token(token, context, blocked_labels):
    return token is not None and token_entity_label(context, token) in blocked_labels


def is_start_token(token, context, start_deprels, name_pos, blocked_labels=()):
    return (
        token is not None
        and token.morph_pos in name_pos
        and token.deprel in start_deprels
        and not is_blocked_token(token, context, blocked_labels)
    )


def is_continuation_token(
    token,
    context,
    continuation_deprels,
    name_pos,
    blocked_labels=(),
    reference_token=None,
    keep_same_caps=False,
):
    return (
        token is not None
        and token.morph_pos in name_pos
        and token.deprel in continuation_deprels
        and not is_blocked_token(token, context, blocked_labels)
        and (
            reference_token is None
            or caps_match(token, reference_token, keep_same_caps)
        )
    )


def find_name_chain(
    span,
    context,
    start_deprels,
    continuation_deprels,
    name_pos,
    blocked_labels,
    keep_same_caps=False,
):
    reference_token = span.tokens[0]
    start_i = span.start_i
    end_i = span.end_i

    while start_i > 0:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        previous_token = context.prev_token(candidate)
        if not is_continuation_token(
            previous_token,
            context,
            continuation_deprels,
            name_pos,
            blocked_labels,
            reference_token=reference_token,
            keep_same_caps=keep_same_caps,
        ):
            break
        start_i -= 1

    candidate = context.span_from_indices(span.label, start_i, end_i)
    first_token = candidate.tokens[0]
    if not is_start_token(first_token, context, start_deprels, name_pos, blocked_labels):
        previous_token = context.prev_token(candidate)
        if not is_start_token(previous_token, context, start_deprels, name_pos, blocked_labels):
            return None
        if not caps_match(previous_token, reference_token, keep_same_caps):
            return None
        start_i -= 1

    while True:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        next_token = context.next_token(candidate)
        if not is_continuation_token(
            next_token,
            context,
            continuation_deprels,
            name_pos,
            blocked_labels,
            reference_token=reference_token,
            keep_same_caps=keep_same_caps,
        ):
            break
        end_i += 1

    new_span = context.span_from_indices(span.label, start_i, end_i)
    if not is_start_token(new_span.tokens[0], context, start_deprels, name_pos, blocked_labels):
        return None
    if not any(
        is_continuation_token(
            token,
            context,
            continuation_deprels,
            name_pos,
            blocked_labels,
            reference_token=reference_token,
            keep_same_caps=keep_same_caps,
        )
        for token in new_span.tokens[1:]
    ):
        return None
    return new_span


def is_flat_token(token, continuation_deprels, name_pos):
    return token is not None and token.morph_pos in name_pos and token.deprel in continuation_deprels


def has_blocking_entity(context, token, current_label, block_other_labels=True):
    label = token_entity_label(context, token)
    if label is None:
        return False
    if block_other_labels and label != current_label:
        return True
    return False


def find_start_flat_chain(
    span,
    context,
    start_deprels,
    continuation_deprels,
    name_pos,
    block_other_labels=True,
):
    start_i = span.start_i
    end_i = span.end_i

    while start_i > 0:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        previous_token = context.prev_token(candidate)
        previous_index = start_i - 1

        if not is_flat_token(previous_token, continuation_deprels, name_pos):
            break
        if not (span.start_i <= previous_index < span.end_i):
            if has_blocking_entity(context, previous_token, span.label, block_other_labels):
                break
        start_i -= 1

    candidate = context.span_from_indices(span.label, start_i, end_i)
    first_token = candidate.tokens[0]
    if not is_start_token(first_token, context, start_deprels, name_pos):
        previous_token = context.prev_token(candidate)
        previous_index = start_i - 1
        if not is_start_token(previous_token, context, start_deprels, name_pos):
            return None
        if not (span.start_i <= previous_index < span.end_i):
            if has_blocking_entity(context, previous_token, span.label, block_other_labels):
                return None
        start_i -= 1

    while True:
        candidate = context.span_from_indices(span.label, start_i, end_i)
        next_token = context.next_token(candidate)
        next_index = end_i
        if not is_flat_token(next_token, continuation_deprels, name_pos):
            break
        if not (span.start_i <= next_index < span.end_i):
            if has_blocking_entity(context, next_token, span.label, block_other_labels):
                break
        end_i += 1

    new_span = context.span_from_indices(span.label, start_i, end_i)
    if len(new_span.tokens) < 2:
        return None
    if not is_start_token(new_span.tokens[0], context, start_deprels, name_pos):
        return None
    if not all(is_flat_token(token, continuation_deprels, name_pos) for token in new_span.tokens[1:]):
        return None
    return new_span


def replace_with_span(rule_id, score, old_span, new_span):
    return RuleProposal(
        rule_id=rule_id,
        operation="replace",
        score=score,
        spans=[new_span],
        metadata={"from": old_span.text, "to": new_span.text},
    )
