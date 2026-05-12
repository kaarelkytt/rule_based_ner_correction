from .engine import MissingRuleEngine
from .loc_rules import *
from .org_rules import *
from .per_rules import *


def get_default_rules():
    return [
        InsertPersonRootChainRule(),
        InsertProperLocationHeadPhraseRule(),
        InsertCoreInstitutionMentionRule(),
        InsertGenitiveInstitutionOwnerRule(),
        InsertShortInstitutionHeadPhraseRule(),
        
        #InsertUppercasePersonHeadingRule(),
        #InsertShortHeadlineEntityRule(),
        #InsertSentenceStartReportingPersonRule(),
        #InsertSentenceStartPersonLabelRule(),
        #InsertSentenceStartInstitutionChainRule(),
        #InsertPersonConjChainRule(),
        #InsertPersonAttributionRule(),
        #InsertSentenceStartSimplePersonRule(),
        #InsertInstitutionChainRoleOwnerRule(),
        #InsertInstitutionRoleOwnerRule(),
        #InsertInstitutionConjRule(),
        #InsertLocativeProperLocationRule(),
    ]


def build_rule_list(custom_rules=None, include_default=False):
    rules = list(get_default_rules()) if include_default else []
    if custom_rules:
        rules.extend(custom_rules)
    return rules


def build_missing_engine(rules=None, morph_layer=None, syntax_layer="stanza_syntax"):
    if rules is None:
        rules = get_default_rules()
    return MissingRuleEngine(rules, morph_layer=morph_layer, syntax_layer=syntax_layer)
