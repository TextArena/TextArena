import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

class QuantumTicTacToeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}
        self.max_turns = 25

    def setup(self) -> Dict[str, Any]:
        return {
            "board": [['' for _ in range(3)] for _ in range(3)],
            "classical_moves": [[None for _ in range(3)] for _ in range(3)],
            "superpositions": {},
            "move_log": [],
            "move_count": 0,
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Quantum Tic Tac Toe.\n"
            f"Your symbol is '{'X' if player_id == 1 else 'O'}', and your move numbers are always "
            f"{'even' if player_id == 1 else 'odd'} in this environment because Player 0 moves first.\n\n"
            "Goal: Win by forming a line of three classical marks (solidified from superpositions).\n\n"
            "How to Play:\n"
            "- Cells are numbered 0-8, left to right and top to bottom (0 1 2 / 3 4 5 / 6 7 8).\n"
            "- On each turn, place a spooky mark in two different open (not yet collapsed) cells by replying with the two cell numbers, e.g. 'a,b'.\n"
            "- Both halves of a spooky mark are entangled and carry your symbol and the move number, e.g. 'O1' or 'X2'.\n"
            "- You cannot place spooky marks in a square that has already collapsed (solidified).\n\n"
            "Collapse Rule:\n"
            "- If your move creates a cycle in the entanglement graph, it collapses automatically.\n"
            "- The mark you just placed becomes a classical mark in the lower-numbered of its two cells.\n"
            "- Every other spooky mark in a cell that collapses is pushed into its other cell, which can collapse further marks in turn.\n"
            "- If a collapse leaves only one open cell, it is filled automatically with the next player's classical mark.\n\n"
            "Victory:\n"
            "- The game ends when a player has three classical marks in a row.\n"
            "- If both players get a line during the same collapse, the one with the lower max move number wins.\n"
            "- A full board without a line is a draw.\n\n"
            "Example move: '0,4' places a spooky mark in cells 0 and 4."
        )

    def render(self, player_id: int) -> str:
        return f"Quantum Tic Tac Toe Board:\n\n{self._render_board()}\n\nSubmit your move as 'a,b' to place a quantum mark in two locations."

    def get_board_str(self) -> str:
        return self._render_board()

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match = re.search(r"^([0-9]+)\s*,\s*([0-9]+)$", action)
        if not match:
            return self.invalid("Invalid format. Use 'a,b'.")
        try:
            a, b = int(match.group(1)), int(match.group(2))
        except ValueError:
            return self.invalid("Cell indices are too large.")
        if a == b or a not in self.cell_mapping or b not in self.cell_mapping:
            return self.invalid("Invalid or duplicate cell indices.")
        # A spooky mark joins an unordered pair of cells. Canonicalize it so
        # reversing the submitted coordinates cannot select a different
        # automatic collapse.
        pos_a, pos_b = sorted((self.cell_mapping[a], self.cell_mapping[b]))
        gs = self.game_state
        board = gs["board"]
        if board[pos_a[0]][pos_a[1]] or board[pos_b[0]][pos_b[1]]:
            return self.invalid("One of the cells is already solidified.")

        gs["superpositions"][gs["move_count"]] = (player_id, pos_a, pos_b)
        gs["move_log"].append((gs["move_count"], player_id, pos_a, pos_b))
        gs["move_count"] += 1
        self.broadcast(
            f"Player {player_id} placed spooky mark {self._mark(player_id, gs['move_count'] - 1)} "
            f"in cells {self._cell(pos_a)} and {self._cell(pos_b)}.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        return self._resolve_cycles()

    @staticmethod
    def _mark(player_id: int, move_id: int) -> str:
        return f"{'O' if player_id == 0 else 'X'}{move_id + 1}"

    @staticmethod
    def _cell(position: Tuple[int, int]) -> int:
        return position[0] * 3 + position[1]

    def _render_board(self):
        """Classical marks in the grid (open cells show their number), then every spooky mark and the open cells."""
        gs = self.game_state
        rows = []
        for r in range(3):
            cells = []
            for c in range(3):
                if gs["board"][r][c]:
                    move_number = gs["classical_moves"][r][c]
                    cells.append(f"{gs['board'][r][c]}{move_number if move_number is not None else ''}")
                else:
                    cells.append(str(r * 3 + c))
            rows.append("|".join(f" {cell:<2} " for cell in cells))
        spooky = "; ".join(
            f"{self._mark(pid, move_id)} in cells {self._cell(a)} and {self._cell(b)}"
            for move_id, (pid, a, b) in sorted(gs["superpositions"].items())
        )
        open_cells = ", ".join(str(self._cell(position)) for position in self._get_empty_cells())
        return (
            "\n----+----+----\n".join(rows)
            + f"\n\nSpooky marks: {spooky or 'none'}\nOpen cells: {open_cells or 'none'}"
        )

    def _resolve_cycles(self) -> Optional[ta.Outcome]:
        superpositions = self.game_state["superpositions"]
        if not superpositions:
            return None

        newest_id = max(superpositions)
        _, start, target = superpositions[newest_id]
        graph: Dict[Tuple[int, int], List[Tuple[Tuple[int, int], int]]] = {}
        for move_id, (_, a, b) in superpositions.items():
            if move_id == newest_id:
                continue
            graph.setdefault(a, []).append((b, move_id))
            graph.setdefault(b, []).append((a, move_id))

        queue = deque([start])
        parent: Dict[Tuple[int, int], Tuple[Tuple[int, int], int]] = {}
        seen = {start}
        while queue:
            node = queue.popleft()
            if node == target:
                path_ids: List[int] = []
                while node != start:
                    previous, move_id = parent[node]
                    path_ids.append(move_id)
                    node = previous
                path_ids.reverse()
                return self._collapse_superpositions(path_ids + [newest_id], seed_move_id=newest_id)
            for neighbor, move_id in graph.get(node, []):
                if neighbor not in seen:
                    seen.add(neighbor)
                    parent[neighbor] = (node, move_id)
                    queue.append(neighbor)
        return None

    def _collapse_move(self, move_id: int, chosen: Tuple[int, int]) -> None:
        gs = self.game_state
        player_id, a, b = gs["superpositions"].pop(move_id)
        if chosen not in (a, b) or gs["board"][chosen[0]][chosen[1]]:
            raise RuntimeError("Inconsistent quantum collapse")
        symbol = 'X' if player_id == 1 else 'O'
        r, c = chosen
        gs["board"][r][c] = symbol
        gs["classical_moves"][r][c] = move_id + 1
        self.broadcast(
            f"Superposition {symbol}{move_id + 1} resolved at cell {self._cell(chosen)}.",
            ta.ObservationType.GAME_MESSAGE,
        )

    def _get_empty_cells(self):
        board = self.game_state["board"]
        return [(r, c) for r in range(3) for c in range(3) if not board[r][c]]

    def _collapse_last_empty_cell(self):
        empty_cells = self._get_empty_cells()
        if len(empty_cells) != 1: return

        r, c = empty_cells[0]
        next_player_symbol = 'X' if self.current_player_id == 0 else 'O'
        self.game_state["board"][r][c] = next_player_symbol
        self.game_state["classical_moves"][r][c] = self.game_state["move_count"] + 1
        self.broadcast(
            f"Superposition for last cell resolved. Cell {self._cell((r, c))} is now "
            f"{next_player_symbol}{self.game_state['move_count'] + 1}.",
            ta.ObservationType.GAME_MESSAGE,
        )

    def _collapse_superpositions(self, move_ids: List[int], seed_move_id: Optional[int] = None) -> Optional[ta.Outcome]:
        gs = self.game_state
        superpositions = gs["superpositions"]
        if move_ids:
            seed_move_id = move_ids[-1] if seed_move_id is None else seed_move_id
            if seed_move_id not in superpositions:
                raise RuntimeError("Cycle seed is missing")
            _, preferred, _ = superpositions[seed_move_id]
            pending = deque([(seed_move_id, preferred)])
            while pending:
                move_id, chosen = pending.popleft()
                if move_id not in superpositions:
                    continue
                self._collapse_move(move_id, chosen)
                for dependent_id, (_, a, b) in list(superpositions.items()):
                    if chosen == a:
                        pending.append((dependent_id, b))
                    elif chosen == b:
                        pending.append((dependent_id, a))

        outcome = self._line_outcome()
        if outcome is not None:
            return outcome

        self._collapse_last_empty_cell()
        outcome = self._line_outcome()
        if outcome is not None:
            return outcome
        if not self._get_empty_cells():
            return self.draw(reason="The game is a draw!")
        return None

    def _line_outcome(self) -> Optional[ta.Outcome]:
        winning_maxima = {
            pid: self._winning_line_max('X' if pid == 1 else 'O')
            for pid in range(2)
        }
        winners = [pid for pid, maximum in winning_maxima.items() if maximum is not None]
        if len(winners) == 1:
            return self.winner(winners[0], reason=f"Player {winners[0]} wins with solidified marks!")
        if len(winners) == 2:
            p0_max, p1_max = winning_maxima[0], winning_maxima[1]
            if p0_max == p1_max:
                return self.draw(reason="Both players completed equally early quantum lines.")
            winner = 0 if p0_max < p1_max else 1
            return self.winner(winner, reason=f"Player {winner} wins the simultaneous collapse with the earlier line.")
        return None

    def _winning_line_max(self, symbol: str) -> Optional[int]:
        board = self.game_state["board"]
        move_numbers = self.game_state["classical_moves"]
        lines = [
            [(r, c) for c in range(3)] for r in range(3)
        ] + [
            [(r, c) for r in range(3)] for c in range(3)
        ] + [
            [(0, 0), (1, 1), (2, 2)],
            [(0, 2), (1, 1), (2, 0)],
        ]
        maxima = [
            max(move_numbers[r][c] or 0 for r, c in line)
            for line in lines
            if all(board[r][c] == symbol for r, c in line)
        ]
        return min(maxima) if maxima else None

    def _check_winner(self, symbol: str) -> bool:
        board = self.game_state["board"]
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] == symbol: return True
            if board[0][i] == board[1][i] == board[2][i] == symbol: return True
        if board[0][0] == board[1][1] == board[2][2] == symbol: return True
        if board[0][2] == board[1][1] == board[2][0] == symbol: return True

        return False
