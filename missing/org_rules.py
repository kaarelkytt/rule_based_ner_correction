from .base import BaseMissingRule, MissingProposal
from .common import is_title_case_name, lower_key


ORG_CONTEXT_NOUNS = {
    "asekantsler",
    "direktor",
    "esimees",
    "esindaja",
    "juhataja",
    "liige",
    "otsus",
    "peadirektor",
    "pressinõunik",
    "pressiesindaja",
}

SINGLE_TOKEN_ORG_LEMMAS = {
    "amet",
    "ametkond",
    "asutus",
    "büroo",
    "haigekassa",
    "haigla",
    "haridusministeerium",
    "isamaaliit",
    "kaitsejõud",
    "kaitsevägi",
    "keskkriminaalpolitsei",
    "keskus",
    "keskkonnainspektsioon",
    "kool",
    "linnavalitsus",
    "meteoroloogiakeskus",
    "ministeerium",
    "munitsipaalpolitsei",
    "pank",
    "piirivalveamet",
    "politsei",
    "politseiamet",
    "prefektuur",
    "prokuratuur",
    "päästeamet",
    "päästeteenistus",
    "reformierakond",
    "riigikogu",
    "sõjaväekohus",
    "tervisekaitse",
    "terviseleht",
    "transpordiamet",
    "ülikool",
    "valitsus",
    "volikogu",
}

MULTI_TOKEN_ORG_HEADS = {
    "andmebüroo",
    "büroo",
    "direktoraat",
    "infokeskus",
    "inspektsioon",
    "keskus",
    "komitee",
    "nõukogu",
    "osakond",
    "pressitalitus",
    "pressiteenistus",
    "sekretariaat",
    "talitus",
    "teenistus",
}

GENERIC_SINGLE_ORG_OWNER_BLOCKLIST = {
    "erakond",
    "juhatus",
    "komisjon",
    "liit",
    "riigikogu",
    "valitsus",
    "volikogu",
}

INSTITUTION_SUFFIXES = (
    "amet",
    "ametkond",
    "erakond",
    "haigla",
    "kassa",
    "keskus",
    "liit",
    "ministeerium",
    "politsei",
    "prefektuur",
    "prokuratuur",
    "teater",
    "televisioon",
    "ülikool",
    "valitsus",
    "volikogu",
)

ORG_OWNER_HEAD_SUFFIXES = (
    "amet",
    "büroo",
    "juhatus",
    "komisjon",
    "komitee",
    "ministeerium",
    "osakond",
    "peastaap",
    "politsei",
    "prefekt",
    "prefektuur",
    "prokuratuur",
    "staap",
    "talitus",
    "teenistus",
)


def is_institution_like(token):
    key = lower_key(token)
    return key in SINGLE_TOKEN_ORG_LEMMAS or any(key.endswith(suffix) for suffix in INSTITUTION_SUFFIXES)


def is_org_owner_head(token):
    key = lower_key(token)
    return is_institution_like(token) or key in MULTI_TOKEN_ORG_HEADS or any(
        key.endswith(suffix) for suffix in ORG_OWNER_HEAD_SUFFIXES
    )


def is_owner_chain_token(token):
    return token.morph_pos in {"S", "A", "H", "Y"} or token.lower == "ja" or token.text == "-"


class InsertCoreInstitutionMentionRule(BaseMissingRule):
    rule_id = "lisa_põhiasutus"
    description = "Lisab puuduva ühesõnalise ORG märgendi sagedastele asutusenimedele."

    LEMMAS = {
        "haigekassa",
        "haridusministeerium",
        "keskkonnaministeerium",
        "rahandusministeerium",
        "häirekeskus",
        "kaitsepolitsei",
        "kaitsevägi",
        "keskkriminaalpolitsei",
        "keskpank",
        "keskvalimiskomisjon",
        "linnavalitsus",
        "linnavolikogu",
        "parlament",
        "põllumajandusülikool",
    }
    FOLLOWING_HEADS = {
        "amet",
        "erikomisjon",
        "juhatus",
        "kantselei",
        "keskus",
        "komisjon",
        "kommunikatsioonibüroo",
        "nõukogu",
        "osakond",
        "pank",
        "riigikaitsekomisjon",
    }
    CONTEXT_CASES = {"g", "in", "ill", "ad", "all", "el", "abl", "kom", "tr", "es"}
    CONTEXT_DEPRELS = {"nmod", "obl", "obj", "nsubj", "root", "conj", "appos"}

    def find(self, context, occupied):
        proposals = []
        for index, token in enumerate(context.tokens):
            if index in occupied:
                continue

            key = lower_key(token)
            if key not in self.LEMMAS:
                continue

            next_token = context.tokens[index + 1] if index + 1 < len(context.tokens) else None
            if next_token is not None and lower_key(next_token) in self.FOLLOWING_HEADS:
                continue

            form_parts = set((token.form or "").split())
            strong_context = (
                token.text[:1].isupper()
                or bool(form_parts & self.CONTEXT_CASES)
                or token.deprel in self.CONTEXT_DEPRELS
            )
            if not strong_context:
                continue

            proposals.append(MissingProposal(self.rule_id, "ORG", index, index + 1, 0.92))
        return proposals


class InsertShortInstitutionHeadPhraseRule(BaseMissingRule):
    rule_id = "lisa_lühike_asutusefraas"
    description = "Lisab puuduva lühikese ORG fraasi nagu Veeteede amet või presidendi kantselei."

    HEADS = {
        "amet",
        "andmebüroo",
        "büroo",
        "direktoraat",
        "infokeskus",
        "inspektsioon",
        "juhatus",
        "kantselei",
        "komisjon",
        "kommunikatsioonibüroo",
        "nõukogu",
        "osakond",
        "sekretariaat",
        "talitus",
        "teenistus",
    }
    LOWERCASE_OWNER_ALLOW = {
        "linnavalitsus",
        "president",
        "presidendi",
        "rahandusministeerium",
        "riigikogu",
        "siseministeerium",
        "valitsus",
        "välisministeerium",
    }
    FIRST_KEY_BLOCKLIST = {
        "abiprokurör",
        "jäänuk",
        "jäänukid",
        "kohad",
        "lisaks",
        "moodustama",
        "mõistus",
        "näitleja",
        "politseinik",
        "prokurör",
        "vastuseks",
    }

    def find(self, context, occupied):
        proposals = []
        for start_i in range(len(context.tokens) - 1):
            if start_i in occupied or start_i + 1 in occupied:
                continue

            first = context.tokens[start_i]
            head = context.tokens[start_i + 1]
            previous = context.tokens[start_i - 1] if start_i > 0 else None

            if lower_key(head) not in self.HEADS or head.morph_pos not in {"S", "H"}:
                continue
            if previous is not None and previous.text in {'"', "“", "”"}:
                continue

            first_key = lower_key(first)
            if first_key in self.FIRST_KEY_BLOCKLIST or first.deprel in {"advmod", "discourse"}:
                continue
            if lower_key(head) == "amet" and first.text[:1].isupper() and first.xpostag == "H":
                continue

            first_form_parts = set((first.form or "").split())
            first_ok = (
                first.xpostag == "H"
                or (is_title_case_name(first.text) and first.morph_pos in {"S", "H", "Y"})
                or (
                    first_key in self.LOWERCASE_OWNER_ALLOW
                    and first.morph_pos in {"S", "H"}
                    and ("g" in first_form_parts or first.deprel in {"nmod", "appos", "obl"})
                )
            )
            if not first_ok:
                continue

            after = context.tokens[start_i + 2] if start_i + 2 < len(context.tokens) else None
            if after is not None and after.text in {'"', "“", "”"}:
                continue
            if after is not None and (
                lower_key(after) in ORG_CONTEXT_NOUNS
                or lower_key(after) in MULTI_TOKEN_ORG_HEADS
                or is_org_owner_head(after)
            ):
                continue

            span = context.span_from_indices("ORG", start_i, start_i + 2)
            if span.root_count > 2:
                continue

            linked = (
                first.head == head.syntax_id
                or head.head == first.syntax_id
                or first.deprel in {"flat", "nmod", "appos", "obl"}
                or head.deprel in {"flat", "nmod", "appos", "obl", "root", "nsubj", "obj"}
            )
            if not linked:
                continue

            proposals.append(MissingProposal(self.rule_id, "ORG", start_i, start_i + 2, 0.94))
        return proposals


class InsertGenitiveInstitutionOwnerRule(BaseMissingRule):
    rule_id = "lisa_genitiivne_asutus"
    description = "Lisab puuduva ORG omaniku enne rolli- või otsusesõna."

    def find(self, context, occupied):
        proposals = []
        for role_i in range(1, len(context.tokens)):
            role = context.tokens[role_i]
            if lower_key(role) not in ORG_CONTEXT_NOUNS:
                continue

            end_i = role_i
            last = context.tokens[end_i - 1]
            if not is_org_owner_head(last):
                continue

            start_i = end_i - 1
            while start_i > 0 and end_i - start_i < 5:
                previous = context.tokens[start_i - 1]
                current = context.tokens[start_i]
                if previous.text in {"-", "–"} or previous.lower == "ja":
                    start_i -= 1
                    continue
                if is_org_owner_head(previous) or previous.xpostag == "H":
                    start_i -= 1
                    continue
                if previous.morph_pos == "A" and current.morph_pos in {"S", "H"} and previous.form and "g" in previous.form.split():
                    start_i -= 1
                    continue
                break

            while start_i < end_i and not is_owner_chain_token(context.tokens[start_i]):
                start_i += 1
            while start_i < end_i and context.tokens[start_i].text in {"-", "–"}:
                start_i += 1
            while start_i < end_i and context.tokens[start_i].lower == "ja":
                start_i += 1

            token_range = set(range(start_i, end_i))
            if not token_range or token_range & occupied:
                continue
            if all(token.text in {"-", "ja"} for token in context.tokens[start_i:end_i]):
                continue
            if end_i - start_i == 1 and lower_key(context.tokens[start_i]) in GENERIC_SINGLE_ORG_OWNER_BLOCKLIST:
                continue

            span = context.span_from_indices("ORG", start_i, end_i)
            has_upper = any(token.text[:1].isupper() for token in span.tokens)
            has_proper_pos = any(token.xpostag == "H" for token in span.tokens)
            has_specific_lower_owner = len(span.tokens) > 1 and lower_key(span.tokens[0]) == "riigikogu"
            if not (has_upper or has_proper_pos or has_specific_lower_owner):
                continue
            if span.root_count > 3:
                continue
            if sum(is_org_owner_head(token) for token in span.tokens) < 1:
                continue

            proposals.append(MissingProposal(self.rule_id, "ORG", start_i, end_i, 0.98))
        return proposals
