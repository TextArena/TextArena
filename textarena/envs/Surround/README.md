# Surround

Two to fifteen light cycles move simultaneously on a grid, each leaving a permanent trail; whoever crashes into a
wall or a trail is out, and the last player moving wins ([background](https://en.wikipedia.org/wiki/Surround_%28video_game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Surround-v1` | `width=5`, `height=5`, `max_turns=40` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Surround-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Surround-v1", width=...)`.
<!-- END GENERATED: variants -->

## Rules

- Players start on interior cells (never on the outer ring), spread out by farthest-point sampling.
- Every round, each living player chooses a direction in secret; once all have chosen, everyone moves one cell at
  once. Players submit in turn order, but nobody sees another player's choice before the round resolves.
- Every cell a player leaves becomes a permanent trail, including the last cell of a player who crashes.
- A player crashes if they move off the board, onto a trail, onto a cell another player occupies at the start of the
  round, or onto the same cell as another player. Two players who swap cells both crash. Crashed players are out, and
  their trails stay.
- An invalid reply counts as a crash; there is no retry.
- The game ends when at most one player is left or after `max_turns` rounds.

## Actions

Reply with one direction: `up`, `down`, `left`, or `right`, or the shortcuts `w`, `s`, `a`, `d` (case-insensitive).
`up` moves toward the top of the printed board.

## Observations

Each player first receives the rules, their player number, and their symbol on the board. Before every move, the
acting player sees the board, the number of rounds played, and whether each player is still in (or the round they
crashed in, and why). On the board, players show their number (players 10–14 appear as `A`–`E`), trails are `#`, and
empty cells `.`. Choices stay hidden until the round resolves; then everyone sees each player's move and who crashed,
and why.

## Rewards

Players are ranked by how long they survived: players still in at the end share the top rank, and players who crashed
in the same round share a rank (later is better). Rewards are spread evenly from `+1` for the best rank to `-1` for
the worst, so three distinct ranks get `+1`, `0`, and `-1`.

| Outcome | Reward |
| --- | --- |
| One player left | Survivor `+1`; the others are ranked by when they crashed |
| `max_turns` rounds reached | Players still in share the top rank, above everyone who crashed |
| Every player tied (all crash in the same round, or nobody crashes before the round limit) | Everyone `0` |
| Invalid move | The player crashes in that round and is ranked like any other crash |

With two players, the survivor gets `+1` and the other `-1`, or both get `0` when they are tied.

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `width` (default `10`): The board width. Accepts an integer of at least 3.
- `height` (default `10`): The board height. Accepts an integer of at least 3.
- `max_turns` (default `100`): The number of rounds, each one move by every living player, before the game ends. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->
