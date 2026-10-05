import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.TowerOfHanoi.renderer import create_board_str

class TowerOfHanoiEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    MAX_DISKS = 20
    _MOVE_RE = re.compile(r"(?P<source>[ABCabc])(?:\s*,\s*|\s+)(?P<target>[ABCabc])")

    num_disks = ta.Param(3, "The number of disks.", min=1, max=MAX_DISKS)
    max_turns = ta.Param(
        100, "The number of valid moves allowed. It must be at least `2^num_disks − 1`, the length of the shortest "
             "solution. The registered variants allow about twice that (`2^(num_disks + 1) − 2`).", min=1,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.max_turns < 2**self.num_disks - 1:
            raise ValueError("max_turns is too small for this number of disks")

    def get_board_str(self):
        return create_board_str(towers=self.game_state['towers'])

    def setup(self) -> Dict[str, Any]:
        return {"towers": {"A": list(range(self.num_disks, 0, -1)), "B": [], "C": []}}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing Tower of Hanoi with {self.num_disks} disks.\nYou have to move the disks from tower A to tower C.\n"
            "To move a disk, reply with the source tower and the target tower (e.g., 'A C').\nNote that you can only move the top disk of a tower, and that a bigger disk cannot be placed on a smaller disk.\n"
            "The board lists each tower's disks from bottom to top; larger numbers are larger disks.\n"
            f"At each turn, submit one move. You have {self.max_turns} moves."
        )

    def render(self, player_id: int) -> str:
        return f"Current Board (disks listed bottom to top):\n{self._render_board()}"

    def _render_board(self):
        rendered_board = ""
        for tower, disks in self.game_state["towers"].items():
            rendered_board += f"{tower}: {disks}\n"
        return rendered_board

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        m = self._MOVE_RE.fullmatch(move.strip())
        if not m:
            return self.invalid("You did not respond with a valid 'source target' move (e.g. 'A C').")
        source, target = m.group("source").upper(), m.group("target").upper()
        towers = self.game_state['towers']
        if source == target:
            return self.invalid("The source and target towers must be different.")
        elif not towers[source]:
            return self.invalid("You tried to move a disk from an empty tower.")
        elif towers[target] and towers[target][-1] < towers[source][-1]:
            return self.invalid("You tried to place a larger disk on a smaller disk.")
        disk = towers[source].pop()
        towers[target].append(disk)
        self.broadcast(f"You moved disk {disk} from {source} to {target}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if self.game_state['towers']["C"] == list(range(self.num_disks, 0, -1)):  # check if the game is over
            return self.outcome({0: 1}, reason="Congratulations! You solved the Tower of Hanoi puzzle.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        return self.outcome({0: pct_complete}, reason=f"The turn limit has been reached. You correctly placed {round(pct_complete * 100)}% of the disks on Tower C.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _get_percentage_completion(self) -> float:
        """ Compute how many disks are in the correct order on Tower C, starting from the base """
        correct = 0
        goal = list(range(self.num_disks, 0, -1))  # e.g. [3, 2, 1]
        for placed, expected in zip(self.game_state['towers']["C"], goal):
            if placed == expected:
                correct += 1
            else:
                break  # stop at the first mismatch
        return correct/self.num_disks
