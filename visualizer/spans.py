def get_span_label(span, attribute_name):
    if attribute_name is None:
        return ""
    if not hasattr(span, attribute_name):
        return ""

    value = getattr(span, attribute_name)
    if isinstance(value, str):
        return value
    if value:
        return str(value[0])
    return ""
