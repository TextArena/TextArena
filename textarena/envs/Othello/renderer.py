from typing import List 

def create_board_str(board: List[List[str]]) -> str:
    piece_symbols = {'B': '○', 'W': '●', '': ' '}
    lines = []
    lines.append("    " + "   ".join(str(i) for i in range(8)))
    lines.append("  "+"┌" + "───┬" * 7 + "───┐")
    for r in range(8):
        row_cells = " │ ".join(piece_symbols[cell] for cell in board[r])
        lines.append(f"{r} │ {row_cells} │")
        if r < 7: lines.append("  "+"├" + "───┼" * 7 + "───┤")
        else: lines.append("  "+"└" + "───┴" * 7 + "───┘")
    return "\n".join(lines)
