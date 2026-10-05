from typing import Optional 

def create_board_str(board, player_id: Optional[int]=None) -> str:
    def cell_str(value: str) -> str:        return "   " if value == "." else f" {value} "
    def top_border(cols: int) -> str:       return "┌" + "───┬" * (cols - 1) + "───┐"
    def mid_border(cols: int) -> str:       return "├" + "───┼" * (cols - 1) + "───┤"
    def bottom_border(cols: int) -> str:    return "└" + "───┴" * (cols - 1) + "───┘"
    lines = []
    lines.append(" " + "".join(f"{col:^4}" for col in range(len(board[0]))))
    lines.append(top_border(len(board[0])))
    for r in range(len(board)):
        row_line = "│" + "│".join(cell_str(val) for val in board[r]) + "│"
        lines.append(row_line)
        if r < len(board)-1:    lines.append(mid_border(len(board[0])))
        else:                   lines.append(bottom_border(len(board[0])))
    return "\n".join(lines)
