import re
import random
from typing import Dict, Tuple, Any, Optional, List, Set
from collections import defaultdict, deque

import textarena as ta


class SlitherlinkEnv(ta.Env):
    _ACTION_RE = re.compile(r"\[\s*([hv])\s+(\d+)\s+(\d+)\s*\]", re.I)

    def __init__(self, rows: int = 4, cols: int = 4, max_turns: int = 200):
        """
        Initialize Slitherlink environment with configurable grid size.
        
        Args:
            rows: Number of rows in the grid
            cols: Number of columns in the grid  
            max_turns: Maximum number of moves allowed
        """
        super().__init__()
        self.R = rows
        self.C = cols
        self.max_turns = max_turns
        self.clues: List[List[Optional[int]]] = []

        # Edge sets (row, col) index the *upper-left* dot
        self.h_edges: Set[Tuple[int, int]] = set()
        self.v_edges: Set[Tuple[int, int]] = set()

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.h_edges.clear()
        self.v_edges.clear()
        
        # Generate a random solvable puzzle
        self.clues = self._generate_puzzle(seed)

        self.state = ta.SinglePlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.state.reset(game_state={}, player_prompt_function=self._prompt)
        self._observe()

    def _generate_puzzle(self, seed: Optional[int] = None) -> List[List[Optional[int]]]:
        """Generate a random solvable Slitherlink puzzle by creating a solution first."""
        if seed is not None:
            random.seed(seed)
        
        # Start with empty edges
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
                if random.random() < 0.6:  # 60% chance to add a clue
                    clues[r][c] = edge_count
        
        return clues

    def _generate_random_loop(self, h_edges: Set[Tuple[int, int]], v_edges: Set[Tuple[int, int]]):
        """Generate a simple random rectangular loop."""
        # Create a simple rectangular loop to ensure solvability
        # This is a basic implementation - could be made more sophisticated
        
        # Choose random rectangle dimensions within the grid
        min_size = 2
        max_width = min(self.C, 4)
        max_height = min(self.R, 4)
        
        width = random.randint(min_size, max_width)
        height = random.randint(min_size, max_height)
        
        # Choose random position for the rectangle
        start_r = random.randint(0, self.R - height)
        start_c = random.randint(0, self.C - width)
        
        # Add horizontal edges (top and bottom of rectangle)
        for c in range(start_c, start_c + width):
            h_edges.add((start_r, c))                    # top edge
            h_edges.add((start_r + height, c))           # bottom edge
        
        # Add vertical edges (left and right of rectangle)  
        for r in range(start_r, start_r + height):
            v_edges.add((r, start_c))                    # left edge
            v_edges.add((r, start_c + width))            # right edge

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(self.state.current_player_id, action, ta.ObservationType.PLAYER_ACTION)

        m = self._ACTION_RE.fullmatch(action.strip().lower())
        if not m:
            self.state.set_invalid_move(self._progress(), self.m("invalid_move", "wrong_format"))
            return self.state.step()

        kind, r, c = m.group(1), int(m.group(2)), int(m.group(3))
        if not self._valid_edge(kind, r, c):
            self.state.set_invalid_move(self._progress(), self.m("invalid_move", "out_of_bounds"))
            return self.state.step()

        self._toggle_edge(kind, r, c)
        self._observe()

        if self._is_solved():                
            self.state.set_outcome(1.0, self.m("outcome", "win"))
        elif self.state.check_turn_limit():  
            self.state.set_outcome(self._progress(), self.m("outcome", "turn_limit"))

        return self.state.step()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", R=self.R, C=self.C, max_turns=self.max_turns)

    def _valid_edge(self, kind: str, r: int, c: int) -> bool:
        if kind == 'h': return 0 <= r <= self.R and 0 <= c < self.C
        else:           return 0 <= r < self.R and 0 <= c <= self.C # 'v'

    def _toggle_edge(self, kind: str, r: int, c: int):
        if kind == 'h':
            edge = (r, c)
            self.h_edges.discard(edge) if edge in self.h_edges else self.h_edges.add(edge)
        else:
            edge = (r, c)
            self.v_edges.discard(edge) if edge in self.v_edges else self.v_edges.add(edge)

    def _progress(self) -> float:
        """Fraction of clue cells currently satisfied."""
        satisfied = 0
        total = 0
        for r in range(self.R):
            for c in range(self.C):
                if self.clues[r][c] is not None:
                    total += 1
                    if self._cell_edge_count(r, c) == self.clues[r][c]:
                        satisfied += 1
        return satisfied / max(1, total)

    def _cell_edge_count(self, r: int, c: int) -> int:
        cnt = 0
        if (r, c) in self.h_edges:               cnt += 1
        if (r+1, c) in self.h_edges:             cnt += 1
        if (r, c) in self.v_edges:               cnt += 1
        if (r, c+1) in self.v_edges:             cnt += 1
        return cnt

    def _is_solved(self) -> bool:
        # 1. All clues satisfied
        if self._progress() < 1.0: 
            return False
        # 2. Every dot has 0 or 2 incident edges AND at least one edge exists
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
        # 3. Exactly one loop → start BFS from any edge-dot and ensure all
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

    def _observe(self):
        progress_pct = f"{self._progress():.0%}"
        message = self.m("board", "current_board", board=self._render_board(), progress=progress_pct)
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_BOARD)