from typing import Any, Dict, List, Optional, Tuple

import textarena as ta

from .klondike import KlondikeGame

# Internal sentinel for a forfeit action; never shown to the player.
FORFEIT = "FORFEIT"


class KlondikeEnv(ta.Env):
    """Environment for Klondike Solitaire"""

    def __init__(
        self, seed: Optional[int] = None, max_turns: int = 200, draw_count: int = 1
    ):
        """
        Args:
            seed: Random seed for reproducible games
            max_turns: Maximum number of turns before game ends
            draw_count: Number of cards to draw from stock (1 or 3)
        """
        self.seed = seed
        self.max_turns = max_turns
        self.draw_count = draw_count

    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the game state"""
        self.state = ta.SinglePlayerState(
            num_players=num_players,
            seed=seed,
            max_turns=self.max_turns,
            error_allowance=5,
        )

        # Create a new Klondike game
        game_seed = seed if seed is not None else self.seed
        self.klondike = KlondikeGame(seed=game_seed, draw_count=self.draw_count)

        game_state = {"turn_count": 0, "game_won": False}

        self.state.reset(
            game_state=game_state, player_prompt_function=self._generate_player_prompt
        )
        self._observe_state()

    def _generate_player_prompt(
        self, player_id: int, game_state: Dict[str, Any]
    ) -> str:
        return self.m("player_prompt", "intro")

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process a player action"""
        player_id = self.state.current_player_id
        self.state.add_observation(
            from_id=player_id,
            message=action,
            observation_type=ta.ObservationType.PLAYER_ACTION,
        )

        # Parse and execute multiple actions (comma-separated)
        success, messages, is_format_error = self._execute_actions(action.strip())

        if not success:
            if is_format_error:
                # Format/syntax errors are invalid moves
                self.state.set_invalid_move(reason=messages[0])
            else:
                # Legal moves that fail are just unsuccessful, not invalid
                self.state.game_state["turn_count"] += 1
                for message in messages:
                    self.state.add_observation(
                        message=message,
                        observation_type=ta.ObservationType.GAME_MESSAGE,
                    )
        else:
            self.state.game_state["turn_count"] += 1
            
            # Check for forfeit action
            forfeit_requested = any(message == FORFEIT for message in messages)

            if forfeit_requested:
                # Player forfeited - end game with current score
                cards_in_foundations = sum(len(pile) for pile in self.klondike.foundations)
                self.state.set_outcome(
                    reward=cards_in_foundations,
                    reason=self.m("outcome", "forfeit", score=cards_in_foundations),
                )
            else:
                # Normal message processing
                for message in messages:
                    if message and message != FORFEIT:
                        self.state.add_observation(
                            message=message,
                            observation_type=ta.ObservationType.GAME_MESSAGE,
                        )

                # Check if game is won
                if self.klondike.is_won():
                    self.state.game_state["game_won"] = True
                    self.state.set_outcome(
                        reward=52, reason=self.m("outcome", "won")
                    )
                elif self.state.game_state["turn_count"] >= self.max_turns:
                    # Partial reward based on cards in foundations (1 point per card)
                    cards_in_foundations = sum(
                        len(pile) for pile in self.klondike.foundations
                    )
                    self.state.set_outcome(
                        reward=cards_in_foundations,
                        reason=self.m("outcome", "turn_limit", max_turns=self.max_turns, score=cards_in_foundations),
                    )

            # Update board observation
            self._observe_state()

        return self.state.step()

    def _execute_actions(self, action: str) -> Tuple[bool, List[str], bool]:
        """Execute multiple comma-separated actions and return (success, messages, is_format_error)"""
        # Extract content from brackets (added by ActionFormattingWrapper)
        if "[" not in action:
            return False, [self.m("format_error", "no_brackets")], True

        # Extract the content between brackets
        action = action.split("[")[1]
        if "]" not in action:
            return False, [self.m("format_error", "no_closing_bracket")], True
        action = action.split("]")[0].strip()

        if not action:
            return (
                False,
                [self.m("format_error", "empty_command")],
                True,
            )

        # Split by commas and execute each action
        action_list = [act.strip() for act in action.split(",")]
        messages = []

        for i, single_action in enumerate(action_list):
            success, message, is_format_error = self._execute_single_action(
                single_action
            )

            if not success:
                if is_format_error:
                    # Format error - return immediately with format error
                    return False, [self.m("format_error", "wrapped", n=i + 1, msg=message)], True
                else:
                    # Game rule violation - add message and stop executing further actions
                    messages.append(self.m("action_result", "failed", n=i + 1, msg=message))
                    if i > 0:
                        messages.insert(0, self.m("action_result", "before_failure", n=i))
                    return False, messages, False
            else:
                # Success - add message and continue
                if message == FORFEIT:
                    messages.append(FORFEIT)
                else:
                    messages.append(self.m("action_result", "success", n=i + 1, msg=message))

        return True, messages, False

    def _execute_single_action(self, action: str) -> Tuple[bool, str, bool]:
        """Execute a single action and return (success, message, is_format_error)"""
        parts = action.lower().split()
        if not parts:
            return False, self.m("format_error", "empty_action"), True

        command = parts[0]

        if command == "draw":
            if self.klondike.draw():
                return True, self.m("move_result", "drew"), False
            else:
                return False, self.m("move_result", "cannot_draw"), False

        elif command == "forfeit":
            # Special action that triggers game end with current score
            return True, FORFEIT, False

        elif command == "move":
            if len(parts) < 3:
                return (
                    False,
                    self.m("format_error", "move_needs_args"),
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
                            return False, self.m("format_error", "count_positive"), True
                except ValueError:
                    return False, self.m("format_error", "count_invalid"), True

            success, message = self._execute_move(source, destination, count)
            return success, message, False  # Move attempts are never format errors

        else:
            return (
                False,
                self.m("format_error", "unknown_command", cmd=command),
                True,
            )

    def _execute_move(
        self, source: str, destination: str, count: int
    ) -> Tuple[bool, str]:
        """Execute a move command"""
        src_type, src_idx = self._parse_pile(source)
        dst_type, dst_idx = self._parse_pile(destination)

        if src_type == "?" or dst_type == "?":
            return False, self.m("move_result", "invalid_pile")

        # Move to foundation
        if dst_type == "F":
            if count != 1:
                return False, self.m("move_result", "foundation_one_card")

            if src_type == "W":
                if self.klondike.move_from_waste_to_foundation_at(dst_idx):
                    return True, self.m("move_result", "waste_to_foundation_ok", dst=dst_idx + 1)
                else:
                    return False, self.m("move_result", "waste_to_foundation_bad")

            elif src_type == "T":
                if self.klondike.move_from_tableau_to_foundation_at(src_idx, dst_idx):
                    return (
                        True,
                        self.m("move_result", "tableau_to_foundation_ok", src=src_idx + 1, dst=dst_idx + 1),
                    )
                else:
                    return False, self.m("move_result", "tableau_to_foundation_bad")

            else:
                return False, self.m("move_result", "foundation_to_foundation")

        # Move to tableau
        elif dst_type == "T":
            if src_type == "W":
                if count != 1:
                    return False, self.m("move_result", "waste_to_tableau_one_card")

                if self.klondike.move_waste_to_tableau(dst_idx):
                    return True, self.m("move_result", "waste_to_tableau_ok", dst=dst_idx + 1)
                else:
                    return False, self.m("move_result", "waste_to_tableau_bad")

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
                    return False, self.m("move_result", "no_face_up")

                if self.klondike.move_tableau_to_tableau(src_idx, count, dst_idx):
                    return (
                        True,
                        self.m("move_result", "tableau_to_tableau_ok", count=count, src=src_idx + 1, dst=dst_idx + 1),
                    )
                else:
                    return (
                        False,
                        self.m("move_result", "tableau_to_tableau_bad", count=count, src=src_idx + 1, dst=dst_idx + 1),
                    )

            elif src_type == "F":
                if count != 1:
                    return False, self.m("move_result", "foundation_to_tableau_one_card")

                foundation_pile = self.klondike.foundations[src_idx]
                if not foundation_pile:
                    return False, self.m("move_result", "foundation_empty", src=src_idx + 1)

                card = foundation_pile[-1]
                dest_pile = self.klondike.tableau[dst_idx]
                dest_top_card = dest_pile[-1][0] if dest_pile else None

                if self.klondike.can_place_on_tableau(dest_top_card, card):
                    foundation_pile.pop()
                    dest_pile.append((card, True))
                    return (
                        True,
                        self.m("move_result", "foundation_to_tableau_ok", src=src_idx + 1, dst=dst_idx + 1),
                    )
                else:
                    return (
                        False,
                        self.m("move_result", "foundation_to_tableau_bad", dst=dst_idx + 1),
                    )

        else:
            return False, self.m("move_result", "to_waste_or_stock")

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

    def _observe_state(self):
        """Add current game board to observations"""
        board_str = self._render_board()
        self.state.add_observation(
            to_id=-1, message=board_str, observation_type=ta.ObservationType.GAME_BOARD
        )

    def _render_board(self) -> str:
        """Render the current game board as a string"""
        lines = []
        lines.append(self.t("board", "title", _pid=0))
        lines.append(self.t("board", "turn", _pid=0, turn=self.state.game_state["turn_count"], max_turns=self.max_turns))
        lines.append("")

        # Stock and waste
        stock_count = len(self.klondike.stock)
        waste_top = str(self.klondike.waste[-1][0]) if self.klondike.waste else "--"
        lines.append(self.t("board", "stock", _pid=0, stock=stock_count))
        lines.append(self.t("board", "waste", _pid=0, waste=waste_top))
        lines.append("")

        # Foundations
        lines.append(self.t("board", "foundations_header", _pid=0))
        for i, pile in enumerate(self.klondike.foundations):
            cards_str = " ".join(str(c) for c in pile) if pile else "--"
            lines.append(self.t("board", "foundation_row", _pid=0, n=i + 1, cards=cards_str))
        lines.append("")

        # Tableau
        lines.append(self.t("board", "tableau_header", _pid=0))
        for i, pile in enumerate(self.klondike.tableau):
            pile_str = ""
            for j, (card, face_up) in enumerate(pile):
                if j > 0:
                    pile_str += " "
                pile_str += str(card) if face_up else "XX"
            if not pile_str:
                pile_str = "--"
            lines.append(self.t("board", "tableau_row", _pid=0, n=i + 1, cards=pile_str))

        return "\n".join(lines)

    def get_board_str(self) -> str:
        """Return the current board state as a string for rendering"""
        if not hasattr(self.state, "game_state") or not self.state.game_state:
            return "Game not started"
        return self._render_board()
