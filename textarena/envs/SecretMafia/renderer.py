def create_board_str(game_state: dict) -> str:
    phase = game_state.get("phase", "Unknown")
    phase_name = getattr(phase, "value", str(phase))
    lines = []
    lines.append(f"SECRET MAFIA — Phase: {phase_name} | Day: {game_state.get('day_number', 0)}")
    lines.append("Player Status")
    for pid in sorted(game_state.get("player_roles", {})):
        alive = pid in set(game_state.get('alive_players', []))
        status = "🟢 Alive" if alive else "⚫️ Dead "
        lines.append(f"- Player {pid}: {status}")
    if phase_name == "Day-Voting":
        lines.append("\n🗳️ VOTES")
        if game_state.get("votes", {}):
            for voter, target in sorted(game_state.get("votes", {}).items()): lines.append(f" - Player {voter} ➜ Player {target}")
        else: lines.append(" - No votes have been cast yet.")
    return "\n".join(lines)
