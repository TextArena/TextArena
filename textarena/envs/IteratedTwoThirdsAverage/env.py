import math
import re
from numbers import Real
from typing import Any, Dict, Optional, Union

import textarena as ta


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class IteratedTwoThirdsAverageEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    def __init__(self, num_rounds: int = 5, min_guess: float = 0.0, max_guess: float = 100.0):
        if (
            not isinstance(num_rounds, int)
            or isinstance(num_rounds, bool)
            or num_rounds <= 0
            or not _is_renderable(num_rounds)
        ):
            raise ValueError("num_rounds must be a positive integer")
        try:
            bounds_are_finite = all(
                isinstance(bound, Real)
                and not isinstance(bound, bool)
                and math.isfinite(float(bound))
                for bound in (min_guess, max_guess)
            )
        except (OverflowError, TypeError, ValueError):
            bounds_are_finite = False
        if not bounds_are_finite:
            raise ValueError("guess bounds must be finite numbers")
        if min_guess > max_guess:
            raise ValueError("min_guess must not exceed max_guess")

        self.num_rounds = num_rounds
        self.min_guess = min_guess
        self.max_guess = max_guess
        self._guess_re = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$")

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 1,
            "num_rounds": self.num_rounds,
            "points": {0: 0, 1: 0},
            "guesses": {},
            "history": [],
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a {self.num_rounds}-round of IteratedTwoThirdsAverage.\nEach round, guess a number between {self.min_guess} and {self.max_guess}.\n"
            "After both guesses, the target is (2/3)x(average of both guesses),\nand the player whose guess is closest to the target wins that round.\n"
            "Equal distances tie the round. The player who wins more rounds wins the game; equal round wins is a draw.\n"
            "Reply with your guess as a plain number, e.g. '42'."
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # guesses stay hidden until the round resolves

    def get_board_str(self) -> str:
        s = f"Round {self.game_state['round']}/{self.num_rounds}\n"
        if self.game_state["history"]:
            s += "History:\n"
            for i, past in enumerate(self.game_state["history"], start=1): s += (f"  Round {i}: " + ", ".join(f"P{pid}→{guess}" for pid, guess in past.items()) + "\n")
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
        if player_id in gs["guesses"]:
            return self.invalid("You have already submitted a guess for this round.")
        m = self._guess_re.match(action)
        if not m:
            return self.invalid("Invalid format; please submit your guess as a plain number, e.g. '42'.")
        guess = float(m.group(1))
        if not math.isfinite(guess) or not (self.min_guess <= guess <= self.max_guess):
            return self.invalid(f"Guess must be between {self.min_guess} and {self.max_guess}.")
        gs["guesses"][player_id] = guess
        if len(gs["guesses"]) == 2:
            guesses = gs["guesses"]
            # Scale before adding so two individually finite, same-sign guesses
            # cannot overflow while computing their average.
            avg = guesses[0] / 2.0 + guesses[1] / 2.0
            target = (2.0 / 3.0) * avg
            gs["history"].append(guesses.copy())  # update history
            self.broadcast(f"Player 0 guessed {guesses[0]}; Player 1 guessed {guesses[1]}. Thus the Target is: {target:.2f}.", ta.ObservationType.GAME_MESSAGE)
            # For two guesses a and b, distances from (a+b)/3 compare as
            # |2a-b| versus |2b-a|. Their squared difference is
            # 3(a-b)(a+b), so the guess with smaller absolute value is closer.
            # This equivalent comparison avoids overflow and subnormal
            # underflow in direct floating-point distance calculations.
            magnitude_0 = abs(guesses[0])
            magnitude_1 = abs(guesses[1])
            if magnitude_0 == magnitude_1:
                winner = None
            elif magnitude_0 < magnitude_1:
                winner = 0
            else:
                winner = 1
            if winner is None:
                self.broadcast("Round is a draw.", ta.ObservationType.GAME_MESSAGE)
            else:
                gs["points"][winner] += 1
                self.broadcast(f"Player {winner} wins the round!", ta.ObservationType.GAME_MESSAGE)
            self.broadcast(f"Score after round {gs['round']}/{self.num_rounds}: Player 0 {gs['points'][0]}, Player 1 {gs['points'][1]}.", ta.ObservationType.GAME_MESSAGE)
            gs["guesses"].clear()
            # check end-of-game
            if gs["round"] >= self.num_rounds:
                p0, p1 = gs["points"][0], gs["points"][1]
                if p0 > p1: return self.winner(0, reason="Player 0 won more rounds.")
                elif p1 > p0: return self.winner(1, reason="Player 1 won more rounds.")
                else: return self.draw(reason="Overall game is a draw.")
            # prepare next round
            gs["round"] += 1
        return None
