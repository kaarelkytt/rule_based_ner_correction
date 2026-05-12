from .base import BaseMissingRule, MissingProposal
from .common import *

GEO_ACRONYMS = {"EU", "EL", "NATO", "USA", "ÜRO"}

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

ACRONYM_BLOCKLIST = {"PS", "VIP"}

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
    return is_institution_like(token) or key in MULTI_TOKEN_ORG_HEADS or any(key.endswith(suffix) for suffix in ORG_OWNER_HEAD_SUFFIXES)

def is_owner_chain_token(token):
    return token.morph_pos in {"S", "A", "H", "Y"} or token.lower == "ja" or token.text == "-"


class InsertSentenceStartInstitutionChainRule(BaseMissingRule):
    rule_id = "lisa_lausealguse_asutuseahel"
    description = "Lisab puuduva kaheosalise ORG märgendi lause alguses."

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 2):
            if i in occupied or i + 1 in occupied:
                continue
            first = context.tokens[i]
            second = context.tokens[i + 1]
            prev = context.tokens[i - 1] if i > 0 else None
            if not is_sentence_start(prev):
                continue
            if first.xpostag != "H" and not is_upper_name(first.text):
                continue
            if lower_key(second) not in MULTI_TOKEN_ORG_HEADS:
                continue
            after = context.tokens[i + 2]
            if lower_key(after) not in ORG_REPORTING_VERBS and lower_key(after) not in ORG_CONTEXT_NOUNS and after.text != ":":
                continue
            proposals.append(MissingProposal(self.rule_id, "ORG", i, i + 2, 0.94))
        return proposals


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
        for i, token in enumerate(context.tokens):
            if i in occupied:
                continue
            key = lower_key(token)
            if key not in self.LEMMAS:
                continue
            next_token = context.tokens[i + 1] if i + 1 < len(context.tokens) else None
            if next_token is not None and lower_key(next_token) in self.FOLLOWING_HEADS:
                continue
            form_parts = set((token.form or "").split())
            strong_context = token.text[:1].isupper() or bool(form_parts & self.CONTEXT_CASES) or token.deprel in self.CONTEXT_DEPRELS
            if not strong_context:
                continue
            proposals.append(MissingProposal(self.rule_id, "ORG", i, i + 1, 0.92))
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
    FIRST_KEY_BLOCKLIST = {"abiprokurör", "jäänuk", "jäänukid", "kohad", "lisaks", "moodustama", "mõistus", "näitleja", "politseinik", "prokurör", "vastuseks"}

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied or i + 1 in occupied:
                continue
            first = context.tokens[i]
            head = context.tokens[i + 1]
            prev = context.tokens[i - 1] if i > 0 else None
            if lower_key(head) not in self.HEADS or head.morph_pos not in {"S", "H"}:
                continue
            if prev is not None and prev.text in {'"', "“", "”"}:
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
            after = context.tokens[i + 2] if i + 2 < len(context.tokens) else None
            if after is not None and after.text in {'"', "“", "”"}:
                continue
            if after is not None and (lower_key(after) in ORG_CONTEXT_NOUNS or lower_key(after) in MULTI_TOKEN_ORG_HEADS or is_org_owner_head(after)):
                continue
            span = context.span_from_indices("ORG", i, i + 2)
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
            proposals.append(MissingProposal(self.rule_id, "ORG", i, i + 2, 0.94))
        return proposals


class InsertInstitutionChainRoleOwnerRule(BaseMissingRule):
    rule_id = "lisa_asutuseahel_rolli_ees"
    description = "Lisab puuduva lühikese ORG ahela enne rollisõna."

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 2):
            if i in occupied:
                continue
            start_token = context.tokens[i]
            if not (is_institution_like(start_token) or is_title_case_name(start_token.text) or is_upper_name(start_token.text)):
                continue
            for end_i in range(i + 2, min(i + 5, len(context.tokens)) + 1):
                token_range = set(range(i, end_i))
                if token_range & occupied:
                    break
                last = context.tokens[end_i - 1]
                after = context.tokens[end_i] if end_i < len(context.tokens) else None
                if lower_key(last) not in MULTI_TOKEN_ORG_HEADS:
                    continue
                if after is None or lower_key(after) not in ORG_CONTEXT_NOUNS:
                    continue
                span = context.span_from_indices("ORG", i, end_i)
                if span.root_count > 2:
                    continue
                proposals.append(MissingProposal(self.rule_id, "ORG", i, end_i, 0.90))
                break
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
                prev = context.tokens[start_i - 1]
                curr = context.tokens[start_i]
                if prev.text in {"-", "–"} or prev.lower == "ja":
                    start_i -= 1
                    continue
                if is_org_owner_head(prev) or prev.xpostag == "H":
                    start_i -= 1
                    continue
                if prev.morph_pos == "A" and curr.morph_pos in {"S", "H"} and prev.form and "g" in prev.form.split():
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


class InsertInstitutionRoleOwnerRule(BaseMissingRule):
    rule_id = "lisa_rolli_eelne_asutus"
    description = "Lisab puuduva ühesõnalise ORG märgendi rollisõna ette."

    SPECIFIC_SUFFIXES = ("amet", "ministeerium", "politsei", "keskus", "inspektsioon", "valitsus", "volikogu")

    def find(self, context, occupied):
        proposals = []
        for i in range(len(context.tokens) - 1):
            if i in occupied:
                continue
            token = context.tokens[i]
            if not is_institution_like(token):
                continue
            key = lower_key(token)
            if not (token.text[:1].isupper() or key in self.SPECIFIC_KEYS or any(key.endswith(suffix) for suffix in self.SPECIFIC_SUFFIXES)):
                continue
            next_token = context.tokens[i + 1] if i + 1 < len(context.tokens) else None
            if next_token is not None and lower_key(next_token) in ORG_CONTEXT_NOUNS:
                proposals.append(MissingProposal(self.rule_id, "ORG", i, i + 1, 0.95))
        return proposals


class InsertInstitutionConjRule(BaseMissingRule):
    rule_id = "lisa_koordineeritud_asutus"
    description = "Lisab puuduva ORG märgendi, kui asutusesarnane token on teise asutuse konjunkt."

    TOKEN_BLOCKLIST = {"kool", "kooli"}
    HEAD_BLOCKLIST = {"side"}

    def find(self, context, occupied):
        proposals = []
        for i, token in enumerate(context.tokens):
            if i in occupied:
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
            proposals.append(MissingProposal(self.rule_id, "ORG", i, i + 1, 0.94))
        return proposals
