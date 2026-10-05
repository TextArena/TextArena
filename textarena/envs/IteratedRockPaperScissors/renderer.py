from typing import Dict, Any
def create_board_str(game_state: Dict[str, Any]) -> str:
    emoji_map = {"rock": "🪨", "paper": "📄", "scissors": "✂️ ", None: "❓"}
    round_num = game_state.get("round", 1)
    points = game_state.get("points", {0: 0, 1: 0})
    history = game_state.get("history", [])
    lines = []
    lines.append(f"🏁 Round: {round_num} / {game_state.get('num_rounds', '?')}")
    lines.append(f"📊 Score: Player 0 = {points[0]} | Player 1 = {points[1]}")
    lines.append("")
    if history:
        lines.append("📜 History:")
        for i, (hist_dict) in enumerate(history, 1): lines.append(f"  Round {i}: Player 0 {emoji_map[hist_dict[0]]} vs Player 1 {emoji_map[hist_dict[1]]}")
    else: lines.append("📜 No rounds completed yet.")
    return "\n".join(lines)
