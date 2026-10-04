import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta
from textarena.envs.MemoryGame.renderer import create_board_str


def _parse_grid_index(text: str, grid_size: int) -> Optional[int]:
    """Parse an in-bounds decimal coordinate without building a huge integer."""
    normalized = text.lstrip("0") or "0"
    maximum_text = str(grid_size - 1)
    if len(normalized) > len(maximum_text):
        return None
    if len(normalized) == len(maximum_text) and normalized > maximum_text:
        return None
    return int(normalized)


def _pair_label(index: int) -> str:
    """Return spreadsheet-style labels: A..Z, AA..AZ, BA..."""
    label = ""
    while True:
        index, remainder = divmod(index, 26)
        label = chr(65 + remainder) + label
        if index == 0:
            return label
        index -= 1


class MemoryGameEnv(ta.GameEnv):
    """ Environment for Memory Game """
    min_players = 2
    max_players = 2
    MAX_GRID_SIZE = 20
    action_pattern = (
        r"^\s*(?P<bracket>\[)?\s*"
        r"(?P<r1>[0-9]+)\s+(?P<c1>[0-9]+)\s+"
        r"(?P<r2>[0-9]+)\s+(?P<c2>[0-9]+)\s*"
        r"(?(bracket)\])\s*$"
    )

    def __init__(self, grid_size: Optional[int] = 4, max_turns: Optional[int] = 100):
        """
        Args:
            grid_size (int): The grid size used
        """
        if type(grid_size) is not int or grid_size < 2 or grid_size % 2 != 0:
            raise ValueError("grid_size must be an even integer of at least 2.")
        if grid_size > self.MAX_GRID_SIZE:
            raise ValueError(f"grid_size cannot exceed {self.MAX_GRID_SIZE}.")
        if max_turns is not None and (type(max_turns) is not int or max_turns < 1):
            raise ValueError("max_turns must be None or a positive integer.")
        self.grid_size = grid_size
        self.max_turns = max_turns

    def setup(self) -> Dict[str, Any]:
        return {"board": self._generate_board(), "matched_positions": set(), "score": {0: 0, 1: 0}, "scores": {0: {"Score": 0}, 1: {"Score": 0}}}

    def prompt(self, player_id: int) -> str:
        turn_limit_rule = (
            ""
            if self.max_turns is None
            else f" or after {self.max_turns} completed turns"
        )
        return (
            f"You are Player {player_id}. You are playing the Memory Game.\n"
            "Your goal is to match more pairs of cards on the board, than your opponent.\n"
            "On your turn, select two cards to flip by entering the row and column numbers of the first and second card respectively, e.g. '0 1 1 0', where the first card is in row 0 and column 1, and the second card is in row 1 and column 0.\n"
            "If the two cards match, you get a point, the cards remain face up, and you take another turn. If they do not match, the cards are flipped back face down, e.g. '.'.\n"
            f"The game ends when all pairs have been matched{turn_limit_rule}. The player with the higher score wins."
        )

    def render(self, player_id: int) -> str:
        return f"Current board:\n{self._render_board()}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        positions = tuple(
            _parse_grid_index(move.group(name), self.grid_size)
            for name in ("r1", "c1", "r2", "c2")
        )
        if any(position is None for position in positions):
            return self.invalid(f"Invalid move. Player {player_id} selected an out-of-bounds position.")
        r1, c1, r2, c2 = positions
        if (r1, c1) == (r2, c2):
            return self.invalid(f"Invalid move. Player {player_id} selected the same card twice.")
        if (r1, c1) in gs["matched_positions"] or (r2, c2) in gs["matched_positions"]:
            return self.invalid(f"Invalid move. Player {player_id} selected one or both cards that have already been matched.")

        if gs["board"][r1][c1] == gs["board"][r2][c2]:
            gs["score"][player_id] += 1
            gs["matched_positions"].update([(r1, c1), (r2, c2)])
            gs["scores"] = {0: {"Score": gs["score"][0]}, 1: {"Score": gs["score"][1]}}
            self.broadcast(f"The cards selected by Player {player_id} at positions ({r1}, {c1}) and ({r2}, {c2}) match!", ta.ObservationType.GAME_MESSAGE)
            if len(gs["matched_positions"]) == self.grid_size ** 2:
                if gs["score"][0] == gs["score"][1]:
                    return self.draw(reason="Both players matched the same number of pairs of cards.")
                winner_id = max(gs["score"], key=gs["score"].get)
                return self.winner(winner_id, reason=f"Player {winner_id} has won!")
            self.set_next_player(player_id)  # a match grants another turn
        else:
            pos1, pos2 = gs["board"][r1][c1], gs["board"][r2][c2]
            self.broadcast(f"The cards selected by Player {player_id} do not match. Cards at positions ({r1}, {c1}) and ({r2}, {c2}) are {pos1} and {pos2} respectively.", ta.ObservationType.GAME_MESSAGE)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        score = self.game_state["score"]
        reason = f"The turn limit has been reached. The game is over. Player 0 scored {score[0]} points, Player 1 scored {score[1]} points."
        if score[0] == score[1]:
            return self.draw(reason=reason)
        winner_id = max(score, key=score.get)
        return self.winner(winner_id, reason=f"{reason} Player {winner_id} has won!")

    def get_board_str(self):
        return create_board_str(game_state=self.game_state)

    def _generate_board(self) -> List[List[str]]:
        symbols = [_pair_label(i) for i in range((self.grid_size ** 2) // 2)] * 2
        self.rng.shuffle(symbols)
        return [symbols[i * self.grid_size:(i + 1) * self.grid_size] for i in range(self.grid_size)]

    def _render_board(self) -> str:
        gs = self.game_state
        rendered_board = "  " + " ".join(str(c) for c in range(self.grid_size)) + "\n"
        for r in range(self.grid_size):
            row = f"{r} "
            for c in range(self.grid_size):
                if (r, c) in gs["matched_positions"]: row += f"{gs['board'][r][c]} "
                else: row += ". "
            rendered_board += row.strip() + "\n"
        return rendered_board
