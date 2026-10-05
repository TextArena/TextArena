from typing import Dict, Any

def create_board_str(game_state: Dict[str, Any]) -> str:
    board = game_state["board"]
    highlighted = game_state.get("highlighted_positions", set())
    height = len(board)
    width = len(board[0]) if height > 0 else 0
    header = "     " + "  ".join(f"C{col:02}" for col in range(width))
    lines = [header]
    border = "    +" + "-----" * width + "+"
    lines.append(border)
    for row_idx, row in enumerate(board):
        row_str = f"R{row_idx:02} |"
        for col_idx, cell in enumerate(row):
            if isinstance(cell, str) and len(cell) == 1:
                row_str += f"[{cell}]" if (row_idx, col_idx) in highlighted else f" {cell} "
            else:
                row_str += f"{cell} "
            row_str += "  "
        row_str += "|"
        lines.append(row_str)

    lines.append(border)

    # Show correct guesses if tracked (optional for more advanced renderer)
    if "correct_words" in game_state:
        lines.append("\nWords Found:")
        for word in sorted(game_state["correct_words"]):
            lines.append(f" - {word}")

    return "\n".join(lines)
