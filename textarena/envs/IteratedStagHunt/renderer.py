def create_board_str(game_state: dict) -> str:
    """Create a secrecy-safe board for the Iterated Stag Hunt."""
    phase = game_state["phase"]
    round_number = game_state["round"]
    total_rounds = game_state["num_rounds"]
    scores = game_state["total_payoff"]
    payoffs = game_state["payoffs"]
    decisions = game_state["decisions"]

    lines = [
        "ITERATED STAG HUNT",
        f"Round {round_number}/{total_rounds} | Phase: {phase}",
        f"Scores: Player 0 = {scores[0]} | Player 1 = {scores[1]}",
        (
            "Payoffs: both stag "
            f"{payoffs.get('mutual_stag', '?')}, both hare {payoffs.get('mutual_hare', '?')}, "
            f"mixed stag/hare {payoffs.get('single_stag', '?')}/{payoffs.get('single_hare', '?')}"
        ),
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

    history = game_state.get("history", [])
    if history:
        lines.append("History:")
        for item in history:
            lines.append(
                f"  Round {item['round']}: P0 {item['decisions'][0]}, "
                f"P1 {item['decisions'][1]} "
                f"(+{item['payoffs'][0]}/+{item['payoffs'][1]})"
            )
    return "\n".join(lines)