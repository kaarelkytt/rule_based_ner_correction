from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import pandas as pd

from .boundary.base import BaseRule
from .boundary.engine import RuleEngine
from .context import TextContext
from .missing.base import BaseMissingRule
from .missing.engine import MissingRuleEngine

from tqdm import tqdm


def _get_token_by_syntax_id(tokens, syntax_id):
    for token in tokens:
        if token.syntax_id == syntax_id:
            return token
    return None


def _internal_root_tokens(span_view):
    if span_view is None:
        return []

    span_token_ids = {token.syntax_id for token in span_view.tokens}
    return [
        token for token in span_view.tokens
        if token.head not in span_token_ids
    ]


def _external_head_tokens(span_view, context):
    roots = _internal_root_tokens(span_view)
    if not roots:
        return []

    heads = []
    seen_indexes = set()
    for root in roots:
        head = _get_token_by_syntax_id(context.tokens, root.head)
        if head is None:
            continue
        if head.index in seen_indexes:
            continue
        seen_indexes.add(head.index)
        heads.append(head)
    return heads


def _external_head_features(span_view, context):
    roots = _internal_root_tokens(span_view)
    heads = _external_head_tokens(span_view, context)

    return {
        "internal_root_texts": [token.text for token in roots],
        "internal_root_deprels": [token.deprel for token in roots],
        "internal_root_morph_pos": [token.morph_pos for token in roots],
        "external_head_texts": [token.text for token in heads],
        "external_head_deprels": [token.deprel for token in heads],
        "external_head_morph_pos": [token.morph_pos for token in heads],
    }


def _span_patterns(span_view, context=None):
    if span_view is None:
        return {
            "start_i": None,
            "end_i": None,
            "lemmas": [],
            "forms": [],
            "morph_pos_pattern": [],
            "deprel_pattern": [],
            "upostag_pattern": [],
            "xpostag_pattern": [],
            "head_pattern": [],
            "root_count": None,
            "name_like_ratio": None,
            "first_token_text": None,
            "last_token_text": None,
            "first_lemma": None,
            "last_lemma": None,
            "first_form": None,
            "last_form": None,
            "first_morph_pos": None,
            "last_morph_pos": None,
            "first_deprel": None,
            "last_deprel": None,
            "internal_root_texts": [],
            "internal_root_deprels": [],
            "internal_root_morph_pos": [],
            "external_head_texts": [],
            "external_head_deprels": [],
            "external_head_morph_pos": [],
        }

    external = (
        _external_head_features(span_view, context)
        if context is not None
        else {
            "internal_root_texts": [],
            "internal_root_deprels": [],
            "internal_root_morph_pos": [],
            "external_head_texts": [],
            "external_head_deprels": [],
            "external_head_morph_pos": [],
        }
    )

    return {
        "start_i": span_view.start_i,
        "end_i": span_view.end_i,
        "lemmas": [token.lemma for token in span_view.tokens],
        "forms": [token.form for token in span_view.tokens],
        "morph_pos_pattern": [token.morph_pos for token in span_view.tokens],
        "deprel_pattern": [token.deprel for token in span_view.tokens],
        "upostag_pattern": [token.upostag for token in span_view.tokens],
        "xpostag_pattern": [token.xpostag for token in span_view.tokens],
        "head_pattern": [token.head for token in span_view.tokens],
        "root_count": span_view.root_count,
        "name_like_ratio": span_view.name_like_ratio,
        "first_token_text": span_view.tokens[0].text if span_view.tokens else None,
        "last_token_text": span_view.tokens[-1].text if span_view.tokens else None,
        "first_lemma": span_view.tokens[0].lemma if span_view.tokens else None,
        "last_lemma": span_view.tokens[-1].lemma if span_view.tokens else None,
        "first_form": span_view.tokens[0].form if span_view.tokens else None,
        "last_form": span_view.tokens[-1].form if span_view.tokens else None,
        "first_morph_pos": span_view.tokens[0].morph_pos if span_view.tokens else None,
        "last_morph_pos": span_view.tokens[-1].morph_pos if span_view.tokens else None,
        "first_deprel": span_view.tokens[0].deprel if span_view.tokens else None,
        "last_deprel": span_view.tokens[-1].deprel if span_view.tokens else None,
        **external,
    }

def _layer_spans(text, layer_name, context=None):
    spans = []
    if layer_name not in text.layers:
        return spans
    for index, span in enumerate(text[layer_name]):
        annotation = span.annotations[0]
        span_view = context.span_from_annotation(span) if context is not None else None
        patterns = _span_patterns(span_view, context=context)
        spans.append(
            {
                "id": index,
                "start": span.start,
                "end": span.end,
                "label": annotation["nertag"],
                "text": span.text,
                "start_i": patterns["start_i"],
                "end_i": patterns["end_i"],
                "lemmas": patterns["lemmas"],
                "forms": patterns["forms"],
                "morph_pos_pattern": patterns["morph_pos_pattern"],
                "deprel_pattern": patterns["deprel_pattern"],
                "upostag_pattern": patterns["upostag_pattern"],
                "xpostag_pattern": patterns["xpostag_pattern"],
                "head_pattern": patterns["head_pattern"],
                "root_count": patterns["root_count"],
                "name_like_ratio": patterns["name_like_ratio"],
                "first_token_text": patterns["first_token_text"],
                "last_token_text": patterns["last_token_text"],
                "first_lemma": patterns["first_lemma"],
                "last_lemma": patterns["last_lemma"],
                "first_form": patterns["first_form"],
                "last_form": patterns["last_form"],
                "first_morph_pos": patterns["first_morph_pos"],
                "last_morph_pos": patterns["last_morph_pos"],
                "first_deprel": patterns["first_deprel"],
                "last_deprel": patterns["last_deprel"],
                "internal_root_texts": patterns["internal_root_texts"],
                "internal_root_deprels": patterns["internal_root_deprels"],
                "internal_root_morph_pos": patterns["internal_root_morph_pos"],
                "external_head_texts": patterns["external_head_texts"],
                "external_head_deprels": patterns["external_head_deprels"],
                "external_head_morph_pos": patterns["external_head_morph_pos"],
            }
        )
    return spans


def _context_window_text(context, start_i, end_i, window=4):
    if start_i is None or end_i is None:
        return ""
    left = max(0, start_i - window)
    right = min(len(context.tokens), end_i + window)
    return " ".join(token.text for token in context.tokens[left:right])


def _component_window_text(context, spans):
    indexed = [
        span for span in spans
        if span.get("start_i") is not None and span.get("end_i") is not None
    ]
    if not indexed:
        return ""
    return _context_window_text(
        context,
        min(span["start_i"] for span in indexed),
        max(span["end_i"] for span in indexed),
    )


def _overlap(first, second):
    return max(0, min(first["end"], second["end"]) - max(first["start"], second["start"]))


def _change_type(base_spans, new_spans):
    if len(base_spans) == 1 and len(new_spans) == 1:
        base = base_spans[0]
        new = new_spans[0]
        same_bounds = base["start"] == new["start"] and base["end"] == new["end"]
        same_label = base["label"] == new["label"]
        if same_bounds and same_label:
            return "UNCHANGED"
        if same_bounds and not same_label:
            return "RELABELED"
        if base["start"] >= new["start"] and base["end"] <= new["end"]:
            return "EXPANDED"
        if new["start"] >= base["start"] and new["end"] <= base["end"]:
            return "TRIMMED"
        return "SHIFTED"
    if len(base_spans) == 1 and len(new_spans) > 1:
        return "SPLIT"
    if len(base_spans) > 1 and len(new_spans) == 1:
        return "MERGED"
    return "COMPLEX"


def collect_layer_changes(
    text,
    base_layer,
    new_layer,
    text_id=None,
    include_unchanged=False,
    morph_layer="morph_analysis",
    syntax_layer="stanza_syntax",
):
    context = TextContext(text, morph_layer=morph_layer, syntax_layer=syntax_layer)
    base_spans = _layer_spans(text, base_layer, context=context)
    new_spans = _layer_spans(text, new_layer, context=context)

    base_to_new = {span["id"]: set() for span in base_spans}
    new_to_base = {span["id"]: set() for span in new_spans}

    for base in base_spans:
        for new in new_spans:
            if _overlap(base, new) > 0:
                base_to_new[base["id"]].add(new["id"])
                new_to_base[new["id"]].add(base["id"])

    rows = []
    seen_base = set()
    seen_new = set()

    for base in base_spans:
        if base["id"] in seen_base:
            continue

        linked_new = base_to_new[base["id"]]
        if not linked_new:
            seen_base.add(base["id"])
            rows.append(
                {
                    "text_id": text_id,
                    "change_type": "REMOVED",
                    "base_count": 1,
                    "new_count": 0,
                    "base_texts": [base["text"]],
                    "new_texts": [],
                    "base_labels": [base["label"]],
                    "new_labels": [],
                    "base_lemmas": [base["lemmas"]],
                    "new_lemmas": [],
                    "base_forms": [base["forms"]],
                    "new_forms": [],
                    "base_morph_pos_patterns": [base["morph_pos_pattern"]],
                    "new_morph_pos_patterns": [],
                    "base_deprel_patterns": [base["deprel_pattern"]],
                    "new_deprel_patterns": [],
                    "base_upostag_patterns": [base["upostag_pattern"]],
                    "new_upostag_patterns": [],
                    "base_xpostag_patterns": [base["xpostag_pattern"]],
                    "new_xpostag_patterns": [],
                    "base_head_patterns": [base["head_pattern"]],
                    "new_head_patterns": [],
                    "base_root_counts": [base["root_count"]],
                    "new_root_counts": [],
                    "base_name_like_ratios": [base["name_like_ratio"]],
                    "new_name_like_ratios": [],
                    "base_first_token_texts": [base["first_token_text"]],
                    "new_first_token_texts": [],
                    "base_last_token_texts": [base["last_token_text"]],
                    "new_last_token_texts": [],
                    "base_first_forms": [base["first_form"]],
                    "new_first_forms": [],
                    "base_last_forms": [base["last_form"]],
                    "new_last_forms": [],
                    "base_first_deprels": [base["first_deprel"]],
                    "new_first_deprels": [],
                    "base_last_deprels": [base["last_deprel"]],
                    "new_last_deprels": [],

                    "base_internal_root_texts": [base["internal_root_texts"]],
                    "new_internal_root_texts": [],
                    "base_internal_root_deprels": [base["internal_root_deprels"]],
                    "new_internal_root_deprels": [],
                    "base_internal_root_morph_pos": [base["internal_root_morph_pos"]],
                    "new_internal_root_morph_pos": [],

                    "base_external_head_texts": [base["external_head_texts"]],
                    "new_external_head_texts": [],
                    "base_external_head_deprels": [base["external_head_deprels"]],
                    "new_external_head_deprels": [],
                    "base_external_head_morph_pos": [base["external_head_morph_pos"]],
                    "new_external_head_morph_pos": [],
                    "anchor_window_text": _context_window_text(context, base["start_i"], base["end_i"]),
                    "text": text.text,
                }
            )
            continue

        component_base_ids = set()
        component_new_ids = set()
        stack = [("base", base["id"])]
        while stack:
            node_type, node_id = stack.pop()
            if node_type == "base":
                if node_id in component_base_ids:
                    continue
                component_base_ids.add(node_id)
                for new_id in base_to_new[node_id]:
                    stack.append(("new", new_id))
            else:
                if node_id in component_new_ids:
                    continue
                component_new_ids.add(node_id)
                for base_id in new_to_base[node_id]:
                    stack.append(("base", base_id))

        component_base = [item for item in base_spans if item["id"] in component_base_ids]
        component_new = [item for item in new_spans if item["id"] in component_new_ids]
        seen_base.update(component_base_ids)
        seen_new.update(component_new_ids)

        change_type = _change_type(component_base, component_new)
        if change_type == "UNCHANGED" and not include_unchanged:
            continue

        rows.append(
            {
                "text_id": text_id,
                "change_type": change_type,
                "base_count": len(component_base),
                "new_count": len(component_new),
                "base_texts": [span["text"] for span in component_base],
                "new_texts": [span["text"] for span in component_new],
                "base_labels": [span["label"] for span in component_base],
                "new_labels": [span["label"] for span in component_new],
                "base_lemmas": [span["lemmas"] for span in component_base],
                "new_lemmas": [span["lemmas"] for span in component_new],
                "base_forms": [span["forms"] for span in component_base],
                "new_forms": [span["forms"] for span in component_new],
                "base_morph_pos_patterns": [span["morph_pos_pattern"] for span in component_base],
                "new_morph_pos_patterns": [span["morph_pos_pattern"] for span in component_new],
                "base_deprel_patterns": [span["deprel_pattern"] for span in component_base],
                "new_deprel_patterns": [span["deprel_pattern"] for span in component_new],
                "base_upostag_patterns": [span["upostag_pattern"] for span in component_base],
                "new_upostag_patterns": [span["upostag_pattern"] for span in component_new],
                "base_xpostag_patterns": [span["xpostag_pattern"] for span in component_base],
                "new_xpostag_patterns": [span["xpostag_pattern"] for span in component_new],
                "base_head_patterns": [span["head_pattern"] for span in component_base],
                "new_head_patterns": [span["head_pattern"] for span in component_new],
                "base_root_counts": [span["root_count"] for span in component_base],
                "new_root_counts": [span["root_count"] for span in component_new],
                "base_name_like_ratios": [span["name_like_ratio"] for span in component_base],
                "new_name_like_ratios": [span["name_like_ratio"] for span in component_new],
                "base_first_token_texts": [span["first_token_text"] for span in component_base],
                "new_first_token_texts": [span["first_token_text"] for span in component_new],
                "base_last_token_texts": [span["last_token_text"] for span in component_base],
                "new_last_token_texts": [span["last_token_text"] for span in component_new],
                "base_first_forms": [span["first_form"] for span in component_base],
                "new_first_forms": [span["first_form"] for span in component_new],
                "base_last_forms": [span["last_form"] for span in component_base],
                "new_last_forms": [span["last_form"] for span in component_new],
                "base_first_deprels": [span["first_deprel"] for span in component_base],
                "new_first_deprels": [span["first_deprel"] for span in component_new],
                "base_last_deprels": [span["last_deprel"] for span in component_base],
                "new_last_deprels": [span["last_deprel"] for span in component_new],

                "base_internal_root_texts": [span["internal_root_texts"] for span in component_base],
                "new_internal_root_texts": [span["internal_root_texts"] for span in component_new],
                "base_internal_root_deprels": [span["internal_root_deprels"] for span in component_base],
                "new_internal_root_deprels": [span["internal_root_deprels"] for span in component_new],
                "base_internal_root_morph_pos": [span["internal_root_morph_pos"] for span in component_base],
                "new_internal_root_morph_pos": [span["internal_root_morph_pos"] for span in component_new],

                "base_external_head_texts": [span["external_head_texts"] for span in component_base],
                "new_external_head_texts": [span["external_head_texts"] for span in component_new],
                "base_external_head_deprels": [span["external_head_deprels"] for span in component_base],
                "new_external_head_deprels": [span["external_head_deprels"] for span in component_new],
                "base_external_head_morph_pos": [span["external_head_morph_pos"] for span in component_base],
                "new_external_head_morph_pos": [span["external_head_morph_pos"] for span in component_new],
                "anchor_window_text": _component_window_text(context, component_base + component_new),
                "text": text.text,
            }
        )

    for new in new_spans:
        if new["id"] in seen_new:
            continue
        rows.append(
            {
                "text_id": text_id,
                "change_type": "ADDED",
                "base_count": 0,
                "new_count": 1,
                "base_texts": [],
                "new_texts": [new["text"]],
                "base_labels": [],
                "new_labels": [new["label"]],
                "base_lemmas": [],
                "new_lemmas": [new["lemmas"]],
                "base_forms": [],
                "new_forms": [new["forms"]],
                "base_morph_pos_patterns": [],
                "new_morph_pos_patterns": [new["morph_pos_pattern"]],
                "base_deprel_patterns": [],
                "new_deprel_patterns": [new["deprel_pattern"]],
                "base_upostag_patterns": [],
                "new_upostag_patterns": [new["upostag_pattern"]],
                "base_xpostag_patterns": [],
                "new_xpostag_patterns": [new["xpostag_pattern"]],
                "base_head_patterns": [],
                "new_head_patterns": [new["head_pattern"]],
                "base_root_counts": [],
                "new_root_counts": [new["root_count"]],
                "base_name_like_ratios": [],
                "new_name_like_ratios": [new["name_like_ratio"]],
                "base_first_token_texts": [],
                "new_first_token_texts": [new["first_token_text"]],
                "base_last_token_texts": [],
                "new_last_token_texts": [new["last_token_text"]],
                "base_first_forms": [],
                "new_first_forms": [new["first_form"]],
                "base_last_forms": [],
                "new_last_forms": [new["last_form"]],
                "base_first_deprels": [],
                "new_first_deprels": [new["first_deprel"]],
                "base_last_deprels": [],
                "new_last_deprels": [new["last_deprel"]],

                "base_internal_root_texts": [],
                "new_internal_root_texts": [new["internal_root_texts"]],
                "base_internal_root_deprels": [],
                "new_internal_root_deprels": [new["internal_root_deprels"]],
                "base_internal_root_morph_pos": [],
                "new_internal_root_morph_pos": [new["internal_root_morph_pos"]],

                "base_external_head_texts": [],
                "new_external_head_texts": [new["external_head_texts"]],
                "base_external_head_deprels": [],
                "new_external_head_deprels": [new["external_head_deprels"]],
                "base_external_head_morph_pos": [],
                "new_external_head_morph_pos": [new["external_head_morph_pos"]],
                "anchor_window_text": _context_window_text(context, new["start_i"], new["end_i"]),
                "text": text.text,
            }
        )

    return rows


def _iter_items(items):
    for index, item in enumerate(items):
        if isinstance(item, tuple) and len(item) == 2:
            yield item[0], item[1]
        else:
            yield index, item


def _detect_stage(rule):
    if isinstance(rule, BaseRule):
        return "boundary"
    if isinstance(rule, BaseMissingRule):
        return "missing"
    raise TypeError(f"Unknown rule type: {type(rule)!r}")


def apply_single_rule(
    text,
    rule,
    base_layer,
    output_layer,
    morph_layer,
    syntax_layer,
):
    text = deepcopy(text)
    stage = _detect_stage(rule)

    if stage == "boundary":
        engine = RuleEngine([rule], morph_layer=morph_layer, syntax_layer=syntax_layer)
        final_spans, proposal_rows = engine.propose_for_text(text, input_layer=base_layer)
        engine.attach_output_layer(text, final_spans, output_layer=output_layer)
        return text, proposal_rows

    engine = MissingRuleEngine([rule], morph_layer=morph_layer, syntax_layer=syntax_layer)
    chosen, proposal_rows = engine.propose_for_text(text, input_layer=base_layer)
    engine.attach_output_layer(text, input_layer=base_layer, chosen=chosen, output_layer=output_layer)
    return text, proposal_rows


def _normalize_list_cell(value):
    if isinstance(value, list):
        return tuple(_normalize_list_cell(item) if isinstance(item, list) else _normalize_scalar_cell(item) for item in value)
    if pd.isna(value):
        return tuple()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return tuple()
        if stripped.startswith("[") and stripped.endswith("]"):
            parsed = ast.literal_eval(stripped)
            if isinstance(parsed, list):
                return _normalize_list_cell(parsed)
        return (stripped,)
    return (str(value),)


def _normalize_scalar_cell(value):
    if pd.isna(value):
        return ""
    return str(value)


def _normalize_change_row(row):
    return {
        "text_id": _normalize_scalar_cell(row.get("text_id")),
        "change_type": _normalize_scalar_cell(row.get("change_type")),
        "base_count": _normalize_scalar_cell(row.get("base_count")),
        "new_count": _normalize_scalar_cell(row.get("new_count")),
        "base_texts": _normalize_list_cell(row.get("base_texts")),
        "new_texts": _normalize_list_cell(row.get("new_texts")),
        "base_labels": _normalize_list_cell(row.get("base_labels")),
        "new_labels": _normalize_list_cell(row.get("new_labels")),
        "base_lemmas": _normalize_list_cell(row.get("base_lemmas")),
        "new_lemmas": _normalize_list_cell(row.get("new_lemmas")),
        "base_forms": _normalize_list_cell(row.get("base_forms")),
        "new_forms": _normalize_list_cell(row.get("new_forms")),
        "base_morph_pos_patterns": _normalize_list_cell(row.get("base_morph_pos_patterns")),
        "new_morph_pos_patterns": _normalize_list_cell(row.get("new_morph_pos_patterns")),
        "base_deprel_patterns": _normalize_list_cell(row.get("base_deprel_patterns")),
        "new_deprel_patterns": _normalize_list_cell(row.get("new_deprel_patterns")),
        "base_upostag_patterns": _normalize_list_cell(row.get("base_upostag_patterns")),
        "new_upostag_patterns": _normalize_list_cell(row.get("new_upostag_patterns")),
        "base_xpostag_patterns": _normalize_list_cell(row.get("base_xpostag_patterns")),
        "new_xpostag_patterns": _normalize_list_cell(row.get("new_xpostag_patterns")),
        "base_head_patterns": _normalize_list_cell(row.get("base_head_patterns")),
        "new_head_patterns": _normalize_list_cell(row.get("new_head_patterns")),
        "base_root_counts": _normalize_list_cell(row.get("base_root_counts")),
        "new_root_counts": _normalize_list_cell(row.get("new_root_counts")),
        "base_name_like_ratios": _normalize_list_cell(row.get("base_name_like_ratios")),
        "new_name_like_ratios": _normalize_list_cell(row.get("new_name_like_ratios")),
        "base_first_token_texts": _normalize_list_cell(row.get("base_first_token_texts")),
        "new_first_token_texts": _normalize_list_cell(row.get("new_first_token_texts")),
        "base_last_token_texts": _normalize_list_cell(row.get("base_last_token_texts")),
        "new_last_token_texts": _normalize_list_cell(row.get("new_last_token_texts")),
        "base_first_forms": _normalize_list_cell(row.get("base_first_forms")),
        "new_first_forms": _normalize_list_cell(row.get("new_first_forms")),
        "base_last_forms": _normalize_list_cell(row.get("base_last_forms")),
        "new_last_forms": _normalize_list_cell(row.get("new_last_forms")),
        "base_first_deprels": _normalize_list_cell(row.get("base_first_deprels")),
        "new_first_deprels": _normalize_list_cell(row.get("new_first_deprels")),
        "base_last_deprels": _normalize_list_cell(row.get("base_last_deprels")),
        "new_last_deprels": _normalize_list_cell(row.get("new_last_deprels")),
        "base_internal_root_texts": _normalize_list_cell(row.get("base_internal_root_texts")),
        "new_internal_root_texts": _normalize_list_cell(row.get("new_internal_root_texts")),
        "base_internal_root_deprels": _normalize_list_cell(row.get("base_internal_root_deprels")),
        "new_internal_root_deprels": _normalize_list_cell(row.get("new_internal_root_deprels")),
        "base_internal_root_morph_pos": _normalize_list_cell(row.get("base_internal_root_morph_pos")),
        "new_internal_root_morph_pos": _normalize_list_cell(row.get("new_internal_root_morph_pos")),
        "base_external_head_texts": _normalize_list_cell(row.get("base_external_head_texts")),
        "new_external_head_texts": _normalize_list_cell(row.get("new_external_head_texts")),
        "base_external_head_deprels": _normalize_list_cell(row.get("base_external_head_deprels")),
        "new_external_head_deprels": _normalize_list_cell(row.get("new_external_head_deprels")),
        "base_external_head_morph_pos": _normalize_list_cell(row.get("base_external_head_morph_pos")),
        "new_external_head_morph_pos": _normalize_list_cell(row.get("new_external_head_morph_pos")),
        "anchor_window_text": _normalize_scalar_cell(row.get("anchor_window_text")),
        "text": _normalize_scalar_cell(row.get("text")),
    }


def _change_anchor(row):
    if row["base_texts"] or row["base_labels"]:
        return ("base", row["text_id"], row["base_texts"], row["base_labels"])
    return ("new", row["text_id"], row["new_texts"], row["new_labels"])


def _change_signature(row):
    return (
        row["change_type"],
        row["base_count"],
        row["new_count"],
        row["base_texts"],
        row["new_texts"],
        row["base_labels"],
        row["new_labels"],
        row["base_lemmas"],
        row["new_lemmas"],
        row["base_forms"],
        row["new_forms"],
        row["base_morph_pos_patterns"],
        row["new_morph_pos_patterns"],
        row["base_deprel_patterns"],
        row["new_deprel_patterns"],
        row["base_upostag_patterns"],
        row["new_upostag_patterns"],
        row["base_xpostag_patterns"],
        row["new_xpostag_patterns"],
        row["base_head_patterns"],
        row["new_head_patterns"],
        row["base_root_counts"],
        row["new_root_counts"],
        row["base_name_like_ratios"],
        row["new_name_like_ratios"],
        row["base_first_token_texts"],
        row["new_first_token_texts"],
        row["base_last_token_texts"],
        row["new_last_token_texts"],
        row["base_first_forms"],
        row["new_first_forms"],
        row["base_last_forms"],
        row["new_last_forms"],
        row["base_first_deprels"],
        row["new_first_deprels"],
        row["base_last_deprels"],
        row["new_last_deprels"],
        row["base_internal_root_texts"],
        row["new_internal_root_texts"],
        row["base_internal_root_deprels"],
        row["new_internal_root_deprels"],
        row["base_internal_root_morph_pos"],
        row["new_internal_root_morph_pos"],
        row["base_external_head_texts"],
        row["new_external_head_texts"],
        row["base_external_head_deprels"],
        row["new_external_head_deprels"],
        row["base_external_head_morph_pos"],
        row["new_external_head_morph_pos"],
        row["anchor_window_text"],
        row["text"],
    )


def _row_sort_key(record):
    row = record["normalized"]
    return (
        row["text_id"],
        row["change_type"],
        row["base_texts"],
        row["new_texts"],
        row["base_labels"],
        row["new_labels"],
        row["base_morph_pos_patterns"],
        row["new_morph_pos_patterns"],
        row["base_internal_root_texts"],
        row["new_internal_root_texts"],
        row["base_external_head_texts"],
        row["new_external_head_texts"],
    )


def _display_row(row):
    base_count = int(row["base_count"]) if row["base_count"].isdigit() else row["base_count"]
    new_count = int(row["new_count"]) if row["new_count"].isdigit() else row["new_count"]
    return {
        "text_id": row["text_id"],
        "change_type": row["change_type"],
        "base_count": base_count,
        "new_count": new_count,
        "base_texts": list(row["base_texts"]),
        "new_texts": list(row["new_texts"]),
        "base_labels": list(row["base_labels"]),
        "new_labels": list(row["new_labels"]),
        "base_lemmas": list(row["base_lemmas"]),
        "new_lemmas": list(row["new_lemmas"]),
        "base_forms": list(row["base_forms"]),
        "new_forms": list(row["new_forms"]),
        "base_morph_pos_patterns": list(row["base_morph_pos_patterns"]),
        "new_morph_pos_patterns": list(row["new_morph_pos_patterns"]),
        "base_deprel_patterns": list(row["base_deprel_patterns"]),
        "new_deprel_patterns": list(row["new_deprel_patterns"]),
        "base_upostag_patterns": list(row["base_upostag_patterns"]),
        "new_upostag_patterns": list(row["new_upostag_patterns"]),
        "base_xpostag_patterns": list(row["base_xpostag_patterns"]),
        "new_xpostag_patterns": list(row["new_xpostag_patterns"]),
        "base_head_patterns": list(row["base_head_patterns"]),
        "new_head_patterns": list(row["new_head_patterns"]),
        "base_root_counts": list(row["base_root_counts"]),
        "new_root_counts": list(row["new_root_counts"]),
        "base_name_like_ratios": list(row["base_name_like_ratios"]),
        "new_name_like_ratios": list(row["new_name_like_ratios"]),
        "base_first_token_texts": list(row["base_first_token_texts"]),
        "new_first_token_texts": list(row["new_first_token_texts"]),
        "base_last_token_texts": list(row["base_last_token_texts"]),
        "new_last_token_texts": list(row["new_last_token_texts"]),
        "base_first_forms": list(row["base_first_forms"]),
        "new_first_forms": list(row["new_first_forms"]),
        "base_last_forms": list(row["base_last_forms"]),
        "new_last_forms": list(row["new_last_forms"]),
        "base_first_deprels": list(row["base_first_deprels"]),
        "new_first_deprels": list(row["new_first_deprels"]),
        "base_last_deprels": list(row["base_last_deprels"]),
        "new_last_deprels": list(row["new_last_deprels"]),
        "base_internal_root_texts": list(row["base_internal_root_texts"]),
        "new_internal_root_texts": list(row["new_internal_root_texts"]),
        "base_internal_root_deprels": list(row["base_internal_root_deprels"]),
        "new_internal_root_deprels": list(row["new_internal_root_deprels"]),
        "base_internal_root_morph_pos": list(row["base_internal_root_morph_pos"]),
        "new_internal_root_morph_pos": list(row["new_internal_root_morph_pos"]),
        "base_external_head_texts": list(row["base_external_head_texts"]),
        "new_external_head_texts": list(row["new_external_head_texts"]),
        "base_external_head_deprels": list(row["base_external_head_deprels"]),
        "new_external_head_deprels": list(row["new_external_head_deprels"]),
        "base_external_head_morph_pos": list(row["base_external_head_morph_pos"]),
        "new_external_head_morph_pos": list(row["new_external_head_morph_pos"]),
        "anchor_window_text": row["anchor_window_text"],
        "text": row["text"],
    }


def _collect_unmatched(records, matched_indexes):
    return [record for index, record in enumerate(records) if index not in matched_indexes]


def _build_compare_summary(added_df, removed_df, changed_df):
    return pd.DataFrame(
        [
            {"category": "added", "count": int(len(added_df))},
            {"category": "removed", "count": int(len(removed_df))},
            {"category": "changed", "count": int(len(changed_df))},
        ]
    )


def compare_change_rows(old_path, new_path):
    old_df = pd.read_csv(old_path)
    new_df = pd.read_csv(new_path)

    old_records = [{"normalized": _normalize_change_row(row)} for _, row in old_df.iterrows()]
    new_records = [{"normalized": _normalize_change_row(row)} for _, row in new_df.iterrows()]

    old_by_signature = defaultdict(list)
    new_by_signature = defaultdict(list)

    for index, record in enumerate(old_records):
        old_by_signature[_change_signature(record["normalized"])].append(index)
    for index, record in enumerate(new_records):
        new_by_signature[_change_signature(record["normalized"])].append(index)

    matched_old = set()
    matched_new = set()

    for signature, old_indexes in old_by_signature.items():
        new_indexes = new_by_signature.get(signature, [])
        keep_count = min(len(old_indexes), len(new_indexes))
        matched_old.update(old_indexes[:keep_count])
        matched_new.update(new_indexes[:keep_count])

    old_unmatched = _collect_unmatched(old_records, matched_old)
    new_unmatched = _collect_unmatched(new_records, matched_new)

    old_by_anchor = defaultdict(list)
    new_by_anchor = defaultdict(list)

    for record in old_unmatched:
        old_by_anchor[_change_anchor(record["normalized"])].append(record)
    for record in new_unmatched:
        new_by_anchor[_change_anchor(record["normalized"])].append(record)

    changed_rows = []
    added_rows = []
    removed_rows = []

    shared_anchors = set(old_by_anchor) & set(new_by_anchor)
    for anchor in shared_anchors:
        old_group = sorted(old_by_anchor[anchor], key=_row_sort_key)
        new_group = sorted(new_by_anchor[anchor], key=_row_sort_key)
        pair_count = min(len(old_group), len(new_group))

        for index in range(pair_count):
            old_row = _display_row(old_group[index]["normalized"])
            new_row = _display_row(new_group[index]["normalized"])
            changed_rows.append(
                {
                    "text_id": new_row["text_id"] or old_row["text_id"],
                    "text": new_row["text"] or old_row["text"],
                    "old_change_type": old_row["change_type"],
                    "new_change_type": new_row["change_type"],
                    "old_base_texts": old_row["base_texts"],
                    "new_base_texts": new_row["base_texts"],
                    "old_new_texts": old_row["new_texts"],
                    "new_new_texts": new_row["new_texts"],
                    "old_base_labels": old_row["base_labels"],
                    "new_base_labels": new_row["base_labels"],
                    "old_new_labels": old_row["new_labels"],
                    "new_new_labels": new_row["new_labels"],
                    "old_base_lemmas": old_row["base_lemmas"],
                    "new_base_lemmas": new_row["base_lemmas"],
                    "old_new_lemmas": old_row["new_lemmas"],
                    "new_new_lemmas": new_row["new_lemmas"],
                    "old_base_morph_pos_patterns": old_row["base_morph_pos_patterns"],
                    "new_base_morph_pos_patterns": new_row["base_morph_pos_patterns"],
                    "old_new_morph_pos_patterns": old_row["new_morph_pos_patterns"],
                    "new_new_morph_pos_patterns": new_row["new_morph_pos_patterns"],
                    "old_base_deprel_patterns": old_row["base_deprel_patterns"],
                    "new_base_deprel_patterns": new_row["base_deprel_patterns"],
                    "old_new_deprel_patterns": old_row["new_deprel_patterns"],
                    "new_new_deprel_patterns": new_row["new_deprel_patterns"],
                    "old_base_internal_root_texts": old_row["base_internal_root_texts"],
                    "new_base_internal_root_texts": new_row["base_internal_root_texts"],
                    "old_new_internal_root_texts": old_row["new_internal_root_texts"],
                    "new_new_internal_root_texts": new_row["new_internal_root_texts"],
                    "old_base_internal_root_deprels": old_row["base_internal_root_deprels"],
                    "new_base_internal_root_deprels": new_row["base_internal_root_deprels"],
                    "old_new_internal_root_deprels": old_row["new_internal_root_deprels"],
                    "new_new_internal_root_deprels": new_row["new_internal_root_deprels"],
                    "old_base_internal_root_morph_pos": old_row["base_internal_root_morph_pos"],
                    "new_base_internal_root_morph_pos": new_row["base_internal_root_morph_pos"],
                    "old_new_internal_root_morph_pos": old_row["new_internal_root_morph_pos"],
                    "new_new_internal_root_morph_pos": new_row["new_internal_root_morph_pos"],
                    "old_base_external_head_texts": old_row["base_external_head_texts"],
                    "new_base_external_head_texts": new_row["base_external_head_texts"],
                    "old_new_external_head_texts": old_row["new_external_head_texts"],
                    "new_new_external_head_texts": new_row["new_external_head_texts"],
                    "old_base_external_head_deprels": old_row["base_external_head_deprels"],
                    "new_base_external_head_deprels": new_row["base_external_head_deprels"],
                    "old_new_external_head_deprels": old_row["new_external_head_deprels"],
                    "new_new_external_head_deprels": new_row["new_external_head_deprels"],
                    "old_base_external_head_morph_pos": old_row["base_external_head_morph_pos"],
                    "new_base_external_head_morph_pos": new_row["base_external_head_morph_pos"],
                    "old_new_external_head_morph_pos": old_row["new_external_head_morph_pos"],
                    "new_new_external_head_morph_pos": new_row["new_external_head_morph_pos"],
                }
            )

        for record in old_group[pair_count:]:
            removed_rows.append(_display_row(record["normalized"]))
        for record in new_group[pair_count:]:
            added_rows.append(_display_row(record["normalized"]))

    for anchor, records in old_by_anchor.items():
        if anchor in shared_anchors:
            continue
        for record in records:
            removed_rows.append(_display_row(record["normalized"]))

    for anchor, records in new_by_anchor.items():
        if anchor in shared_anchors:
            continue
        for record in records:
            added_rows.append(_display_row(record["normalized"]))

    added_df = pd.DataFrame(added_rows)
    removed_df = pd.DataFrame(removed_rows)
    changed_df = pd.DataFrame(changed_rows)
    summary_df = _build_compare_summary(added_df, removed_df, changed_df)

    return {
        "summary": summary_df,
        "added": added_df,
        "removed": removed_df,
        "changed": changed_df,
    }


def run_rule_analysis_on_items(
    items,
    rule,
    output_dir,
    base_layer="v171_named_entities",
    output_layer="v171_named_entities_single_rule",
    morph_layer="morph_analysis",
    syntax_layer="v172_stanza_syntax",
):
    stage = _detect_stage(rule)
    items = list(_iter_items(items))

    change_rows = []
    proposal_rows = []
    corrected_items = []

    for text_id, text in tqdm(items, total=len(items)):
        corrected, proposals = apply_single_rule(
            text=text,
            rule=rule,
            base_layer=base_layer,
            output_layer=output_layer,
            morph_layer=morph_layer,
            syntax_layer=syntax_layer,
        )
        corrected_items.append((text_id, corrected))

        for row in proposals:
            row["text_id"] = text_id
            if stage == "boundary":
                row["source_rule"] = row.get("chosen_rule")
            else:
                row["source_rule"] = row.get("rule_id")
            proposal_rows.append(row)

        rows = collect_layer_changes(
            corrected,
            base_layer=base_layer,
            new_layer=output_layer,
            text_id=text_id,
            include_unchanged=False,
            morph_layer=morph_layer,
            syntax_layer=syntax_layer,
        )
        for row in rows:
            row["source_stage"] = stage
            row["source_rule"] = rule.rule_id
        change_rows.extend(rows)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    change_df = pd.DataFrame(change_rows)
    proposal_df = pd.DataFrame(proposal_rows)

    change_path = output_dir / f"{rule.rule_id}_change_rows.csv"
    change_df.to_csv(change_path, index=False)

    return {
        "rule_id": rule.rule_id,
        "change_rows": change_df,
        "proposal_rows": proposal_df,
        "corrected_items": corrected_items,
        "paths": {"change_rows": change_path},
    }
