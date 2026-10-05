from typing import Any, Dict, List

def create_board_str(game_state: Dict[str, Any]) -> str:
    """
    Render the Lights Out board with lit cells shaded
    """
    board: List[List[bool]] = game_state.get("grid", [])
    if not board:
        return "Board not available."

    grid_size = len(board)
    label_width = len(str(grid_size - 1))
    on_symbol = "███"  
    off_symbol = "   "  

    def cell_display(r: int, c: int) -> str:
        """Returns the 3-character representation for a cell"""
        return on_symbol if board[r][c] else off_symbol

    def horizontal_line(left: str, mid: str, right: str) -> str:
        """Creates a horizontal line for the grid border"""
        return " " * (label_width + 1) + left + ("─" * 3 + mid) * (grid_size - 1) + "─" * 3 + right

    header = " " * (label_width + 2) + " ".join(f"{c:^3}" for c in range(grid_size))
    lines = [header]
    lines.append(horizontal_line("┌", "┬", "┐"))

    for r in range(grid_size):
        row_content = "│".join(cell_display(r, c) for c in range(grid_size))
        lines.append(f"{r:>{label_width}} │{row_content}│")
        if r < grid_size - 1:
            lines.append(horizontal_line("├", "┼", "┤"))

    lines.append(horizontal_line("└", "┴", "┘"))

    return "\n".join(lines)