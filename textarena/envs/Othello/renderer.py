from typing import List 

def create_board_str(board: List[List[str]]) -> str:
    piece_symbols = {'B': '●', 'W': '○', '': ' '}
    size = len(board)
    label_width = len(str(size - 1))
    lines = []
    lines.append(" " * (label_width + 2) + "".join(f"{i:^4}" for i in range(size)))
    lines.append(" " * (label_width + 1) + "┌" + "───┬" * (size - 1) + "───┐")
    for r in range(size):
        row_cells = " │ ".join(piece_symbols[cell] for cell in board[r])
        lines.append(f"{r:>{label_width}} │ {row_cells} │")
        if r < size - 1: lines.append(" " * (label_width + 1) + "├" + "───┼" * (size - 1) + "───┤")
        else: lines.append(" " * (label_width + 1) + "└" + "───┴" * (size - 1) + "───┘")
    return "\n".join(lines)
