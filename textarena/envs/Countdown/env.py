import operator
import re
import random
from typing import Tuple, List, Optional

import textarena as ta


class CountdownEnv(ta.Env):
    _ACTION_RE = re.compile(r"\[\s*(\d+)\s+(\d+)\s*([+\-*/])\s*\]")
    _OPS = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv}

    def __init__(self, numbers: List[int] = None, target: int = None, max_turns: int = 12):
        super().__init__()
        big_numbers = [25, 50, 75, 100]
        small_numbers = list(range(1, 11)) * 2
        
        if numbers is None: numbers = random.sample(big_numbers, 2) + random.sample(small_numbers, 4)
        if target is None:  target = random.randint(100, 999)
        self.orig_numbers = numbers[:]  # Deep copy to avoid mutation
        self.target = target
        self.max_turns = max_turns

        # Mutable state (reset per episode)
        self.numbers: List[int] = []
        self.expressions: List[str] = []
        self.best_value: int = 0
        self.best_expression: str = ""
        self.move_history: List[str] = []

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.numbers = self.orig_numbers[:]
        self.expressions = [str(n) for n in self.numbers]
        self.best_value = self._find_closest_value()
        self.best_expression = str(self.best_value)
        self.move_history = []
        
        self.state = ta.SinglePlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.state.reset(game_state={}, player_prompt_function=self._get_player_prompt)
        self._add_board_observation()

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(self.state.current_player_id, action, ta.ObservationType.PLAYER_ACTION)
        
        # Parse and validate action
        parsed_action = self._parse_action(action)
        if parsed_action is None:
            self.state.set_invalid_move(self._calculate_progress(), self.m("invalid_move", "wrong_format"))
            return self.state.step()
        
        i, j, op = parsed_action
        
        # Validate indices
        if not self._validate_indices(i, j):
            self.state.set_invalid_move(self._calculate_progress(), self.m("invalid_move", "invalid_indices", max_index=len(self.numbers)-1))
            return self.state.step()

        # Execute operation
        result = self._execute_operation(i, j, op)
        if result is None:
            self.state.set_invalid_move(self._calculate_progress(), self.m("invalid_move", "invalid_operation"))
            return self.state.step()

        # Update game state
        self._update_state(i, j, op, result)
        self._add_board_observation()

        # Check win/end conditions
        if result == self.target:           self.state.set_outcome(1.0, self.m("outcome", "win", target=self.target))
        elif len(self.numbers) == 1:        self.state.set_outcome(self._calculate_progress(), self.m("outcome", "no_moves", best_value=self.best_value, target=self.target))
        elif self.state.check_turn_limit(): self.state.set_outcome(self._calculate_progress(), self.m("outcome", "turn_limit", best_value=self.best_value, target=self.target))
        return self.state.step()

    def _parse_action(self, action: str) -> Optional[Tuple[int, int, str]]:
        match = self._ACTION_RE.fullmatch(action.strip())
        if not match: return None
        try:
            i, j, op = int(match.group(1)), int(match.group(2)), match.group(3)
            return i, j, op
        except (ValueError, IndexError):
            return None

    def _validate_indices(self, i: int, j: int) -> bool:
        return (0 <= i < len(self.numbers) and 0 <= j < len(self.numbers) and i != j)

    def _execute_operation(self, i: int, j: int, op: str) -> Optional[int]:
        """Execute arithmetic operation and return result."""
        if op not in self._OPS: return None
        a, b = self.numbers[i], self.numbers[j]
        operation = self._OPS[op]
        
        try:
            if op == '/':
                if b == 0: return None
                result = operation(a, b)
                # Only allow integer results for division
                if not result.is_integer(): return None
                return int(result)
            else:
                result = operation(a, b)
                # Ensure result is reasonable (prevent overflow)
                if abs(result) > 1000000: return None
                return result
        except (ZeroDivisionError, OverflowError, ValueError):
            return None

    def _update_state(self, i: int, j: int, op: str, result: int):
        """Update game state after successful operation."""
        # Record the move
        move_desc = f"{self.numbers[i]} {op} {self.numbers[j]} = {result}"
        self.move_history.append(move_desc)
        
        # Create new expression
        new_expr = f"({self.expressions[i]} {op} {self.expressions[j]})"
        
        # Remove used numbers/expressions (higher index first to avoid shifting)
        indices_to_remove = sorted([i, j], reverse=True)
        for idx in indices_to_remove:
            self.numbers.pop(idx)
            self.expressions.pop(idx)
        
        # Add new number/expression
        self.numbers.append(result)
        self.expressions.append(new_expr)
        
        # Update best result if improved
        if abs(result - self.target) < abs(self.best_value - self.target):
            self.best_value = result
            self.best_expression = new_expr

    def _find_closest_value(self) -> int:
        """Find the value closest to target from current numbers."""
        if not self.numbers:
            return 0
        return min(self.numbers, key=lambda v: abs(v - self.target))

    def _calculate_progress(self) -> float:
        """Calculate progress score (0.0 to 1.0, higher is better)."""
        distance = abs(self.best_value - self.target)
        # Scale progress: exact match = 1.0, distance of 1000 = 0.0
        return max(0.0, 1.0 - distance / 1000.0)

    def _get_player_prompt(self, player_id, game_state) -> str:
        return self.m("player_prompt", "intro")

    def _add_board_observation(self):
        observation = self.m("board", "header", target=self.target, numbers=self._render_numbers())
        observation = self.m("board", "best", observation=observation, best_value=self.best_value, distance=abs(self.best_value - self.target), best_expression=self.best_expression)
        observation = self.m("board", "history", observation=observation, moves=self._render_moves()) if self.move_history else observation
        observation = self.m("board", "progress", observation=observation, progress=f"{self._calculate_progress():.3f}")
        self.state.add_observation(message=observation, observation_type=ta.ObservationType.GAME_BOARD)

    def _render_numbers(self) -> str:
        return "\n".join(f"  [{idx}] {num}   (from: {expr})" for idx, (num, expr) in enumerate(zip(self.numbers, self.expressions)))

    def _render_moves(self) -> str:
        return "\n".join(f"  {i}. {move}" for i, move in enumerate(self.move_history, 1))