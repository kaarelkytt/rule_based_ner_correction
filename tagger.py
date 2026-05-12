from estnltk import Layer
from estnltk.taggers import Tagger

from .boundary.engine import RuleEngine
from .boundary.registry import get_default_rules
from .context import TextContext
from .missing.engine import MissingRuleEngine
from .missing.registry import get_default_rules as get_default_missing_rules


class RuleBasedNerCorrectionTagger(Tagger):
    """Rakendab olemasoleva NER-kihi peale reeglipõhise paranduse."""

    conf_param = [
        "ner_layer",
        "words_layer",
        "morph_layer",
        "syntax_layer",
        "output_layer",
        "boundary_rules",
        "missing_rules",
        "_RuleBasedNerCorrectionTagger__boundary_tmp_layer",
        "_RuleBasedNerCorrectionTagger__boundary_engine",
        "_RuleBasedNerCorrectionTagger__missing_engine",
    ]

    def __init__(
        self,
        ner_layer="ner",
        words_layer="words",
        morph_layer="morph_analysis",
        syntax_layer="stanza_syntax",
        output_layer="ner_rules_corrected",
        boundary_rules=None,
        missing_rules=None,
    ):
        self.input_layers = [ner_layer, words_layer, morph_layer, syntax_layer]
        self.output_layer = output_layer
        self.output_attributes = ["nertag"]

        self.ner_layer = ner_layer
        self.words_layer = words_layer
        self.morph_layer = morph_layer
        self.syntax_layer = syntax_layer
        self.boundary_rules = list(get_default_rules()) if boundary_rules is None else list(boundary_rules)
        self.missing_rules = list(get_default_missing_rules()) if missing_rules is None else list(missing_rules)

        self.__boundary_tmp_layer = "__rule_based_ner_boundary_tmp"
        self.__boundary_engine = RuleEngine(
            self.boundary_rules,
            morph_layer=self.morph_layer,
            syntax_layer=self.syntax_layer,
        )
        self.__missing_engine = MissingRuleEngine(
            self.missing_rules,
            morph_layer=self.morph_layer,
            syntax_layer=self.syntax_layer,
        )

    def _make_layer_template(self):
        return Layer(
            name=self.output_layer,
            text_object=None,
            attributes=self.output_attributes,
            ambiguous=False,
        )

    def _build_output_layer(self, text, input_layer, chosen):
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

        for proposal in chosen:
            start = context.tokens[proposal.start_i].start
            end = context.tokens[proposal.end_i - 1].end
            key = (start, end)
            if key in seen:
                continue
            layer.add_annotation(key, nertag=proposal.label)
            seen.add(key)

        return layer

    def _make_layer(self, text, layers, status):
        try:
            if self.__boundary_tmp_layer in text.layers:
                text.pop_layer(self.__boundary_tmp_layer)

            boundary_spans, _ = self.__boundary_engine.propose_for_text(text, input_layer=self.ner_layer)
            self.__boundary_engine.attach_output_layer(text, boundary_spans, output_layer=self.__boundary_tmp_layer)

            chosen, _ = self.__missing_engine.propose_for_text(text, input_layer=self.__boundary_tmp_layer)
            output_layer = self._build_output_layer(text, self.__boundary_tmp_layer, chosen)
        finally:
            if self.__boundary_tmp_layer in text.layers:
                text.pop_layer(self.__boundary_tmp_layer)

        return output_layer
