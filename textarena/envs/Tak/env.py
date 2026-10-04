import ast
import re
from collections import deque
from typing import Any, Dict, Optional, Union

import textarena as ta

PIECE_PATTERN = re.compile(r"[FWC][01]")


class TakEnv(ta.GameEnv):
    """
    Tak environment.
    """
    min_players = 2
    max_players = 2
    action_pattern = (
        r"(?i)^(place|move)\s+"  # Match action: "place" or "move"
        r"\((\d+\s*,\s*\d+|\s*)\)\s+"  # Match source: "(row,col)" or "()"
        r"(\{.*\})$"              # Match allocation dictionary
    )  # Example: move (2,2) {(2,3): [F1], (2,4): [F0, C0]}

    def __init__(self, board_size, stones, capstones, max_turns: int = 100):
        """
        Initialize the Tak game environment

        Args:
            board_size: Size of the (square) board.
            stones: Number of flat/wall stones per player.
            capstones: Number of capstones per player.
            max_turns: Safeguard cap on the total number of moves. Real Tak has no
                turn limit, but stack moves alone can continue forever; when the cap
                is reached the flat count decides the game.
        """
        if not isinstance(board_size, int) or isinstance(board_size, bool) or not 3 <= board_size <= 8:
            raise ValueError("board_size must be an integer from 3 through 8")
        if not isinstance(stones, int) or isinstance(stones, bool) or stones < 1:
            raise ValueError("stones must be a positive integer")
        if not isinstance(capstones, int) or isinstance(capstones, bool) or capstones < 0:
            raise ValueError("capstones must be a non-negative integer")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.board_size = board_size
        self.stones = stones
        self.capstones = capstones
        self.max_turns = max_turns

    @property
    def terminal_render_keys(self):
        return ["rendered_board"]

    @property
    def action_format(self) -> str:
        player_id = self.state.current_player_id
        piece = f"F{1 - player_id}" if self.game_state["move_count"] < 2 else f"F{player_id}"
        return (
            "a placement 'place () {(row,col): [piece]}' or a stack move "
            "'move (row,col) {(row,col): [pieces], (row,col): [pieces]}' "
            f"with rows and columns from 0 to {self.board_size - 1}, for example 'place () {{(1,2): [{piece}]}}'"
        )

    @property
    def board(self):
        return self.game_state["board"]

    @property
    def players(self):
        return self.game_state["players"]

    def setup(self) -> Dict[str, Any]:
        board = [[[] for _ in range(self.board_size)] for _ in range(self.board_size)]
        players = {
            0: {"stones": self.stones, "capstones": self.capstones},
            1: {"stones": self.stones, "capstones": self.capstones},
        }
        game_state = {"board": board, "players": players, "move_count": 0}
        game_state["rendered_board"] = self._render_board_from(board)
        return game_state

    def prompt(self, player_id: int) -> str:
        me, opp, size = player_id, 1 - player_id, self.board_size
        examples = [
            f"- place () {{(1,2): [F{me}]}} places a flat stone on row 1, column 2.",
            f"- place () {{(0,1): [W{me}]}} places a wall on row 0, column 1.",
            f"- move (1,1) {{(1,2): [F{me}]}} moves the single flat stone on (1,1) one square to the right.",
            f"- move (2,0) {{(1,0): [F{opp}], (0,0): [F{me}]}} carries the stack '(2) F{opp}/F{me}' upward, "
            f"dropping F{opp} on (1,0) and then F{me} on (0,0).",
        ]
        if self.capstones:
            examples.insert(2, f"- place () {{(2,2): [C{me}]}} places a capstone on row 2, column 2.")
            examples.append(f"- move (0,2) {{(0,1): [C{me}]}} carries only your capstone from (0,2) onto (0,1); if a wall stands there, it is flattened.")
        return "\n".join([
            f"You are Player {me} in Tak, playing on a {size}x{size} board. Player 0 moves first.",
            "Your goal is to build a road: a path of orthogonally adjacent squares topped by your flat stones or capstones "
            "that connects two opposite edges of the board (top to bottom or left to right), while blocking your opponent from doing the same.",
            "",
            "Pieces are written as a letter followed by the owner's player number:",
            f"- Flat stone (F{me}): counts toward roads, and any piece may be stacked on top of it.",
            f"- Wall, a standing stone (W{me}): never part of a road, and nothing may be stacked on it except a capstone that flattens it.",
            f"- Capstone (C{me}): counts toward roads, can flatten walls, and can never be covered.",
            f"Each player starts with {self._count(self.stones, 'stone')} (each one is placed as either a flat stone or a wall) "
            f"and {self._count(self.capstones, 'capstone')}.",
            "",
            "On your turn, do exactly one of the following:",
            "1. Place one of your pieces on an empty square: place () {(row,col): [piece]}",
            f"2. Move a stack whose top piece is yours: pick up 1 to {size} pieces from the top of the stack (never more than {size}, the board size), "
            "travel in a straight line (up, down, left, or right), and drop at least one piece on every square you enter, starting with the square "
            "next to the source. Pieces leave the bottom of the carried pile first.",
            "   Write the drops in travel order, mapping each square to the pieces left there from bottom to top: "
            "move (row,col) {(row,col): [pieces], (row,col): [pieces]}. Read in order, the dropped pieces must equal the top of the source stack from bottom to top.",
            "   A move cannot enter a square topped by a wall or a capstone, except that a capstone dropped alone as the final piece flattens a wall into a flat stone.",
            "Opening: on each of the first two turns, place one of your opponent's flat stones instead of your own "
            "(Player 0 places an F1, then Player 1 places an F0); no stack may move yet.",
            "",
            "The game ends:",
            "- as soon as a move completes a road: the road's owner wins. If one move completes roads for both players, the player who made the move wins.",
            "- when the board is full or either player has placed all of their stones and capstones: unless that move completed a road, "
            "the player with more flat stones on top of stacks wins the flat count (walls, capstones, and covered stones do not count); a tied flat count is a draw.",
            f"- as a safeguard, after {self.max_turns} turns in total (every move by either player counts): the flat count decides the result.",
            "",
            "Rows and columns are numbered from 0, so (0,0) is the top-left square. Each square on the board shows its stack height in parentheses "
            "and its pieces from bottom to top: '(2) F1/W0' is a wall W0 standing on a flat stone F1.",
            "",
            f"Examples (as Player {me}):",
            *examples,
        ])

    def render(self, player_id: int) -> str:
        reserves = "\n".join(
            f"- Player {pid}: {self._count(pieces['stones'], 'stone')} and {self._count(pieces['capstones'], 'capstone')} left"
            for pid, pieces in self.players.items()
        )
        lines = [
            f"Current Board:\n\n{self._render_board()}",
            f"Reserves (each stone can be placed as a flat stone or a wall):\n{reserves}",
            f"Turns played: {self.state.turn} of {self.state.max_turns}",
        ]
        if self.game_state["move_count"] < 2:
            lines.append(f"Opening: place one of Player {1 - player_id}'s flat stones (F{1 - player_id}) on an empty square.")
        return "\n".join(lines) + "\n"

    def get_board_str(self) -> str:
        return self.game_state["rendered_board"]

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        action, source, allocation = self.extract_values(move.groups())
        if action is None or allocation is None:
            return self.invalid(
                f"The allocation could not be parsed. Write it as a dictionary from squares to piece lists, e.g. {{(1,2): [F{player_id}]}}."
            )

        if action == "place":
            error = self._placement_error(source, allocation, player_id)
            if error is not None:
                return self.invalid(error)
            (row, col), pieces = next(iter(allocation.items()))
            self._apply_placement(allocation, player_id)
            self.broadcast(f"Player {player_id} placed {pieces[0]} on ({row},{col}).", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

        elif action == "move":
            error = self._movement_error(source, allocation, player_id)
            if error is not None:
                return self.invalid(error)
            description = self._describe_movement(source, allocation)
            self._apply_movement(source, allocation)
            self.broadcast(f"Player {player_id} {description}", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

        else:
            return self.invalid(f"Invalid action. Player {player_id} tried to perform an unknown action.")

        self.game_state["move_count"] += 1
        self.game_state["rendered_board"] = self._render_board()

        if self._check_win(player_id):
            return self.winner(player_id, reason=f"Player {player_id} has connected two opposite edges of the board.")
        opponent_id = 1 - player_id
        if self._check_win(opponent_id):
            return self.winner(opponent_id, reason=f"Player {opponent_id} has connected two opposite edges of the board.")
        flat_trigger = self._flat_count_trigger()
        if flat_trigger is not None:
            return self._flat_outcome(flat_trigger)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self._flat_outcome("The turn limit has been reached.")

    @staticmethod
    def _count(number: int, noun: str) -> str:
        return f"{number} {noun}{'' if number == 1 else 's'}"

    def _render_board(self):
        return self._render_board_from(self.board)

    def _render_board_from(self, board):
        """
        Renders the board as a string and returns it.
        """
        max_cell_width = max(len(self._format_stack(cell)) for row in board for cell in row)
        cell_width = max(max_cell_width, 5)  # Ensure minimum cell width for readability

        header = "      " + "   ".join(f"{i:^{cell_width}}" for i in range(self.board_size))
        separator = "     " + "-" * (self.board_size * (cell_width + 3) - 1)

        rows = []
        for row_idx, row in enumerate(board):
            row_display = [self._pad_cell(self._format_stack(cell), cell_width) for cell in row]
            rows.append(f"{row_idx:>3} | " + " | ".join(row_display) + " |")
            rows.append(separator)

        return "\n".join([header, separator] + rows)

    def _format_stack(self, stack):
        """
        Helper function to format stacks in each cell,
        """
        if not stack:
            return ""  # Empty cell
        return f"({len(stack)}) {'/'.join(stack)}"  # Full stack representation

    def _pad_cell(self, content, cell_width):
        return content.center(cell_width)

    def _check_win(self, player_id):
        """
        Check if the specified player has won by forming a continuous road
        connecting two opposite edges of the board.
        """
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # Right, Down, Left, Up

        def is_road(row, col):
            """Check if the cell is valid for the player."""
            if 0 <= row < self.board_size and 0 <= col < self.board_size:
                stack = self.board[row][col]
                return stack and stack[-1].endswith(str(player_id)) and stack[-1][0] in ["F", "C"]
            return False

        def connects(starts, target) -> bool:
            queue = deque(starts)
            visited = set(starts)
            while queue:
                row, col = queue.popleft()
                if target(row, col):
                    return True
                for dr, dc in directions:
                    neighbor = row + dr, col + dc
                    if neighbor not in visited and is_road(*neighbor):
                        visited.add(neighbor)
                        queue.append(neighbor)
            return False

        top = [(0, col) for col in range(self.board_size) if is_road(0, col)]
        if connects(top, lambda row, _col: row == self.board_size - 1):
            return True
        left = [(row, 0) for row in range(self.board_size) if is_road(row, 0)]
        return connects(left, lambda _row, col: col == self.board_size - 1)

    def _flat_count_trigger(self) -> Optional[str]:
        """Why the game must now be decided by flat count, or None if play continues."""
        if all(self.board[row][col] for row in range(self.board_size) for col in range(self.board_size)):
            return "The board is full."
        for pid, player in self.players.items():
            if player["stones"] == 0 and player["capstones"] == 0:
                return f"Player {pid} has no pieces left to place."
        return None

    def _flat_counts(self) -> Dict[int, int]:
        return {
            pid: sum(
                bool(stack) and stack[-1] == f"F{pid}"
                for row in self.board
                for stack in row
            )
            for pid in range(2)
        }

    def _flat_outcome(self, trigger: str) -> ta.Outcome:
        counts = self._flat_counts()
        if counts[0] > counts[1]:
            return self.winner(0, reason=f"{trigger} Player 0 wins the flat count {counts[0]}-{counts[1]}.")
        if counts[1] > counts[0]:
            return self.winner(1, reason=f"{trigger} Player 1 wins the flat count {counts[1]}-{counts[0]}.")
        return self.draw(reason=f"{trigger} The flat count is tied {counts[0]}-{counts[1]}, so the game is a draw.")

    def _update_pieces(self, player_id, piece):
        """
        Update the player's piece count if a new piece is placed.
        """
        if piece[0][0] == "F" or piece[0][0] == "W":
            self.players[player_id]["stones"] -= 1
        else:
            self.players[player_id]["capstones"] -= 1

    def extract_values(self, matched_groups):
        """
        Extract and process the matched groups from the action string.
        """
        action, source, allocation = matched_groups
        action = action.lower()

        try:
            # Process source: Convert to a tuple of integers or None.
            if source.strip():
                source = tuple(map(int, source.split(',')))
            else:
                source = None
            allocation_dict = self._convert_to_dict(allocation)
        except (TypeError, ValueError, SyntaxError):
            return None, None, None

        return action, source, allocation_dict

    @staticmethod
    def _is_square(value) -> bool:
        return (
            isinstance(value, tuple)
            and len(value) == 2
            and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
        )

    @staticmethod
    def _is_piece_list(value) -> bool:
        return isinstance(value, list) and all(isinstance(item, str) and PIECE_PATTERN.fullmatch(item) for item in value)

    def _placement_error(self, source, allocation, player_id) -> Optional[str]:
        """Why the placement is illegal, or None if it is legal."""
        usage = f"A placement names one square and one piece, e.g. place () {{(1,2): [F{player_id}]}}."
        if source is not None:
            return f"Use () as the source of a placement. {usage}"
        if not isinstance(allocation, dict) or len(allocation) != 1:
            return usage
        target, pieces = next(iter(allocation.items()))
        if not self._is_square(target) or not self._is_piece_list(pieces) or len(pieces) != 1:
            return usage
        row, col = target
        piece = pieces[0]
        opponent = 1 - player_id

        if self.game_state["move_count"] < 2:
            if piece != f"F{opponent}":
                return f"During the opening you must place one of your opponent's flat stones (F{opponent})."
            owner = opponent
        else:
            if piece[1] != str(player_id):
                return f"You can only place your own pieces (F{player_id}, W{player_id}, or C{player_id})."
            owner = player_id

        if piece[0] == "C" and self.players[owner]["capstones"] == 0:
            return "There are no capstones left to place."
        if piece[0] in "FW" and self.players[owner]["stones"] == 0:
            return "There are no stones left to place."
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return f"Square ({row},{col}) is not on the {self.board_size}x{self.board_size} board."
        if self.board[row][col]:
            return f"Square ({row},{col}) is not empty; pieces can only be placed on empty squares."
        return None

    def _apply_placement(self, allocation, player_id):
        ## valid placement
        row, col = list(allocation.keys())[0]
        piece = list(allocation.values())[0]
        self.board[row][col].extend(piece)
        self._update_pieces(int(piece[0][-1]), piece)

    def _movement_error(self, source, allocation, player_id) -> Optional[str]:
        """Why the stack move is illegal, or None if it is legal."""
        size = self.board_size
        if self.game_state["move_count"] < 2:
            return f"Stacks cannot move during the opening; place one of your opponent's flat stones (F{1 - player_id}) instead."
        if (
            not self._is_square(source)
            or not isinstance(allocation, dict)
            or not allocation
            or any(not self._is_square(target) or not self._is_piece_list(pieces) for target, pieces in allocation.items())
        ):
            return f"A move names a source square and one or more drops, e.g. move (1,1) {{(1,2): [F{player_id}]}}."

        source_row, source_col = source
        if not (0 <= source_row < size and 0 <= source_col < size):
            return f"Square ({source_row},{source_col}) is not on the {size}x{size} board."
        source_stack = self.board[source_row][source_col]
        if not source_stack:
            return f"There is no stack on ({source_row},{source_col})."
        if source_stack[-1][-1] != str(player_id):
            return f"The stack on ({source_row},{source_col}) is topped by {source_stack[-1]}; you can only move stacks topped by your own piece."

        if any(not pieces for pieces in allocation.values()):
            return "Every square you move onto must receive at least one piece."
        pieces_to_move = [value for values in allocation.values() for value in values]
        if len(pieces_to_move) > size:
            return f"You can carry at most {size} pieces (the board size)."
        if len(pieces_to_move) > len(source_stack):
            return f"The stack on ({source_row},{source_col}) only has {self._count(len(source_stack), 'piece')}."
        top = source_stack[-len(pieces_to_move):]
        if pieces_to_move != top:  ## pieces to move must match the top of the stack in order
            return (
                f"The dropped pieces must be the top {self._count(len(top), 'piece')} of the stack on ({source_row},{source_col}) "
                f"in bottom-to-top order: {', '.join(top)}."
            )

        targets = list(allocation)
        first_row, first_col = targets[0]
        direction = first_row - source_row, first_col - source_col
        if abs(direction[0]) + abs(direction[1]) != 1:
            return "The first drop must be on a square next to the source (up, down, left, or right)."

        for index, ((target_row, target_col), pieces) in enumerate(allocation.items(), start=1):
            if (target_row, target_col) != (
                source_row + direction[0] * index,
                source_col + direction[1] * index,
            ):
                return "Drops must be on consecutive squares in one straight line from the source."
            if not (0 <= target_row < size and 0 <= target_col < size):
                return f"Square ({target_row},{target_col}) is not on the {size}x{size} board."

            destination = self.board[target_row][target_col]
            if not destination:
                continue
            blocking_type = destination[-1][0]
            if blocking_type == "C":
                return f"You cannot move onto the capstone on ({target_row},{target_col})."
            if blocking_type == "W":
                is_final = index == len(targets)
                if not (is_final and len(pieces) == 1 and pieces[0][0] == "C"):
                    return (
                        f"You cannot move onto the wall on ({target_row},{target_col}); "
                        "only a capstone dropped alone as the final piece can flatten it."
                    )

        return None

    def _describe_movement(self, source, allocation) -> str:
        drops = []
        for (row, col), pieces in allocation.items():
            drop = f"{'/'.join(pieces)} to ({row},{col})"
            destination = self.board[row][col]
            if destination and destination[-1][0] == "W":
                drop += f", flattening the wall {destination[-1]}"
            drops.append(drop)
        carried = sum(len(pieces) for pieces in allocation.values())
        return f"moved {self._count(carried, 'piece')} from ({source[0]},{source[1]}): {'; '.join(drops)}."

    def _apply_movement(self, source, allocation):
        """ Apply the movement to the board """
        source_row, source_col = source
        source_stack = self.board[source_row][source_col]
        pieces_to_move = [value for values in allocation.values() for value in values]
        for target, pieces in allocation.items():
            target_row, target_col = target
            if self.board[target_row][target_col] and self.board[target_row][target_col][-1][0] == "W":
                self.board[target_row][target_col][-1] = "F" + self.board[target_row][target_col][-1][1]
            self.board[target_row][target_col].extend(pieces)
        self.board[source_row][source_col] = source_stack[:-len(pieces_to_move)]

    def _convert_to_dict(self, input_str):
        """
        Converts a string representation of a dictionary with tuple keys and list-like values
        into a valid Python dictionary, ensuring:
        - Tuple keys retain their integer types.
        - List elements are converted to strings.
        """
        input_str = re.sub(r"(?i)\b([fwc])([01])\b", lambda match: match.group(1).upper() + match.group(2), input_str)
        # Quote bare Tak piece identifiers while leaving integer coordinates intact.
        input_str = re.sub(
            r"(?P<prefix>[\[,]\s*)(?P<piece>[FWC][01])(?=\s*[,\]])",
            lambda match: f"{match.group('prefix')}'{match.group('piece')}'",
            input_str,
        )

        try:
            parsed_expression = ast.parse(input_str, mode="eval")
            if not isinstance(parsed_expression.body, ast.Dict):
                raise ValueError("Allocation must be a dictionary")
            raw_keys = [ast.literal_eval(key) for key in parsed_expression.body.keys]
            if len(raw_keys) != len(set(raw_keys)):
                raise ValueError("Allocation cannot contain duplicate targets")
            parsed_dict = ast.literal_eval(parsed_expression)
            if not isinstance(parsed_dict, dict):
                raise ValueError("Allocation must be a dictionary")
            for key, value in parsed_dict.items():
                if not self._is_square(key) or not self._is_piece_list(value):
                    raise ValueError("Invalid allocation entry")
            return parsed_dict
        except Exception as e:
            raise ValueError(f"Invalid input string: {input_str}") from e
