from .base import BaseMissingRule, MissingProposal


def token_is_blocked_by_label(token, context, blocked_labels):
    return token is not None and context.token_entity_label(token) in blocked_labels


def is_missing_name_token(token, start_deprels, name_pos):
    return token is not None and token.morph_pos in name_pos and token.deprel in start_deprels


def is_all_caps_text(text):
    return any(character.isalpha() for character in text) and text.isupper()


def caps_match(token, reference_token, keep_same_caps):
    if not keep_same_caps:
        return True
    return is_all_caps_text(token.text) == is_all_caps_text(reference_token.text)


def find_missing_name_chain_from_start(
    context,
    start_i,
    occupied,
    start_deprels,
    continuation_deprels,
    name_pos,
    blocked_labels,
    keep_same_caps=False,
    min_len=2,
    max_len=None,
):
    if start_i in occupied:
        return None

    start_token = context.tokens[start_i]
    if token_is_blocked_by_label(start_token, context, blocked_labels):
        return None
    if not is_missing_name_token(start_token, start_deprels, name_pos):
        return None

    end_i = start_i + 1
    reference_token = start_token

    while end_i < len(context.tokens):
        token = context.tokens[end_i]
        if end_i in occupied:
            break
        if token_is_blocked_by_label(token, context, blocked_labels):
            break
        if not is_missing_name_token(token, continuation_deprels, name_pos):
            break
        if not caps_match(token, reference_token, keep_same_caps):
            break
        end_i += 1

    if end_i - start_i < min_len:
        return None
    if max_len is not None and end_i - start_i > max_len:
        return None

    return start_i, end_i


class InsertPersonRootChainRule(BaseMissingRule):
    rule_id = "lisa_nimeahel_root"
    description = "Lisab puuduva PER märgendi root + flat nimeahela põhjal."

    def _is_valid_candidate(self, context, start_i, end_i):
        tokens = context.tokens[start_i:end_i]
        if not all(token.text[:1].isupper() for token in tokens):
            return False
        text = "".join(token.text for token in tokens).replace("-", "")
        return text.isalpha()

    def find(self, context, occupied):
        proposals = []
        for index, _token in enumerate(context.tokens):
            chain = find_missing_name_chain_from_start(
                context,
                index,
                occupied,
                {"root"},
                {"flat"},
                {"H", "Y"},
                {"LOC"},
                keep_same_caps=True,
                min_len=2,
                max_len=2,
            )
            if chain is None:
                continue

            start_i, end_i = chain
            if not self._is_valid_candidate(context, start_i, end_i):
                continue

            proposals.append(
                MissingProposal(
                    rule_id=self.rule_id,
                    label="PER",
                    start_i=start_i,
                    end_i=end_i,
                    score=0.97,
                )
            )
        return proposals
