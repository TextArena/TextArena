from typing import Optional


def create_board_str(game_state: dict, viewer_id: Optional[int] = None, reveal_all: bool = False) -> str:
    lines = []
    lines.append(f"╭── SIMPLE BLIND AUCTION ───── Phase: {game_state.get('phase', '').capitalize():<10} | Round: {game_state.get('round', 0)} ──────────────────────╮")
    lines.append("│ Item │ Item Name                                                     │ Base Value │")
    lines.append("├──────┼───────────────────────────────────────────────────────────────┼────────────┤")
    for idx, (name, val) in enumerate(zip(game_state.get("item_names", []), game_state.get("base_item_values", []))): lines.append(f"│ {idx:^4} │ {name:<61} │ {val:>10} │")
    lines.append("╰───────────────────────────────────────────────────────────────────────────────────╯")
    lines.append("┌─ PLAYER-SPECIFIC ITEM VALUES ────────────────────────────────────────────────────┐")
    header_str = " ".join([f"I{idx:<2}" for idx in range(len(game_state.get("item_names", [])))])
    lines.append("│ Player │ " + f"{header_str:<72}" + "│")
    lines.append("├────────┼─────────────────────────────────────────────────────────────────────────┤")
    for pid in [0, 1]:
        if reveal_all or pid == viewer_id:
            value_str = " ".join(f"{game_state.get('player_item_values', {})[pid][i]:<4}" for i in range(len(game_state.get("item_names", []))))
        else:
            value_str = "(private)"
        lines.append(f"│   {pid:<4} │ {value_str:<72}│")
    lines.append("└──────────────────────────────────────────────────────────────────────────────────┘")
    lines.append("┌─ PLAYER CAPITAL ────────────┐")
    for pid in [0, 1]:
        cap = game_state.get("remaining_capital", {}).get(pid, 0)
        lines.append(f"│ Player {pid}: {cap:<6} coins      │")
    lines.append("└─────────────────────────────┘")
    if game_state.get("phase", "") == "bidding":
        lines.append("┌──── PLAYER BIDS ───────────────────────────────────┐")
        header_str = " ".join([f"I{idx:<2}" for idx in range(len(game_state.get("item_names", [])))])
        lines.append("│ Player │ " + f"{header_str:<42}" + "│")
        lines.append("├────────┼───────────────────────────────────────────┤")
        for pid in [0, 1]:
            if reveal_all or pid == viewer_id:
                bids = game_state.get("player_bids", {}).get(pid, {})
                bid_str = " ".join(f"{bids.get(i, 0):<4}" for i in range(len(game_state.get("item_names", []))))
            else:
                bid_str = "(sealed)"
            lines.append(f"│   {pid:<4} │ {bid_str:<42}│")
        lines.append("└────────────────────────────────────────────────────┘")
    return "\n".join(lines)
