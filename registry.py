from .boundary.registry import get_default_rules as get_default_boundary_rules
from .missing.registry import get_default_rules as get_default_missing_rules


VALID_STAGES = ("split", "adjust", "finalize", "missing")


def get_rule_stage(rule):
    stage = getattr(rule, "stage", None)
    if stage not in VALID_STAGES:
        raise ValueError(
            f"Reeglil {rule.__class__.__name__} puudub korrektne stage. "
            f"Oodatud on üks neist: {', '.join(VALID_STAGES)}."
        )
    return stage


def split_rules_by_stage(rules):
    grouped = {stage: [] for stage in VALID_STAGES}
    for rule in rules:
        grouped[get_rule_stage(rule)].append(rule)
    return grouped


def get_default_rules():
    return [
        *get_default_boundary_rules(),
        *get_default_missing_rules(),
    ]


def build_rule_list(custom_rules=None, include_default=False):
    rules = list(get_default_rules()) if include_default else []
    if custom_rules:
        rules.extend(custom_rules)
    return rules
