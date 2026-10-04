# Win as Much as You Can

Four players secretly choose X or Y in each of ten rounds of a multi-player prisoner's dilemma, negotiating publicly
and privately before the 3×, 5×, and 10× rounds ([rules](https://www.pibetaphi.org/Admin/PiBetaPhi/media/About-Us/Programs/Collegiate-Leading-With-Values/Win-as-Much-as-You-Can.pdf)).
It tests the tension between individual gain and group benefit, coalition building, and trust over repeated play.

<!-- BEGIN GENERATED: variants -->
**Players:** 4

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `WinAsMuchAsYouCan-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `WinAsMuchAsYouCan-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Exactly four players play ten rounds. In each round, every player secretly picks X or Y, and points depend on how
  many players chose X:

  | Choices | Each X player | Each Y player |
  | --- | --- | --- |
  | 1 X, 3 Y | `+3` | `-1` |
  | 2 X, 2 Y | `+2` | `-2` |
  | 3 X, 1 Y | `+1` | `-3` |
  | 4 X | `-1` | — |
  | 4 Y | — | `+1` |

- Points are multiplied by the round's multiplier: 3× in round 5, 5× in round 8, 10× in round 10, and 1× otherwise.
- Rounds 5, 8, and 10 open with a talk phase. Players take turns, starting with Player 0 and skipping anyone who has
  passed, to broadcast a public message, whisper to one other player, or pass. Passing ends your participation in
  that talk phase. Each player may take at most 10 talk actions per phase (after the 10th they pass automatically),
  and the phase ends after 40 talk actions in total or once everyone has passed.
- In every act phase, players choose in order from Player 0 to Player 3, and no choice is revealed until all four are
  in.
- After round 10, the player or players with the highest total score win.
- Every invalid move is reported to its author. After `error_allowance + 1` consecutive invalid moves (four by
  default), the player's pending decision is made for them and play moves on. In a talk phase they `Pass`, and in an
  act phase they `Choose Y`. Only the offender is told that a default was applied, so a forced act-phase choice stays
  secret until the round is scored. `Choose Y` is the default because `Choose X` always scores more for the chooser,
  so the default never beats the offender's best valid move.

## Actions

During an act phase:

- `Choose X`
- `Choose Y`

During a talk phase:

- `Broadcast: <message>` sends a public message to everyone.
- `Whisper <player>: <message>` sends a private message to another player. `Whisper to 2:` and
  `Whisper to Player 2:` also work.
- `Pass` ends your talking for the rest of this talk phase.

Examples: `Broadcast: Let's all choose Y this round.` or `Whisper 2: I'll choose Y if you do.`

Commands are case-insensitive. `Choose X`, `Choose Y`, and `Pass` must be the entire reply; broadcasts and whispers
must start with the command.

## Observations

Each player first receives the rules, the scoring rubric, the round structure, and the invalid-move defaults. Before
every move, the acting player sees a status board with the round, phase, and multiplier; in a talk phase, the number
of talk actions so far out of 40, who has passed, and the latest messages they are allowed to see; in an act phase,
who has already chosen; every player's total score; and the choices and points of the last three rounds.

Broadcasts are seen by everyone. A whisper's content is seen only by its sender and recipient; the other two players
are only told that a private message was sent between two players. During an act phase, the others only learn that a
player has made their choice. All four choices and the resulting points are announced once the round is scored.

## Rewards

| Outcome | Reward |
| --- | --- |
| Highest total score after round 10 | `+1` for every player tied for the top score, even if it is negative |
| Any lower total score | `-1` |
| Repeated invalid moves | The default `Pass` or `Choose Y` is applied and the game continues, but that player can no longer win: they get `-1` at the end |

If everyone chooses Y in every round, all four players tie and each gets `+1`: cooperation is a shared victory. A
player whose move ever had to be forced is excluded from the win and gets `-1` (their game info has `invalid_move`
set); the top score is decided among the remaining players, and if every player had a move forced, everyone gets `-1`.

## Parameters

- `error_allowance` (default `3`): the number of consecutive invalid moves that only receive a warning. The next one
  also gets feedback, sets `invalid_move` in the player's game info, and applies the default decision. The count then
  starts over.

## Notes

- Every game ends. Each decision, valid or forced, advances the fixed structure. A game has 40 act-phase choices, and
  each of the three talk phases has at most 40 talk actions, so a game takes at most 160 decisions. Each decision
  takes at most `error_allowance + 1` steps. A game where every move is invalid ends after
  52 × (`error_allowance` + 1) steps (208 by default). There is no separate turn limit, because the engine's turn
  limit counts only valid turns, and the round structure already caps those at 160.
- Credit: Pi Beta Phi, *Win as Much as You Can*
  ([exercise PDF](https://www.pibetaphi.org/Admin/PiBetaPhi/media/About-Us/Programs/Collegiate-Leading-With-Values/Win-as-Much-as-You-Can.pdf)).
