import operator
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class CountdownEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False

    max_action_chars = 128
    max_value = 1_000_000
    max_numbers = 100
    _ACTION_RE = re.compile(r"(?P<i>\d+)\s+(?P<j>\d+)\s*(?P<op>[+\-*/])")
    _OPS = {'+': operator.add, '-': operator.sub, '*': operator.mul}

    def __init__(self, numbers: Optional[List[int]] = None, target: Optional[int] = None, max_turns: int = 12):
        if numbers is not None and (
            not isinstance(numbers, (list, tuple))
            or not 2 <= len(numbers) <= self.max_numbers
            or any(isinstance(number, bool) or not isinstance(number, int) or number <= 0 for number in numbers)
            or any(number > self.max_value for number in numbers)
        ):
            raise ValueError(
                f"numbers must contain 2 to {self.max_numbers} positive integers no greater than {self.max_value}."
            )
        if target is not None and (
            isinstance(target, bool)
            or not isinstance(target, int)
            or not 0 < target <= self.max_value
        ):
            raise ValueError(f"target must be a positive integer no greater than {self.max_value}.")
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer.")
        if numbers is not None and target is not None and target in numbers:
            raise ValueError("target must not be one of the starting numbers.")
        self._configured_numbers = list(numbers) if numbers is not None else None
        self._configured_target = target
        self.max_turns = max_turns

    @property
    def numbers(self) -> List[int]:
        return self.game_state["numbers"]

    def setup(self) -> Dict[str, Any]:
        big_numbers = [25, 50, 75, 100]
        small_numbers = list(range(1, 11)) * 2

        def draw_numbers() -> List[int]:
            return self.rng.sample(big_numbers, 2) + self.rng.sample(small_numbers, 4)

        self.orig_numbers = self._configured_numbers[:] if self._configured_numbers is not None else draw_numbers()
        self.target = self._configured_target if self._configured_target is not None else self.rng.randint(100, 999)
        # A starting number equal to the target would award the full score without a single operation.
        while self.target in self.orig_numbers:
            if self._configured_target is None:
                self.target = self.rng.randint(100, 999)
            else:
                self.orig_numbers = draw_numbers()
        numbers = self.orig_numbers[:]
        best_value = min(numbers, key=lambda v: abs(v - self.target)) if numbers else 0
        return {
            "numbers": numbers,
            "expressions": [str(n) for n in numbers],
            "best_value": best_value,
            "best_expression": str(best_value),
            "move_history": [],
        }

    def prompt(self, player_id: int) -> str:
        return (
            "You are playing Countdown numbers game!\n"
            f"Goal: Combine numbers using +, -, *, / to reach the target {self.target} exactly.\n"
            "Action format: 'i j op' where i,j are the indices of two different numbers on the board and op is the "
            "operation. It computes (number i) op (number j), so the order matters for '-' and '/'.\n"
            "Example: '0 1 +' adds the number at index 0 to the number at index 1.\n"
            "Both numbers are replaced by the result, which is appended to the end of the list, so indices change after every move.\n"
            f"Division must result in whole numbers only, and results must stay between -{self.max_value:,} and {self.max_value:,}.\n"
            f"The game ends when you reach the target, when only one number is left, or after {self.max_turns} moves. "
            "If you miss the target, your score is the fraction of the starting gap you closed: how much closer the "
            "closest value ever on the board got to the target than the closest starting number."
        )

    def render(self, player_id: int) -> str:
        return f"{self._render_board()}\nCurrent progress score: {self._calculate_progress():.3f}"

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        return super().action_echo_target(player_id, action)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        parsed_action = self._parse_action(move)
        if parsed_action is None:
            return self.invalid("Invalid action format. Use 'i j op' where i,j are indices and op is +,-,*,/")

        i, j, op = parsed_action
        numbers = self.game_state["numbers"]

        if not self._validate_indices(i, j):
            return self.invalid(f"Invalid indices. Must be different and in range 0-{len(numbers)-1}")

        result = self._execute_operation(i, j, op)
        if isinstance(result, ta.Invalid):
            return result

        self._update_state(i, j, op, result)

        if result == self.target:
            return self.outcome({0: 1.0}, reason=f"Perfect! Found exact target: {self.target}")
        if len(self.game_state["numbers"]) == 1:
            return self.outcome(
                {0: self._calculate_progress()},
                reason=f"No more moves. Best result: {self.game_state['best_value']} (target: {self.target})",
            )
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome(
            {0: self._calculate_progress()},
            reason=f"Turn limit reached. Best result: {self.game_state['best_value']} (target: {self.target})",
        )

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._calculate_progress()}, reason=f"Invalid Move: {reason}")

    def _parse_action(self, action: str) -> Optional[Tuple[int, int, str]]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        match = self._ACTION_RE.fullmatch(action.strip())
        if not match: return None
        try:
            i = int(match.group("i"))
            j = int(match.group("j"))
            op = match.group("op")
            return i, j, op
        except (ValueError, IndexError):
            return None

    def _validate_indices(self, i: int, j: int) -> bool:
        numbers = self.game_state["numbers"]
        return (0 <= i < len(numbers) and 0 <= j < len(numbers) and i != j)

    def _execute_operation(self, i: int, j: int, op: str) -> Union[int, ta.Invalid]:
        """Execute arithmetic operation and return the result, or why it is not allowed."""
        numbers = self.game_state["numbers"]
        a, b = numbers[i], numbers[j]
        if op == '/':
            if b == 0:
                return self.invalid("Division by zero is not allowed.")
            if a % b != 0:
                return self.invalid(f"{a} / {b} is not a whole number.")
            result = a // b
        else:
            result = self._OPS[op](a, b)
        if abs(result) > self.max_value:
            return self.invalid(
                f"{a} {op} {b} = {result}, but results must stay between -{self.max_value:,} and {self.max_value:,}."
            )
        return result

    def _update_state(self, i: int, j: int, op: str, result: int):
        """Update game state after successful operation."""
        gs = self.game_state
        numbers, expressions = gs["numbers"], gs["expressions"]

        move_desc = f"{numbers[i]} {op} {numbers[j]} = {result}"
        gs["move_history"].append(move_desc)

        new_expr = f"({expressions[i]} {op} {expressions[j]})"

        # Remove used numbers/expressions (higher index first to avoid shifting)
        for idx in sorted([i, j], reverse=True):
            numbers.pop(idx)
            expressions.pop(idx)

        numbers.append(result)
        expressions.append(new_expr)

        if abs(result - self.target) < abs(gs["best_value"] - self.target):
            gs["best_value"] = result
            gs["best_expression"] = new_expr

    def _calculate_progress(self) -> float:
        """Fraction of the starting gap to the target closed by the best value: 0.0 at the start, below 1.0 unless solved."""
        start_distance = min(abs(number - self.target) for number in self.orig_numbers)  # >= 1: target is never a starting number
        distance = abs(self.game_state["best_value"] - self.target)
        return max(0.0, (start_distance - distance) / start_distance)

    def _render_board(self) -> str:
        gs = self.game_state
        lines = [f"TARGET: {self.target}", "", "Available numbers:"]
        for idx, (num, expr) in enumerate(zip(gs["numbers"], gs["expressions"])):
            lines.append(f"  [{idx}] {num}   (from: {expr})")
        lines.extend(["", f"Best so far: {gs['best_value']} (distance: {abs(gs['best_value'] - self.target)})", f"Best expression: {gs['best_expression']}"])
        if gs["move_history"]:
            lines.extend(["", "Move history:"])
            for i, move in enumerate(gs["move_history"], 1):
                lines.append(f"  {i}. {move}")
        return "\n".join(lines)
