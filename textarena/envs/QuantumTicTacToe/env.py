import re
from typing import Optional, Dict, Tuple, List, Any, Set
import textarena as ta

class QuantumTicTacToeEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=2, max_turns=25, seed=seed)
        self.state.reset(game_state={"board": [['' for _ in range(3)] for _ in range(3)], "superpositions": {}, "move_log": []}, player_prompt_function=self._prompt)
        self.move_count = 0
        self._observer_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in Quantum Tic Tac Toe.\n"
            f"Your symbol is '{'X' if player_id == 1 else 'O'}', and your move numbers are always {'odd' if player_id == 1 else 'even'} (e.g., X1, X3 or O2, O4).\n\n"
            "Goal: Win by forming a line of three classical marks (solidified from superpositions).\n\n"
            "How to Play:\n"
            "- On each turn, place a spooky mark in two different empty squares using the format '[a,b]'.\n"
            "- These marks are entangled, and labeled like 'X1 / X1' or 'O4 / O4'.\n"
            "- You cannot place spooky marks in a square that has already collapsed (solidified).\n\n"
            "Collapse Rule:\n"
            "- If your move creates a cycle in the entanglement graph, it collapses automatically.\n"
            "- Each spooky mark in the cycle turns into a classical mark in one of its two positions.\n"
            "- Any dependent spooky marks also collapse.\n\n"
            "Victory:\n"
            "- The game ends when a player has three classical marks in a row.\n"
            "- If both players get a line during the same collapse, the one with the lower max move number wins.\n\n"
            "Example move: '[0,4]' places a spooky mark in cells 0 and 4."
        )

    def _render_board(self):
        # Build a dictionary from cell -> list of marks
        cell_marks = {(r, c): [] for r in range(3) for c in range(3)}
        for move_id, (pid, a, b) in self.state.game_state["superpositions"].items():
            mark = f"{move_id}{'A' if pid == 0 else 'B'}"
            cell_marks[a].append(mark)
            cell_marks[b].append(mark)

        def render_cell(r, c):
            if self.state.game_state['board'][r][c]: return [f"[{r * 3 + c}]", "", f"  {self.state.game_state['board'][r][c]}"]
            elif cell_marks[(r, c)]: 
                lines = [f"[{r * 3 + c}]"]
                if len(cell_marks[(r, c)]) <= 2: lines += [" / ".join(cell_marks[(r, c)]), ""]
                else: lines += [" / ".join(cell_marks[(r, c)][:2]), " / ".join(cell_marks[(r, c)][2:])]
                return lines
            else: return [f"[{r * 3 + c}]", "", ""]

        rendered_rows = []
        for r in range(3):
            row_lines = [""] * 3  # three lines per cell
            for c in range(3):
                cell = render_cell(r, c)
                for i in range(3): row_lines[i] += f"{cell[i]:^10}"
            rendered_rows.append("\n".join(row_lines))
        return "\n" + "\n" + "\n---+----------+----------+---\n".join(rendered_rows) + "\n"

    def _observer_current_state(self):
        self.state.add_observation(message=f"Quantum Tic Tac Toe Board:\n\n{self._render_board()}\n\nSubmit your move as '[a,b]' to place a quantum mark in two locations.", observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r"\[(\d+),(\d+)\]", action.replace(" ", ""))
        if not match: self.state.set_invalid_move(reason="Invalid format. Use '[a,b]'.")
        else:
            a, b = int(match.group(1)), int(match.group(2))
            if a == b or a not in self.cell_mapping or b not in self.cell_mapping: self.state.set_invalid_move(reason="Invalid or duplicate cell indices.")
            else:
                pos_a, pos_b = self.cell_mapping[a], self.cell_mapping[b]
                board = self.state.game_state["board"]
                if board[pos_a[0]][pos_a[1]] or board[pos_b[0]][pos_b[1]]: self.state.set_invalid_move(reason="One of the cells is already solidified.")
                else:
                    self.state.game_state["superpositions"][self.move_count] = (self.state.current_player_id, pos_a, pos_b)
                    self.state.game_state["move_log"].append((self.move_count, self.state.current_player_id, pos_a, pos_b))
                    self.move_count += 1
                    self.state.add_observation(message=f"Player {self.state.current_player_id} placed their symbol in a superposition between cells {pos_a} and {pos_b}.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    self._resolve_cycles()
        self._observer_current_state()
        return self.state.step()

    def _resolve_cycles(self):
        superpositions = self.state.game_state["superpositions"]
        graph = {}
        for move_id, (_, a, b) in superpositions.items():
            graph.setdefault(a, []).append((b, move_id))
            graph.setdefault(b, []).append((a, move_id))

        visited = set()
        def dfs(node, path, seen_ids):
            if node in path:
                cycle = path[path.index(node):]
                involved_ids = seen_ids[path.index(node):]
                return cycle, involved_ids
            if node not in graph: return None
            for neighbor, move_id in graph[node]:
                if move_id in seen_ids: continue
                result = dfs(neighbor, path + [node], seen_ids + [move_id])
                if result: return result
            return None

        for start in graph:
            result = dfs(start, [], [])
            if result:
                cycle, involved_ids = result
                self._collapse_superpositions(involved_ids)
                break

    def _collapse_dependent_superpositions(self):
        while True:
            has_collapsed = False
            for move_id, (player_id, (r0, c0), (r1, c1)) in self.state.game_state["superpositions"].items():
                if self.state.game_state["board"][r0][c0]:
                    assert not self.state.game_state["board"][r1][c1], "The other cell cannot be filled."
                    symbol = 'X' if player_id == 1 else 'O'
                    self.state.game_state["board"][r1][c1] = symbol
                    self.state.add_observation(message=f"Dependent superposition resolved. Cell ({r1}, {c1}) is now {symbol}.", observation_type=ta.ObservationType.GAME_MESSAGE)
                    del self.state.game_state["superpositions"][move_id]
                    has_collapsed = True
                    break

                if self.state.game_state["board"][r1][c1]:
                    assert not self.state.game_state["board"][r0][c0], "The other cell cannot be filled."
                    symbol = 'X' if player_id == 1 else 'O'
                    self.state.game_state["board"][r0][c0] = symbol
                    self.state.add_observation(message=f"Dependent superposition resolved. Cell ({r0}, {c0}) is now {symbol}.", observation_type=ta.ObservationType.GAME_MESSAGE)
                    del self.state.game_state["superpositions"][move_id]
                    has_collapsed = True
                    break
            if not has_collapsed: break

    def _get_empty_cells(self):
        empty_cells = []
        for r in range(3):
            for c in range(3):
                if not self.state.game_state["board"][r][c]: empty_cells.append((r, c))
        return empty_cells

    def _collapse_last_empty_cell(self):
        empty_cells = self._get_empty_cells()
        if len(empty_cells) != 1: return

        r, c = empty_cells[0]
        next_player_symbol = 'X' if self.state.current_player_id == 0 else 'O'
        self.state.game_state["board"][r][c] = next_player_symbol
        self.state.add_observation(message=f"Superposition for last cell resolved. Cell ({r}, {c}) is now {next_player_symbol}.", observation_type=ta.ObservationType.GAME_MESSAGE)

    def _check_superpositions(self):
        for _, (_, (r0, c0), (r1, c1)) in self.state.game_state["superpositions"].items():
            assert not self.state.game_state["board"][r0][c0] and not self.state.game_state["board"][r1][c1], "Both cells cannot be filled."

    def _collapse_superpositions(self, move_ids: List[int]):
        board = self.state.game_state["board"]
        superpositions = self.state.game_state["superpositions"]
        for move_id in move_ids:
            if move_id not in superpositions:
                continue
            player_id, a, b = superpositions.pop(move_id)
            symbol = 'X' if player_id == 1 else 'O'
            for r, c in [a, b]:
                if board[r][c] == '':
                    board[r][c] = symbol
                    self.state.add_observation(message=f"Superposition resolved. Cell ({r}, {c}) is now {symbol}.", observation_type=ta.ObservationType.GAME_MESSAGE)
                    break  # collapse to the first available cell
        # Collapse dependent superpositions
        self._collapse_dependent_superpositions()
        # Validate superpositions
        self._check_superpositions()
        # Collapse last empty cell
        self._collapse_last_empty_cell()
        # Check for a win
        for pid in range(2):
            symbol = 'X' if pid == 1 else 'O'
            if self._check_winner(symbol): self.state.set_winner(player_id=pid, reason=f"Player {pid} wins with solidified marks!")

        # Check for a draw
        if not self._get_empty_cells():
            self.state.set_draw(reason="The game is a draw!")

    def _check_winner(self, symbol: str) -> bool:
        board = self.state.game_state["board"]
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] == symbol: return True
            if board[0][i] == board[1][i] == board[2][i] == symbol: return True
        if board[0][0] == board[1][1] == board[2][2] == symbol: return True
        if board[0][2] == board[1][1] == board[2][0] == symbol: return True

        return False
