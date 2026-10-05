from typing import List

def create_board_str(game_state) -> str:
    grid = game_state["board"]
    placed_words = game_state.get("placed_words", {})
    clues = game_state.get("clues", {})
    
    rows, cols = len(grid), len(grid[0])

    # Assign clue numbers to starting positions
    clue_numbers = {}
    number = 1
    for word, (row, col, direction) in placed_words.items():
        if (row, col) not in clue_numbers:
            clue_numbers[(row, col)] = number
            number += 1

    def cell_display(i, j, val):
        if val == ".":
            return "   "
        elif (i, j) in clue_numbers and val == "_":
            return f"{clue_numbers[(i, j)]:>2} "
        elif val == "_":
            return " ▢ "
        else:
            return f" {val.upper()} "

    # Column header
    header = "   " + " ".join(f"{j:>3}" for j in range(cols))
    lines = [header]
    lines.append("   +" + "---+" * cols)

    # Grid with clue numbers
    for i, row in enumerate(grid):
        row_str = f"{i:>2} |"
        for j, val in enumerate(row):
            row_str += cell_display(i, j, val) + "|"
        lines.append(row_str)
        lines.append("   +" + "---+" * cols)

    # Append clues
    clue_lines = []
    for word, (row, col, direction) in placed_words.items():
        if word in clues:
            clue_lines.append(f"{clue_numbers[(row, col)]}. ({direction}) {clues[word]}")

    if clue_lines:
        lines.append("\nClues:")
        lines += clue_lines

    return "\n".join(lines)
