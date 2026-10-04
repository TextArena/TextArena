# Ultimate Tic Tac Toe

Two players play tic-tac-toe on nine small boards arranged in a 3×3 grid, where each move dictates the opponent's next
board and three won boards in a row win the game ([rules](https://en.wikipedia.org/wiki/Ultimate_tic-tac-toe)). Every
move both claims a square and chooses the opponent's next board, so good play means thinking about the large board,
not just the small one in front of you.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `UltimateTicTacToe-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `UltimateTicTacToe-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 is `X` and moves first; Player 1 is `O`.
- The board is a 3×3 grid of mini-boards numbered 0–8, left to right and top to bottom. Each mini-board is a
  tic-tac-toe grid whose squares are also numbered 0–8 the same way.
- The first move may go in any square. After that, the square you mark sends your opponent to the mini-board with the
  same number: marking square 8 of any mini-board means they must play in mini-board 8 next.
- Three of your marks in a row inside a mini-board win it. A mini-board that fills up without a winner is drawn and
  counts for nobody.
- Won and drawn mini-boards are closed: nobody can play there again, even if empty squares remain. If you are sent to
  a closed mini-board, you may play in any open one.
- Winning three mini-boards in a row (horizontally, vertically, or diagonally) wins the game. If every mini-board is
  closed without such a line, the game is a draw.

## Actions

Reply with `macro micro`: the mini-board number and the square number inside it, each 0–8, separated by a space (a
comma also works).

Example: `7 8` marks square 8 of mini-board 7 and sends your opponent to mini-board 8 (unless it is closed).

## Observations

Each player first receives the rules and their mark. Before every move, the acting player sees:

- the full board, where every empty square of an open mini-board is labeled `'macro,micro'` and unused squares of
  closed mini-boards show `.`;
- a 3×3 summary of the mini-boards (`X` or `O` for won, `D` for drawn, the board number for open);
- where they must play (one specific mini-board, or any open one) and the list of valid moves.

Both players see every move, along with where the next player must play. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Three mini-boards in a row | Winner `+1`, loser `-1` |
| Every mini-board closed, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Notes

- This is the common rule set: closed mini-boards accept no more marks, and drawn mini-boards count for nobody. A
  known variant makes players keep playing in won mini-boards that still have empty squares; it is not implemented.
