from ..base import BaseMissingRule, MissingProposal
from ..common import is_sentence_start, is_title_case_name, is_upper_name, lower_key
from ..org_rules import (
    GENERIC_SINGLE_ORG_OWNER_BLOCKLIST,
    MULTI_TOKEN_ORG_HEADS,
    ORG_CONTEXT_NOUNS,
    SINGLE_TOKEN_ORG_LEMMAS,
    is_institution_like,
    is_org_owner_head,
    is_owner_chain_token,
)


class InsertSentenceStartInstitutionChainRule(BaseMissingRule):
    rule_id = "lisa_lausealguse_asutuseahel"
    description = "Lisab puuduva kaheosalise ORG märgendi lause alguses."

    ORG_REPORTING_VERBS = {
        "avalikustama",
        "hoiatama",
        "kinnitama",
        "koordineerima",
        "leidma",
        "lõpetama",
        "lokaliseerima",
        "ootama",
        "otsustama",
        "pidama",
        "saama",
        "tahtma",
        "teatama",
        "tuvastama",
        "vabastama",
    }

    def find(self, context, occupied):
        proposals = []
        for index in range(len(context.tokens) - 2):
            if index in occupied or index + 1 in occupied:
                continue
            first = context.tokens[index]
            second = context.tokens[index + 1]
            previous = context.tokens[index - 1] if index > 0 else None
            if not is_sentence_start(previous):
                continue
            if first.xpostag != "H" and not is_upper_name(first.text):
                continue
            if lower_key(second) not in MULTI_TOKEN_ORG_HEADS:
                continue
            after = context.tokens[index + 2]
            if lower_key(after) not in self.ORG_REPORTING_VERBS and lower_key(after) not in ORG_CONTEXT_NOUNS and after.text != ":":
                continue
            proposals.append(MissingProposal(self.rule_id, "ORG", index, index + 2, 0.94))
        return proposals


class InsertInstitutionChainRoleOwnerRule(BaseMissingRule):
    rule_id = "lisa_asutuseahel_rolli_ees"
    description = "Lisab puuduva lühikese ORG ahela enne rollisõna."

    def find(self, context, occupied):
        proposals = []
        for start_i in range(len(context.tokens) - 2):
            if start_i in occupied:
                continue
            start_token = context.tokens[start_i]
            if not (is_institution_like(start_token) or is_title_case_name(start_token.text) or is_upper_name(start_token.text)):
                continue
            for end_i in range(start_i + 2, min(start_i + 5, len(context.tokens)) + 1):
                token_range = set(range(start_i, end_i))
                if token_range & occupied:
                    break
                last = context.tokens[end_i - 1]
                after = context.tokens[end_i] if end_i < len(context.tokens) else None
                if lower_key(last) not in MULTI_TOKEN_ORG_HEADS:
                    continue
                if after is None or lower_key(after) not in ORG_CONTEXT_NOUNS:
                    continue
                span = context.span_from_indices("ORG", start_i, end_i)
                if span.root_count > 2:
                    continue
                proposals.append(MissingProposal(self.rule_id, "ORG", start_i, end_i, 0.90))
                break
        return proposals


class InsertInstitutionRoleOwnerRule(BaseMissingRule):
    rule_id = "lisa_rolli_eelne_asutus"
    description = "Lisab puuduva ühesõnalise ORG märgendi rollisõna ette."

    SPECIFIC_SUFFIXES = ("amet", "ministeerium", "politsei", "keskus", "inspektsioon", "valitsus", "volikogu")

    def find(self, context, occupied):
        proposals = []
        for index in range(len(context.tokens) - 1):
            if index in occupied:
                continue
            token = context.tokens[index]
            if not is_institution_like(token):
                continue
            key = lower_key(token)
            if not (token.text[:1].isupper() or key in SINGLE_TOKEN_ORG_LEMMAS or any(key.endswith(suffix) for suffix in self.SPECIFIC_SUFFIXES)):
                continue
            next_token = context.tokens[index + 1] if index + 1 < len(context.tokens) else None
            if next_token is not None and lower_key(next_token) in ORG_CONTEXT_NOUNS:
                proposals.append(MissingProposal(self.rule_id, "ORG", index, index + 1, 0.95))
        return proposals


class InsertInstitutionConjRule(BaseMissingRule):
    rule_id = "lisa_koordineeritud_asutus"
    description = "Lisab puuduva ORG märgendi, kui asutusesarnane token on teise asutuse konjunkt."

    TOKEN_BLOCKLIST = {"kool", "kooli"}
    HEAD_BLOCKLIST = {"side"}

    def find(self, context, occupied):
        proposals = []
        for index, token in enumerate(context.tokens):
            if index in occupied:
                continue
            if token.deprel != "conj" or token.head in {None, 0}:
                continue
            if not is_institution_like(token) or lower_key(token) in self.TOKEN_BLOCKLIST:
                continue
            head_token = context.by_syntax_id.get(token.head)
            if head_token is None or not is_institution_like(head_token):
                continue
            if lower_key(head_token) in self.HEAD_BLOCKLIST:
                continue
            proposals.append(MissingProposal(self.rule_id, "ORG", index, index + 1, 0.94))
        return proposals
