# Chess

Two players alternate moves on an 8×8 board, each trying to checkmate the opponent's king
([rules](https://en.wikipedia.org/wiki/Rules_of_chess)). Games start from the standard position and are played with the
full FIDE move rules; draws that a player could claim are applied automatically, and a turn limit caps game length.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Chess-v1` | `is_open=True`, `max_turns=100`, `show_valid=True` |
| `Chess-v1-blind` | `is_open=False`, `max_turns=100`, `show_valid=False` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Chess-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Chess-v1", is_open=...)`.
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays White and moves first; Player 1 plays Black.
- Pieces move as in standard chess. A move that leaves your own king in check is illegal.
- **Castling:** the king moves two squares toward a rook, which jumps to the square the king crossed. Allowed only if
  neither piece has moved, the squares between them are empty, and the king is not in check, does not pass through
  an attacked square, and does not land on one.
- **En passant:** immediately after an enemy pawn advances two squares and lands beside your pawn, your pawn may
  capture it as if it had moved one square.
- **Promotion:** a pawn reaching the last rank must promote to a queen, rook, bishop, or knight.

The game ends as soon as any of these holds after a move, checked in this order:

| Condition | Result |
| --- | --- |
| Checkmate | The side delivering mate wins |
| Insufficient material (neither side can mate: e.g. K v K, K+minor v K, only same-colored bishops) | Draw |
| Stalemate (side to move has no legal move and is not in check) | Draw |
| Seventy-five-move rule (150 plies without a capture or pawn move) | Draw |
| Fivefold repetition of a position | Draw |
| Threefold repetition of the current position (auto-applied) | Draw |
| Fifty-move rule: 100 plies without a capture or pawn move (auto-applied) | Draw |
| `max_turns` moves played in total (both players combined) | Draw |

Because threefold repetition and the fifty-move rule are applied without a claim, they always trigger before the
fivefold and seventy-five-move rules could. A checkmate or stalemate on the deciding move takes precedence over
the fifty-move rule and the turn limit. Repetition compares piece placement, side to move, castling rights, and
en passant possibilities.

## Actions

Reply with one move in [UCI](https://en.wikipedia.org/wiki/Universal_Chess_Interface) notation: the from-square
followed by the to-square, plus a promotion letter (`q`, `r`, `b`, `n`) when a pawn reaches the last rank.
Matching is case-insensitive, and surrounding whitespace is ignored.

- `e2e4`: pawn from e2 to e4.
- `g1f3`: knight from g1 to f3.
- `e1g1`: White castles kingside (the king's two-square move; `e1c1` castles queenside).
- `e7e8q`: pawn from e7 to e8, promoting to a queen.

A pawn move to the last rank without a promotion letter is illegal. Malformed text, an impossible move such as
`a1a1`, or an illegal move counts as an invalid move.

## Observations

Each player first receives their color, how to write moves (including castling and promotion), what the board
letters mean, and the turn limit. Every move is broadcast to both players as `White played e2e4.`, followed by
`Black is in check.` when it gives check.

Before each move, the acting player also receives:

- with `is_open=True`, the current board: an 8×8 grid with rank numbers and file letters, White pieces in
  uppercase (`K Q R B N P`), Black in lowercase, and `.` for empty squares;
- with `show_valid=True`, the full list of legal moves in UCI notation.

With both disabled (`Chess-v1-blind`), players must track the position from the move history alone.

## Rewards

| Outcome | Reward |
| --- | --- |
| Checkmate | Winner `+1`, loser `-1` |
| Stalemate, insufficient material, repetition, fifty/seventy-five-move rule | Both `0` |
| Turn limit reached | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

The first invalid move only triggers a retry message; a valid move resets the count.

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `is_open` (default `True`): Show the board to the acting player before each move.
- `max_turns` (default `30`): The total number of moves (both players combined) before the game is drawn. Accepts an integer of at least 1.
- `show_valid` (default `True`): Show the list of legal moves before each move.
<!-- END GENERATED: parameters -->

## Notes

The rules engine is implemented in-house in `board.py`, with no third-party chess dependency. Its move
generator is verified by perft node counts on the standard test positions (`test_board.py`) and by a
differential test that replays random games against [python-chess](https://python-chess.readthedocs.io/) and
compares legal moves, FEN, and game-ending state at every position (`test_board_differential.py`). python-chess
is only an optional test oracle, installed with the `test` extra; that test is skipped when it is absent.
