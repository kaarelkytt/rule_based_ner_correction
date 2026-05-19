import matplotlib.pyplot as plt

from .layout import compute_depths, compute_positions
from .spans import get_span_label


DEFAULT_COLORS = ["red", "blue", "green", "orange", "purple"]


def _normalize_span_configs(spans):
    return [] if spans is None else list(spans)


def _build_canvas(syntax, char_width, spacing, y_scale, units_to_inches, span_configs):
    depths = compute_depths(syntax)
    max_depth = max(depths.values())
    x_positions, widths, total_tree_width = compute_positions(syntax, char_width, spacing)
    y_positions = [(max_depth - depths[index]) * y_scale for index in range(len(syntax))]

    legend_lines = ["Kihid"] + [config["name"] for config in span_configs]
    max_legend_length = max(len(str(item)) for item in legend_lines) if legend_lines else 0
    legend_width = max_legend_length * char_width * 0.9 + 1
    legend_margin = 0.5
    line_height = 0.5
    legend_height = len(legend_lines) * line_height + 0.2

    figure_width = (legend_width + legend_margin + total_tree_width) * units_to_inches
    figure_height = (max_depth * y_scale + 2) * units_to_inches
    figure, axis = plt.subplots(figsize=(figure_width, figure_height))

    return {
        "figure": figure,
        "axis": axis,
        "depths": depths,
        "max_depth": max_depth,
        "x_positions": x_positions,
        "y_positions": y_positions,
        "widths": widths,
        "legend_width": legend_width,
        "legend_margin": legend_margin,
        "legend_height": legend_height,
        "line_height": line_height,
    }


def _draw_edges(axis, syntax, x_positions, y_positions):
    for index, token in enumerate(syntax):
        head = token["head"]
        if head == 0:
            continue

        head_index = head - 1
        x_head, y_head = x_positions[head_index], y_positions[head_index]
        x_token, y_token = x_positions[index], y_positions[index]
        middle_y = (y_head + y_token) / 2

        axis.plot([x_head, x_head], [y_head, middle_y], color="#444444", linewidth=1)
        axis.plot([x_head, x_token], [middle_y, middle_y], color="#444444", linewidth=1)
        axis.plot([x_token, x_token], [middle_y, y_token], color="#444444", linewidth=1)


def _draw_tokens(axis, syntax, x_positions, y_positions):
    for index, token in enumerate(syntax):
        axis.text(
            x_positions[index],
            y_positions[index],
            token.text,
            ha="center",
            va="center",
            fontsize=11,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="black"),
            zorder=3,
        )
        axis.text(
            x_positions[index],
            y_positions[index] - 0.5,
            token["deprel"],
            ha="center",
            fontsize=8,
            color="gray",
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9),
            zorder=4,
        )


def _draw_span_layers(axis, text, syntax, span_configs, x_positions, y_positions, widths):
    layer_offsets = {config["name"]: index * 0.25 + 0.15 for index, config in enumerate(span_configs)}

    for index, config in enumerate(span_configs):
        layer_name = config["name"]
        if layer_name not in text.layers:
            continue

        color = config.get("color", DEFAULT_COLORS[index % len(DEFAULT_COLORS)])
        label_field = config.get("label")

        for span in text[layer_name]:
            token_ids = [
                token_index
                for token_index, token in enumerate(syntax)
                if token.start >= span.start and token.end <= span.end
            ]
            if not token_ids:
                continue

            xmin = x_positions[token_ids[0]] - widths[token_ids[0]] / 2
            xmax = x_positions[token_ids[-1]] + widths[token_ids[-1]] / 2
            y_base = min(y_positions[token_index] for token_index in token_ids)
            y_line = y_base - 0.6 - layer_offsets[layer_name]

            axis.plot([xmin, xmax], [y_line, y_line], color=color, linewidth=3, solid_capstyle="round", alpha=0.6)

            label = get_span_label(span, label_field)
            if label:
                axis.text(
                    (xmin + xmax) / 2,
                    y_line - 0.05,
                    label,
                    fontsize=8,
                    ha="center",
                    family="monospace",
                    alpha=0.8,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7),
                )


def _draw_legend(axis, span_configs, x_positions, widths, y_positions, legend_width, legend_margin, legend_height, line_height):
    if not x_positions:
        return

    tree_left = min(x_positions[index] - widths[index] / 2 for index in range(len(x_positions)))
    legend_x = tree_left - legend_width - legend_margin
    legend_top = max(y_positions) + 1

    axis.add_patch(
        plt.Rectangle(
            (legend_x - 0.1, legend_top - legend_height + 0.4),
            legend_width,
            legend_height,
            facecolor="white",
            alpha=0.85,
            edgecolor="gray",
        )
    )
    axis.text(legend_x, legend_top, "Kihid:", fontsize=12, weight="bold", family="monospace")

    for index, config in enumerate(span_configs):
        color = config.get("color", DEFAULT_COLORS[index % len(DEFAULT_COLORS)])
        axis.text(
            legend_x,
            legend_top - (index + 1) * line_height,
            "* " + config["name"],
            color=color,
            fontsize=11,
            family="monospace",
        )

    axis.set_xlim(legend_x - 0.5, max(x_positions) + 1)
    axis.set_ylim(-2, legend_top + 0.5)


def draw_tree(
    text,
    syntax_layer="stanza_syntax",
    spans=None,
    char_width=0.15,
    spacing=0.3,
    y_scale=1.2,
    units_to_inches=0.8,
):
    span_configs = _normalize_span_configs(spans)
    syntax = text[syntax_layer]

    canvas = _build_canvas(
        syntax=syntax,
        char_width=char_width,
        spacing=spacing,
        y_scale=y_scale,
        units_to_inches=units_to_inches,
        span_configs=span_configs,
    )
    axis = canvas["axis"]

    _draw_edges(axis, syntax, canvas["x_positions"], canvas["y_positions"])
    _draw_tokens(axis, syntax, canvas["x_positions"], canvas["y_positions"])
    _draw_span_layers(
        axis,
        text,
        syntax,
        span_configs,
        canvas["x_positions"],
        canvas["y_positions"],
        canvas["widths"],
    )
    _draw_legend(
        axis,
        span_configs,
        canvas["x_positions"],
        canvas["widths"],
        canvas["y_positions"],
        canvas["legend_width"],
        canvas["legend_margin"],
        canvas["legend_height"],
        canvas["line_height"],
    )

    axis.axis("off")
    plt.show()
    return axis
