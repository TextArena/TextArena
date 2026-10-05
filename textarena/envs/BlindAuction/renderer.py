from typing import Optional


def create_board_str(game_state: dict, viewer_id: Optional[int] = None, reveal_all: bool = False) -> str:
    item_names = game_state.get("item_names", [])
    base_values = game_state.get("base_item_values", [])
    player_values = game_state.get("player_item_values", {})
    remaining_capital = game_state.get("remaining_capital", {})
    player_bids = game_state.get("player_bids", {})
    phase = game_state.get("phase", "")
    round_num = game_state.get("round", 0)

    num_items = len(item_names)
    num_players = len(player_values)

    lines = []
    lines.append(f"┌─ BLIND AUCTION ────── Phase: {phase.capitalize()} | Round: {round_num} ──────┐")
    lines.append("│ Item ID │ Item Name                           │ Base Value │")
    lines.append("├─────────┼─────────────────────────────────────┼────────────┤")
    for idx, (name, val) in enumerate(zip(item_names, base_values)):
        lines.append(f"│   {idx:<5} │ {name:<35} │ {val:>10} │")
    lines.append("└────────────────────────────────────────────────────────────┘")

    # Subjective values table
    lines.append("┌─ PLAYER-SPECIFIC ITEM VALUES ─────────────────────────────────────────────┐")
    header = "│ Player │ " + " ".join([f"I{idx:<3}" for idx in range(num_items)])
    lines.append(f"{header:<76}│")
    lines.append("├────────┼──────────────────────────────────────────────────────────────────┤")
    for pid in range(num_players):
        if reveal_all or pid == viewer_id:
            values = " ".join(f"{player_values[pid][i]:<4}" for i in range(num_items))
        else:
            values = "(private)"
        line_str = f"│   {pid:<4} │ {values}"
        lines.append(f"{line_str:<76}│")
    lines.append("└" + "─" * (len(lines[-1]) - 2) + "┘")

    # Player capital
    lines.append("┌─ PLAYER CAPITAL ──────────────────┐")
    for pid in range(num_players):
        cap = remaining_capital.get(pid, 0)
        lines.append(f"│ Player {pid:<2}: {cap:<6} coins{' ' * 11}│")
    lines.append("└───────────────────────────────────┘")

    # Player bids table (structured)
    if phase == "bidding":
        lines.append("┌─ PLAYER BIDS ─────────────────────────────────────────────────────────────┐")
        header = "│ Player │ " + " ".join([f"I{idx:<3}" for idx in range(num_items)]) #+ "│"

        lines.append(f"{header:<76}│")
        lines.append("├────────┼──────────────────────────────────────────────────────────────────┤")
        for pid in range(num_players):
            if reveal_all or pid == viewer_id:
                bids = game_state["player_bids"].get(pid, {})
                bid_row = " ".join(f"{bids.get(i, 0):<4}" for i in range(num_items))
            else:
                bid_row = "(sealed)"
            line_str = f"│   {pid:<4} │ {bid_row}"
            lines.append(f"{line_str:<76}│")
        lines.append("└───────────────────────────────────────────────────────────────────────────┘")

    return "\n".join(lines)
