from typing import List

def create_board_str(grid: List[List[int]], revealed: List[List[bool]], flags: List[List[bool]]) -> str:
    """
    Render the Minesweeper board with clean alignment for multi-digit columns.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0

    row_width = max(1, len(str(max(0, rows - 1))))
    cell_width = max(1, len(str(max(0, cols - 1))))
    inner_width = cols * (cell_width + 1) + 1

    # Column header
    col_header = " " * (row_width + 2) + " ".join(
        f"{c:>{cell_width}}" for c in range(cols)
    )

    # Top border
    top_border = " " * row_width + "┌" + "─" * inner_width + "┐"

    # Board content
    board_rows = []
    for r in range(rows):
        row_content = ""
        for c in range(cols):
            if flags[r][c]:
                cell = "F"
            elif not revealed[r][c]:
                cell = "."
            elif grid[r][c] == -1:
                cell = "*"
            else:
                cell = str(grid[r][c])
            row_content += f" {cell:>{cell_width}}"
        board_rows.append(f"{r:>{row_width}}│{row_content} │")

    # Bottom border
    bottom_border = " " * row_width + "└" + "─" * inner_width + "┘"

    return "\n".join([col_header, top_border, *board_rows, bottom_border])
