# Character Conclave

Players hold a free-form discussion under a strict per-player character budget, then each secretly votes for the most
impressive other player; the most-voted player wins. It tests concise, persuasive communication.

<!-- BEGIN GENERATED: variants -->
**Players:** 3–15

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `CharacterConclave-v0` | `character_budget=1000` |

Append `-mdp` to any ID for the state-complete variant (e.g. `CharacterConclave-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("CharacterConclave-v0", character_budget=...)`.
<!-- END GENERATED: variants -->

## Rules

- Every player starts with a budget of `character_budget` characters.
- **Discussion phase:** players take turns in order, starting with Player 0. The length of each message is subtracted
  from the sender's budget, and a message longer than the remaining budget is cut off at the budget (the sender is told
  when this happens). Players who have used up their budget are skipped.
- The discussion ends only once every player's budget is used up; there is no separate turn limit.
- **Voting phase:** starting with the player who spent the last characters and continuing in turn order, every player
  casts exactly one vote for another player. Votes stay secret until the final tally.
- Players are ranked by the number of votes they received, and the game ends after the last vote.

## Actions

During the discussion, reply with any non-empty free text; the whole reply is your message, e.g.
`What is the most surprising thing you have changed your mind about?` Whitespace-only messages are invalid, as is a
message whose part within your remaining budget is blank.

During voting, reply with the id of the player you vote for, e.g. `2` or `player 2` (case-insensitive). Voting for
yourself, for a non-existent player, or for an eliminated player is invalid, and a vote cannot be changed.

## Observations

Each player first receives the rules, the number of players, and the character budget. Before each discussion turn,
the acting player is shown their own remaining budget, e.g. `Your remaining character budget: 412 of 1000 characters.`
Every discussion message is shown to all players, attributed to its sender, exactly as it was counted (that is, already
truncated if it ran over the budget), and a sender whose message was cut off is privately told how much was sent. A
game message announces the start of voting, and before each vote the voter is reminded which players they can vote
for. Votes are never shown to other players; the voter only gets a private confirmation. Eliminations are announced to
everyone. When voting ends, the number of votes each player received is broadcast.

## Rewards

Rewards are spread evenly between `-1` and `+1` by rank, where players with the same number of votes share a rank.

| Outcome | Reward |
| --- | --- |
| Most votes | `+1` |
| Fewest votes | `-1` |
| In between | Evenly spaced by rank, e.g. `0` for the middle group when there are three distinct vote counts |
| Every player receives the same number of votes | Everyone `0` |
| Second consecutive invalid move | Offender is eliminated with `-1` (announced to everyone) and can no longer receive votes; during voting their vote is discarded and votes already cast for them no longer count |
| Only one player left after an elimination (during the discussion or voting) | That player `+1`, everyone else `-1` |

## Parameters

- `character_budget` (default `1000`): total number of characters each player may use during the discussion.

## Notes

- Scoring depends only on the votes, so the game needs no external judge or API key.
- Eliminating a player for invalid moves follows the engine's default policy and the original game: an eliminated
  player drops out of the ranking, so votes already cast for them are wasted, while later voters are told about the
  elimination and can choose someone else.
