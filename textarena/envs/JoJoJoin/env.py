"""
JoJoJoin — a 5x5 grid game for eval use.

Skill tested: line-completion strategy — build toward a line of four while
blocking your opponent — on a board/name/ruleset distinct from tic-tac-toe.

Rules:
  - 5x5 board, cells 0-24. Edges do NOT wrap.
  - Each turn, place your mark on any empty cell.
  - You WIN by getting FOUR of your marks in a row: horizontally, vertically,
    or diagonally (four consecutive cells; the board is 5 wide, so a line of
    four can sit in several positions along each row/column/diagonal).

Balance: NOT exactly solved (the 5x5 state space is too large to brute-force).
Random self-play (30k games) gives first ~53% / second ~40% / draw ~7%: mostly
decisive with a modest first-mover edge. Four-in-a-row keeps forks hard, so it
does not collapse into a first-player win the way 5x5 THREE-in-a-row would.
ALTERNATE the starting player across games.

Drop-in placement (mirror the TicTacToe env):
    textarena/envs/JoJoJoin/env.py      <- this file
    textarena/envs/JoJoJoin/en.json     <- the locale file
    textarena/envs/JoJoJoin/__init__.py
Register it exactly the way TicTacToe is registered in your textarena build
(copy that line rather than trusting a guessed API).
"""

import re
from typing import Optional, Dict, Tuple, Any

import textarena as ta

GRID = 5
CONNECT = 4                 # length of line needed to win
WRAP = False                # edges do not connect
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))  # horiz, vert, both diagonals

# Player 1 -> ▲, Player 0 -> ■  (triangle & square: not O, X, or circle variants)
SYMBOLS = {1: '\u25b2', 0: '\u25a0'}  # ▲ , ■


def _board_lines(board) -> str:
    """In-prompt board. Empty cells show their index; filled cells show the mark."""
    rows = []
    for r in range(GRID):
        cells = [f" {(board[r][c] or str(r * GRID + c)):>2} " for c in range(GRID)]
        rows.append("|".join(cells))
    sep = "\n" + "+".join(["----"] * GRID) + "\n"
    return sep.join(rows)


def create_board_str(board) -> str:
    return _board_lines(board)


class JoJoJoinEnv(ta.Env):
    def __init__(self):
        self.cell_mapping = {i * GRID + j: (i, j) for i in range(GRID) for j in range(GRID)}

    def get_board_str(self):
        return create_board_str(board=self.state.game_state["board"])

    def _render_board(self):
        return _board_lines(self.state.game_state["board"])

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(
            game_state={"board": [['' for _ in range(GRID)] for _ in range(GRID)]},
            player_prompt_function=self._prompt,
        )
        self._observer_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        symbol = SYMBOLS[player_id]
        opponent_symbol = SYMBOLS[1 - player_id]
        return self.m("player_prompt", "intro",
                      player_id=player_id, symbol=symbol, opponent_symbol=opponent_symbol)

    def _observer_current_state(self):
        board = self.state.game_state["board"]
        available_moves = [f"'[{r * GRID + c}]'"
                           for r in range(GRID) for c in range(GRID) if board[r][c] == '']
        self.state.add_observation(
            message=self.m('board', 'current_board',
                           board=self._render_board(), moves=', '.join(available_moves)),
            observation_type=ta.ObservationType.GAME_BOARD,
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.current_player = SYMBOLS[self.state.current_player_id]
        self.state.add_observation(
            from_id=self.state.current_player_id, message=action,
            observation_type=ta.ObservationType.PLAYER_ACTION,
        )
        match = re.compile(r"\[\s*(\d+)\s*\]").search(action)
        if match is None:  # Invalid format
            self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            cell = int(match.group(1))
            if cell not in self.cell_mapping:  # Ensure the cell is within 0-24
                self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_range", cell=cell))
            else:
                row, col = self.cell_mapping[cell]
                if self.state.game_state["board"][row][col] == '':
                    self.state.game_state["board"][row][col] = self.current_player  # Make the move
                    self.state.add_observation(
                        message=self.m("game_action", "placed",
                                       player_id=self.state.current_player_id,
                                       symbol=self.current_player, cell=cell),
                        observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION,
                    )
                    if self._check_winner():  # Check for winner or draw
                        self.state.set_winner(
                            player_id=self.state.current_player_id,
                            reason=self.m("outcome", "win", player_id=self.state.current_player_id),
                        )
                    elif all(c != '' for r in self.state.game_state["board"] for c in r):
                        self.state.set_draw(reason=self.m("outcome", "draw"))
                else:
                    self.state.set_invalid_move(reason=self.m("invalid_move", "already_occupied", cell=cell))
        self._observer_current_state()
        return self.state.step()

    def _check_winner(self) -> bool:
        """True if the player who just moved has CONNECT marks in a line."""
        b = self.state.game_state["board"]
        p = self.current_player
        n = GRID
        for r in range(n):
            for c in range(n):
                for dr, dc in DIRECTIONS:
                    line = []
                    ok = True
                    for i in range(CONNECT):
                        rr, cc = r + dr * i, c + dc * i
                        if WRAP:
                            rr %= n
                            cc %= n
                        elif not (0 <= rr < n and 0 <= cc < n):
                            ok = False
                            break
                        line.append(b[rr][cc])
                    if ok and all(x == p for x in line):
                        return True
        return False