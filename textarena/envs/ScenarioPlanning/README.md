# Scenario Planning

Two players each write a survival strategy for the same hypothetical crisis without seeing each other's plan, and an
AI jury votes for the more effective and feasible one.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `ScenarioPlanning-v0` | `jury_size=11` |

Append `-mdp` to any ID for the state-complete variant (e.g. `ScenarioPlanning-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("ScenarioPlanning-v0", jury_size=...)`.
<!-- END GENERATED: variants -->

## Rules

- A scenario is drawn at random from the bundled list of 68 (or from `scenarios_path`), for example a plane crash on a
  deserted island or a zombie outbreak in a city.
- Player 0 submits a strategy, then Player 1 does. Each player submits exactly one.
- Once both are in, a jury of `jury_size` AI judges reads the scenario and both strategies and votes `Player 0` or
  `Player 1` for the more effective and feasible plan. More votes wins; equal votes are a draw.

## Actions

Any non-empty text of up to 10,000 characters is a strategy, e.g.
`Ration water to one liter a day, build a raised shelter near the beach, and keep a signal fire ready.` An empty reply or
a longer one is invalid.

## Observations

Each player receives the scenario and the rules. Strategies are never shown to the other player, and nobody sees the
jury's votes; the final message names the winner.

## Rewards

| Outcome | Reward |
| --- | --- |
| More jury votes | Winner `+1`, loser `-1` |
| Equal votes | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |
| Jury unavailable or returns an unusable vote | Nothing is scored: the second strategy is not counted and Player 1 is asked to resubmit it |

## Parameters

- `jury_size` (default `5`, at most `100`): number of judges.
- `jury_class` (default `OpenRouterJury`): class or factory called with `options` and `jury_size` (and the env's
  seeded `rng` if it accepts one). The object it returns must provide `evaluate(context)` returning
  `{"Player 0": votes, "Player 1": votes}`.
- `scenarios_path` (default: the bundled `scenarios.json`): JSON file of the form `{"scenarios": ["...", ...]}` with
  unique, non-empty scenarios.

## Notes

- The default jury calls OpenRouter and needs `OPENROUTER_API_KEY`. Judges are picked from a default list of models in
  `textarena/utils/jury.py` using the env's seeded random generator, but their votes are model outputs and can differ
  between runs. If any judge errors out or gives an invalid answer, the whole vote fails and the move is retried.
- The jury always reads Player 0's strategy first.
