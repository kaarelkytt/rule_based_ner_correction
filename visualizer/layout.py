def compute_depths(syntax):
    depths = {}

    def get_depth(index):
        if index in depths:
            return depths[index]
        head = syntax[index]["head"]
        if head == 0:
            depths[index] = 0
        else:
            depths[index] = get_depth(head - 1) + 1
        return depths[index]

    for index in range(len(syntax)):
        get_depth(index)

    return depths


def compute_positions(syntax, char_width, spacing):
    positions = []
    widths = []
    current_x = 0

    for token in syntax:
        width = len(token.text) * char_width
        widths.append(width)
        positions.append(current_x + width / 2)
        current_x += width + spacing

    return positions, widths, current_x
