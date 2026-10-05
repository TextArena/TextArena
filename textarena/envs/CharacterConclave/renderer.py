def create_board_str(game_state: dict) -> str:
    lines = []
    if game_state.get("phase", "unknown") == "discussion":
        lines.append("┌─ CHARACTER CONCLAVE ──────── Phase: Discussion ──────────────────────────┐")
        lines.append("│ Player ID │ Characters Remaining                                         │")
        lines.append("├───────────┼──────────────────────────────────────────────────────────────┤")
        for pid in sorted(game_state.get("budget_remaining", {}).keys()):
            remaining = game_state.get("budget_remaining", {})[pid]
            lines.append(f"│    {pid:<7}│ {remaining:<61}│")
        lines.append("└──────────────────────────────────────────────────────────────────────────┘")
    elif game_state.get("phase", "unknown") == "voting":
        lines.append("┌─ CHARACTER CONCLAVE ──────────── Phase: Voting ──────────────────────────┐")
        lines.append("│ Players who have voted:                                                  │")
        voted = set(game_state.get("votes", {}).keys())
        for pid in sorted(game_state.get("budget_remaining", {}).keys()):
            mark = "✔" if pid in voted else " "
            lines.append(f"│   [{mark}] Player {pid:<2}                                                          │")
        lines.append("├──────────────────────────────────────────────────────────────────────────┤")
        lines.append("│ Waiting for all players to submit their votes...                         │")
        lines.append("└──────────────────────────────────────────────────────────────────────────┘")
    elif game_state.get("phase", "unknown") == "finished":
        lines.append("┌─ CHARACTER CONCLAVE ──────────── Final Vote Count ───────────────────────┐")
        tally = game_state.get("final_vote_counts", {})
        for pid in sorted(game_state.get("budget_remaining", {}).keys()):
            lines.append(f"│   Player {pid}: {tally.get(pid, 0)} vote(s)                                                    │")
        lines.append("└──────────────────────────────────────────────────────────────────────────┘")
    else:
        lines.append("┌─ CHARACTER CONCLAVE ─────────────────────────────────────────────────────┐")
        lines.append("│ Unknown game phase.                                                      │")
        lines.append("└──────────────────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)
