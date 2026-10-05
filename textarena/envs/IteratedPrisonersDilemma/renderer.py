def create_board_str(game_state: dict) -> str:
    """Create a board without revealing a pending simultaneous decision."""
    phase = game_state["phase"]
    scores = game_state["scores"]
    decisions = game_state["decisions"]
    lines = [
        "ITERATED PRISONER'S DILEMMA",
        f"Round {game_state['round']}/{game_state['num_rounds']} | Phase: {phase}",
        f"Scores: Player 0 = {scores[0]} | Player 1 = {scores[1]}",
    ]
    if phase == "conversation":
        lines.append(
            f"Communication cycle {game_state['conversation_round'] + 1}/"
            f"{game_state['total_conversation_rounds']}"
        )
    else:
        submitted = [pid for pid, decision in decisions.items() if decision is not None]
        lines.append(
            "Decisions submitted: "
            + (", ".join(f"Player {pid}" for pid in submitted) if submitted else "none")
        )
    if game_state["history"]:
        lines.append("History:")
        for item in game_state["history"]:
            lines.append(
                f"  Round {item['round']}: P0 {item['decisions'][0]}, "
                f"P1 {item['decisions'][1]} "
                f"(+{item['payoffs'][0]}/+{item['payoffs'][1]})"
            )
    return "\n".join(lines)
