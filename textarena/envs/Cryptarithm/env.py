import re
from typing import Dict, Tuple, Optional, Any, List, Set

import textarena as ta


class CryptarithmEnv(ta.Env):
    _ACTION_RE = re.compile(r"\[\s*([A-Za-z])\s+(\d)\s*\]")

    def __init__(self, equation: str = "SEND + MORE = MONEY", max_turns: int = 100):
        """ equation : string of the form 'WORD [+ WORD …] = WORD' """
        super().__init__()
        self.equation_raw = equation.upper().replace(' ', '')
        lhs, rhs = self.equation_raw.split('=')
        self.addends: List[str] = lhs.split('+')
        self.result: str = rhs
        self.letters: Set[str] = set(''.join(self.addends) + self.result)
        self.first_letters: Set[str] = {w[0] for w in self.addends + [self.result]}
        self.max_turns = max_turns

        # mutable state (reset each episode)
        self.mapping: Dict[str, int] = {}      # current letter → digit
        self.digit_used: Dict[int, str] = {}   # digit → letter

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.mapping.clear()
        self.digit_used.clear()
        self.state = ta.SinglePlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.state.reset(game_state={}, player_prompt_function=self._prompt)
        self._observe()

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        m = self._ACTION_RE.fullmatch(action.strip())
        if not m: self.state.set_invalid_move(self.m("invalid_move", "wrong_format"), self._progress()); return self.state.step()

        letter, digit = m.group(1).upper(), int(m.group(2))

        # basic validity checks
        if letter not in self.letters:                                  self.state.set_invalid_move(self.m("invalid_move", "letter_not_in_puzzle", letter=letter), self._progress());                           return self.state.step()
        if digit in self.digit_used and self.digit_used[digit]!=letter: self.state.set_invalid_move(self.m("invalid_move", "digit_used", digit=digit, used_letter=self.digit_used[digit]), self._progress());  return self.state.step()
        if letter in self.first_letters and digit == 0:                 self.state.set_invalid_move(self.m("invalid_move", "leading_zero"), self._progress());                      return self.state.step()

        # apply (re)assignment
        prev_digit = self.mapping.get(letter)
        if prev_digit is not None:
            del self.digit_used[prev_digit]
        self.mapping[letter] = digit
        self.digit_used[digit] = letter

        self._observe()

        # check win / max-turn
        if len(self.mapping) == len(self.letters):
            if self._equation_holds():      self.state.set_outcome(1.0, self.m("outcome", "correct"))
            else:                           self.state.set_outcome(0.0, self.m("outcome", "incorrect"))
        elif self.state.check_turn_limit(): self.state.set_outcome(self._progress(), self.m("outcome", "limit"))
        return self.state.step()

    def _prompt(self, player_id, game_state) -> str:    return self.m("player_prompt", "intro")
    def _word_value(self, word: str) -> int:            return int(''.join(str(self.mapping[ch]) for ch in word))
    def _equation_holds(self) -> bool:                  return sum(self._word_value(w) for w in self.addends) == self._word_value(self.result) # leading-zero guard already enforced, so just compute integers
    def _progress(self) -> float:                       return len(self.mapping) / len(self.letters)

    def _render_board(self) -> str:
        # 1) Original equation with letters
        eq_letters = ' + '.join(self.addends) + f' = {self.result}'

        # 2) Partially-filled numeric view (digits for mapped letters, '_' for unknown)
        def show_word(w): return ''.join(str(self.mapping[ch]) if ch in self.mapping else '_' for ch in w)

        eq_digits = ' + '.join(show_word(w) for w in self.addends) + f' = {show_word(self.result)}'

        # 3) Current mapping table
        mapping_lines = [self.t("board", "mapping_header", _pid=0)]
        mapping_lines += [f"  {l} → {d}" for l, d in sorted(self.mapping.items())]
        if len(mapping_lines) == 1:
            mapping_lines.append(self.t("board", "none_yet", _pid=0))

        # Combine everything
        return "\n"+'\n'.join([eq_letters, eq_digits, *mapping_lines])


    def _observe(self):
        assigned = self.t("board", "assigned", _pid=0, assigned=len(self.mapping), total=len(self.letters), pct=f"{self._progress():.0%}")
        self.state.add_observation(message=self._render_board()+assigned, observation_type=ta.ObservationType.GAME_MESSAGE)
