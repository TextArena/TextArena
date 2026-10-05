from typing import Any, Dict

def create_board_str(game_state: Dict[str, Any]) -> str:
    board = game_state.get("board", [])
    scores = game_state.get("scores", {})
    grid_size = len(board)
    matched_positions = set(game_state.get("matched_positions", set()))

    # Header row
    output = ["🧠 Memory Game", "  " + " ".join(f"{c:2}" for c in range(grid_size))]

    # Board rows
    for r in range(grid_size):
        row = f"{r:2} "
        for c in range(grid_size):
            cell = board[r][c]
            if (r, c) in matched_positions:
                row += f"{cell:2} "
            else:
                row += "🔲 "
        output.append(row)

    # Scores
    output.append("\n📊 Scores:")
    for player_id, score_obj in scores.items():
        output.append(f"Player {player_id}: {score_obj['Score']} point(s)")

    return "\n".join(output)
