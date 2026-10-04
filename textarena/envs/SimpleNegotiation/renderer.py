def create_board_str(player_resources, player_values, inventory_values, current_offer, viewer_id: int) -> str:
    def render_inventory(player_id):
        header = f"┌──────────────────────────── Player {player_id} Inventory ─────────────────────────────┐\n"
        if player_id != viewer_id:
            body = "│                       Inventory and values are private.                      │\n"
            footer = "└─────────────────────────────────────────────────────────────────────────────┘\n"
            return header + body + footer
        body = "│ Resource    Qty   Value                                                     │\n"
        body += "│ ─────────────────────────────────────────────────────────────────────────── │\n"
        for res in ["Wheat", "Wood", "Sheep", "Brick", "Ore"]:
            qty = player_resources[player_id][res]
            val = player_values[player_id][res]
            body += f"│ {res:<10} {qty:<5} {val:<5}                                                      │\n"
        body += "│                                                                             │\n"
        total = inventory_values[player_id]["current"]
        change = inventory_values[player_id].get("change", 0)
        change_str = f" ({'+' if change > 0 else ''}{change})" if change != 0 else ""
        body += f"│                    Total Portfolio Value: {total:<5}{change_str:<25}    │\n"
        footer = "└─────────────────────────────────────────────────────────────────────────────┘\n"
        return header + body + footer
    def render_offer():
        lines = ["┌─────────────────────────────── Current Offer ───────────────────────────────┐"]
        if current_offer and (current_offer.get('offered_resources') or current_offer.get('requested_resources')):
            proposer = current_offer["from_player"]
            recipient = current_offer["to_player"]
            lines.append(f"│ Player {proposer} offers:                                                            │")
            for res, qty in current_offer.get('offered_resources', {}).items(): lines.append(f"│   - {qty} {res:<10}                                                            │")
            lines.append("│                                                                             │")
            lines.append("│ In exchange for:                                                            │")
            for res, qty in current_offer.get('requested_resources', {}).items(): lines.append(f"│   - {qty} {res:<10}                                                            │")
            lines.append("│                                                                             │")
            lines.append(f"│ Player {recipient}'s turn to respond: Accept or Deny                                  │")
        else:
            lines.append("│                                                                             │")
            lines.append("│                      No current offer on the table                          │")
            lines.append("│                                                                             │")
        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        return "\n".join(lines)
    return "\n".join([render_inventory(0), "", render_inventory(1), "", render_offer()])
