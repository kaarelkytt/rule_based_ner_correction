from .engine import RuleEngine
from .adjust_rules import *
from .split_rules import *
from .finalize_rules import *


def get_default_rules():
    return [
        SplitDisconnectedOrgTreeRule(),
        SplitDisconnectedPerTreeRule(),
        SplitDisconnectedLocTreeRule(),
        SplitCoordinatedLocationRule(),
        ExpandRightLocationFacilityHeadRule(),
        ExpandRightPersonFlatRule(),
        TrimQuotedOrgRule(),
        ExpandRightGoverningBodyRule(),
        ExpandPersonRootChainRule(),
        ExpandLeftCompanyPrefixRule(),
        ExpandLocNsubjFlatRule(),
        RemoveGenericUppercaseHeadingRule(),
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
