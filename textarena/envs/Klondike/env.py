from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

from .klondike import KlondikeGame


class KlondikeEnv(ta.GameEnv):
    """Environment for Klondike Solitaire"""

    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    error_allowance = 5
    max_action_chars = 4096

    def __init__(self, max_turns: int = 200, draw_count: int = 1):
        """
        Args:
            max_turns: Maximum number of turns before game ends
            draw_count: Number of cards to draw from stock (1 or 3)
        """
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        if (
            not isinstance(draw_count, int)
            or isinstance(draw_count, bool)
            or draw_count not in (1, 3)
        ):
            raise ValueError("draw_count must be either 1 or 3")
        self.max_turns = max_turns
        self.draw_count = draw_count

    @property
    def klondike(self) -> KlondikeGame:
        return self.game_state["klondike"]

    def setup(self) -> Dict[str, Any]:
        return {
            "turn_count": 0,
            "game_won": False,
            "klondike": KlondikeGame(seed=self.rng.getrandbits(64), draw_count=self.draw_count),
        }

    def prompt(self, player_id: int) -> str:
        drawn = "the next card" if self.draw_count == 1 else f"the next {self.draw_count} cards"
        return (
            "You are playing Klondike Solitaire. Your goal is to move all 52 cards to the foundation piles.\n\n"
            "Game Rules:\n"
            "- Foundation piles (F1-F4): Build up from Ace to King in suit; any empty foundation accepts an Ace\n"
            "- Tableau piles (T1-T7): Build down alternating colors (red on black, black on red)\n"
            f"- Stock: 'draw' turns {drawn} from the stock onto the waste; when the stock is empty, "
            "it first turns the whole waste back over into the stock (unlimited passes)\n"
            "- Waste (W): Top card available for play\n\n"
            "Commands:\n"
            "- 'draw' - Draw cards from stock to waste\n"
            "- 'move <source> <destination> [count]' - Move cards between piles\n"
            "  Examples: 'move W T1', 'move T1 F2', 'move T3 T5 2'. count can also be 'all', which will try to move all face-up cards.\n"
            "- 'forfeit' - End the game immediately and lock in your current score\n"
            "- Pile names: W (waste), F1-F4 (foundations), T1-T7 (tableau)\n\n"
            "You can execute multiple actions in one turn by separating them with commas:\n"
            "  Example: 'draw, move W T1, move T2 F1'\n\n"
            "Only Kings can be placed on empty tableau piles.\n"
            "Actions execute in order - if one fails, the remaining actions are skipped.\n"
            f"You have {self.max_turns} turns; each reply counts as one turn, however many actions it contains.\n"
            "Your score is the number of cards on the foundations (52 for a win). The game ends when you win, "
            "forfeit, or run out of turns.\n"
            "Use 'forfeit' if you believe the game is impossible to win."
        )

    def render(self, player_id: int) -> str:
        return self._render_board()

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        # Parse and execute multiple actions (comma-separated)
        success, messages, is_format_error = self._execute_actions(move.strip())

        if not success:
            if is_format_error:
                # Format/syntax errors are invalid moves
                return self.invalid(messages[0])
            # Legal moves that fail are just unsuccessful, not invalid
            self.game_state["turn_count"] += 1
            for message in messages:
                self.broadcast(message, ta.ObservationType.GAME_MESSAGE)
            return None

        self.game_state["turn_count"] += 1

        # Check for forfeit action
        forfeit_requested = any("FORFEIT" in message for message in messages)

        if forfeit_requested:
            # Player forfeited - end game with current score
            cards_in_foundations = self._cards_in_foundations()
            return self.outcome(
                {0: cards_in_foundations},
                reason=f"Game forfeited. Final score: {cards_in_foundations} cards in foundations.",
            )

        # Normal message processing
        for message in messages:
            if message and message != "FORFEIT":
                self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

        # Check if game is won
        if self.klondike.is_won():
            self.game_state["game_won"] = True
            return self.outcome({0: 52}, reason="Congratulations! You've won Klondike Solitaire!")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        # Partial reward based on cards in foundations (1 point per card)
        cards_in_foundations = self._cards_in_foundations()
        return self.outcome(
            {0: cards_in_foundations},
            reason=f"Game over! You reached the maximum of {self.max_turns} turns. Score: {cards_in_foundations} cards in foundations.",
        )

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        cards_in_foundations = self._cards_in_foundations()
        return self.outcome(
            {0: cards_in_foundations},
            reason=f"Invalid Move: {reason} Final score: {cards_in_foundations} cards in foundations.",
        )

    def _cards_in_foundations(self) -> int:
        return sum(len(pile) for pile in self.klondike.foundations)

    def _execute_actions(self, action: str) -> Tuple[bool, List[str], bool]:
        """Execute multiple comma-separated actions and return (success, messages, is_format_error)"""
        action = action.strip()

        if not action:
            return (
                False,
                ["Empty command. Type 'draw' or 'move <source> <destination>'; add an optional card count at the end."],
                True,
            )

        action_list = [act.strip() for act in action.split(",")]
        if any(not act for act in action_list):
            return False, ["Empty action in comma-separated command."], True

        # Validate the complete batch before applying anything. GameEnv requires
        # actions returning Invalid to leave game state untouched.
        for i, single_action in enumerate(action_list):
            format_error = self._validate_action_format(single_action)
            if format_error is not None:
                return False, [f"Action {i + 1}: {format_error}"], True
        if len(action_list) > 1 and any(
            act.lower().split()[0] == "forfeit" for act in action_list
        ):
            return False, ["Forfeit must be submitted as the only action."], True

        messages = []

        for i, single_action in enumerate(action_list):
            success, message, is_format_error = self._execute_single_action(
                single_action
            )

            if not success:
                if is_format_error:
                    # Format error - return immediately with format error
                    return False, [f"Action {i + 1}: {message}"], True
                else:
                    # Game rule violation - add message and stop executing further actions
                    messages.append(f"Action {i + 1} failed: {message}")
                    if i > 0:
                        messages.insert(0, f"Executed {i} action(s) before failure.")
                    return False, messages, False
            else:
                # Success - add message and continue
                messages.append(f"Action {i + 1}: {message}")
                if self.klondike.is_won():
                    # The game is over the moment the last card reaches a foundation.
                    break

        return True, messages, False

    def _validate_action_format(self, action: str) -> Optional[str]:
        """Return a syntax error without mutating state, or ``None``."""
        parts = action.split()
        if not parts:
            return "Empty action"
        command = parts[0].lower()
        if command in ("draw", "forfeit"):
            if len(parts) != 1:
                return f"'{command}' does not accept arguments"
            return None
        if command != "move":
            return (
                f"Unknown command '{parts[0]}'. Use 'draw', "
                "'move <source> <destination> [count]', or 'forfeit'"
            )
        if len(parts) not in (3, 4):
            return (
                "Move command usage: "
                "'move <source> <destination> [count]'"
            )
        if self._parse_pile(parts[1])[0] == "?" or self._parse_pile(parts[2])[0] == "?":
            return "Invalid pile name. Use W, F1-F4, or T1-T7"
        if len(parts) == 4:
            if parts[3].lower() == "all":
                return None
            try:
                count = int(parts[3])
            except ValueError:
                return "Invalid count. Use a positive number or 'all'"
            if count <= 0:
                return "Count must be positive or 'all'"
        return None

    def _execute_single_action(self, action: str) -> Tuple[bool, str, bool]:
        """Execute a single action and return (success, message, is_format_error)"""
        parts = action.lower().split()
        if not parts:
            return False, "Empty action", True

        command = parts[0]

        if command == "draw":
            if len(parts) != 1:
                return False, "'draw' does not accept arguments", True
            if self.klondike.draw():
                return True, "Drew card(s) from stock to waste.", False
            else:
                return False, "Cannot draw. Both stock and waste are empty.", False

        elif command == "forfeit":
            if len(parts) != 1:
                return False, "'forfeit' does not accept arguments", True
            # Special action that triggers game end with current score
            return True, "FORFEIT", False

        elif command == "move":
            if len(parts) not in (3, 4):
                return (
                    False,
                    "Move command usage: 'move <source> <destination> [count]'",
                    True,
                )

            source = parts[1].upper()
            destination = parts[2].upper()
            count = 1

            if len(parts) > 3:
                try:
                    if parts[3].lower() == "all":
                        count = -1  # Special value for moving all face-up cards
                    else:
                        count = int(parts[3])
                        if count <= 0:
                            return False, "Count must be positive or 'all'", True
                except ValueError:
                    return False, "Invalid count. Use a number or 'all'", True

            success, message = self._execute_move(source, destination, count)
            return success, message, False  # Move attempts are never format errors

        else:
            return (
                False,
                f"Unknown command '{command}'. Use 'draw', 'move <source> <destination> [count]', or 'forfeit'",
                True,
            )

    def _execute_move(
        self, source: str, destination: str, count: int
    ) -> Tuple[bool, str]:
        """Execute a move command"""
        src_type, src_idx = self._parse_pile(source)
        dst_type, dst_idx = self._parse_pile(destination)

        if src_type == "?" or dst_type == "?":
            return False, "Invalid pile name. Use W, F1-F4, or T1-T7"

        # Move to foundation
        if dst_type == "F":
            if count != 1:
                return False, "Can only move 1 card to foundation"

            if src_type == "W":
                if self.klondike.move_from_waste_to_foundation_at(dst_idx):
                    return True, f"Moved card from waste to foundation F{dst_idx + 1}"
                else:
                    return False, "Cannot move waste card to that foundation pile"

            elif src_type == "T":
                if self.klondike.move_from_tableau_to_foundation_at(src_idx, dst_idx):
                    return (
                        True,
                        f"Moved card from tableau T{src_idx + 1} to foundation F{dst_idx + 1}",
                    )
                else:
                    return False, "Cannot move tableau card to that foundation pile"

            else:
                return False, "Cannot move from foundation to foundation"

        # Move to tableau
        elif dst_type == "T":
            if src_type == "W":
                if count != 1:
                    return False, "Can only move 1 card from waste to tableau"

                if self.klondike.move_waste_to_tableau(dst_idx):
                    return True, f"Moved card from waste to tableau T{dst_idx + 1}"
                else:
                    return False, "Cannot place waste card on that tableau pile"

            elif src_type == "T":
                if count == -1:
                    # Move all face-up cards
                    src_pile = self.klondike.tableau[src_idx]
                    face_up_count = 0
                    for card, face_up in reversed(src_pile):
                        if not face_up:
                            break
                        face_up_count += 1
                    count = face_up_count

                if count <= 0:
                    return False, "No face-up cards to move"

                if self.klondike.move_tableau_to_tableau(src_idx, count, dst_idx):
                    return (
                        True,
                        f"Moved {count} card(s) from tableau T{src_idx + 1} to T{dst_idx + 1}",
                    )
                else:
                    return (
                        False,
                        f"Cannot move {count} card(s) from T{src_idx + 1} to T{dst_idx + 1}",
                    )

            elif src_type == "F":
                if count != 1:
                    return False, "Can only move 1 card from foundation to tableau"

                foundation_pile = self.klondike.foundations[src_idx]
                if not foundation_pile:
                    return False, f"Foundation F{src_idx + 1} is empty"

                card = foundation_pile[-1]
                dest_pile = self.klondike.tableau[dst_idx]
                dest_top_card = dest_pile[-1][0] if dest_pile else None

                if self.klondike.can_place_on_tableau(dest_top_card, card):
                    foundation_pile.pop()
                    dest_pile.append((card, True))
                    return (
                        True,
                        f"Moved card from foundation F{src_idx + 1} to tableau T{dst_idx + 1}",
                    )
                else:
                    return (
                        False,
                        f"Cannot place foundation card on tableau T{dst_idx + 1}",
                    )

        else:
            return False, "Cannot move to waste or stock"

    def _parse_pile(self, pile_str: str) -> Tuple[str, Optional[int]]:
        """Parse pile string into type and index"""
        pile_str = pile_str.upper()

        if pile_str == "W":
            return ("W", None)
        elif pile_str.startswith("F") and pile_str[1:].isdigit():
            idx = int(pile_str[1:])
            if 1 <= idx <= 4:
                return ("F", idx - 1)
        elif pile_str.startswith("T") and pile_str[1:].isdigit():
            idx = int(pile_str[1:])
            if 1 <= idx <= 7:
                return ("T", idx - 1)

        return ("?", None)

    def _render_board(self) -> str:
        """Render the current game board as a string"""
        lines = []
        lines.append("=== KLONDIKE SOLITAIRE ===")
        lines.append(f"Turn: {self.state.game_state['turn_count']}/{self.max_turns}")
        lines.append("")

        # Stock and waste
        stock_count = len(self.klondike.stock)
        waste_top = str(self.klondike.waste[-1][0]) if self.klondike.waste else "--"
        lines.append(f"Stock: {stock_count} cards")
        lines.append(f"Waste (W): {waste_top}")
        lines.append("")

        # Foundations
        lines.append("Foundations:")
        for i, pile in enumerate(self.klondike.foundations):
            cards_str = " ".join(str(c) for c in pile) if pile else "--"
            lines.append(f"  F{i + 1}: {cards_str}")
        lines.append("")

        # Tableau
        lines.append("Tableau:")
        for i, pile in enumerate(self.klondike.tableau):
            pile_str = ""
            for j, (card, face_up) in enumerate(pile):
                if j > 0:
                    pile_str += " "
                pile_str += str(card) if face_up else "XX"
            if not pile_str:
                pile_str = "--"
            lines.append(f"  T{i + 1}: {pile_str}")

        return "\n".join(lines)

    def get_board_str(self) -> str:
        """Return the current board state as a string for rendering"""
        if not hasattr(self, "state") or not self.state.game_state:
            return "Game not started"
        return self._render_board()
