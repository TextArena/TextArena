# Scorable Games

Stakeholders with secret scoring sheets negotiate a multi-issue agreement by proposing complete deals and voting on
them; a deal passes once enough parties, including every veto holder, accept it. It is based on Susskind's scorable
games for negotiation teaching, as adapted for language models by LLM-Deliberation
([paper](https://arxiv.org/abs/2309.17234)), and tests multi-party bargaining, coalition building, and finding
compromises under private preferences.

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `ScorableGames-v0` | `game_config="base"`, `max_rounds=120`, `invalid_move_default="Accept"` |

Append `-mdp` to any ID for the state-complete variant (e.g. `ScorableGames-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("ScorableGames-v0", game_config=...)`.
<!-- END GENERATED: variants -->

## Rules

- The scenario (`game_config`) fixes the parties, the issues (five or six, each with 3–5 options), and every party's
  private scoring sheet: points for each option plus a minimum acceptable score. The number of players must equal the
  scenario's number of parties (see the table under Parameters).
- Players act one at a time in player order, starting with the party that holds `starting_role`. Each turn is either a
  complete proposal (one option per issue) or a vote on the proposal currently on the table.
- A new proposal replaces the one on the table, clears all votes, and counts as its proposer's acceptance. Proposing
  the deal that is already on the table counts as accepting it. Votes can be changed on a later turn.
- A deal passes as soon as it has `required_votes` acceptances and every veto holder has accepted it. If every party
  has accepted at that moment, the party holding `unanimity_bonus_role` earns 10 extra points.
- The game ends when a deal passes or after `max_rounds` turns in total; every player's turn counts as one round.

## Actions

Reply with optional reasoning followed by exactly one command, which must start its own line. Anything after the
command line is ignored. Keywords and option codes are case-insensitive.

- `Propose <option> <option> ...` lists one option per issue, e.g. `Propose A2 B2 C3 D2 E3` (scenarios with six
  issues also need an `F` option). On the proposal line only option codes (an issue letter followed by a number) are
  read, so other words such as `And` or `Because` are ignored. If an issue is listed twice, the last option counts.
- `Accept` or `Reject` votes on the proposal on the table.

```
This keeps the federal loan affordable and protects the shoreline.
Propose A2 B2 C3 D2 E3
```

A reply without a command or with several command lines, a proposal that skips an issue or names an option that does
not exist for one of the scenario's issues (e.g. `A9`), and a vote when no proposal is on the table are invalid. Codes
for issues the scenario does not have (e.g. `F1` in a five-issue scenario) are ignored.

## Observations

Each player first receives the scenario (with their own party marked as represented by them), all issues and options,
their private instructions and scoring sheet, the voting rules, and their minimum acceptable score; the instructions
forbid revealing exact scores. Every proposal and vote is announced to all players together with the reasoning written
before the command, while the raw reply is echoed only to its author. While a proposal is on the table, the acting
player sees it before every turn with their own points for each option and in total, plus every party's current vote.
Other parties' scores stay hidden: when a deal passes, every party's score, minimum, and reward are announced, and when
no deal is reached, each player is told their fallback score privately.

## Rewards

| Outcome | Reward |
| --- | --- |
| Deal passes | `+1` for every player whose score (including any bonus) reaches their minimum acceptable score, `-1` for every other player (everyone `-1` if nobody reaches it) |
| No deal after `max_rounds` turns | Everyone `0` |
| Invalid move after `error_allowance` warnings | No penalty: the player's vote is set to `invalid_move_default`; if no proposal is on the table, the deal that maximizes their own score is proposed for them first. The turn counts as a round |

A party's minimum acceptable score is its walk-away value: players are told that without a deal they receive exactly
that score. A deal that reaches it is a success (`+1`), a deal below it leaves the party worse off than no deal (`-1`),
and no deal leaves every party exactly at its minimum (`0`). The raw points are recorded in `game_info` (`score`,
`threshold`, `deal_accepted`).

## Parameters

| `game_config` | Players | Scenario |
| --- | :---: | --- |
| `base` | 6 | SportCo's Harbour Sport Park in England (Mayor, Other cities, Local Labour Union, SportCo, Department of Tourism, Environmental League) |
| `base_7players` | 7 | `base` plus a National Heritage Committee and a sixth issue |
| `base_rewritten` | 6 | A reworded `base`: Eventix's Coastal Sport Zone in Aberdeen (not registered) |
| `game1` | 6 | A new airport on a small island nation |
| `game2` | 6 | A solar power plant in a developing country |
| `game3` | 6 | A new airport in Saarland, Germany |
| `medical_ethics` | 4 | An ICU team allocating a single ventilator (no veto holders or bonus) |
| `vendor_retailer` | 2 | A supplier–retailer partnership agreement |

The class accepts 2–15 players in general, but each scenario has a fixed number of parties: `reset()` raises a
`ValueError` naming the expected count for any other `num_players`.

- `max_rounds` (default `120`): total number of turns before the game ends without a deal.
- `required_votes` (default `None`): acceptances needed for a deal to pass; `None` means all players but one.
- `veto_roles` (default `("p1", "p2")`): scenario roles whose acceptance is mandatory.
- `unanimity_bonus_role` (default `"p1"`): scenario role that earns the unanimity bonus.
- `starting_role` (default `"p1"`): scenario role that moves first; Player 0 starts if no party has that role.
- `invalid_move_default` (default `"Accept"`): vote cast for a player who exceeds the invalid-move allowance, including
  on a deal proposed for them.
- `error_allowance` (default `3`): consecutive invalid moves that only produce a warning.

## Notes

- Credits: L. E. Susskind, "Scorable games: A better way to teach negotiation", *Negotiation Journal* 1(3), 1985
  ([PDF](https://web.mit.edu/publicdisputes/teach/scorablegames.pdf)); S. Abdelnabi et al., "Cooperation, competition,
  and maliciousness: LLM-stakeholders interactive negotiation", NeurIPS 2024 Datasets and Benchmarks
  ([PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/984dd3db213db2d1454a163b65b84d08-Paper-Datasets_and_Benchmarks_Track.pdf)).
- Unlike LLM-Deliberation, games start with no deal on the table and have no final-offer round or scratchpad. A party's
  incentive (`cooperative`, `greedy`, ...) only selects its instruction text; in `base`, SportCo, the Department of
  Tourism, and the Environmental League receive the greedy instructions.
- A deal passes the moment the voting rule is met, so parties who have not voted yet never get to. The unanimity bonus
  is therefore only earned when the acceptance that completes the voting rule is also the last one outstanding (for
  example, when a veto holder accepts last), which depends on turn order.
- To add a scenario, create a folder in `games_descriptions/` containing `config.txt` (one
  `name,file,role,incentive,model` line per party; the model column is unused), `global_instructions.txt` (the
  scenario followed by `Issue A: "Name"` sections with `A1 "option": description` lines, separated by `====` lines),
  `scores_files/<file>.txt` (one comma-separated line of option points per issue, then the minimum acceptable score),
  and `individual_instructions/<incentive>/<file>.txt`, where `#A1_NUM` and `#A_MAX_NUM` placeholders are filled in.
