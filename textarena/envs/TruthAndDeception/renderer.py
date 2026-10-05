def create_board_str(game_state: dict, reveal_answer: bool = False) -> str:
    lines = []
    lines.append("+" + "-" * 79 + "+")
    for label, key in (("Fact 1", "fact1"), ("Fact 2", "fact2")):
        status = "?"
        if reveal_answer:
            status = "✅" if game_state[key]["is_correct"] else "❌"
        lines.append("| {:<7} | {:<60} | {:^3} |".format(label, game_state[key]["fact"][:60], status))
    lines.append("+" + "-" * 79 + "+")
    lines.append("| {:<10} | {:<64} |".format("Player 0", "Deceiver"))
    lines.append("| {:<10} | {:<64} |".format("Player 1", "Guesser"))
    lines.append("+" + "-" * 79 + "+")
    return "\n".join(lines)
