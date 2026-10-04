import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta
from textarena.envs.Nim.renderer import create_board_str


def _parse_bounded_uint(text: str, maximum: int) -> Optional[int]:
    """Parse decimal text only when it is no larger than ``maximum``."""
    normalized = text.lstrip("0") or "0"
    maximum_text = str(maximum)
    if len(normalized) > len(maximum_text):
        return None
    if len(normalized) == len(maximum_text) and normalized > maximum_text:
        return None
    return int(normalized)


class NimEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    MAX_PILES = 100
    MAX_PILE_SIZE = 1_000_000
    action_pattern = (
        r"^\s*(?P<bracket>\[)?\s*"
        r"(?P<pile>[0-9]+)\s+(?P<quantity>[0-9]+)\s*"
        r"(?(bracket)\])\s*$"
    )

    def __init__(self, piles: List[int] = None):
        """
        Args:
            piles (List[int]): Initial sizes of the piles (e.g. [3, 5, 7]). If None, defaults to [3,4,5].
        """
        initial_piles = [3, 4, 5] if piles is None else piles
        if not isinstance(initial_piles, list) or not initial_piles:
            raise ValueError("piles must be a non-empty list of non-negative integers.")
        if any(type(pile) is not int or pile < 0 for pile in initial_piles):
            raise ValueError("piles must contain only non-negative integers.")
        if len(initial_piles) > self.MAX_PILES:
            raise ValueError(f"piles cannot contain more than {self.MAX_PILES} piles.")
        if any(pile > self.MAX_PILE_SIZE for pile in initial_piles):
            raise ValueError(f"pile sizes cannot exceed {self.MAX_PILE_SIZE}.")
        if not any(initial_piles):
            raise ValueError("At least one pile must contain an object.")
        self.initial_piles = initial_piles.copy()

    @property
    def action_format(self) -> str:
        pile = next(index for index, size in enumerate(self.initial_piles) if size)
        quantity = min(3, self.initial_piles[pile])
        return (
            f"a pile number from 0 to {len(self.initial_piles) - 1} and how many objects to remove from it, "
            f"separated by a space, for example '{pile} {quantity}'"
        )

    def setup(self) -> Dict[str, Any]:
        return {"piles": self.initial_piles.copy()}

    def prompt(self, player_id: int) -> str:
        return (
            f"Welcome to Nim, Player {player_id}!\nRules:\n- On your turn, remove at least one object from exactly one pile.\n"
            "- Remove objects with the format 'pile quantity', e.g. '0 3' removes 3 objects from pile 0.\n- Whoever takes the last object(s) wins!"
        )

    def render(self, player_id: int) -> str:
        return "Current Piles:\n" + self._render_piles()

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        piles = self.game_state["piles"]
        pile_index = _parse_bounded_uint(move.group("pile"), len(piles) - 1)
        if pile_index is None:
            return self.invalid("Pile index is out of range.")
        quantity_text = move.group("quantity")
        if not quantity_text.strip("0"):
            return self.invalid("Must remove at least 1 object.")
        quantity = _parse_bounded_uint(quantity_text, piles[pile_index])
        if quantity is None:
            return self.invalid(
                f"Cannot remove the requested quantity from pile {pile_index} "
                f"(only {piles[pile_index]} left)."
            )
        piles[pile_index] -= quantity
        self.broadcast(f"Player {player_id} removes {quantity} from pile {pile_index}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if all(pile == 0 for pile in piles):
            return self.winner(player_id, reason=f"Player {player_id} took the last object(s)!")
        return None

    def get_board_str(self):
        return create_board_str(self.game_state["piles"])

    def _render_piles(self) -> str:
        return "\n".join(f"  pile {i}: {amt}" for i, amt in enumerate(self.game_state["piles"]))
