import operator
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class CountdownEnv(ta.GameEnv):
    min_players = 1
    max_players = 1

    max_action_chars = 128
    max_value = 1_000_000
    _ACTION_RE = re.compile(
        r"^\s*(?P<legacy>\[)?\s*(?P<i>\d+)\s+(?P<j>\d+)\s*(?P<op>[+\-*/])\s*(?(legacy)\])\s*$"
    )
    _OPS = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv}

    def __init__(self, numbers: Optional[List[int]] = None, target: Optional[int] = None, max_turns: int = 12):
        if numbers is not None and (
            not isinstance(numbers, (list, tuple))
            or len(numbers) < 2
            or any(isinstance(number, bool) or not isinstance(number, int) or number <= 0 for number in numbers)
            or any(number > self.max_value for number in numbers)
        ):
            raise ValueError(
                f"numbers must contain at least two positive integers no greater than {self.max_value}."
            )
        if target is not None and (
            isinstance(target, bool)
            or not isinstance(target, int)
            or not 0 < target <= self.max_value
        ):
            raise ValueError(f"target must be a positive integer no greater than {self.max_value}.")
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer.")
        self._configured_numbers = list(numbers) if numbers is not None else None
        self._configured_target = target
        self.max_turns = max_turns

    @property
    def numbers(self) -> List[int]:
        return self.game_state["numbers"]

    def setup(self) -> Dict[str, Any]:
        big_numbers = [25, 50, 75, 100]
        small_numbers = list(range(1, 11)) * 2
        self.orig_numbers = self._configured_numbers[:] if self._configured_numbers is not None else (
            self.rng.sample(big_numbers, 2) + self.rng.sample(small_numbers, 4)
        )
        self.target = self._configured_target if self._configured_target is not None else self.rng.randint(100, 999)
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
            "Goal: Combine numbers using +, -, *, / to reach the target.\n"
            "Action format: 'i j op' where i,j are indices and op is the operation.\n"
            "Example: '0 2 *' multiplies number at index 0 with number at index 2.\n"
            "Division must result in whole numbers only."
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
        if result is None:
            return self.invalid("Invalid operation (division by zero or non-integer result)")

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

    def _execute_operation(self, i: int, j: int, op: str) -> Optional[int]:
        """Execute arithmetic operation and return result."""
        if op not in self._OPS: return None
        numbers = self.game_state["numbers"]
        a, b = numbers[i], numbers[j]
        operation = self._OPS[op]

        try:
            if op == '/':
                if b == 0 or a % b != 0: return None
                result = a // b
            else:
                result = operation(a, b)
            if abs(result) > self.max_value:
                return None
            return result
        except (ZeroDivisionError, OverflowError, ValueError):
            return None

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
        """Calculate progress score (0.0 to 1.0, higher is better)."""
        distance = abs(self.game_state["best_value"] - self.target)
        # Scale progress: exact match = 1.0, distance of 1000 = 0.0
        return max(0.0, 1.0 - distance / 1000.0)

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
