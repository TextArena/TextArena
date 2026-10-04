import re
from typing import Any, Callable, Dict, List, Set, Union

import textarena as ta


class CryptarithmEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    MAX_EQUATION_LENGTH = 512
    MAX_ADDENDS = 20
    MAX_WORD_LENGTH = 64
    MAX_SOLVER_DEPTH = 500

    _ACTION_RE = re.compile(r"(?P<letter>[A-Za-z])(?:\s*,\s*|\s+)(?P<digit>\d|-)")

    def __init__(self, equation: str = "SEND + MORE = MONEY", max_turns: int = 100):
        """ equation : string of the form 'WORD [+ WORD …] = WORD' """
        if not isinstance(equation, str):
            raise ValueError("equation must be a string")
        if len(equation) > self.MAX_EQUATION_LENGTH:
            raise ValueError(f"equation cannot exceed {self.MAX_EQUATION_LENGTH} characters")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")

        self.equation_raw = re.sub(r"\s+", "", equation.upper())
        if self.equation_raw.count("=") != 1:
            raise ValueError("equation must contain exactly one '='")
        lhs, rhs = self.equation_raw.split("=")
        self.addends: List[str] = lhs.split('+')
        self.result: str = rhs
        if len(self.addends) > self.MAX_ADDENDS:
            raise ValueError(f"equation cannot contain more than {self.MAX_ADDENDS} addends")
        if not self.addends or any(re.fullmatch(r"[A-Z]+", word) is None for word in self.addends):
            raise ValueError("each addend must contain only letters")
        if re.fullmatch(r"[A-Z]+", self.result) is None:
            raise ValueError("the result must contain only letters")
        if any(len(word) > self.MAX_WORD_LENGTH for word in self.addends + [self.result]):
            raise ValueError(f"words cannot exceed {self.MAX_WORD_LENGTH} letters")
        columns = max(max(map(len, self.addends)), len(self.result))
        if columns * (len(self.addends) + 2) > self.MAX_SOLVER_DEPTH:
            raise ValueError("equation is too large to solve safely")
        self.letters: Set[str] = set(''.join(self.addends) + self.result)
        self.first_letters: Set[str] = {w[0] for w in self.addends + [self.result]}
        if len(self.letters) > 10:
            raise ValueError("equation cannot contain more than 10 distinct letters")
        self.max_turns = max_turns
        if not self._has_solution():
            raise ValueError("equation has no valid digit assignment")

    def setup(self) -> Dict[str, Any]:
        return {
            "mapping": {},     # current letter -> digit
            "digit_used": {},  # digit -> letter
        }

    def prompt(self, player_id: int) -> str:
        example = self.addends[0][0]
        return (
            f"Solve the cryptarithm {' + '.join(self.addends)} = {self.result}: map each letter to a digit so the arithmetic holds.\n"
            "Different letters need different digits, and the first letter of a word cannot be 0 "
            f"(here: {', '.join(sorted(self.first_letters))}).\n"
            f"Assign by replying with the letter and digit, e.g. '{example} 5'; re-assign anytime to a digit no other letter is using.\n"
            f"Reply with the letter and '-' (e.g. '{example} -') to clear its digit so another letter can use it.\n"
            f"You win as soon as every letter is assigned and the equation holds. You have {self.max_turns} moves.\n"
        )

    def render(self, player_id: int) -> str:
        mapping = self.game_state["mapping"]
        return self._render_board() + f"\nAssigned: {len(mapping)}/{len(self.letters)} ({self._progress():.0%})"

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        m = self._ACTION_RE.fullmatch(move.strip())
        if not m:
            example = self.addends[0][0]
            return self.invalid(
                f"Bad action format. Reply with a letter and a digit, e.g. '{example} 5', or a letter and '-' to clear it."
            )

        letter = m.group("letter").upper()
        mapping, digit_used = self.game_state["mapping"], self.game_state["digit_used"]
        if letter not in self.letters:
            return self.invalid(f"Letter {letter} not in puzzle.")
        if m.group("digit") == "-":
            if letter not in mapping:
                return self.invalid(f"Letter {letter} has no digit to clear.")
            del digit_used[mapping.pop(letter)]
            return None

        digit = int(m.group("digit"))
        if digit in digit_used and digit_used[digit] != letter:
            return self.invalid(f"Digit {digit} already used by {digit_used[digit]}.")
        if letter in self.first_letters and digit == 0:
            return self.invalid("Leading digit of a word cannot be 0.")

        # apply (re)assignment
        prev_digit = mapping.get(letter)
        if prev_digit is not None:
            del digit_used[prev_digit]
        mapping[letter] = digit
        digit_used[digit] = letter

        if len(mapping) == len(self.letters):
            if self._equation_holds():
                return self.outcome({0: 1.0}, reason="Correct! Equation satisfied.")
            self.message(
                player_id,
                "All letters are assigned, but the equation is incorrect. Reassign or clear a letter and try again.",
                ta.ObservationType.GAME_MESSAGE,
            )
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome({0: self._partial_credit()}, reason="Move limit reached.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._partial_credit()}, reason=f"Invalid Move: {reason}")

    def _word_value(self, word: str) -> int:
        mapping = self.game_state["mapping"]
        return int(''.join(str(mapping[ch]) for ch in word))

    def _equation_holds(self) -> bool:
        # leading-zero guard already enforced, so just compute integers
        return sum(self._word_value(w) for w in self.addends) == self._word_value(self.result)

    def _progress(self) -> float:
        """Share of letters that have a digit, right or wrong; shown on the board."""
        return len(self.game_state["mapping"]) / len(self.letters)

    def _partial_credit(self) -> float:
        """Fraction of letters whose digit matches a solution, taking the best-matching solution if there are several."""
        mapping = self.game_state["mapping"]
        best = 0

        def visit(solution: Dict[str, int]) -> bool:
            nonlocal best
            best = max(best, sum(mapping.get(letter) == digit for letter, digit in solution.items()))
            return best == len(mapping)  # no solution can match more letters than are assigned

        if mapping:
            self._search_solutions(visit)
        return best / len(self.letters)

    def _has_solution(self) -> bool:
        """Return whether the configured alphametic has at least one solution."""
        return self._search_solutions(lambda solution: True)

    def _search_solutions(self, visit: Callable[[Dict[str, int]], bool]) -> bool:
        """Call `visit` with each solution until it returns True; return whether it did."""
        mapping: Dict[str, int] = {}
        used: Set[int] = set()
        columns = max(max(map(len, self.addends)), len(self.result))

        def assign_addends(column: int, addend_index: int, total: int) -> bool:
            if addend_index == len(self.addends):
                result_letter = self.result[-1 - column] if column < len(self.result) else None
                required = total % 10
                carry = total // 10
                if result_letter is None:
                    return required == 0 and solve_column(column + 1, carry)
                if result_letter in mapping:
                    return mapping[result_letter] == required and solve_column(column + 1, carry)
                if required in used or (required == 0 and result_letter in self.first_letters):
                    return False
                mapping[result_letter] = required
                used.add(required)
                solved = solve_column(column + 1, carry)
                used.remove(required)
                del mapping[result_letter]
                return solved

            word = self.addends[addend_index]
            if column >= len(word):
                return assign_addends(column, addend_index + 1, total)
            letter = word[-1 - column]
            if letter in mapping:
                return assign_addends(column, addend_index + 1, total + mapping[letter])
            for digit in range(10):
                if digit in used or (digit == 0 and letter in self.first_letters):
                    continue
                mapping[letter] = digit
                used.add(digit)
                if assign_addends(column, addend_index + 1, total + digit):
                    return True
                used.remove(digit)
                del mapping[letter]
            return False

        def solve_column(column: int, carry: int) -> bool:
            if column == columns:
                return carry == 0 and visit(dict(mapping))
            return assign_addends(column, 0, carry)

        return solve_column(0, 0)

    def _render_board(self) -> str:
        mapping = self.game_state["mapping"]
        eq_letters = ' + '.join(self.addends) + f' = {self.result}'

        def show_word(w):
            return ''.join(str(mapping[ch]) if ch in mapping else '_' for ch in w)

        eq_digits = ' + '.join(show_word(w) for w in self.addends) + f' = {show_word(self.result)}'

        mapping_lines = ["Mapping:"]
        mapping_lines += [f"  {l} → {d}" for l, d in sorted(mapping.items())]
        if len(mapping_lines) == 1:
            mapping_lines.append("  (none yet)")

        return "\n" + '\n'.join([eq_letters, eq_digits, *mapping_lines])
