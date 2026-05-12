from estnltk import Layer

from ..context import TextContext


class MissingRuleEngine:
    def __init__(self, rules, morph_layer=None, syntax_layer="stanza_syntax"):
        self.rules = list(rules)
        self.morph_layer = morph_layer
        self.syntax_layer = syntax_layer

    def _occupied_tokens(self, text, input_layer):
        context = TextContext(
            text,
            morph_layer=self.morph_layer,
            syntax_layer=self.syntax_layer,
            entity_layer=input_layer,
        )
        occupied = set()
        for annotation in text[input_layer]:
            span = context.span_from_annotation(annotation)
            if span is None:
                continue
            occupied.update(range(span.start_i, span.end_i))
        return context, occupied

    def propose_for_text(self, text, input_layer="ner"):
        context, occupied = self._occupied_tokens(text, input_layer)
        proposals = []

        for rule in self.rules:
            for proposal in rule.find(context, occupied):
                token_range = set(range(proposal.start_i, proposal.end_i))
                if token_range & occupied:
                    continue
                proposals.append(proposal)

        proposals.sort(key=lambda item: item.score, reverse=True)
        chosen = []
        chosen_tokens = set(occupied)
        proposal_rows = []

        for proposal in proposals:
            token_range = set(range(proposal.start_i, proposal.end_i))
            if token_range & chosen_tokens:
                continue
            chosen.append(proposal)
            chosen_tokens.update(token_range)
            proposal_rows.append({
                "rule_id": proposal.rule_id,
                "label": proposal.label,
                "text": " ".join(context.tokens[i].text for i in range(proposal.start_i, proposal.end_i)),
                "start": context.tokens[proposal.start_i].start,
                "end": context.tokens[proposal.end_i - 1].end,
                "start_i": proposal.start_i,
                "end_i": proposal.end_i,
                "score": proposal.score,
            })

        return chosen, proposal_rows

    def attach_output_layer(self, text, input_layer, chosen, output_layer="ner_missing_rules"):
        context, _ = self._occupied_tokens(text, input_layer)

        if output_layer in text.layers:
            text.pop_layer(output_layer)

        layer = Layer(name=output_layer, attributes=["nertag"], text_object=text, ambiguous=False)
        for annotation in text[input_layer]:
            layer.add_annotation((annotation.start, annotation.end), nertag=annotation.annotations[0]["nertag"])
        for proposal in chosen:
            layer.add_annotation(
                (context.tokens[proposal.start_i].start, context.tokens[proposal.end_i - 1].end),
                nertag=proposal.label,
            )
        text.add_layer(layer)
        return text

    def apply_to_text(self, text, input_layer="ner", output_layer="ner_missing_rules"):
        chosen, proposal_rows = self.propose_for_text(text, input_layer=input_layer)
        self.attach_output_layer(text, input_layer=input_layer, chosen=chosen, output_layer=output_layer)
        return text, proposal_rows
