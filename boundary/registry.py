from .engine import RuleEngine
from .org_rules import *
from .loc_rules import *
from .per_rules import *
from .relable_remove import *


def get_default_rules():
    return [
        ExpandRightLocationFacilityHeadRule(),
        ExpandRightPersonFlatRule(),
        SplitDisconnectedOrgTreeRule(),
        TrimQuotedNameRule(),
        ExpandRightGoverningBodyRule(),
        SplitDisconnectedPerTreeRule(),
        SplitDisconnectedLocTreeRule(),
        ExpandPersonRootChainRule(),
        ExpandLeftCompanyPrefixRule(),
        SplitCoordinatedLocationRule(),
        RemoveGenericUppercaseHeadingRule(),
        ExpandLocNsubjFlatRule(),
        
        #TrimLeftReportingPrefixRule(),
        #TrimLeftLegalFormRule(),
        #TrimRightRoleTailRule(),
        #TrimRightMeetingTailRule(),
        #TrimRightCorporateBodyTailRule(),
        #ExpandLeftHyphenJaOrgRule(),
        #ExpandLeftCompanyNameRule(),
        #ExpandRightCompanySuffixRule(),
        #SplitByCaseMismatchRule(),
        #TrimQuotedPersonRule(),
        #TrimLeftPersonTitleRule(),
        #RelabelSingleTokenNameToPersonRule(),
        #RelabelExpandNamePairToPersonRule(),
        #ExpandLeftPersonFlatPrefixRule(),
        #ExpandRightPersonSuffixRule(),
        #ExpandLocApposFlatHeadObjOblRule(),
        #ExpandLocNmodFlatHeadOblNsubjNmodRule(),
        #ExpandLocOblFlatHeadNotAclRule(),
        #ExpandPersonNsubjChainRule(),
        #ExpandPersonNmodChainRule(),
        #ExpandPersonConjChainRule(),
        #ExpandPersonApposChainRule(),
        #TrimRightLocationPublicationRule(),
        #TrimRightLocationCaseContextRule(),
    ]


def build_rule_list(custom_rules=None, include_default=False):
    rules = list(get_default_rules()) if include_default else []
    if custom_rules:
        rules.extend(custom_rules)
    return rules


def build_rule_engine(rules=None, morph_layer=None, syntax_layer="stanza_syntax"):
    if rules is None:
        rules = get_default_rules()
    return RuleEngine(rules, morph_layer=morph_layer, syntax_layer=syntax_layer)
