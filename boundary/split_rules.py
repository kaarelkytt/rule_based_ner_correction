from .base import BaseRule, RuleProposal


class BaseSplitDisconnectedEntityTreeRule(BaseRule):
    rule_id = "lahuta_mittesidus_ne_puu_base"
    description = "Baasklass mittesidusa nimeüksuse lahutamiseks."
    stage = "split"

    LABEL = None
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = set()
    DO_NOT_SPLIT_DEPREL_PATTERNS = set()
    ALLOW_COMPONENTS_WITH_SAME_EXTERNAL_HEAD = False
    MERGE_ADJACENT_SAME_HEAD_COMPONENTS = True
    TRIM_EDGE_DEPRELS = set()
    TRIM_EDGE_POS = set()

    def applies_to(self, span, context):
        return self.LABEL is not None and span.label == self.LABEL and len(span.tokens) > 1

    def _token_id(self, token):
        return token.syntax_id

    def _token_head(self, token):
        return token.head

    def _pos_pattern(self, span):
        return tuple(token.morph_pos for token in span.tokens)

    def _deprel_pattern(self, span):
        return tuple(token.deprel for token in span.tokens)

    def _should_keep_whole(self, span):
        pos_pattern = self._pos_pattern(span)
        deprel_pattern = self._deprel_pattern(span)
        if pos_pattern in self.DO_NOT_SPLIT_POS_PATTERNS:
            return True
        if deprel_pattern in self.DO_NOT_SPLIT_DEPREL_PATTERNS:
            return True
        return False

    def _get_components(self, span):
        tokens = span.tokens
        token_ids = [self._token_id(token) for token in tokens]
        id_to_local_index = {token_id: index for index, token_id in enumerate(token_ids)}
        graph = {index: set() for index in range(len(tokens))}

        for index, token in enumerate(tokens):
            head = self._token_head(token)
            if head not in id_to_local_index:
                continue
            head_index = id_to_local_index[head]
            graph[index].add(head_index)
            graph[head_index].add(index)

        components = []
        seen = set()
        for index in range(len(tokens)):
            if index in seen:
                continue
            stack = [index]
            component = set()
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                component.add(node)
                for neighbor in graph[node]:
                    if neighbor not in seen:
                        stack.append(neighbor)
            components.append(component)
        return components

    def _external_heads(self, span, component):
        tokens = span.tokens
        component_token_ids = {self._token_id(tokens[index]) for index in component}
        external_heads = set()
        for index in component:
            head = self._token_head(tokens[index])
            if head not in component_token_ids:
                external_heads.add(head)
        return external_heads

    def _all_tokens_share_same_external_head(self, span):
        span_token_ids = {self._token_id(token) for token in span.tokens}
        external_heads = set()
        for token in span.tokens:
            head = self._token_head(token)
            if head in span_token_ids:
                return False
            external_heads.add(head)
        return len(external_heads) == 1

    def _all_components_share_same_external_head(self, span, components):
        all_external_heads = set()
        for component in components:
            external_heads = self._external_heads(span, component)
            if len(external_heads) != 1:
                return False
            all_external_heads.update(external_heads)
        return len(all_external_heads) == 1

    def _is_trim_token(self, token):
        return token.deprel in self.TRIM_EDGE_DEPRELS or token.morph_pos in self.TRIM_EDGE_POS

    def _component_first_index(self, component):
        return min(component)

    def _component_last_index(self, component):
        return max(component)

    def _components_are_adjacent(self, left, right):
        return self._component_last_index(left) + 1 == self._component_first_index(right)

    def _can_merge_components(self, span, left, right):
        if not self._components_are_adjacent(left, right):
            return False

        left_heads = self._external_heads(span, left)
        right_heads = self._external_heads(span, right)
        if len(left_heads) != 1 or len(right_heads) != 1:
            return False
        if left_heads != right_heads:
            return False

        tokens = span.tokens
        right_first = tokens[self._component_first_index(right)]
        if self._is_trim_token(right_first):
            return False
        return True

    def _merge_adjacent_same_head_components(self, span, components):
        if not self.MERGE_ADJACENT_SAME_HEAD_COMPONENTS:
            return components

        ordered = sorted(components, key=lambda component: min(component))
        merged = []
        for component in ordered:
            if not merged:
                merged.append(set(component))
                continue
            previous = merged[-1]
            if self._can_merge_components(span, previous, component):
                previous.update(component)
            else:
                merged.append(set(component))
        return merged

    def _trim_edge_tokens(self, span, component):
        ordered = sorted(component)
        while ordered and self._is_trim_token(span.tokens[ordered[0]]):
            ordered.pop(0)
        while ordered and self._is_trim_token(span.tokens[ordered[-1]]):
            ordered.pop()
        if not ordered:
            return set()
        return set(ordered)

    def _is_contiguous_component(self, component):
        if not component:
            return False
        ordered = sorted(component)
        return ordered == list(range(ordered[0], ordered[-1] + 1))

    def _component_to_span(self, span, context, component):
        ordered = sorted(component)
        start_i = span.start_i + ordered[0]
        end_i = span.start_i + ordered[-1] + 1
        return context.span_from_indices(span.label, start_i, end_i)

    def _is_valid_entity_tree(self, span):
        if self._should_keep_whole(span):
            return True

        components = self._get_components(span)
        if self._all_tokens_share_same_external_head(span):
            return True
        if len(components) == 1:
            external_heads = self._external_heads(span, components[0])
            return len(external_heads) <= 1
        if self.ALLOW_COMPONENTS_WITH_SAME_EXTERNAL_HEAD:
            return self._all_components_share_same_external_head(span, components)
        return False

    def propose(self, span, context):
        if self._is_valid_entity_tree(span):
            return None

        components = self._get_components(span)
        if len(components) <= 1:
            return None

        components = self._merge_adjacent_same_head_components(span, components)
        new_spans = []

        for component in sorted(components, key=lambda item: min(item)):
            component = self._trim_edge_tokens(span, component)
            if not component:
                continue
            if not self._is_contiguous_component(component):
                return None
            external_heads = self._external_heads(span, component)
            if len(external_heads) > 1:
                return None
            new_spans.append(self._component_to_span(span, context, component))

        if len(new_spans) <= 1:
            return None

        return RuleProposal(
            rule_id=self.rule_id,
            operation="replace",
            score=self.SCORE,
            spans=new_spans,
        )
    

class SplitDisconnectedOrgTreeRule(BaseSplitDisconnectedEntityTreeRule):
    rule_id = "lahuta_mittesidus_org_puu"
    description = "Lahutab mittesidusa ORG nimeüksuse."

    LABEL = "ORG"
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = {
        ("H", "S"),
        ("S", "S"),
        ("H", "Y"),
        ("A", "S"),
        ("Y", "H"),
        ("H", "H", "Y"),
    }
    DO_NOT_SPLIT_DEPREL_PATTERNS = {
        ("appos", "flat", "nmod"),
    }
    TRIM_EDGE_DEPRELS = {"cc"}
    TRIM_EDGE_POS = {"J", "O"}


class SplitDisconnectedPerTreeRule(BaseSplitDisconnectedEntityTreeRule):
    rule_id = "lahuta_mittesidus_per_puu"
    description = "Lahutab mittesidusa PER nimeüksuse."

    LABEL = "PER"
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = {
        ("H", "S"),
        ("H", "O"),
        ("H", "H", "O"),
    }
    DO_NOT_SPLIT_DEPREL_PATTERNS = set()
    TRIM_EDGE_DEPRELS = {"cc"}
    TRIM_EDGE_POS = {"J"}


class SplitDisconnectedLocTreeRule(BaseSplitDisconnectedEntityTreeRule):
    rule_id = "lahuta_mittesidus_loc_puu"
    description = "Lahutab mittesidusa LOC nimeüksuse."

    LABEL = "LOC"
    SCORE = 0.95

    DO_NOT_SPLIT_POS_PATTERNS = {
        ("H", "S"),
        ("S", "S"),
        ("H", "Y"),
        ("A", "S"),
    }
    DO_NOT_SPLIT_DEPREL_PATTERNS = set()
    TRIM_EDGE_DEPRELS = {"cc"}
    TRIM_EDGE_POS = {"J", "O"}


class SplitCoordinatedLocationRule(BaseRule):
    rule_id = "jaga_koordineeritud_loc"
    description = "Jagab koordineeritud LOC märgendi kaheks üksuseks."
    stage = "split"

    def applies_to(self, span, context):
        return span.label == "LOC" and len(span.tokens) >= 3

    def propose(self, span, context):
        conjunction_offset = None
        for offset, token in enumerate(span.tokens):
            if token.lower == "ja":
                conjunction_offset = offset
                break

        if conjunction_offset is None or conjunction_offset == 0 or conjunction_offset == len(span.tokens) - 1:
            return None

        left_tokens = span.tokens[:conjunction_offset]
        if not any(token.text == "-" or token.text.endswith("-") for token in left_tokens):
            return None

        right_token = span.tokens[conjunction_offset + 1]
        if "ill" in (right_token.form or "").split():
            return None

        left_span = context.span_from_indices(span.label, span.start_i, span.start_i + conjunction_offset)
        right_span = context.span_from_indices(span.label, span.start_i + conjunction_offset + 1, span.end_i)

        if not left_span.tokens or not right_span.tokens:
            return None
        if left_span.name_like_ratio < 0.5 or right_span.name_like_ratio < 0.5:
            return None

        return RuleProposal(
            self.rule_id,
            "split",
            0.97,
            [left_span, right_span],
            {"from": span.text, "parts": [left_span.text, right_span.text]},
        )
