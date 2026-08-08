from typing import Optional, List, Dict

BOARD_WIDTH = 80  # inner width (without the border chars)

def fmt_line(content: str) -> str:
    """Format a line to fit inside │ … │ with consistent width."""
    return f"│ {content.ljust(BOARD_WIDTH-2)} │"

def create_board_str(
    pool: int,
    current_offer: Optional[int],
    game_phase: str,
    round_number: int,
    total_rounds: int,
    player_totals: Dict[int, int],
    round_history: List[Dict],
    current_proposer: int,
) -> str:
    lines = []

    # Header
    lines.append("┌" + "─" * BOARD_WIDTH + "┐")
    lines.append(fmt_line("ITERATED ULTIMATUM GAME".center(BOARD_WIDTH-2)))
    lines.append("├" + "─" * BOARD_WIDTH + "┤")
    lines.append(fmt_line(f"Round {round_number}/{total_rounds}     Pool this round: ${pool}"))
    lines.append("└" + "─" * BOARD_WIDTH + "┘")
    lines.append("")

    # Player totals
    lines.append("┌" + "─" * BOARD_WIDTH + "┐")
    lines.append(fmt_line(f"Player 0: ${player_totals[0]}     Player 1: ${player_totals[1]}"))
    lines.append("└" + "─" * BOARD_WIDTH + "┘")
    lines.append("")

    # Current status
    current_responder = 1 - current_proposer
    lines.append("┌" + "─" * BOARD_WIDTH + "┐")
    lines.append(fmt_line(f"Proposer:  Player {current_proposer} (has ${pool} to split)"))
    lines.append(fmt_line(f"Responder: Player {current_responder} (decides on offer)"))
    if game_phase == "offering":
        lines.append(fmt_line(f"Phase: OFFERING - Waiting for Player {current_proposer}'s offer"))
    else:
        lines.append(fmt_line(f"Phase: RESPONDING - Waiting for Player {current_responder}'s decision"))
    lines.append("└" + "─" * BOARD_WIDTH + "┘")
    lines.append("")

    # Current offer
    lines.append("┌" + "─" * BOARD_WIDTH + "┐")
    if current_offer is not None:
        lines.append(fmt_line(f"Player {current_proposer} offers: ${current_offer} to Player {current_responder}"))
        lines.append(fmt_line(f"Player {current_proposer} keeps:  ${pool - current_offer}"))
        lines.append(fmt_line(""))
        lines.append(fmt_line(f"Player {current_responder}'s turn to respond: [Accept] or [Reject]"))
    else:
        lines.append(fmt_line("No current offer pending"))
    lines.append("└" + "─" * BOARD_WIDTH + "┘")
    lines.append("")

    # Rules
    lines.append("┌" + "─" * BOARD_WIDTH + "┐")
    rules = [
        "• Players alternate as Proposer/Responder each round",
        "• Each round: Proposer offers part of the pool to Responder",
        "• Responder can ACCEPT (both get their shares) or REJECT (both get $0)",
        "• Money accumulates across rounds - highest total wins!",
    ]
    for r in rules:
        lines.append(fmt_line(r))
    lines.append("└" + "─" * BOARD_WIDTH + "┘")

    return "\n".join(lines)
