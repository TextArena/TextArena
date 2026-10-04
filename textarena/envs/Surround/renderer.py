from typing import Dict, Any

def create_board_str(width: int, height: int, game_state: Dict[str, Any]) -> str:
    board = [['.' for _ in range(width)] for _ in range(height)]
    trail_data = game_state["board"] # Fill in trails
    for y in range(height):
        for x in range(width):
            if trail_data[y][x] is not None: board[y][x] = '#'
    for pid, pdata in game_state["players"].items(): # Fill in live player heads
        alive = pdata.alive if hasattr(pdata, "alive") else pdata["alive"]
        if alive:
            position = pdata.position if hasattr(pdata, "position") else pdata["position"]
            px, py = position
            board[py][px] = format(pid, 'X')  # Hex digit for player ID
    lines = []
    content_width = width * 2 - 1
    border_line = "+" + "-" * (content_width + 2) + "+"
    lines.append(border_line)
    for row_idx in range(height - 1, -1, -1):
        row_str = " ".join(board[row_idx])
        lines.append(f"| {row_str} |")
    lines.append(border_line)
    return "\n".join(lines)
