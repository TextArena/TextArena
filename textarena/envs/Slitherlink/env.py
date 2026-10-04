import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict, deque

import textarena as ta


class SlitherlinkEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False

    max_grid_cells = 10_000
    max_action_chars = 4096
    _ACTION_RE = re.compile(r"([hv])\s+(\d+)\s+(\d+)", re.I)

    def __init__(self, rows: int = 4, cols: int = 4, max_turns: int = 200):
        """
        Initialize Slitherlink environment with configurable grid size.

        Args:
            rows: Number of rows in the grid
            cols: Number of columns in the grid
            max_turns: Maximum number of moves allowed
        """
        if not isinstance(rows, int) or isinstance(rows, bool) or rows < 2:
            raise ValueError("rows must be an integer of at least 2")
        if not isinstance(cols, int) or isinstance(cols, bool) or cols < 2:
            raise ValueError("cols must be an integer of at least 2")
        if rows * cols > self.max_grid_cells:
            raise ValueError(
                f"rows and cols create more than {self.max_grid_cells} cells"
            )
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        self.R = rows
        self.C = cols
        self.max_turns = max_turns

    @property
    def clues(self) -> List[List[Optional[int]]]: return self.game_state["clues"]

    @property
    def h_edges(self) -> Set[Tuple[int, int]]: return self.game_state["h_edges"]

    @property
    def v_edges(self) -> Set[Tuple[int, int]]: return self.game_state["v_edges"]

    def setup(self) -> Dict[str, Any]:
        clues, solution_h_edges, solution_v_edges = self._generate_puzzle()
        return {
            "clues": clues,
            "h_edges": set(),  # (row, col) indexes the *upper-left* dot
            "v_edges": set(),
            "solution_h_edges": frozenset(solution_h_edges),
            "solution_v_edges": frozenset(solution_v_edges),
        }

    def _generate_puzzle(
        self,
    ) -> Tuple[
        List[List[Optional[int]]],
        Set[Tuple[int, int]],
        Set[Tuple[int, int]],
    ]:
        """Generate a random solvable Slitherlink puzzle by creating a solution first."""
        solution_h_edges: Set[Tuple[int, int]] = set()
        solution_v_edges: Set[Tuple[int, int]] = set()

        # Generate a random simple loop
        self._generate_random_loop(solution_h_edges, solution_v_edges)

        # Create clues based on the solution
        clues = [[None for _ in range(self.C)] for _ in range(self.R)]

        # For each cell, count how many edges surround it in the solution
        for r in range(self.R):
            for c in range(self.C):
                edge_count = 0
                if (r, c) in solution_h_edges:         edge_count += 1
                if (r+1, c) in solution_h_edges:       edge_count += 1
                if (r, c) in solution_v_edges:         edge_count += 1
                if (r, c+1) in solution_v_edges:       edge_count += 1

                # Add clue with some probability (not every cell needs a clue)
                if self.rng.random() < 0.6:  # 60% chance to add a clue
                    clues[r][c] = edge_count

        # A clue-free puzzle makes clue progress permanently zero and therefore
        # cannot satisfy _is_solved, even if the loop itself is correct.
        if not any(clue is not None for row in clues for clue in row):
            clue_r = self.rng.randrange(self.R)
            clue_c = self.rng.randrange(self.C)
            edge_count = 0
            if (clue_r, clue_c) in solution_h_edges:
                edge_count += 1
            if (clue_r + 1, clue_c) in solution_h_edges:
                edge_count += 1
            if (clue_r, clue_c) in solution_v_edges:
                edge_count += 1
            if (clue_r, clue_c + 1) in solution_v_edges:
                edge_count += 1
            clues[clue_r][clue_c] = edge_count

        return clues, solution_h_edges, solution_v_edges

    def _generate_random_loop(self, h_edges: Set[Tuple[int, int]], v_edges: Set[Tuple[int, int]]):
        """Generate a simple random rectangular loop."""
        # Choose random rectangle dimensions within the grid
        min_size = 2
        max_width = min(self.C, 4)
        max_height = min(self.R, 4)

        width = self.rng.randint(min_size, max_width)
        height = self.rng.randint(min_size, max_height)

        # Choose random position for the rectangle
        start_r = self.rng.randint(0, self.R - height)
        start_c = self.rng.randint(0, self.C - width)

        # Add horizontal edges (top and bottom of rectangle)
        for c in range(start_c, start_c + width):
            h_edges.add((start_r, c))                    # top edge
            h_edges.add((start_r + height, c))           # bottom edge

        # Add vertical edges (left and right of rectangle)
        for r in range(start_r, start_r + height):
            v_edges.add((r, start_c))                    # left edge
            v_edges.add((r, start_c + width))            # right edge

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing Slitherlink on a {self.R}x{self.C} grid of cells!\n"
            "Draw a single continuous loop along the grid lines so each numbered cell has exactly that many of its four "
            "sides on the loop. The loop must close and may not branch or cross itself. '·' means no constraint.\n"
            f"Dots are numbered by row 0 to {self.R} and column 0 to {self.C}, as labeled on the board; cell (r, c) is "
            "the square whose top-left corner is dot (r, c).\n"
            "Each move toggles (draws or erases) one edge:\n"
            f"  'h r c' - the horizontal edge from dot (r, c) to dot (r, c+1), the top side of cell (r, c); r is 0 to {self.R}, c is 0 to {self.C - 1}\n"
            f"  'v r c' - the vertical edge from dot (r, c) to dot (r+1, c), the left side of cell (r, c); r is 0 to {self.R - 1}, c is 0 to {self.C}\n"
            "For example, 'h 0 0' toggles the top side of the top-left cell.\n"
            f"You have up to {self.max_turns} moves to solve the puzzle.\n"
            "An edge outside the board or a malformed reply is an invalid move. It changes nothing and you may try again, "
            "but two invalid moves in a row end the game."
        )

    def render(self, player_id: int) -> str:
        return f"{self._render_board()}\nClues satisfied: {self._progress():.0%}"

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        action_text = move.strip()
        m = self._ACTION_RE.fullmatch(action_text.lower())
        if not m:
            return self.invalid("Bad action format. Use 'h row col' or 'v row col'.")

        kind, r, c = m.group(1), int(m.group(2)), int(m.group(3))
        if not self._valid_edge(kind, r, c):
            return self.invalid("Edge outside board.")

        self._toggle_edge(kind, r, c)

        if self._is_solved():
            return self.outcome({0: 1.0}, reason="🎉 You formed a single loop! Puzzle solved!")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome({0: self._partial_score()}, reason="Move limit reached. Puzzle unfinished.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._partial_score()}, reason=f"Invalid Move: {reason}")

    def _partial_score(self) -> float:
        """Drawn edges on the hidden solution loop minus drawn edges off it, as a share of the loop's length.

        An empty board scores 0, every wrong edge cancels a right one, and only drawing the loop itself
        (which wins) reaches 1.
        """
        solution_h, solution_v = self.game_state["solution_h_edges"], self.game_state["solution_v_edges"]
        on_loop = len(self.h_edges & solution_h) + len(self.v_edges & solution_v)
        off_loop = len(self.h_edges - solution_h) + len(self.v_edges - solution_v)
        return max(0, on_loop - off_loop) / (len(solution_h) + len(solution_v))

    def _valid_edge(self, kind: str, r: int, c: int) -> bool:
        if kind == 'h': return 0 <= r <= self.R and 0 <= c < self.C
        else:           return 0 <= r < self.R and 0 <= c <= self.C  # 'v'

    def _toggle_edge(self, kind: str, r: int, c: int):
        edges = self.h_edges if kind == 'h' else self.v_edges
        edge = (r, c)
        edges.discard(edge) if edge in edges else edges.add(edge)

    def _progress(self) -> float:
        """Fraction of clue cells currently satisfied."""
        satisfied, total = self._clue_counts()
        return satisfied / max(1, total)

    def _clue_counts(self) -> Tuple[int, int]:
        satisfied = 0
        total = 0
        for r in range(self.R):
            for c in range(self.C):
                if self.clues[r][c] is not None:
                    total += 1
                    if self._cell_edge_count(r, c) == self.clues[r][c]:
                        satisfied += 1
        return satisfied, total

    def _cell_edge_count(self, r: int, c: int) -> int:
        cnt = 0
        if (r, c) in self.h_edges:               cnt += 1
        if (r+1, c) in self.h_edges:             cnt += 1
        if (r, c) in self.v_edges:               cnt += 1
        if (r, c+1) in self.v_edges:             cnt += 1
        return cnt

    def _is_solved(self) -> bool:
        return self._progress() == 1.0 and self._is_single_loop()

    def _is_single_loop(self) -> bool:
        # 1. Every dot has 0 or 2 incident edges AND at least one edge exists
        if not (self.h_edges or self.v_edges):
            return False

        deg = defaultdict(int)
        for (r, c) in self.h_edges:
            deg[(r, c)]     += 1
            deg[(r, c+1)]   += 1
        for (r, c) in self.v_edges:
            deg[(r, c)]     += 1
            deg[(r+1, c)]   += 1
        if any(v not in (0, 2) for v in deg.values()):
            return False
        # 2. Exactly one loop → start BFS from any edge-dot and ensure all
        start = next(iter(deg.keys()))
        seen = set([start])
        q = deque([start])
        while q:
            p = q.popleft()
            for nb in self._neighbors_with_edge(p):
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        return len([p for p in deg if deg[p] == 2]) == len(seen)

    def _neighbors_with_edge(self, dot: Tuple[int, int]):
        r, c = dot
        if (r, c) in self.h_edges:           yield (r, c+1)
        if (r, c-1) in self.h_edges:         yield (r, c-1)
        if (r, c) in self.v_edges:           yield (r+1, c)
        if (r-1, c) in self.v_edges:         yield (r-1, c)

    def _render_board(self) -> str:
        """Render a clean, spacious Slitherlink grid."""
        lines = []

        # Add some spacing at the top
        lines.append("")

        # Column headers with better spacing
        col_header = " "  # indent for row labels
        for c in range(self.C + 1):
            col_header += f"{c:>4}"
        lines.append(col_header)
        lines.append("")  # blank line for separation

        # Build the grid row by row
        for r in range(self.R + 1):
            # Dot row with horizontal edges
            dot_line = f"{r:>2}: "  # row label
            for c in range(self.C):
                dot_line += "+"
                if (r, c) in self.h_edges:
                    dot_line += "───"
                else:
                    dot_line += "   "
            dot_line += "+"
            lines.append(dot_line)

            # Cell row with vertical edges and clues (if not the last row)
            if r < self.R:
                cell_line = "    "  # indent to align with dot row
                for c in range(self.C + 1):
                    if (r, c) in self.v_edges:
                        cell_line += "│"
                    else:
                        cell_line += " "

                    if c < self.C:
                        clue = self.clues[r][c]
                        if clue is not None:
                            cell_line += f" {clue} "
                        else:
                            cell_line += " · "
                lines.append(cell_line)

        lines.append("")  # blank line at bottom
        return '\n'+'\n'.join(lines)
