def create_board_str(game_state: dict) -> str:
    board = game_state["board"]
    grid_size = len(board[0])

    def cell_repr(cell):
        if cell == '~':
            return "🌊"
        elif cell == 'X':
            return "🔥"
        elif cell == 'O':
            return "💦"
        else:
            return f"{cell} "

    def render_single_board(grid, title):
        lines = []
        # Each cell is five columns wide ("│ " + two-column content + " ").
        board_width = 3 + grid_size * 5
        header = ("    " + "".join(f"{i:<5}" for i in range(grid_size)))[:board_width]
        lines.append(title.center(board_width))
        lines.append(header)
        lines.append("  ┌" + "────┬" * (grid_size - 1) + "────┐")
        for r in range(grid_size):
            row_cells = " │ ".join(cell_repr(grid[r][c]) for c in range(grid_size))
            lines.append(f"{chr(65 + r)} │ {row_cells} │")
            if r < grid_size - 1:
                lines.append("  ├" + "────┼" * (grid_size - 1) + "────┤")
            else:
                lines.append("  └" + "────┴" * (grid_size - 1) + "────┘")
        return lines

    board_0 = render_single_board(board[0], "Player 0")
    board_1 = render_single_board(board[1], "Player 1")

    # Merge the boards side by side
    combined = []
    for left, right in zip(board_0, board_1):
        combined.append(left + "    " + right)

    return "\n".join(combined)