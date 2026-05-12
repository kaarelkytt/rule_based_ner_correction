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
            "morph_pos_pattern": [],
            "deprel_pattern": [],
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
        "morph_pos_pattern": [token.morph_pos for token in span_view.tokens],
        "deprel_pattern": [token.deprel for token in span_view.tokens],
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
                "morph_pos_pattern": patterns["morph_pos_pattern"],
                "deprel_pattern": patterns["deprel_pattern"],
                "internal_root_texts": patterns["internal_root_texts"],
                "internal_root_deprels": patterns["internal_root_deprels"],
                "internal_root_morph_pos": patterns["internal_root_morph_pos"],
                "external_head_texts": patterns["external_head_texts"],
                "external_head_deprels": patterns["external_head_deprels"],
                "external_head_morph_pos": patterns["external_head_morph_pos"],
            }
        )
    return spans


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
                    "base_morph_pos_patterns": [base["morph_pos_pattern"]],
                    "new_morph_pos_patterns": [],
                    "base_deprel_patterns": [base["deprel_pattern"]],
                    "new_deprel_patterns": [],

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
                "base_morph_pos_patterns": [span["morph_pos_pattern"] for span in component_base],
                "new_morph_pos_patterns": [span["morph_pos_pattern"] for span in component_new],
                "base_deprel_patterns": [span["deprel_pattern"] for span in component_base],
                "new_deprel_patterns": [span["deprel_pattern"] for span in component_new],

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
                "base_morph_pos_patterns": [],
                "new_morph_pos_patterns": [new["morph_pos_pattern"]],
                "base_deprel_patterns": [],
                "new_deprel_patterns": [new["deprel_pattern"]],

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

                "text": text.text,
            }
        )

    return rows


def summarize_change_rows(rows):
    counts = {}
    for row in rows:
        key = row["change_type"]
        counts[key] = counts.get(key, 0) + 1
    return counts


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
        return text, proposal_rows, final_spans

    engine = MissingRuleEngine([rule], morph_layer=morph_layer, syntax_layer=syntax_layer)
    chosen, proposal_rows = engine.propose_for_text(text, input_layer=base_layer)
    engine.attach_output_layer(text, input_layer=base_layer, chosen=chosen, output_layer=output_layer)
    return text, proposal_rows, chosen


def _build_summary(change_df, proposal_df):
    rows = []
    if not change_df.empty:
        counts = change_df["change_type"].value_counts()
        for name, count in counts.items():
            rows.append({"kind": "change_type", "name": name, "count": int(count)})
    if not proposal_df.empty:
        if "label" in proposal_df.columns:
            counts = proposal_df["label"].value_counts()
            for name, count in counts.items():
                rows.append({"kind": "label", "name": name, "count": int(count)})
        text_column = "text" if "text" in proposal_df.columns else "input_text" if "input_text" in proposal_df.columns else None
        if text_column is not None:
            counts = proposal_df[text_column].value_counts().head(20)
            for name, count in counts.items():
                rows.append({"kind": "top_text", "name": name, "count": int(count)})
    return pd.DataFrame(rows)


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
        "base_morph_pos_patterns": _normalize_list_cell(row.get("base_morph_pos_patterns")),
        "new_morph_pos_patterns": _normalize_list_cell(row.get("new_morph_pos_patterns")),
        "base_deprel_patterns": _normalize_list_cell(row.get("base_deprel_patterns")),
        "new_deprel_patterns": _normalize_list_cell(row.get("new_deprel_patterns")),
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
        row["base_morph_pos_patterns"],
        row["new_morph_pos_patterns"],
        row["base_deprel_patterns"],
        row["new_deprel_patterns"],
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
        "base_morph_pos_patterns": list(row["base_morph_pos_patterns"]),
        "new_morph_pos_patterns": list(row["new_morph_pos_patterns"]),
        "base_deprel_patterns": list(row["base_deprel_patterns"]),
        "new_deprel_patterns": list(row["new_deprel_patterns"]),
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
    text_rows = []
    corrected_items = []

    for text_id, text in tqdm(items, total=len(items)):
        corrected, proposals, final_objects = apply_single_rule(
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

        counts = summarize_change_rows(rows)
        text_rows.append(
            {
                "text_id": text_id,
                "base_span_count": len(corrected[base_layer]),
                "new_span_count": len(corrected[output_layer]),
                "changed_total": int(sum(counts.values())),
                "added": int(counts.get("ADDED", 0)),
                "removed": int(counts.get("REMOVED", 0)),
                "expanded": int(counts.get("EXPANDED", 0)),
                "trimmed": int(counts.get("TRIMMED", 0)),
                "shifted": int(counts.get("SHIFTED", 0)),
                "split": int(counts.get("SPLIT", 0)),
                "merged": int(counts.get("MERGED", 0)),
                "relabeled": int(counts.get("RELABELED", 0)),
                "complex": int(counts.get("COMPLEX", 0)),
            }
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    change_df = pd.DataFrame(change_rows)
    proposal_df = pd.DataFrame(proposal_rows)
    text_df = pd.DataFrame(text_rows)
    summary_df = _build_summary(change_df, proposal_df)

    change_path = output_dir / f"{rule.rule_id}_change_rows.csv"
    change_df.to_csv(change_path, index=False)

    return {
        "rule_id": rule.rule_id,
        "stage": stage,
        "change_rows": change_df,
        "proposal_rows": proposal_df,
        "text_summary": text_df,
        "summary": summary_df,
        "corrected_items": corrected_items,
        "paths": {"change_rows": change_path},
    }
