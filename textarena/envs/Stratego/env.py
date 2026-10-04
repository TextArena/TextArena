import re
from typing import Any, Dict, Optional, Union

import textarena as ta

class StrategoEnv(ta.GameEnv):
    """ A two-player implementation of the board game Stratego """
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"(?i)^([A-J])([0-9])\s+([A-J])([0-9])$"
    action_format = (
        "the source and destination squares, each a row letter from A to J followed by a column number from 0 to 9, "
        "for example 'A0 B0'"
    )
    broadcast_actions = False  # raw actions are echoed only to their author

    max_turns = ta.Param(1000, "The total number of turns, counting both players, before the game is a draw.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ## set up the board items
        self.piece_counts = {
            'Flag': 1, 'Bomb': 6, 'Spy': 1, 'Scout': 8, 'Miner': 5,
            'Sergeant': 4, 'Lieutenant': 4, 'Captain': 4, 'Major': 3,
            'Colonel': 2, 'General': 1, 'Marshal': 1
        }
        self.piece_ranks = {
            'Flag': 0, 'Bomb': 11, 'Spy': 1, 'Scout': 2, 'Miner': 3,
            'Sergeant': 4, 'Lieutenant': 5, 'Captain': 6, 'Major': 7,
            'Colonel': 8, 'General': 9, 'Marshal': 10
        }
        self.lakes = [(4, 2), (4, 3), (5, 2), (5, 3), (4, 6), (4, 7), (5, 6), (5, 7)]

    @property
    def board(self):
        return self.game_state["board"]

    @property
    def player_pieces(self):
        return self.game_state["player_pieces"]

    def setup(self) -> Dict[str, Any]:
        board, player_pieces = self._populate_board()
        game_state = {
            "board": board,
            "player_pieces": player_pieces,
            "move_history": {},
            "last_moved_piece": {},
        }
        self.state.game_state = game_state  # so helpers can use self.board below
        # Never cache a rank-revealing board before the game is terminal.
        game_state["rendered_board"] = self._render_board(player_id=None, full_board=False)
        return game_state

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Stratego. Player 0 moves first.\n"
            "Your goal is to capture your opponent's Flag or eliminate all of their movable pieces.\n"
            "Your army has been placed for you on the board, including your Flag, Bombs, and other pieces of varying ranks.\n"
            "\n"
            "### Your Pieces (abbreviation, rank, count)\n"
            "- MS Marshal (10) x1, GN General (9) x1, CL Colonel (8) x2, MJ Major (7) x3, CP Captain (6) x4, LT Lieutenant (5) x4,\n"
            "  SG Sergeant (4) x4, MN Miner (3) x5, SC Scout (2) x8, SP Spy (1) x1, BM Bomb x6, FL Flag x1.\n"
            "\n"
            "### Gameplay Instructions\n"
            "1. **Movement Rules:**\n"
            "   - On your turn, you can move one piece by one step to an adjacent empty or enemy square (up, down, left, or right).\n"
            "   - Example: A piece can move from A1 to B1 or A1 to A2 if B1 and A2 are not placed with the player's own pieces.\n"
            "   - Scouts may instead move any number of empty squares in a straight line (not diagonally), and may attack the first enemy piece in that line; they cannot pass pieces or lakes.\n"
            "   - If the selected piece is a Bomb or a Flag, it cannot be moved.\n"
            "   - A piece may not move back and forth between the same two squares more than three turns in a row.\n"
            "2. **Battles:**\n"
            "   - If you move onto a square occupied by an opponent's piece, then a battle will occur and both ranks are revealed to both players:\n"
            "     - The piece with the higher rank wins and eliminates the opponent's piece.\n"
            "     - If the ranks are equal, both pieces are removed from the board.\n"
            "     - **Special Cases:**\n"
            "       - Bombs eliminate most attacking pieces except Miners, which defuse Bombs.\n"
            "       - Spies can defeat the Marshal if the Spy attacks first but lose to all other pieces.\n"
            "3. **End of the Game:**\n"
            "   - Capturing the opponent's Flag wins.\n"
            "   - A player with no movable pieces left, or with no legal move on their turn, loses; if neither player has a movable piece left, the game is a draw.\n"
            f"   - The game is a draw after {self.max_turns} turns in total (each player's move is one turn).\n"
            "4. **Strategic Goals:**\n"
            "   - Identify your opponent's pieces through their movements and battles.\n"
            "   - Protect your Flag while attempting to capture your opponent's Flag.\n"
            "   - Use Scouts strategically to gain information about your opponent's pieces and attack weak ones.\n"
            "\n"
            "### How to Make a Move:\n"
            "1. Specify the coordinates of the piece you want to move and its destination.\n"
            "2. Use the format: 'A0 B0', where A0 is the source position, and B0 is the destination.\n"
            "   - Rows are lettered A-J from top to bottom and columns numbered 0-9 from left to right.\n"
            "   - Example: To move a piece from row A, column 0 to row B, column 0, input 'A0 B0'.\n"
            "3. Choose one of the Available Moves listed under the board.\n"
            "\n"
            "### Important Notes:\n"
            "- The board shows your own pieces by abbreviation, e.g. MN, MS.\n"
            "- Opponent pieces are shown as ? without revealing their ranks.\n"
            "- Grids with ~ are lakes and cannot be moved onto.\n"
            "- As a suggestion, start your game by moving your pieces that are on the front lines to gain information about your opponent's pieces. Player 0 and player 1's frontlines are row D and G respectively.\n"
        )

    def render(self, player_id: int) -> str:
        full_board = self.state.done
        available_moves = [] if full_board else self._available_moves(player_id)
        return (
            f"Current Board:\n\n"
            f"{self._render_board(player_id=player_id, full_board=full_board)}"
            f"\nAvailable Moves: {', '.join(available_moves)}"
        )

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        board = self.board
        player_pieces = self.player_pieces

        src_row, src_col, dest_row, dest_col = move.groups()
        src_row, dest_row = src_row.upper(), dest_row.upper()
        source = f"{src_row}{src_col}"
        dest = f"{dest_row}{dest_col}"
        src_row, src_col = ord(src_row) - 65, int(src_col)
        dest_row, dest_col = ord(dest_row) - 65, int(dest_col)

        invalid_reason = self._validate_move(player_id, src_row, src_col, dest_row, dest_col)
        if invalid_reason is not None:
            return self.invalid(invalid_reason)

        attacking_piece = board[src_row][src_col]
        target_piece = board[dest_row][dest_col]

        if target_piece is None:
            ## move to an empty square
            board[dest_row][dest_col] = attacking_piece
            board[src_row][src_col] = None
            player_pieces[player_id].remove((src_row, src_col))
            player_pieces[player_id].append((dest_row, dest_col))

            self.message(player_id, f"You have moved your piece from {source} to {dest}.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
            self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

        else:
            ## battle
            attacking_rank = self.piece_ranks[attacking_piece['rank']]
            target_rank = self.piece_ranks[target_piece['rank']]
            if attacking_rank == target_rank:
                ## both pieces are removed
                board[src_row][src_col] = None
                board[dest_row][dest_col] = None
                player_pieces[player_id].remove((src_row, src_col))
                player_pieces[1 - player_id].remove((dest_row, dest_col))

                detail = f"The attacking piece was {attacking_piece['rank']} and the destination piece was {target_piece['rank']}. As the ranks are the same, both pieces lost."
                self.message(player_id, f"You have moved your piece from {source} to {dest}. {detail}", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
                self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}. {detail}", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

            elif target_piece['rank'] == 'Bomb':
                if attacking_piece['rank'] == 'Miner':
                    ## Miner defuses the bomb
                    board[dest_row][dest_col] = attacking_piece
                    board[src_row][src_col] = None
                    player_pieces[player_id].remove((src_row, src_col))
                    player_pieces[player_id].append((dest_row, dest_col))
                    player_pieces[1 - player_id].remove((dest_row, dest_col))

                    detail = f"The attacking piece was {attacking_piece['rank']} and the destination piece was {target_piece['rank']}."
                    self.message(player_id, f"You have moved your piece from {source} to {dest}. {detail} As miners can defuse bombs, you won the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
                    self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}. {detail} As miners can defuse bombs, you lost the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

                else:
                    ## attacking piece is destroyed
                    board[src_row][src_col] = None
                    player_pieces[player_id].remove((src_row, src_col))

                    detail = f"The attacking piece was {attacking_piece['rank']} and the destination piece was {target_piece['rank']}."
                    self.message(player_id, f"You have moved your piece from {source} to {dest}. {detail} As the attacker is not a miner, you lost the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
                    self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}. {detail} As the attacker is not a miner, you won the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

            elif target_piece['rank'] == 'Flag':
                board[dest_row][dest_col] = attacking_piece
                board[src_row][src_col] = None
                player_pieces[player_id].remove((src_row, src_col))
                player_pieces[player_id].append((dest_row, dest_col))
                player_pieces[1 - player_id].remove((dest_row, dest_col))
                ## game over
                self.game_state["rendered_board"] = self._render_board(player_id=player_id, full_board=True)
                return self.winner(player_id, reason=f"Player {player_id} has captured the opponent's flag!")

            elif attacking_piece['rank'] == 'Spy' and target_piece['rank'] == 'Marshal':
                ## Spy beats Marshal only if spy attacks first
                board[dest_row][dest_col] = attacking_piece
                board[src_row][src_col] = None
                player_pieces[player_id].remove((src_row, src_col))
                player_pieces[player_id].append((dest_row, dest_col))
                player_pieces[1 - player_id].remove((dest_row, dest_col))

                detail = f"The attacking piece was {attacking_piece['rank']} and the destination piece was {target_piece['rank']}."
                self.message(player_id, f"You have moved your piece from {source} to {dest}. {detail} As the attacker is a spy and the destination is a marshall, you won the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
                self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}. {detail} As the attacker is a spy and the destination is a marshall, you lost the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

            elif attacking_rank > target_rank:
                ## attacker wins
                board[dest_row][dest_col] = attacking_piece
                board[src_row][src_col] = None
                player_pieces[player_id].remove((src_row, src_col))
                player_pieces[player_id].append((dest_row, dest_col))
                player_pieces[1 - player_id].remove((dest_row, dest_col))

                detail = f"The attacking piece was {attacking_piece['rank']} and the destination piece was {target_piece['rank']}."
                self.message(player_id, f"You have moved your piece from {source} to {dest}. {detail} As the attacker is a higher rank than the destination, you won the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
                self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}. {detail} As the attacker is a higher rank than the destination, you lost the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

            else:
                ## defender wins
                board[src_row][src_col] = None
                player_pieces[player_id].remove((src_row, src_col))

                detail = f"The attacking piece was {attacking_piece['rank']} and the destination piece was {target_piece['rank']}."
                self.message(player_id, f"You have moved your piece from {source} to {dest}. {detail} As the attacker is a lower rank than the destination, you lost the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)
                self.message(1 - player_id, f"Player {player_id} has moved a piece from {source} to {dest}. {detail} As the attacker is a lower rank than the destination, you won the battle.", ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=-1)

        self._record_move(attacking_piece, (src_row, src_col), (dest_row, dest_col))

        ## Keep the cached board private until a terminal outcome.
        self.game_state["rendered_board"] = self._render_board(player_id=None, full_board=False)

        opponent = 1 - player_id
        mover_can_move = self._has_movable_piece(player_id)
        if not mover_can_move and not self._has_movable_piece(opponent):
            self.game_state["rendered_board"] = self._render_board(player_id=None, full_board=True)
            return self.draw(reason="Neither player has a movable piece left, so the game is a draw.")

        ## The player who is about to act loses if they have no legal move.
        winner = self._check_winner(opponent)
        if winner is not None:
            self.game_state["rendered_board"] = self._render_board(player_id=None, full_board=True)
            return self.winner(winner, reason=f"Player {winner} wins! Player {1 - winner} has no legal moves left.")

        if not mover_can_move:
            self.game_state["rendered_board"] = self._render_board(player_id=None, full_board=True)
            return self.winner(opponent, reason=f"Player {player_id} has no movable pieces remaining.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        self.game_state["rendered_board"] = self._render_board(player_id=None, full_board=True)
        return self.draw(reason="The turn limit has been reached.")

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        self.game_state["rendered_board"] = self._render_board(player_id=None, full_board=True)
        return super().on_invalid_limit(player_id, reason)

    def _populate_board(self):
        """
        Populates the board with pieces for each player strategically.
        """
        board = [[None for _ in range(10)] for _ in range(10)]
        player_pieces = {0: [], 1: []}
        for player in range(2):
            piece_serial = 0

            def make_piece(rank):
                nonlocal piece_serial
                piece = {'rank': rank, 'player': player, 'id': f"{player}:{piece_serial}"}
                piece_serial += 1
                return piece

            # Define rows for each player
            back_rows = range(0, 2) if player == 0 else range(8, 10)
            front_rows = range(2, 4) if player == 0 else range(6, 8)
            all_rows = range(0, 4) if player == 0 else range(6, 10)

            # Place the Flag strategically
            while True:
                row = self.rng.choice(back_rows)
                col = self.rng.randint(0, 9)
                if (row, col) not in self.lakes and board[row][col] is None:
                    board[row][col] = make_piece('Flag')
                    player_pieces[player].append((row, col))
                    flag_position = (row, col)
                    break

            # Place Bombs around the Flag if possible
            bombs_to_place = self.piece_counts['Bomb']
            bomb_positions = [
                (flag_position[0] + dr, flag_position[1] + dc)
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Adjacent cells
                if 0 <= flag_position[0] + dr < 10 and 0 <= flag_position[1] + dc < 10
            ]

            for pos in bomb_positions:
                if bombs_to_place > 0 and board[pos[0]][pos[1]] is None and pos not in self.lakes:
                    board[pos[0]][pos[1]] = make_piece('Bomb')
                    player_pieces[player].append(pos)
                    bombs_to_place -= 1

            # Place remaining Bombs at the frontline
            for _ in range(bombs_to_place):
                while True:
                    row = self.rng.choice(front_rows)
                    col = self.rng.randint(0, 9)
                    if board[row][col] is None and (row, col) not in self.lakes:
                        board[row][col] = make_piece('Bomb')
                        player_pieces[player].append((row, col))
                        break

            # Place other pieces randomly
            for piece, count in self.piece_counts.items():
                if piece in ['Flag', 'Bomb']:
                    continue  # Skip already placed pieces
                for _ in range(count):
                    while True:
                        row = self.rng.choice(all_rows)
                        col = self.rng.randint(0, 9)
                        if board[row][col] is None and (row, col) not in self.lakes:
                            board[row][col] = make_piece(piece)
                            player_pieces[player].append((row, col))
                            break

        # Place the lakes
        for row, col in self.lakes:
            board[row][col] = "~"

        return board, player_pieces

    def _available_moves(self, player_id: int):
        available_moves = []
        for row in range(10):
            for col in range(10):
                piece = self.board[row][col]
                if isinstance(piece, dict) and piece['player'] == player_id:
                    # Skip immovable pieces
                    if piece['rank'].lower() in ['bomb', 'flag']:
                        continue

                    # Check if this is a scout (can move multiple squares)
                    is_scout = piece['rank'].lower() == 'scout'

                    # Check all four directions
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        if is_scout:
                            # Scout can move multiple squares in this direction
                            distance = 1
                            while True:
                                new_row = row + (dr * distance)
                                new_col = col + (dc * distance)

                                # Check if still within board bounds
                                if not (0 <= new_row < 10 and 0 <= new_col < 10):
                                    break

                                target = self.board[new_row][new_col]

                                if target is None:
                                    # Empty square - scout can move here and continue
                                    if not self._violates_two_square_rule(piece, (row, col), (new_row, new_col)):
                                        available_moves.append(f"{chr(row + 65)}{col} {chr(new_row + 65)}{new_col}")
                                    distance += 1
                                elif isinstance(target, dict) and target['player'] != player_id:
                                    # Enemy piece - scout can attack but cannot continue past
                                    if not self._violates_two_square_rule(piece, (row, col), (new_row, new_col)):
                                        available_moves.append(f"{chr(row + 65)}{col} {chr(new_row + 65)}{new_col}")
                                    break
                                else:
                                    # Own piece or other obstacle - scout cannot move here or past
                                    break
                        else:
                            # Regular piece - can only move one square
                            new_row, new_col = row + dr, col + dc
                            if 0 <= new_row < 10 and 0 <= new_col < 10:
                                target = self.board[new_row][new_col]
                                if (target is None or
                                    (isinstance(target, dict) and target['player'] != player_id)):
                                    if not self._violates_two_square_rule(piece, (row, col), (new_row, new_col)):
                                        available_moves.append(f"{chr(row + 65)}{col} {chr(new_row + 65)}{new_col}")
        return available_moves

    def _render_board(self, player_id, full_board: bool = False):
        """
        Renders the board state with fixed-width formatting for uniform alignment.

        Args:
            player_id (int): The player viewing the board.
            full_board (bool): Whether to render the full board or just the visible pieces.
        """
        # Define abbreviations for each piece
        piece_abbreviations = {
            'Flag': 'FL', 'Bomb': 'BM', 'Spy': 'SP', 'Scout': 'SC', 'Miner': 'MN',
            'Sergeant': 'SG', 'Lieutenant': 'LT', 'Captain': 'CP', 'Major': 'MJ',
            'Colonel': 'CL', 'General': 'GN', 'Marshal': 'MS'
        }

        res = []
        column_headers = "   " + " ".join([f"{i:>3}" for i in range(10)])  # Align column numbers
        res.append(column_headers + "\n")

        for row in range(10):
            row_label = chr(row + 65)  # Convert row index to a letter (A, B, C, ...)
            row_render = [f"{row_label:<3}"]  # Add row label with fixed width
            for col in range(10):
                if (row, col) in self.lakes:
                    cell = "  ~ "  # Lakes
                elif self.board[row][col] is None:
                    cell = "  . "  # Empty space
                else:
                    piece = self.board[row][col]
                    abbreviation = piece_abbreviations[piece['rank']]
                    if full_board:
                        cell = f" {abbreviation.lower() if piece['player'] == 0 else abbreviation.upper()} "  # Full board view
                    elif piece['player'] == player_id:
                        displayed_piece = abbreviation.upper()
                        cell = f" {displayed_piece} "
                    else:
                        cell = "  ? "  # Hidden opponent piece
                row_render.append(cell)

            res.append("".join(row_render) + "\n")

        return "".join(res)

    def _validate_move(self, player_id, src_row, src_col, dest_row, dest_col) -> Optional[str]:
        """
        Validates the move based on the game rules. Returns the invalid-move
        reason, or None if the move is legal.
        """
        board = self.board
        if not (0 <= src_row < 10 and 0 <= src_col < 10 and 0 <= dest_row < 10 and 0 <= dest_col < 10):
            return f"Invalid action format. Player {player_id} did not input valid coordinates."

        if board[src_row][src_col] is None or not isinstance(board[src_row][src_col], dict) or board[src_row][src_col]['player'] != player_id:
            return f"Invalid action format. Player {player_id} must move one of their own pieces."

        if abs(src_row - dest_row) + abs(src_col - dest_col) != 1 and board[src_row][src_col]['rank'].lower() == 'scout':
            ## check if there's a piece in between the source and destination
            if src_row == dest_row:
                for col in range(min(src_col, dest_col) + 1, max(src_col, dest_col)):
                    if board[src_row][col] is not None:
                        return f"Invalid action format. Player {player_id} cannot move a scout through other pieces."
            elif src_col == dest_col:
                for row in range(min(src_row, dest_row) + 1, max(src_row, dest_row)):
                    if board[row][src_col] is not None:
                        return f"Invalid action format. Player {player_id} cannot move a scout through other pieces."
            else:
                return f"Invalid action format. Player {player_id} cannot move a scout diagonally."

        if abs(src_row - dest_row) + abs(src_col - dest_col) != 1 and board[src_row][src_col]['rank'].lower() != 'scout':
            ## !  - by right, only scouts can move more than one square at a time but we are not implementing that yet
            return "Invalid action format. Pieces, apart from scouts, can only move one square at a time."

        if board[dest_row][dest_col] is not None:
            if (dest_row, dest_col) in self.lakes:
                return f"Invalid action format. Player {player_id} cannot move into the lake."

            elif board[dest_row][dest_col]['player'] == player_id:
                return f"Invalid action format. Player {player_id} cannot move onto their own piece."

        if board[src_row][src_col]['rank'].lower() in ['bomb', 'flag']:
            return f"Invalid action format. Player {player_id} cannot move a bomb or flag."

        if self._violates_two_square_rule(
            board[src_row][src_col],
            (src_row, src_col),
            (dest_row, dest_col),
        ):
            return "This move violates Stratego's two-square repetition rule."

        return None

    def _record_move(self, piece, source, destination):
        piece_id = piece.get("id")
        if piece_id is None:
            return
        player_id = piece["player"]
        last_moved = self.game_state["last_moved_piece"]
        if last_moved.get(player_id) != piece_id:
            # Moving another one of this player's pieces interrupts a
            # consecutive two-square sequence. Opponent moves do not.
            self.game_state["move_history"][piece_id] = []
        history = self.game_state["move_history"].setdefault(piece_id, [])
        history.append((source, destination))
        del history[:-3]
        last_moved[player_id] = piece_id

    def _violates_two_square_rule(self, piece, source, destination) -> bool:
        piece_id = piece.get("id")
        if piece_id is None:
            return False
        last_moved = self.game_state.get("last_moved_piece", {})
        if last_moved.get(piece["player"], piece_id) != piece_id:
            return False
        history = self.game_state.get("move_history", {}).get(piece_id, [])
        if len(history) < 3:
            return False
        pair = frozenset((source, destination))
        return all(
            frozenset((old_source, old_destination)) == pair
            for old_source, old_destination in history[-3:]
        )

    def _check_winner(self, player_to_move: Optional[int] = None):
        """
        Determine whether the player about to act has no legal move.
        """
        players = range(2) if player_to_move is None else (player_to_move,)
        for player in players:
            if not self._available_moves(player):
                return 1 - player
        return None

    def _has_movable_piece(self, player_id: int) -> bool:
        return any(
            isinstance(self.board[row][col], dict)
            and self.board[row][col]["rank"] not in ("Bomb", "Flag")
            for row, col in self.player_pieces[player_id]
        )
