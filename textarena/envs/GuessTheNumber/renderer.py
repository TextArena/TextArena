def create_board_str(game_state: dict, reveal_answer: bool = False) -> str:
    guess_history = game_state.get("guess_history", [])
    target = game_state.get("game_number", "?") if reveal_answer else "?"

    lines = ["┌─ GUESS HISTORY ──────────────────┐", "│                                  │"]

    for i, (guess, hint) in enumerate(guess_history, 1):
        arrow = "↑ Higher" if hint == "higher" else "↓ Lower" if hint == "lower" else "✓ Correct"
        lines.append(f"│  Guess #{i}: {guess:<5} {arrow:<15} │")

    if not guess_history:
        lines.append("│                                  │")

    lines.append("│                                  │")
    lines.append(f"│  Target Number: {str(target).ljust(17)}│")
    lines.append("└──────────────────────────────────┘")

    return "\n".join(lines)
