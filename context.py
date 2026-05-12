from __future__ import annotations

from dataclasses import dataclass

NAME_LIKE_POS = {"H", "S", "A", "Y"}


def resolve_morph_layer(syntax_layer="stanza_syntax", morph_layer=None):
    if morph_layer is not None:
        return morph_layer
    if syntax_layer == "stanza_ensemble_syntax":
        return "morph_extended"
    return "morph_analysis"


@dataclass
class TokenInfo:
    index: int
    text: str
    lower: str
    start: int
    end: int
    lemma: str | None
    form: str | None
    morph_pos: str | None
    syntax_id: int | None
    head: int | None
    deprel: str | None
    upostag: str | None
    xpostag: str | None


@dataclass
class SpanView:
    label: str | None
    start_i: int
    end_i: int
    tokens: list[TokenInfo]

    @property
    def text(self):
        return " ".join(token.text for token in self.tokens)

    @property
    def lemmas(self):
        return [token.lemma for token in self.tokens]

    @property
    def root_count(self):
        ids = {token.syntax_id for token in self.tokens if token.syntax_id is not None}
        roots = 0
        for token in self.tokens:
            if token.head is None:
                continue
            if token.head == 0 or token.head not in ids:
                roots += 1
        return roots

    @property
    def name_like_ratio(self):
        if not self.tokens:
            return 0.0
        return sum(token.xpostag in NAME_LIKE_POS for token in self.tokens) / len(self.tokens)


class TextContext:
    def __init__(self, text, morph_layer="morph_analysis", syntax_layer="stanza_syntax", entity_layer=None):
        self.text = text
        self.words = list(text.words)
        morph_layer = resolve_morph_layer(syntax_layer=syntax_layer, morph_layer=morph_layer)
        self.tokens = [self._build_token_info(i, word, morph_layer, syntax_layer) for i, word in enumerate(self.words)]
        self.by_syntax_id = {token.syntax_id: token for token in self.tokens if token.syntax_id is not None}
        self.entity_layer = entity_layer
        self.entities = []
        self.token_to_entity = {}

        if entity_layer is not None and entity_layer in text.layers:
            for annotation in text[entity_layer]:
                span = self.span_from_annotation(annotation)
                if span is None:
                    continue
                self.entities.append(span)
                for token in span.tokens:
                    if token.index not in self.token_to_entity:
                        self.token_to_entity[token.index] = span

    def _build_token_info(self, index, word, morph_layer, syntax_layer):
        morph = getattr(word, morph_layer, None)
        morph_ann = morph.annotations[0] if morph and morph.annotations else None
        syntax = getattr(word, syntax_layer, None)
        syntax_ann = syntax.annotations[0] if syntax and syntax.annotations else None

        return TokenInfo(
            index=index,
            text=word.text,
            lower=word.text.lower(),
            start=word.start,
            end=word.end,
            lemma=morph_ann["lemma"] if morph_ann is not None else None,
            form=morph_ann["form"] if morph_ann is not None else None,
            morph_pos=morph_ann["partofspeech"] if morph_ann is not None else None,
            syntax_id=syntax_ann["id"] if syntax_ann is not None else None,
            head=syntax_ann["head"] if syntax_ann is not None else None,
            deprel=syntax_ann["deprel"] if syntax_ann is not None else None,
            upostag=syntax_ann["upostag"] if syntax_ann is not None else None,
            xpostag=syntax_ann["xpostag"] if syntax_ann is not None else None,
        )

    def span_from_indices(self, label, start_i, end_i):
        return SpanView(label=label, start_i=start_i, end_i=end_i, tokens=self.tokens[start_i:end_i])

    def span_from_annotation(self, annotation):
        inside = [
            token.index for token in self.tokens
            if token.start >= annotation.start and token.end <= annotation.end
        ]
        if not inside:
            return None
        label = getattr(annotation, "nertag", None)
        if isinstance(label, list):
            label = label[0] if label else None
        return self.span_from_indices(label, inside[0], inside[-1] + 1)

    def prev_token(self, span):
        if span.start_i == 0:
            return None
        return self.tokens[span.start_i - 1]

    def next_token(self, span):
        if span.end_i >= len(self.tokens):
            return None
        return self.tokens[span.end_i]

    def token_entity(self, token):
        if token is None:
            return None
        if isinstance(token, int):
            return self.token_to_entity.get(token)
        return self.token_to_entity.get(token.index)
    
    def token_entity_label(self, token):
        entity = self.token_entity(token)
        return entity.label if entity else None

    def span_to_annotation(self, span):
        return {
            "start": self.tokens[span.start_i].start,
            "end": self.tokens[span.end_i - 1].end,
            "label": span.label,
            "text": span.text,
        }

    def span_ids(self, span):
        return {token.syntax_id for token in span.tokens if token.syntax_id is not None}

    def token_depends_on_span(self, token, span):
        return token is not None and token.head in self.span_ids(span)

    def span_depends_on_token(self, span, token):
        if token is None or token.syntax_id is None:
            return False
        return any(item.head == token.syntax_id for item in span.tokens)
