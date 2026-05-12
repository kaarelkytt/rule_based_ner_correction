from estnltk import Layer

from ..context import TextContext


class RuleEngine:
    def __init__(self, rules, morph_layer=None, syntax_layer="stanza_syntax"):
        self.rules = list(rules)
        self.morph_layer = morph_layer
        self.syntax_layer = syntax_layer

    @staticmethod
    def _token_range(spans):
        tokens = set()
        for span in spans:
            tokens.update(range(span.start_i, span.end_i))
        return tokens

    @staticmethod
    def _decision_sort_key(decision):
        total_tokens = sum(span.end_i - span.start_i for span in decision["spans"])
        leftmost_start = min((span.start_i for span in decision["spans"]), default=10**9)
        return (
            decision["score"],
            total_tokens,
            -leftmost_start,
        )

    def _resolve_non_overlapping(self, decisions):
        ranked = sorted(decisions, key=self._decision_sort_key, reverse=True)
        occupied_tokens = set()
        kept_input_ids = set()
        final_spans = []

        for decision in ranked:
            token_range = self._token_range(decision["spans"])
            if token_range & occupied_tokens:
                continue
            kept_input_ids.add(decision["input_id"])
            occupied_tokens.update(token_range)
            final_spans.extend(decision["spans"])

        return final_spans, kept_input_ids

    def propose_for_text(self, text, input_layer="ner"):
        context = TextContext(
            text,
            morph_layer=self.morph_layer,
            syntax_layer=self.syntax_layer,
            entity_layer=input_layer,
        )
        proposal_rows = []
        decisions = []

        for input_id, annotation in enumerate(text[input_layer]):
            span = context.span_from_annotation(annotation)
            if span is None:
                continue

            chosen = None
            candidates = []

            for rule in self.rules:
                if not rule.applies_to(span, context):
                    continue
                proposal = rule.propose(span, context)
                if proposal is None:
                    continue
                candidates.append(proposal)

            if candidates:
                candidates.sort(key=lambda item: item.score, reverse=True)
                chosen = candidates[0]
                output_spans = chosen.spans
                decision_score = chosen.score
            else:
                output_spans = [span]
                decision_score = 0.0

            decisions.append(
                {
                    "input_id": input_id,
                    "score": decision_score,
                    "spans": output_spans,
                }
            )

            proposal_rows.append({
                "input_id": input_id,
                "text": text.text,
                "input_text": span.text,
                "label": span.label,
                "input_start_i": span.start_i,
                "input_end_i": span.end_i,
                "chosen_rule": chosen.rule_id if chosen is not None else None,
                "decision_score": decision_score,
                "output_texts": [item.text for item in output_spans],
                "output_labels": [item.label for item in output_spans],
                "output_start_i": [item.start_i for item in output_spans],
                "output_end_i": [item.end_i for item in output_spans],
                "output_starts": [item.tokens[0].start for item in output_spans],
                "output_ends": [item.tokens[-1].end for item in output_spans],
                "input_start": context.tokens[span.start_i].start,
                "input_end": context.tokens[span.end_i - 1].end,
                "candidate_rules": [candidate.rule_id for candidate in candidates],
                "candidate_count": len(candidates),
            })

        final_spans, kept_input_ids = self._resolve_non_overlapping(decisions)
        for row in proposal_rows:
            row["kept_in_final"] = row["input_id"] in kept_input_ids

        return final_spans, proposal_rows

    def attach_output_layer(self, text, final_spans, output_layer="ner_rules"):
        if output_layer in text.layers:
            text.pop_layer(output_layer)

        layer = Layer(name=output_layer, attributes=["nertag"], text_object=text, ambiguous=False)
        seen_spans = set()
        for span in final_spans:
            key = (span.tokens[0].start, span.tokens[-1].end)
            if key in seen_spans:
                continue
            layer.add_annotation(key, nertag=span.label)
            seen_spans.add(key)
        text.add_layer(layer)

        return text

    def apply_to_text(self, text, input_layer="ner", output_layer="ner_rules"):
        final_spans, proposals = self.propose_for_text(text, input_layer=input_layer)
        self.attach_output_layer(text, final_spans, output_layer=output_layer)

        return text, proposals
