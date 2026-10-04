# Secret Mafia

A hidden Mafia team kills off villagers at night while the village, helped by a Doctor and a Detective, tries to vote
every Mafia member out by day ([rules](https://en.wikipedia.org/wiki/Mafia_%28party_game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 6–15

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `SecretMafia-v0` | `mafia_ratio=0.25`, `discussion_rounds=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SecretMafia-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- **Roles:** `round(num_players × mafia_ratio)` players (at least one) are Mafia, one is the Doctor, one the Detective,
  and the rest are Villagers, dealt at random. With the default ratio that is 2 Mafia for 6–10 players, 3 for 11–13,
  and 4 for 14–15. The Mafia know each other; no other role is ever revealed, not even when a player dies.
- **Night** (the game starts here):
  1. Each living Mafia member, in random order, votes for a living non-Mafia victim. The most-voted player is attacked;
     ties are broken at random.
  2. The Doctor, if alive, protects one other living player. Protecting the victim saves them.
  3. The Detective, if alive, investigates one other living player and privately learns whether they are Mafia.
- **Day:** the night's victim (or that nobody died) is announced. Then come `discussion_rounds` rounds of public
  discussion in which every living player speaks once per round, in a random order that stays the same each round.
  Finally every living player votes, in random order, for any living player (themselves included). The player with
  the most votes is eliminated; ties are broken at random.
- **Winning:** the Village (Villagers, Doctor, and Detective) wins once no Mafia member is alive. The Mafia win as soon
  as they make up at least half of the living players. Both are checked after every elimination.

## Actions

| Phase | Who acts | Reply |
| --- | --- | --- |
| Night: Mafia vote | Each living Mafia member | A living non-Mafia player's number, e.g. `4` |
| Night: Doctor | The Doctor | Another living player's number to protect |
| Night: Detective | The Detective | Another living player's number to investigate |
| Day: discussion | Every living player, in turn | Any text, e.g. `Player 2 dodged my question; I'm suspicious.` |
| Day: vote | Every living player | A living player's number |

A number must be the whole reply; `Player 4` and `[4]` also work (case-insensitive). Anything else, a dead player, a
fellow Mafia member at night, or yourself as Doctor or Detective is invalid.

## Observations

Each player first receives their role, team, and description, the list of players, and an overview of the game; the
Mafia also learn who their teammates are. Each night the Mafia, the Doctor, and the Detective are told their valid
targets, and the start of the day discussion and vote is announced to everyone (the vote message lists the valid
targets).

- **Public:** discussion messages, day votes as they are cast, the result of every night, and every elimination.
- **Mafia only:** the Mafia's night votes.
- **Private:** the Doctor's choice (only the Doctor sees it), the Detective's result, and invalid-move warnings.
- **Hidden:** every role except your own (and your teammates', for the Mafia).

## Rewards

| Outcome | Reward |
| --- | --- |
| Every Mafia member eliminated | Village team `+1`, Mafia `-1` (dead players included) |
| Mafia make up at least half of the living players | Mafia `+1`, Village team `-1` (dead players included) |
| Second consecutive invalid move | Offender is eliminated, which can end the game; they still share their team's final reward |

## Parameters

- `mafia_ratio` (default `0.25`): share of players who are Mafia, rounded to the nearest whole number (at least 1).
  It must leave room for the Doctor and Detective and keep the Mafia in the minority, otherwise `reset` raises an
  error.
- `discussion_rounds` (default `3`): discussion rounds before each day vote.

## Notes

- There is no turn limit: every day vote eliminates somebody, so the game always ends.
- Unlike many tabletop variants, tied votes eliminate a random tied player rather than nobody, and the Doctor cannot
  protect themselves.
- Roles are recorded in each player's `game_info` for analysis after the game.
