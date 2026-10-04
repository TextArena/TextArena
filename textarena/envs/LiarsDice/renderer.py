from typing import Dict, Any, List, Optional, Tuple

def create_board_str(game_state: Dict[str, Any], player_id: Optional[int] = None) -> str:
    def draw_dice_row(dice: List[int]) -> Tuple[str, str, str]:
        tops = "   " + "  ".join("┌───┐" for _ in dice)
        faces = "   " + "  ".join(f"│ {d} │" for d in dice)
        bottoms = "   " + "  ".join("└───┘" for _ in dice)
        return tops, faces, bottoms

    def draw_player_box(player_id: int, dice: List[int]) -> str:
        top_border = f"┌─ PLAYER {player_id} ─{'─' * 26}┐"
        empty_line = "│" + " " * (len(top_border) - 2) + "│"
        tops, faces, bottoms = draw_dice_row(dice)
        return "\n".join([top_border, empty_line, f"│ {tops:<{len(top_border)-4}} │", f"│ {faces:<{len(top_border)-4}} │", f"│ {bottoms:<{len(top_border)-4}} │", empty_line, f"└{'─' * (len(top_border) - 2)}┘"])

    lines = []
    if len(game_state.get("remaining_dice", {})) <= 5:
        for pid in range(len(game_state.get("remaining_dice", {}))):
            if game_state.get("remaining_dice", {}).get(pid, 0) == 0: continue
            if pid == player_id:
                dice = game_state.get("dice_rolls", {}).get(pid, [])
                lines.append(draw_player_box(pid, dice))
            else:
                count = game_state.get("remaining_dice", {})[pid]
                lines.append(f"Player {pid}: {count} hidden die/dice")
            lines.append("")
    else: # Compact summary for > 5 players
        lines.append("Players & Dice:")
        for pid in range(len(game_state.get("remaining_dice", {}))):
            if game_state.get("remaining_dice", {}).get(pid, 0) == 0:
                continue
            dice = game_state.get("dice_rolls", {}).get(pid, []) if pid == player_id else []
            dice_str = " ".join(str(d) for d in dice) if pid == player_id else "[hidden]"
            lines.append(f"  Player {pid} ({game_state.get('remaining_dice', {})[pid]} dice): {dice_str}")
        lines.append("")
    q = game_state.get("current_bid", {"quantity": 0, "face_value": 0}).get("quantity", 0)
    f = game_state.get("current_bid", {"quantity": 0, "face_value": 0}).get("face_value", 0)
    bid_box = f"""
┌─────────────────────────┐
│ Current Bid: {q} × face {f:<2}│
└─────────────────────────┘
""".strip()
    lines.append(bid_box)
    return "\n".join(lines)
