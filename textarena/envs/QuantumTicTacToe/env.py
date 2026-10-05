import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

class QuantumTicTacToeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"(?i)^(?:([0-9]+)\s*,\s*([0-9]+)|collapse\s+([0-9]+))$"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}
        self.max_turns = 25

    @property
    def action_format(self) -> str:
        move_id = self.game_state["pending_collapse"]
        if move_id is None:
            return "two different open cells separated by a comma, for example '0,4'"
        player_id, a, b = self.game_state["superpositions"][move_id]
        return (
            f"'collapse' followed by cell {self._cell(a)} or {self._cell(b)}, the two cells of mark "
            f"{self._mark(player_id, move_id)}, for example 'collapse {self._cell(a)}'"
        )

    def setup(self) -> Dict[str, Any]:
        return {
            "board": [['' for _ in range(3)] for _ in range(3)],
            "classical_moves": [[None for _ in range(3)] for _ in range(3)],
            "superpositions": {},
            "move_log": [],
            "move_count": 0,
            "pending_collapse": None,  # id of the mark that closed a cycle, until the opponent chooses its cell
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
            "- If a move closes a cycle in the entanglement graph (for example, a second mark in the same two cells), the "
            "cycle collapses, and the opponent of the player who closed it chooses how.\n"
            "- The chooser replies 'collapse c', where c is one of the two cells of the mark that closed the cycle. That "
            "mark becomes a classical mark in cell c.\n"
            "- Every other spooky mark in a cell that collapses is pushed into its other cell, which can collapse further "
            "marks in turn. The board lists what each choice would do.\n"
            "- After the collapse, the chooser places their own spooky mark with a separate reply.\n"
            "- If a collapse leaves only one open cell, it is filled automatically with the chooser's classical mark.\n\n"
            "Victory:\n"
            "- The game ends when a player has three classical marks in a row.\n"
            "- If both players get a line during the same collapse, the one with the lower max move number wins.\n"
            "- A full board without a line is a draw.\n\n"
            "Examples: '0,4' places a spooky mark in cells 0 and 4. If Player 0 opens with '0,4' and Player 1 also "
            "plays '0,4', Player 1 has closed a cycle, so Player 0 replies 'collapse 0' (X2 becomes classical in "
            "cell 0 and O1 in cell 4) or 'collapse 4' (X2 in cell 4 and O1 in cell 0)."
        )

    def render(self, player_id: int) -> str:
        board = f"Quantum Tic Tac Toe Board:\n\n{self._render_board()}\n\n"
        move_id = self.game_state["pending_collapse"]
        if move_id is None:
            return board + "Submit your move as 'a,b' to place a quantum mark in two locations."
        return board + f"{self._collapse_options(move_id)}\nSubmit 'collapse <cell>' to choose."

    def get_board_str(self) -> str:
        return self._render_board()

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        pending = gs["pending_collapse"]
        try:
            cells = [int(group) for group in move.groups() if group is not None]
        except ValueError:
            return self.invalid("Cell indices are too large.")

        if move.group(3) is not None:
            if pending is None:
                return self.invalid("No collapse is pending. Place a spooky mark in two open cells, e.g. '0,4'.")
            _, a, b = gs["superpositions"][pending]
            options = {self._cell(a): a, self._cell(b): b}
            if cells[0] not in options:
                return self.invalid(f"Choose cell {self._cell(a)} or {self._cell(b)}, e.g. 'collapse {self._cell(a)}'.")
            return self._resolve_collapse(player_id, pending, options[cells[0]])

        if pending is not None:
            return self.invalid(f"A cycle is waiting to collapse. {self._collapse_options(pending)}")
        a, b = cells
        if a == b or a not in self.cell_mapping or b not in self.cell_mapping:
            return self.invalid("Invalid or duplicate cell indices.")
        # A spooky mark joins an unordered pair of cells; storing it in cell order makes '4,0' and '0,4' identical.
        pos_a, pos_b = sorted((self.cell_mapping[a], self.cell_mapping[b]))
        board = gs["board"]
        if board[pos_a[0]][pos_a[1]] or board[pos_b[0]][pos_b[1]]:
            return self.invalid("One of the cells is already solidified.")

        move_id = gs["move_count"]
        gs["superpositions"][move_id] = (player_id, pos_a, pos_b)
        gs["move_log"].append((move_id, player_id, pos_a, pos_b))
        gs["move_count"] += 1
        self.broadcast(
            f"Player {player_id} placed spooky mark {self._mark(player_id, move_id)} "
            f"in cells {self._cell(pos_a)} and {self._cell(pos_b)}.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        if self._closes_cycle(move_id):
            gs["pending_collapse"] = move_id
            self.broadcast(
                f"Mark {self._mark(player_id, move_id)} closed a cycle. Player {1 - player_id} chooses how it "
                f"collapses. {self._collapse_options(move_id)}",
                ta.ObservationType.GAME_MESSAGE,
            )
        return None

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

    def _closes_cycle(self, move_id: int) -> bool:
        """Whether the other spooky marks already connect the two cells of this mark."""
        superpositions = self.game_state["superpositions"]
        _, start, target = superpositions[move_id]
        graph: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        for other_id, (_, a, b) in superpositions.items():
            if other_id != move_id:
                graph.setdefault(a, []).append(b)
                graph.setdefault(b, []).append(a)
        seen, frontier = {start}, [start]
        while frontier:
            node = frontier.pop()
            if node == target:
                return True
            for neighbor in graph.get(node, []):
                if neighbor not in seen:
                    seen.add(neighbor)
                    frontier.append(neighbor)
        return False

    def _collapse_plan(self, move_id: int, chosen: Tuple[int, int]) -> List[Tuple[int, Tuple[int, int]]]:
        """Where every affected spooky mark ends up if `move_id` collapses into `chosen`, in resolution order."""
        superpositions = self.game_state["superpositions"]
        plan: Dict[int, Tuple[int, int]] = {}
        pending = deque([(move_id, chosen)])
        while pending:
            current_id, cell = pending.popleft()
            if current_id in plan:
                continue
            plan[current_id] = cell
            for dependent_id, (_, a, b) in superpositions.items():
                if dependent_id not in plan and cell in (a, b):
                    pending.append((dependent_id, b if cell == a else a))
        return list(plan.items())

    def _collapse_options(self, move_id: int) -> str:
        player_id, a, b = self.game_state["superpositions"][move_id]
        options = []
        for cell in (a, b):
            placements = ", ".join(
                f"{self._mark(self.game_state['superpositions'][mid][0], mid)} in cell {self._cell(position)}"
                for mid, position in self._collapse_plan(move_id, cell)
            )
            options.append(f"'collapse {self._cell(cell)}' puts {placements}")
        return (
            f"Collapse options for {self._mark(player_id, move_id)} (cells {self._cell(a)} and {self._cell(b)}): "
            + "; ".join(options) + "."
        )

    def _resolve_collapse(self, player_id: int, move_id: int, chosen: Tuple[int, int]) -> Optional[ta.Outcome]:
        gs = self.game_state
        plan = self._collapse_plan(move_id, chosen)
        gs["pending_collapse"] = None
        self.broadcast(
            f"Player {player_id} collapsed {self._mark(gs['superpositions'][move_id][0], move_id)} into cell "
            f"{self._cell(chosen)}.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        for current_id, cell in plan:
            self._collapse_move(current_id, cell)
        self.set_next_player(player_id)
        return self._finish_collapse(player_id)

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

    def _collapse_last_empty_cell(self, player_id: int):
        empty_cells = self._get_empty_cells()
        if len(empty_cells) != 1: return

        r, c = empty_cells[0]
        symbol = 'X' if player_id == 1 else 'O'
        self.game_state["board"][r][c] = symbol
        self.game_state["classical_moves"][r][c] = self.game_state["move_count"] + 1
        self.broadcast(
            f"Superposition for last cell resolved. Cell {self._cell((r, c))} is now "
            f"{symbol}{self.game_state['move_count'] + 1}.",
            ta.ObservationType.GAME_MESSAGE,
        )

    def _finish_collapse(self, player_id: int) -> Optional[ta.Outcome]:
        """Score the board after a collapse chosen by `player_id`, who would move next."""
        outcome = self._line_outcome()
        if outcome is not None:
            return outcome

        self._collapse_last_empty_cell(player_id)
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
