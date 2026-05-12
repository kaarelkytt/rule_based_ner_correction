from .base import BaseMissingRule, MissingProposal
from .common import *

PERSON_ATTRIBUTION_LEMMAS = {"hinnangul", "järgi", "kinnitusel", "sõnul", "teatel"}

PERSON_SENTENCE_START_VERBS = {
    "kinnitama",
    "lisama",
    "olema",
    "rääkima",
    "teatama",
    "tegema",
    "tunnistama",
    "ütlema",
    "vastama",
}

PERSON_SENTENCE_START_EXTRA_VERBS = {"seisma", "tahtma"}


def token_is_blocked_by_label(token, context, block_labels):
    return (
        token is not None
        and context.token_entity_label(token) in block_labels
    )


def token_is_free(token_i, occupied):
    return token_i not in occupied


def is_missing_token(token, start_deprels, name_pos):
    return (
        token is not None
        and token.morph_pos in name_pos
        and token.deprel in start_deprels
    )


def is_all_caps_text(text):
    return any(ch.isalpha() for ch in text) and text.isupper()


def caps_matches_reference(token, reference_token, keep_same_caps):
    if not keep_same_caps:
        return True

    return is_all_caps_text(token.text) == is_all_caps_text(reference_token.text)


def find_missing_name_chain_from_start(
    context,
    start_i,
    occupied,
    start_deprels,
    cont_deprels,
    name_pos,
    block_labels,
    keep_same_caps=False,
    min_len=2,
    max_len=None,
):
    if start_i in occupied:
        return None

    start_token = context.tokens[start_i]

    if token_is_blocked_by_label(start_token, context, block_labels):
        return None

    if not is_missing_token(start_token, start_deprels, name_pos):
        return None

    end_i = start_i + 1
    reference_token = start_token

    while end_i < len(context.tokens):
        token = context.tokens[end_i]

        if end_i in occupied:
            break

        if token_is_blocked_by_label(token, context, block_labels):
            break

        if not is_missing_token(token, cont_deprels, name_pos):
            break

        if not caps_matches_reference(token, reference_token, keep_same_caps):
            break

        end_i += 1

    if end_i - start_i < min_len:
        return None
    
    if max_len is not None and end_i - start_i > max_len:
        return None

    return start_i, end_i


class InsertPersonRootChainRule(BaseMissingRule):
    rule_id = "lisa_nimeahel_root"
    description = "Lisab puuduva PER märgendi root + flat* nimeahela põhjal."

    def _is_valid_candidate(self, context, start_i, end_i):
        tokens = context.tokens[start_i:end_i]

        for t in tokens:
            if not t.text[:1].isupper():
                return False

        text = "".join(t.text for t in tokens)
        cleaned = text.replace("-", "")

        if not cleaned.isalpha():
            return False

        return True

    def find(self, context, occupied):
        proposals = []

        for i, token in enumerate(context.tokens):
            chain = find_missing_name_chain_from_start(
                context,
                i,
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

            proposals.append(MissingProposal(
                rule_id=self.rule_id,
                label="PER",
                start_i=start_i,
                end_i=end_i,
                score=0.97,
            ))

        return proposals


class InsertPersonConjChainRule(BaseMissingRule):
    rule_id = "lisa_nimeahel_conj"
    description = "Lisab puuduva PER märgendi conj + flat* nimeahela põhjal."

    def find(self, context, occupied):
        proposals = []

        for i, token in enumerate(context.tokens):
            chain = find_missing_name_chain_from_start(
                context,
                i,
                occupied,
                {"conj"},
                {"flat"},
                {"H"},
                {"LOC"},
                keep_same_caps=False,
                min_len=2,
                max_len=2,
            )

            if chain is None:
                continue

            start_i, end_i = chain

            proposals.append(MissingProposal(
                rule_id=self.rule_id,
                label="PER",
                start_i=start_i,
                end_i=end_i,
                score=0.95,
                metadata={
                    "text": " ".join(t.text for t in context.tokens[start_i:end_i]),
                    "start_deprels": sorted(self.START_DEPRELS),
                },
            ))

        return proposals


class InsertUppercasePersonHeadingRule(BaseMissingRule):
    rule_id = "lisa_suurtäheline_isikunimi"
    description = "Lisab puuduva PER märgendi kahest suurtähelisest tokenist."

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied or i + 1 in occupied:
                continue
            first = context.tokens[i]
            second = context.tokens[i + 1]
            if not is_upper_name(first.text) or not is_upper_name(second.text):
                continue
            after = context.tokens[i + 2] if i + 2 < len(context.tokens) else None
            if after is not None and after.morph_pos not in {"Z", None}:
                continue
            if after is not None and after.text == ":":
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", i, i + 2, 0.99))
        return proposals


class InsertShortHeadlineEntityRule(BaseMissingRule):
    rule_id = "lisa_lühike_pealkiri"
    description = "Lisab puuduva nimeüksuse, kui kogu tekst on lühikese nime moodi pealkiri."

    def find(self, context, occupied):
        if len(context.tokens) > 3:
            return []
        if any(token.text in {".", "!", "?", ",", ";", ":"} for token in context.tokens):
            return []
        if any(i in occupied for i in range(len(context.tokens))):
            return []
        if not all(token.xpostag == "H" and (is_title_case_name(token.text) or is_upper_name(token.text)) for token in context.tokens):
            return []

        lemmas = {lower_key(token) for token in context.tokens}
        last = context.tokens[-1]
        if lower_key(last) in {"liit", "keskliit"}:
            label = "ORG"
        elif len(context.tokens) == 2 and all(is_title_case_name(token.text) for token in context.tokens):
            label = "PER"
        elif len(context.tokens) == 1 and lower_key(last) == "reuters":
            label = "ORG"
        else:
            label = "LOC"

        return [MissingProposal(self.rule_id, label, 0, len(context.tokens), 0.89)]


class InsertSentenceStartReportingPersonRule(BaseMissingRule):
    rule_id = "lisa_lausealguse_isik"
    description = "Lisab puuduva ühesõnalise PER märgendi lause alguses enne reporting-verbi."

    REPORTING_VERBS = {
        "kinnitama",
        "lausuma",
        "lisama",
        "märkima",
        "nentima",
        "rääkima",
        "teatama",
        "tunnistama",
        "täpsustama",
        "ütlema",
        "väitma",
    }

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied:
                continue
            token = context.tokens[i]
            next_token = context.tokens[i + 1]
            prev = context.tokens[i - 1] if i > 0 else None
            if not is_sentence_start(prev):
                continue
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if lower_key(next_token) not in self.REPORTING_VERBS:
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", i, i + 1, 0.98))
        return proposals


class InsertSentenceStartPersonLabelRule(BaseMissingRule):
    rule_id = "lisa_lausealguse_nimisilt"
    description = "Lisab puuduva ühesõnalise PER märgendi lause alguses enne koolonit."

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied:
                continue
            token = context.tokens[i]
            next_token = context.tokens[i + 1]
            prev = context.tokens[i - 1] if i > 0 else None
            if prev is not None and prev.text not in {".", "!", "?", '"', "“", "”"}:
                continue
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if next_token.text != ":":
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", i, i + 1, 0.97))
        return proposals


class InsertPersonAttributionRule(BaseMissingRule):
    rule_id = "lisa_atributsiooni_isik"
    description = "Lisab puuduva PER märgendi enne sõnu nagu sõnul või teatel."

    GROUP_SOURCE_SUFFIXES = ("jate", "ude")

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied:
                continue
            token = context.tokens[i]
            next_token = context.tokens[i + 1]
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if token.lower.endswith(self.GROUP_SOURCE_SUFFIXES):
                continue
            if lower_key(next_token) not in PERSON_ATTRIBUTION_LEMMAS and next_token.lower not in PERSON_ATTRIBUTION_LEMMAS:
                continue
            start_i = i
            if i > 0 and i - 1 not in occupied:
                prev = context.tokens[i - 1]
                if prev.xpostag == "H" and is_title_case_name(prev.text):
                    start_i = i - 1
            proposals.append(MissingProposal(self.rule_id, "PER", start_i, i + 1, 0.97))
        return proposals


class InsertSentenceStartSimplePersonRule(BaseMissingRule):
    rule_id = "lisa_lihtne_lausealguse_isik"
    description = "Lisab puuduva ühesõnalise PER märgendi lause alguses lihtsa verbi ees."

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied:
                continue
            token = context.tokens[i]
            next_token = context.tokens[i + 1]
            prev = context.tokens[i - 1] if i > 0 else None
            if not is_sentence_start(prev):
                continue
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if token.lower.endswith("ks"):
                continue
            if (token.lemma or "").lower() != token.text.lower():
                continue
            if lower_key(next_token) not in PERSON_SENTENCE_START_VERBS | PERSON_SENTENCE_START_EXTRA_VERBS:
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", i, i + 1, 0.91))
        return proposals
