# Othello

Two players place discs on a square board, flipping every line of opposing discs they enclose; whoever owns more discs
when neither side can move wins ([rules](https://en.wikipedia.org/wiki/Reversi)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Othello-v0` | `board_size=8`, `show_valid=True` |
| `Othello-v0-hard` | `board_size=8`, `show_valid=False` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Othello-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Othello-v0", board_size=...)`.
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays Black (drawn `○`) and moves first; Player 1 plays White (drawn `●`).
- The game starts with four discs in the centre: White on the upper-left and lower-right centre squares, Black on the
  other two.
- A move places one of your discs on an empty square so that at least one straight line (horizontal, vertical, or
  diagonal) of opposing discs lies between it and another of your discs. Every such enclosed disc flips to your
  colour. A move that flips nothing is illegal.
- If you have no legal move, your turn is skipped automatically and both players are told. Otherwise passing is not
  allowed.
- The game ends when the board is full or neither player has a legal move. The player with more discs wins; equal
  counts are a draw.

## Actions

Reply with the row and column of your move, numbered from 0 as labelled on the board, separated by a comma or a space:
`2, 3` or `2 3`. Compact forms such as `23` are rejected because they are ambiguous on larger boards.

```
    0   1   2   3
  ┌───┬───┬───┬───┐
0 │   │   │   │   │
  ├───┼───┼───┼───┤
1 │   │ ● │ ○ │   │
  ├───┼───┼───┼───┤
2 │   │ ○ │ ● │   │
  ├───┼───┼───┼───┤
3 │   │   │   │   │
  └───┴───┴───┴───┘
```

Example: on the 4×4 starting board above, Black's legal moves are `0, 1`, `1, 0`, `2, 3`, and `3, 2`.

## Observations

Each player first receives the rules and which symbol is theirs. Before every move, the acting player sees the board,
both disc counts, and, when `show_valid` is on, the list of valid moves. Both players see each move with the number of
discs it flipped, and every automatic pass. An illegal move is rejected with an explanation, which repeats the valid
moves only when `show_valid` is on.

## Rewards

| Outcome | Reward |
| --- | --- |
| More discs at the end | Winner `+1`, loser `-1` |
| Equal disc counts | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `board_size` (default `8`): side length of the board; an even integer of at least 4.
- `show_valid` (default `True`): whether the acting player is shown the list of valid moves, both before each move and
  after an illegal one.
