import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.IteratedRockPaperScissors.renderer import create_board_str


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class IteratedRockPaperScissorsEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    broadcast_actions = False  # submissions stay hidden until the round resolves

    num_rounds = ta.Param(5, "The number of rounds.", min=1, check=_is_renderable, rule="a positive integer")

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 1,
            "num_rounds": self.num_rounds,
            "points": {0: 0, 1: 0},
            "moves": {0: None, 1: None},
            "history": [],
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a {self.num_rounds}-round Rock-Paper-Scissors game.\nYour goal is to win as many rounds as possible.\n"
            "Identical moves tie the round. The player who wins more rounds wins the game; equal round wins is a draw.\n"
            "In each round, respond with one of: 'rock', 'paper', or 'scissors'.\nYou may also use 'r', 'p', or 's' as shorthand.\n"
        )

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
        if gs["moves"][player_id] is not None:
            return self.invalid("You have already submitted a move for this round.")
        move = self._parse_action(action)
        if move not in {"rock", "paper", "scissors"}:
            return self.invalid("Move not recognized. Reply with 'rock', 'paper', or 'scissors'.")

        gs["moves"][player_id] = move
        self.message(player_id, f"Player {player_id} selects move {move}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if gs["moves"][1 - player_id] is not None:  # resolve the round
            p0_move, p1_move = gs["moves"][0], gs["moves"][1]
            result = self._resolve_round(p0_move, p1_move)
            gs["history"].append({0: p0_move, 1: p1_move})
            gs["moves"] = {0: None, 1: None}

            self.broadcast(f"Player 0 played {p0_move}; Player 1 played {p1_move}.", ta.ObservationType.GAME_MESSAGE)
            if result == 0:
                self.broadcast("Round result: Draw", ta.ObservationType.GAME_MESSAGE)
            else:
                self.broadcast(f"Round result: Player {result - 1} wins!", ta.ObservationType.GAME_MESSAGE)
                gs["points"][result - 1] += 1
            self.broadcast(f"Score after round {gs['round']}/{self.num_rounds}: Player 0 {gs['points'][0]}, Player 1 {gs['points'][1]}.", ta.ObservationType.GAME_MESSAGE)

            if gs["round"] >= self.num_rounds:  # check end condition
                wins = gs["points"]
                if wins[0] > wins[1]: return self.winner(0, reason="Player 0 won the most rounds!")
                elif wins[1] > wins[0]: return self.winner(1, reason="Player 1 won the most rounds!")
                else: return self.draw(reason="The match is a draw!")
            gs["round"] += 1
        return None

    def _parse_action(self, action: str) -> str:
        match = re.match(r"^(rock|paper|scissors|r|p|s)$", action.strip().lower())
        if not match: return ""
        return {"r": "rock", "p": "paper", "s": "scissors"}.get(match.group(1), match.group(1))

    def _resolve_round(self, p0: str, p1: str) -> int:
        if p0 == p1: return 0
        return 1 if {"rock": "scissors", "paper": "rock", "scissors": "paper"}[p0] == p1 else 2
