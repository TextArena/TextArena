import ast
import re
from collections import deque
from typing import Any, Dict, Optional, Union

import textarena as ta

class TakEnv(ta.GameEnv):
    """
    Tak environment.
    """
    min_players = 2
    max_players = 2
    action_pattern = (
        r"^\s*\[?\s*"
        r"(place|move)\s+"       # Match action: "place" or "move"
        r"\((\d+\s*,\s*\d+|\s*)\)\s+"  # Match source: "(row,col)" or "()"
        r"(\{.*\})"               # Match allocation dictionary
        r"\s*\]?\s*$"
    )  # Example: move (2,2) {'(2,3)': ['F0', 'W0'], '(2,4)': ['C1']}

    def __init__(self, board_size, stones, capstones):
        """
        Initialize the Tak game environment

        Args:
            board_size: Size of the (square) board.
            stones: Number of flat/wall stones per player.
            capstones: Number of capstones per player.
        """
        if not isinstance(board_size, int) or isinstance(board_size, bool) or not 3 <= board_size <= 8:
            raise ValueError("board_size must be an integer from 3 through 8")
        if not isinstance(stones, int) or isinstance(stones, bool) or stones < 1:
            raise ValueError("stones must be a positive integer")
        if not isinstance(capstones, int) or isinstance(capstones, bool) or capstones < 0:
            raise ValueError("capstones must be a non-negative integer")
        self.board_size = board_size
        self.stones = stones
        self.capstones = capstones

    @property
    def terminal_render_keys(self):
        return ["rendered_board"]

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
        return (
            f"You are Player {player_id} in Tak.\n"
            "Your goal is to connect two opposite edges of the board with your pieces to form a road while blocking your opponent from doing the same.\n"
            "Opening rule: on each of the first two turns, the acting player must place one of the opponent's flat stones; stacks cannot move yet.\n"
            "You can perform the following actions on your turn:\n"
            "- Place a piece on an empty square.\n"
            "- Move a stack of pieces from one square to one or more squares. You can stack your pieces on top of other pieces on the target square. The topmost piece determines ownership of the stack.\n"
            "- Split a stack of pieces into two or more stacks and distribute them to adjacent squares.\n"
            "- Flatten a wall stone into a flat stone using your capstone.\n"
            "- Place a Capstone on an empty square.\n"
            "- Move a Capstone from one square to one or more squares. A capstone can also flatten a wall stone during its move.\n"
            "\n"
            "For each move, submit your action using the format:\n"
            "ACTION SOURCE ALLOCATION\n"
            "- ACTION: The type of move you are making ('place' or 'move').\n"
            "- SOURCE: The grid coordinates where the stones originate. Use () for 'place'.\n"
            "- ALLOCATION: A dictionary where keys are target grid coordinates and values are the stones or pieces being moved or placed.\n"
            "\n"
            "Stone Types and Their Abilities:\n"
            "- Flat Stone ('F'):\n"
            "  - Forms part of a road (used to connect edges of the board).\n"
            "  - Can be stacked on top of other pieces or have other pieces stacked on it.\n"
            "  - Can be moved as part of a stack or individually.\n"
            "\n"
            "- Wall Stone ('W'):\n"
            "  - Blocks roads and prevents opponents from completing their connections.\n"
            "  - Cannot be part of a road.\n"
            "  - Can be flattened into a flat stone by a capstone.\n"
            "\n"
            "- Capstone ('C'):\n"
            "  - Acts as a flat stone and can form part of a road.\n"
            "  - Can flatten wall stones, removing their blocking effect.\n"
            "  - Cannot be covered by other pieces, always remains on top of the stack.\n"
            "  - Is a powerful tool for both road-building and disrupting your opponent's plans.\n"
            "\n"
            "The stones will be identified by the player as follows:\n"
            "- Flat Stone for Player 0: 'F0'\n"
            "- Wall Stone for Player 1: 'W1'\n"
            "- Capstone for Player 1: 'C1'\n"
            "\n"
            "Examples:\n"
            "- To place a capstone on (3,2):\n"
            "  place () {(3,2): [C0]}\n"
            "- To move all pieces from (2,2) to (2,3):\n"
            "  move (2,2) {(2,3): [F0]}\n"
            "- To split a stack of 5 pieces from (2,2) into two squares:\n"
            "  move (2,2) {(2,3): [F0, F0], (2,4): [W0, F0, C0]}\n"
            "- To move and stack one piece from (2,2) onto an existing stack at (2,3):\n"
            "  move (2,2) {(2,3): [F0]}\n"
            "\n"
            "When submitting your move, think strategically about your road-building goals and your opponent's potential moves.\n"
        )

    def render(self, player_id: int) -> str:
        board_str = self._render_board()
        available_flat_stones = self.players[player_id]["stones"]
        available_capstones = self.players[player_id]["capstones"]
        return f"Current Board:\n\n{board_str}\nAvailable Flat Stones: {available_flat_stones}, Available Capstones: {available_capstones}\n"

    def get_board_str(self) -> str:
        return self.game_state["rendered_board"]

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        action, source, allocation = self.extract_values(move.groups())
        if action is None or allocation is None:
            return self.invalid("The allocation could not be parsed.")

        if action == "place":
            if source is not None or not self._is_valid_placement(allocation, player_id):
                return self.invalid(f"Invalid placement. Player {player_id} tried to place a piece on an invalid square.")
            self._apply_placement(allocation, player_id)
            self.broadcast(f"Player {player_id} placed a piece on ({list(allocation.keys())}).", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

        elif action == "move":
            if not self._is_valid_movement(source, allocation, player_id):
                return self.invalid(f"Invalid movement. Player {player_id} tried to move pieces in an invalid way.")
            self._apply_movement(source, allocation)
            self.broadcast(f"Player {player_id} moved pieces from {source} to {list(allocation.keys())}.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

        else:
            return self.invalid(f"Invalid action. Player {player_id} tried to perform an unknown action.")

        self.game_state["move_count"] += 1
        self.game_state["rendered_board"] = self._render_board()

        if self._check_win(player_id):
            return self.winner(player_id, reason=f"Player {player_id} has connected two opposite edges of the board.")
        opponent_id = 1 - player_id
        if self._check_win(opponent_id):
            return self.winner(opponent_id, reason=f"Player {opponent_id} has connected two opposite edges of the board.")
        if self._flat_game_over():
            return self._flat_outcome()
        return None

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

    def _flat_game_over(self) -> bool:
        board_full = all(self.board[row][col] for row in range(self.board_size) for col in range(self.board_size))
        reserves_empty = any(
            player["stones"] == 0 and player["capstones"] == 0
            for player in self.players.values()
        )
        return board_full or reserves_empty

    def _flat_outcome(self) -> ta.Outcome:
        counts = {
            pid: sum(
                bool(stack) and stack[-1] == f"F{pid}"
                for row in self.board
                for stack in row
            )
            for pid in range(2)
        }
        if counts[0] > counts[1]:
            return self.winner(0, reason=f"Player 0 wins the flat count {counts[0]}-{counts[1]}.")
        if counts[1] > counts[0]:
            return self.winner(1, reason=f"Player 1 wins the flat count {counts[1]}-{counts[0]}.")
        return self.draw(reason=f"The flat count is tied {counts[0]}-{counts[1]}.")

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

    def _is_valid_placement(self, allocation, player_id=None):
        """ Check if the placement is valid """
        player_id = self.current_player_id if player_id is None else player_id
        if not isinstance(allocation, dict) or len(allocation) != 1:
            ## needs to be a single allocation
            return False
        target = next(iter(allocation))
        if (
            not isinstance(target, tuple)
            or len(target) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool) for value in target)
        ):
            return False
        row, col = target
        piece = list(allocation.values())[0]

        if not isinstance(piece, list) or len(piece) != 1 or not isinstance(piece[0], str) or not re.fullmatch(r"[FWC][01]", piece[0]):
            ## needs to be a single recognized piece
            return False

        opening = self.game_state["move_count"] < 2
        piece_owner = 1 - player_id if opening else player_id
        if opening and piece != [f"F{piece_owner}"]:
            return False

        if piece[0][0] == "C" and self.players[piece_owner]["capstones"] == 0:
            ## no capstones left
            return False
        elif piece[0][0] in ["F", "W"] and self.players[piece_owner]["stones"] == 0:
            ## no stones left
            return False

        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            ## needs to be within the board
            return False

        if self.board[row][col]:
            ## needs to be an empty square
            return False

        if piece[0][0] not in ["F", "W", "C"]:
            ## unacceptable piece
            return False

        if piece[0][-1] != str(piece_owner):
            ## piece does not belong to the current player
            return False

        return True

    def _apply_placement(self, allocation, player_id):
        ## valid placement
        row, col = list(allocation.keys())[0]
        piece = list(allocation.values())[0]
        self.board[row][col].extend(piece)
        self._update_pieces(int(piece[0][-1]), piece)

    def _is_valid_movement(self, source, allocation, player_id=None):
        """ check if the movement is valid """
        player_id = self.current_player_id if player_id is None else player_id
        if self.game_state["move_count"] < 2:
            return False
        if (
            not isinstance(source, tuple)
            or len(source) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool) for value in source)
            or not isinstance(allocation, dict)
            or not allocation
        ):
            return False
        if any(
            not isinstance(target, tuple)
            or len(target) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool) for value in target)
            or not isinstance(pieces, list)
            or any(not isinstance(piece, str) or not re.fullmatch(r"[FWC][01]", piece) for piece in pieces)
            for target, pieces in allocation.items()
        ):
            return False

        source_row, source_col = source

        if not (0 <= source_row < self.board_size and 0 <= source_col < self.board_size):
            return False

        if not self.board[source_row][source_col]: ## source must have pieces
            return False

        source_player_id = self.board[source_row][source_col][-1][-1]
        if source_player_id != str(player_id): ## source must have the current player's stone on top
            return False

        source_stack = self.board[source_row][source_col]
        if any(not pieces for pieces in allocation.values()):
            return False
        pieces_to_move = [value for values in allocation.values() for value in values]
        if not pieces_to_move or len(pieces_to_move) > self.board_size or len(pieces_to_move) > len(source_stack):
            return False

        if pieces_to_move != source_stack[-len(pieces_to_move):]: ## pieces to move must match the top of the stack in order
            return False

        targets = list(allocation)
        first_row, first_col = targets[0]
        direction = first_row - source_row, first_col - source_col
        if abs(direction[0]) + abs(direction[1]) != 1:
            return False

        for index, ((target_row, target_col), pieces) in enumerate(allocation.items(), start=1):
            if (target_row, target_col) != (
                source_row + direction[0] * index,
                source_col + direction[1] * index,
            ):
                return False
            if not (0 <= target_row < self.board_size and 0 <= target_col < self.board_size):
                return False

            destination = self.board[target_row][target_col]
            if not destination:
                continue
            blocking_type = destination[-1][0]
            if blocking_type == "C":
                return False
            if blocking_type == "W":
                is_final = index == len(targets)
                if not (is_final and len(pieces) == 1 and pieces[0][0] == "C"):
                    return False

        return True

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
                if (
                    not isinstance(key, tuple)
                    or len(key) != 2
                    or not all(isinstance(item, int) and not isinstance(item, bool) for item in key)
                    or not isinstance(value, list)
                    or any(not isinstance(item, str) or not re.fullmatch(r"[FWC][01]", item) for item in value)
                ):
                    raise ValueError("Invalid allocation entry")
            return parsed_dict
        except Exception as e:
            raise ValueError(f"Invalid input string: {input_str}") from e
