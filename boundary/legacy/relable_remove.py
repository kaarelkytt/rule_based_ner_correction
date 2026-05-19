from .base import BaseRule, RuleProposal


ROMAN_NUMERALS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
GENERIC_UPPER_BLOCKLIST = {
    "INTERVJUU",
    "JAOTIS",
    "KÄESOLEVA",
    "KOKKUVÕTTEKS",
    "KOMISJONI",
    "LISA",
    "MÄÄRUS",
    "MÄÄRUSE",
    "NÕUKOGU",
    "PEATÜKK",
}


def _is_upper_name(text):
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and all(character.isupper() for character in letters)


class RemoveGenericUppercaseHeadingRule(BaseRule):
    rule_id = "eemalda_üldine_suurtähest_pealkiri"
    description = "Eemaldab selgelt üldise suurtähest pealkirjataolise märgendi."

    def applies_to(self, span, context):
        return span.label in {"ORG", "PER", "LOC"}

    def propose(self, span, context):
        if not span.tokens or len(span.tokens) > 3:
            return None
        if not all(_is_upper_name(token.text) for token in span.tokens if any(character.isalpha() for character in token.text)):
            return None
        upper_words = {token.text.upper() for token in span.tokens}
        generic_hits = upper_words & GENERIC_UPPER_BLOCKLIST
        if not generic_hits:
            return None
        first_upper = span.tokens[0].text.upper()
        if first_upper not in ROMAN_NUMERALS and len(generic_hits) < 2 and not upper_words <= GENERIC_UPPER_BLOCKLIST:
            return None
        return RuleProposal(self.rule_id, "remove", 0.999, [], {"from": span.text})