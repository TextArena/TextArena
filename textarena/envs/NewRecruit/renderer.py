from typing import Any, Dict, List


def create_board_str(
    game_state: Dict[str, Any],
    player_id: int,
    issues: List[str],
    point_value_dict: Dict[str, Dict[str, List[int]]],
    letter_choices: Dict[str, Dict[str, str]],
    turn: int,
    max_turns: int,
) -> str:
    """The acting player's view: turn counter and the proposal on the table, scored with their own points only."""
    roles = game_state["roles"]
    lines = [f"NEW RECRUIT - Turn {turn} of {max_turns} - You are Player {player_id} ({roles[player_id]})"]
    proposal = game_state["current_proposal"]
    if proposal is None:
        lines.append("No proposal is on the table.")
        lines.append("Write your rationale, then put 'Propose' and 8 letters (A-E) on the last line, e.g. 'Propose CCAACCCC'.")
        return "\n".join(lines)

    proposer_id = proposal["proposer_id"]
    sequence = "".join(letter_choices[issue][proposal["choices"][issue]] for issue in issues)
    lines.append(f"Proposal on the table from Player {proposer_id} ({roles[proposer_id]}): Propose {sequence}")
    total = 0
    for issue in issues:
        choice = proposal["choices"][issue]
        points = point_value_dict[issue][choice][player_id]
        total += points
        lines.append(f"  - {issue}: {letter_choices[issue][choice]}. {choice} ({points} points for you)")
    lines.append(f"  Total for you: {total} points")
    if proposer_id != player_id:
        lines.append("Reply 'Accept' or 'Reject', or make a counterproposal (rationale, then 'Propose XXXXXXXX' on the last line).")
    return "\n".join(lines)
