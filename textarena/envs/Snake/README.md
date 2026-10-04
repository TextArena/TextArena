# Snake

Two to fifteen snakes move simultaneously on a shared grid and grow by eating apples; the last snake alive wins, and
snakes that survive to the round limit are ranked by apples eaten
([background](https://en.wikipedia.org/wiki/Snake_%28video_game_genre%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Snake-v0` | `width=5`, `height=5`, `num_apples=2`, `max_turns=40` |
| `Snake-v0-large` | `width=15`, `height=15`, `num_apples=5`, `max_turns=250` |
| `Snake-v0-standard` | `width=10`, `height=10`, `num_apples=3`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Snake-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Every snake starts as a single cell. Spawns are spread out by farthest-point sampling over the interior cells (all
  cells when the interior is too small for everyone), and `num_apples` apples are placed on random empty cells.
- Every round, each living snake chooses a direction in secret; once all have chosen, they all move one cell at once.
  Players submit in turn order, but nobody sees another snake's choice before the round resolves.
- Moving onto an apple scores 1 point and grows the snake by one segment. Eaten apples are replaced on random empty
  cells after everyone has moved.
- A snake dies if it moves off the board, into a cell occupied by any snake (its own body and snakes dying in the same
  round included), into the same cell as another head, or trades places with another head. A tail cell is free if its
  snake moves on this round without eating or dying. Dead snakes are removed from the board.
- An invalid reply kills the snake at once; there is no retry.
- The game ends when at most one snake is alive or after `max_turns` rounds.

## Actions

Reply with one direction: `up`, `down`, `left`, or `right`, or the shortcuts `w`, `s`, `a`, `d` (case-insensitive).
`up` moves toward the top of the printed board.

## Observations

Each player first receives the rules, their snake number, and the symbol of their head. Before every move, the acting
player sees the board, the number of rounds played, and every snake's length and score (or the round it died in). On
the board, heads show their snake number (snakes 10–14 appear as `A`–`E`), bodies are `#`, apples `*`, and empty
cells `.`. Choices stay hidden until the round resolves; then everyone sees each snake's move and whether it ate an
apple or died, and why.

## Rewards

At the end, snakes are ranked: living snakes above dead ones, dead snakes by the round they died in (later is
better), and score (apples eaten) breaks ties; snakes that are still tied share a rank. Rewards are spread evenly from
`+1` for the best rank to `-1` for the worst, so four distinct ranks get `+1`, `+1/3`, `-1/3`, and `-1`.

| Outcome | Reward |
| --- | --- |
| One snake left alive | Survivor `+1`; the others are ranked by death round, then score |
| All remaining snakes die in the same round | Ranked by score; equal scores share a rank |
| `max_turns` rounds reached | Survivors ranked by score, above all dead snakes |
| Every snake tied | Everyone `0` |
| Invalid move | The snake dies in that round and is ranked like any other death |

With two players, the winner gets `+1` and the loser `-1`, or both get `0` when they are tied.

## Parameters

- `width` and `height` (default `10` × `10`): board size, positive integers with `width × height` at least
  `num_apples + 15`.
- `num_apples` (default `3`): number of apples kept on the board (fewer only when no empty cell is left).
- `max_turns` (default `100`): number of rounds, each one move by every living snake, before the game ends.
