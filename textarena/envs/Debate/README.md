# Debate

Two players argue opposite sides of a random topic in alternating turns, and an AI jury that votes before and after
the debate decides the winner: the side that gains more of the jury's support.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `Debate-v0` | `max_turns=6`, `jury_class=OpenRouterJury`, `jury_size=7` |
| `Debate-v0-long` | `max_turns=30`, `jury_class=OpenRouterJury`, `jury_size=13` |
| `Debate-v0-medium` | `max_turns=12`, `jury_class=OpenRouterJury`, `jury_size=9` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Debate-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- A topic is drawn at random from the bundled list of 26 (or from `topics_path`), and the Affirmative and Negative
  sides are assigned at random.
- Player 0 speaks first whichever side they hold, and the players alternate for `max_turns` arguments in total, so
  each player makes `max_turns / 2` of them.
- When the first argument is submitted, a jury of `jury_size` AI jurors votes Affirmative or Negative on the topic
  alone. After the final argument, the jury reads the full transcript and votes again.
- Each side's score is its share of the post-debate vote minus its share of the pre-debate vote. The side with the
  larger gain wins; equal gains are a draw.

## Actions

Any non-empty text of up to 10,000 characters is an argument, e.g.
`Mandatory voting gives every community a voice, so elected officials must answer to all of them.` An empty reply or a
longer one is invalid.

## Observations

Each player first receives the topic, their side, the number of turns, and how the jury decides. Both players see
every accepted argument. The jury's votes are never shown during the game; the final message names the winner.

## Rewards

| Outcome | Reward |
| --- | --- |
| Larger gain in jury support | Winner `+1`, loser `-1` |
| Equal gains | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |
| Jury unavailable or returns an unusable vote | Nothing is scored: the argument is not counted and the player is asked to resubmit it |

## Parameters

- `max_turns` (default `4`): arguments in the whole debate; must be an even number of at least 2.
- `jury_size` (default `5`, at most `100`): number of jurors.
- `jury_class` (default `OpenRouterJury`): class or factory called with `options` and `jury_size` (and the env's
  seeded `rng` if it accepts one). The object it returns must provide `evaluate(context)` returning
  `{"Affirmative": votes, "Negative": votes}`.
- `topics_path` (default: the bundled `topics.json`): JSON file of the form `{"topics": ["...", ...]}` with unique,
  non-empty topics.

## Notes

- The default jury calls OpenRouter and needs `OPENROUTER_API_KEY`. Jurors are picked from a default list of models
  in `textarena/utils/jury.py` using the env's seeded random generator, but their votes are model outputs and can
  differ between runs.
- If any juror errors out or answers with something other than `Affirmative` or `Negative`, the whole vote fails and
  the move is retried. A missing API key also surfaces as a retry request rather than a crash.
- Jurors read the arguments verbatim.
