def render_players_list(player_roles: dict) -> str:
    """Render the player list in a clean, text-friendly format."""
    role_icons = {
        "Servant":  "🧑‍🌾 Servant",
        "Merlin":   "🧙 Merlin",
        "Percival": "🛡️ Percival",
        "Minion":   "😈 Minion",
        "Morgana":  "👹 Morgana",
        "Mordred":  "🔥 Mordred",
        "Oberon":   "👺 Oberon",
    }

    lines = []
    for pid in sorted(player_roles):
        role = player_roles[pid]
        icon = role_icons.get(role, role)
        team = "😇 Good" if role in {"Servant", "Merlin", "Percival"} else "😈 Evil"
        lines.append(f"  • Player {pid}: {icon} ({team})")
    return "\n".join(lines)


def render_mission_summary(game_state: dict) -> str:
    """Render the current mission progress and leader info."""
    mission_successes = game_state.get("mission_successes", 0)
    mission_failures = game_state.get("mission_failures", 0)
    consecutive_fails = game_state.get("consecutive_failed_team_proposals", 0)
    leader_pid = game_state.get("leader_pid", None)

    lines = []
    lines.append("🏰 **Mission Progress**")
    lines.append(f"  ✅ Successes: {mission_successes}")
    lines.append(f"  ❌ Failures: {mission_failures}")
    lines.append(f"  🚫 Failed team proposals: {consecutive_fails}/5")
    if leader_pid is not None:
        lines.append(f"  👑 Current Leader: Player {leader_pid}")
    return "\n".join(lines)


def render_proposed_team(game_state: dict) -> str:
    """Render the current team proposal."""
    team_proposal = game_state.get("team_proposal", [])
    lines = ["🧩 **Proposed Team:**"]
    if team_proposal:
        team_str = ", ".join(f"Player {p}" for p in team_proposal)
        lines.append(f"  {team_str}")
    else:
        lines.append("  None yet")
    return "\n".join(lines)


def render_votes_section(game_state: dict) -> str:
    """Render votes if in the voting phase."""
    phase = str(game_state.get("phase", "")).lower()
    votes = game_state.get("votes", {})
    if "voting" not in phase:
        return ""
    lines = ["🗳️ **Team Votes:**"]
    if votes:
        for voter, choice in sorted(votes.items()):
            lines.append(f"  • Player {voter}: {choice.capitalize()}")
    else:
        lines.append("  No votes yet.")
    return "\n".join(lines)


def render_mission_actions(game_state: dict) -> str:
    """Render mission actions if in the mission phase."""
    phase = str(game_state.get("phase", "")).lower()
    actions = game_state.get("mission_actions", {})
    if "mission" not in phase:
        return ""
    lines = ["⚔️ **Mission Actions:**"]
    if actions:
        for pid, action in sorted(actions.items()):
            lines.append(f"  • Player {pid}: {action.capitalize()}")
    else:
        lines.append("  No mission actions yet.")
    return "\n".join(lines)


def render_merlin_guess(game_state: dict) -> str:
    """Render the Merlin guess phase."""
    phase = str(game_state.get("phase", "")).lower()
    guess_phase = game_state.get("guess_merlin_phase", False)
    guesses = game_state.get("merlin_guesses", {})
    if not guess_phase and "guess_merlin" not in phase:
        return ""
    lines = ["🎯 **Merlin Guess Phase:**"]
    if guesses:
        for pid, guess in sorted(guesses.items()):
            lines.append(f"  • Player {pid} guessed Player {guess}")
    else:
        lines.append("  No guesses submitted yet.")
    return "\n".join(lines)


def render_game_state(game_state: dict, show_players: bool = False) -> str:
    """Main Avalon board renderer."""
    phase = str(game_state.get("phase", "Unknown"))
    mission_index = game_state.get("mission_index", 0)
    player_roles = game_state.get("player_roles", {})
    num_players = len(player_roles)

    lines = [
        f"🎲 **AVALON GAME STATUS**",
        f"🏁 Phase: {phase}",
        f"🧭 Mission: {mission_index + 1}/5",
        f"🎭 Players: {num_players} total",
    ]

    # Optional player list
    if show_players:
        lines.append("\n👥 **Players:**")
        lines.append(render_players_list(player_roles))

    # Core sections
    lines.append("\n" + render_mission_summary(game_state))
    lines.append("\n" + render_proposed_team(game_state))

    # Conditional sections
    votes = render_votes_section(game_state)
    if votes:
        lines.append("\n" + votes)

    mission_actions = render_mission_actions(game_state)
    if mission_actions:
        lines.append("\n" + mission_actions)

    merlin_guess = render_merlin_guess(game_state)
    if merlin_guess:
        lines.append("\n" + merlin_guess)

    return "\n".join(lines)
