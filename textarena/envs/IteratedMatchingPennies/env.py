import re
from typing import Any, Dict, Optional, Union

import textarena as ta


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class IteratedMatchingPenniesEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    def __init__(self, num_rounds: int = 5):
        if (
            not isinstance(num_rounds, int)
            or isinstance(num_rounds, bool)
            or num_rounds <= 0
            or not _is_renderable(num_rounds)
        ):
            raise ValueError("num_rounds must be a positive integer")
        self.num_rounds = num_rounds
        self._choice_re = re.compile(r"^(heads|tails|h|t)$", re.IGNORECASE) # parses 'heads', 'tails', or shorthand 'h', 't'

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 1,
            "num_rounds": self.num_rounds,
            "points": {0: 0, 1: 0},
            "moves": {},
            "history": [],
        }

    def prompt(self, player_id: int) -> str:
        role = "Matcher" if player_id == 0 else "Mismatcher"
        return (
            f"You are Player {player_id} ({role}) in a {self.num_rounds}-round Matching Pennies game.\n- Each round, submit 'heads' or 'tails' (or 'h', 't').\n"
            "- If your choice matches your opponent’s, Player 0 wins the round; otherwise Player 1 wins.\n"
            "- The player who wins more rounds wins the game; equal round wins is a draw.\nReply with your choice, e.g. 'heads' or 'tails'.\n"
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # moves are simultaneous, so an echo would reveal the choice to the opponent

    def get_board_str(self) -> str:
        gs = self.state.game_state
        s = f"Round {gs['round']}/{self.num_rounds}\n"
        if gs["history"]:
            s += "History:\n"
            for i, past in enumerate(gs["history"], start=1):
                s += (f"  Round {i}: " + ", ".join(f"P{pid}→{choice}" for pid, choice in past.items()) + "\n")
        return s

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if (
            not isinstance(player_id, int)
            or isinstance(player_id, bool)
            or not 0 <= player_id < self.state.num_players
            or not self.state.is_player_alive(player_id)
            or player_id != self.current_player_id
        ):
            return self.invalid("Action submitted by an unauthorized player.")
        if player_id in gs["moves"]:
            return self.invalid("You have already submitted a choice for this round.")
        m = self._choice_re.search(action)
        if not m:
            return self.invalid("Invalid format; please submit 'heads' or 'tails'.")
        token = m.group(1).lower()
        choice = "heads" if token in ("heads", "h") else "tails"
        gs["moves"][player_id] = choice
        if len(gs["moves"]) == 2:
            moves = gs["moves"]
            same = (moves[0] == moves[1])
            winner = 0 if same else 1
            gs["history"].append(moves.copy())
            gs["points"][winner] += 1
            self.broadcast(f"Player 0 picked {moves[0]}; Player 1 picked {moves[1]}. {'Match -> Player 0 wins.' if same else 'Mismatch -> Player 1 wins.'}", ta.ObservationType.GAME_MESSAGE)
            self.broadcast(f"Score after round {gs['round']}/{self.num_rounds}: Player 0 {gs['points'][0]}, Player 1 {gs['points'][1]}.", ta.ObservationType.GAME_MESSAGE)
            gs["moves"].clear()
            if gs["round"] >= self.num_rounds:
                p0, p1 = gs["points"][0], gs["points"][1]
                if p0 > p1: return self.winner(0, reason="Player 0 won more rounds.")
                elif p1 > p0: return self.winner(1, reason="Player 1 won more rounds.")
                else: return self.draw(reason="Overall game is a draw.")
            gs["round"] += 1
        return None
