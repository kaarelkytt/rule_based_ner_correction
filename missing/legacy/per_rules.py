from ..base import BaseMissingRule, MissingProposal
from ..common import is_sentence_start, is_title_case_name, is_upper_name, lower_key
from ..per_rules import (
    PERSON_ATTRIBUTION_LEMMAS,
    PERSON_SENTENCE_START_EXTRA_VERBS,
    PERSON_SENTENCE_START_VERBS,
    find_missing_name_chain_from_start,
)


class InsertPersonConjChainRule(BaseMissingRule):
    rule_id = "lisa_nimeahel_conj"
    description = "Lisab puuduva PER märgendi conj + flat nimeahela põhjal."

    def find(self, context, occupied):
        proposals = []
        for index, token in enumerate(context.tokens):
            chain = find_missing_name_chain_from_start(
                context,
                index,
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
            proposals.append(MissingProposal(self.rule_id, "PER", start_i, end_i, 0.95))
        return proposals


class InsertUppercasePersonHeadingRule(BaseMissingRule):
    rule_id = "lisa_suurtähest_isikunimi"
    description = "Lisab puuduva PER märgendi kahest suurtähest tokenist."

    def find(self, context, occupied):
        proposals = []
        for index in range(len(context.tokens) - 1):
            if index in occupied or index + 1 in occupied:
                continue
            first = context.tokens[index]
            second = context.tokens[index + 1]
            if not is_upper_name(first.text) or not is_upper_name(second.text):
                continue
            after = context.tokens[index + 2] if index + 2 < len(context.tokens) else None
            if after is not None and after.morph_pos not in {"Z", None}:
                continue
            if after is not None and after.text == ":":
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", index, index + 2, 0.99))
        return proposals


class InsertShortHeadlineEntityRule(BaseMissingRule):
    rule_id = "lisa_lühike_pealkiri"
    description = "Lisab puuduva nimeüksuse, kui kogu tekst on lühike nime moodi pealkiri."

    def find(self, context, occupied):
        if len(context.tokens) > 3:
            return []
        if any(token.text in {".", "!", "?", ",", ";", ":"} for token in context.tokens):
            return []
        if any(index in occupied for index in range(len(context.tokens))):
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
        for index in range(len(context.tokens) - 1):
            if index in occupied:
                continue
            token = context.tokens[index]
            next_token = context.tokens[index + 1]
            previous = context.tokens[index - 1] if index > 0 else None
            if not is_sentence_start(previous):
                continue
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if lower_key(next_token) not in self.REPORTING_VERBS:
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", index, index + 1, 0.98))
        return proposals


class InsertSentenceStartPersonLabelRule(BaseMissingRule):
    rule_id = "lisa_lausealguse_nimisilt"
    description = "Lisab puuduva ühesõnalise PER märgendi lause alguses enne koolonit."

    def find(self, context, occupied):
        proposals = []
        for index in range(len(context.tokens) - 1):
            if index in occupied:
                continue
            token = context.tokens[index]
            next_token = context.tokens[index + 1]
            previous = context.tokens[index - 1] if index > 0 else None
            if previous is not None and previous.text not in {".", "!", "?", '"', "“", "”"}:
                continue
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if next_token.text != ":":
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", index, index + 1, 0.97))
        return proposals


class InsertPersonAttributionRule(BaseMissingRule):
    rule_id = "lisa_atributsiooni_isik"
    description = "Lisab puuduva PER märgendi enne sõnu nagu sõnul või teatel."

    GROUP_SOURCE_SUFFIXES = ("jate", "ude")

    def find(self, context, occupied):
        proposals = []
        for index in range(len(context.tokens) - 1):
            if index in occupied:
                continue
            token = context.tokens[index]
            next_token = context.tokens[index + 1]
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if token.lower.endswith(self.GROUP_SOURCE_SUFFIXES):
                continue
            if lower_key(next_token) not in PERSON_ATTRIBUTION_LEMMAS and next_token.lower not in PERSON_ATTRIBUTION_LEMMAS:
                continue
            start_i = index
            if index > 0 and index - 1 not in occupied:
                previous = context.tokens[index - 1]
                if previous.xpostag == "H" and is_title_case_name(previous.text):
                    start_i = index - 1
            proposals.append(MissingProposal(self.rule_id, "PER", start_i, index + 1, 0.97))
        return proposals


class InsertSentenceStartSimplePersonRule(BaseMissingRule):
    rule_id = "lisa_lihtne_lausealguse_isik"
    description = "Lisab puuduva ühesõnalise PER märgendi lause alguses lihtsa verbi ees."

    COMMON_WORD_BLOCKLIST = {"hetkel", "risotto", "suhe", "teenindusfäär", "tolku"}

    def find(self, context, occupied):
        proposals = []
        for index in range(len(context.tokens) - 1):
            if index in occupied:
                continue
            token = context.tokens[index]
            next_token = context.tokens[index + 1]
            previous = context.tokens[index - 1] if index > 0 else None
            if not is_sentence_start(previous):
                continue
            if token.xpostag != "H" or not is_title_case_name(token.text):
                continue
            if token.lower.endswith("ks") or token.lower in self.COMMON_WORD_BLOCKLIST:
                continue
            if (token.lemma or "").lower() != token.text.lower():
                continue
            if lower_key(next_token) not in PERSON_SENTENCE_START_VERBS | PERSON_SENTENCE_START_EXTRA_VERBS:
                continue
            proposals.append(MissingProposal(self.rule_id, "PER", index, index + 1, 0.91))
        return proposals
