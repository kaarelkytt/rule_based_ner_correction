from estnltk import Layer
from estnltk.taggers import Tagger

from .boundary.engine import RuleEngine
from .context import TextContext
from .missing.engine import MissingRuleEngine
from .registry import split_rules_by_stage, get_default_rules


class RuleBasedNerCorrectionTagger(Tagger):
    """Rakendab olemasoleva NER-kihi peale reeglipõhise paranduse."""

    conf_param = [
        "ner_layer",
        "words_layer",
        "morph_layer",
        "syntax_layer",
        "output_layer",
        "_split_tmp_layer",
        "_adjust_tmp_layer",
        "_finalize_tmp_layer",
        "_split_engine",
        "_adjust_engine",
        "_finalize_engine",
        "_missing_engine",
    ]

    def __init__(
        self,
        ner_layer="ner",
        words_layer="words",
        morph_layer="morph_analysis",
        syntax_layer="stanza_syntax",
        output_layer="ner_rules_corrected",
        rules=None,
    ):
        self.input_layers = [ner_layer, words_layer, morph_layer, syntax_layer]
        self.output_layer = output_layer
        self.output_attributes = ["nertag"]

        self.ner_layer = ner_layer
        self.words_layer = words_layer
        self.morph_layer = morph_layer
        self.syntax_layer = syntax_layer

        if rules is None:
            rules = get_default_rules()
        else:
            rules = list(rules)

        grouped_rules = split_rules_by_stage(rules)

        self._split_tmp_layer = "__rule_based_ner_split_tmp"
        self._adjust_tmp_layer = "__rule_based_ner_adjust_tmp"
        self._finalize_tmp_layer = "__rule_based_ner_finalize_tmp"

        self._split_engine = RuleEngine(grouped_rules["split"], morph_layer=self.morph_layer, syntax_layer=self.syntax_layer)
        self._adjust_engine = RuleEngine(grouped_rules["adjust"], morph_layer=self.morph_layer, syntax_layer=self.syntax_layer)
        self._finalize_engine = RuleEngine(grouped_rules["finalize"], morph_layer=self.morph_layer, syntax_layer=self.syntax_layer)
        self._missing_engine = MissingRuleEngine(grouped_rules["missing"], morph_layer=self.morph_layer, syntax_layer=self.syntax_layer)

    def _make_layer_template(self):
        return Layer(
            name=self.output_layer,
            text_object=None,
            attributes=self.output_attributes,
            ambiguous=False,
        )

    def _apply_boundary_pass(self, text, input_layer, output_layer, engine):
        if not engine.rules:
            return input_layer
        spans, _ = engine.propose_for_text(text, input_layer=input_layer)
        engine.attach_output_layer(text, spans, output_layer=output_layer)
        return output_layer

    def _build_output_layer(self, text, input_layer, chosen_missing):
        context = TextContext(
            text,
            morph_layer=self.morph_layer,
            syntax_layer=self.syntax_layer,
            entity_layer=input_layer,
        )
        layer = self._make_layer_template()
        layer.text_object = text

        seen = set()
        for annotation in text[input_layer]:
            key = (annotation.start, annotation.end)
            if key in seen:
                continue
            layer.add_annotation(key, nertag=annotation.annotations[0]["nertag"])
            seen.add(key)

        for proposal in chosen_missing:
            start = context.tokens[proposal.start_i].start
            end = context.tokens[proposal.end_i - 1].end
            key = (start, end)
            if key in seen:
                continue
            layer.add_annotation(key, nertag=proposal.label)
            seen.add(key)

        return layer

    def _make_layer(self, text, layers, status):
        temp_layers = [
            self._split_tmp_layer,
            self._adjust_tmp_layer,
            self._finalize_tmp_layer,
        ]
        try:
            for layer_name in temp_layers:
                if layer_name in text.layers:
                    text.pop_layer(layer_name)

            current_layer = self.ner_layer
            current_layer = self._apply_boundary_pass(text, current_layer, self._split_tmp_layer, self._split_engine)
            current_layer = self._apply_boundary_pass(text, current_layer, self._adjust_tmp_layer, self._adjust_engine)
            current_layer = self._apply_boundary_pass(text, current_layer, self._finalize_tmp_layer, self._finalize_engine)

            chosen_missing, _ = self._missing_engine.propose_for_text(text, input_layer=current_layer)
            output_layer = self._build_output_layer(text, current_layer, chosen_missing)
        finally:
            for layer_name in temp_layers:
                if layer_name in text.layers:
                    text.pop_layer(layer_name)

        return output_layer
    