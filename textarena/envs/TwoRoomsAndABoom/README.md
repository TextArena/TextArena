# Two Rooms and a Boom

Two hidden teams are split across two rooms whose leaders trade hostages every round; the Red Team wins if its Bomber
ends up in the same room as the Blue Team's President. It tests social deduction, trust building, and deception.

<!-- BEGIN GENERATED: variants -->
**Players:** 6–20

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `TwoRoomsAndABoom-v0` | `num_rounds=3`, `cards_per_room=3`, `discussion_rounds=2` |

Append `-mdp` to any ID for the state-complete variant (e.g. `TwoRoomsAndABoom-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The game needs exactly twice `cards_per_room` players (6 for the registered variant). Half of the players (rounded
  down) are Red and the rest Blue; one Blue player is the President and one Red player is the Bomber. Nobody knows
  anyone else's role.
- Players are split evenly between Room 0 and Room 1, with the President starting in Room 0 and the Bomber in Room 1.
  Each room has a Leader, picked at random and preferably neither the President nor the Bomber. As in the board game,
  leadership is public: everyone in a room is told who its Leader is.
- Every round has three steps:
  1. **Discussion:** every player speaks `discussion_rounds` times, in a random order within each room (Room 0 first).
     Messages only reach players in the same room.
  2. **Hostage selection:** each Leader (Room 0 first) picks one other player from their own room. A Leader can never
     be a hostage, so the Leaders stay the same for the whole game.
  3. **Exchange:** the two hostages swap rooms.
- Instead of sending a discussion message, a player may privately reveal their true role to one player in their room,
  up to 5 times per game.
- After `num_rounds` rounds (the last round also ends with an exchange), Red wins if the President and the Bomber are
  in the same room, and Blue wins otherwise.

## Actions

- **Discussion:** any text, which is sent to everyone in your room, e.g. `I'm Blue. Who will trade reveals with me?`
- **Reveal:** a discussion reply consisting of exactly `reveal` (case-insensitive) starts a reveal instead of being
  sent. Your next reply must name the target: `Player 3` or `3`. Any other reply is sent as discussion, even one that
  mentions revealing or roles, such as `I won't show my role yet`.
- **Leader:** during hostage selection, reply with the hostage's id: `Player 3` or `3`.

Choosing yourself or a player outside your room, replying with anything other than a player id when one is requested,
or sending `reveal` after using all 5 reveals is invalid.

## Observations

Each player first receives their role, team, starting room, who leads their room (or that they do), and the rules. At
the start of every discussion phase, each player is told the round, who is in their room and who its Leader is, which
roles have been revealed to them, and up to ten recent messages they witnessed in that room. Discussion messages arrive
from players in the same room, and the speaker gets a delivery confirmation. When a player reveals, the target
privately learns their true role, and the rest of the room only sees `I am revealing my card to Player X.` Leaders get
a selection prompt with the valid options and the roles revealed to them, and their choice is announced to their room.
Players are not told who leads the other room until they are traded into it. Everyone sees each exchange, and the game
ends by announcing the final rooms and who the President and the Bomber were.

## Rewards

| Outcome | Reward |
| --- | --- |
| President and Bomber in the same room at the end | Red Team `+1`, Blue Team `-1` |
| President and Bomber in different rooms at the end | Blue Team `+1`, Red Team `-1` |
| Second consecutive invalid move | The action is forfeited (the discussion turn passes, a reveal is abandoned, or a Leader's hostage is chosen at random); no elimination or direct penalty |

## Parameters

- `num_rounds` (default `3`): number of rounds, each ending with an exchange.
- `cards_per_room` (default `3`, between 3 and 10): players per room; the game requires exactly twice this many players.
- `discussion_rounds` (default `2`): messages each player sends per round; `0` skips the discussion.

## Notes

- Based on the party game *Two Rooms and a Boom* by Tuesday Knight Games. This version only has the President and the
  Bomber as special roles, and a reveal always shows the full role card.
- Leaders are drawn from regular players whenever possible, and each room starts with exactly one of the President and
  the Bomber, so a player who knows these setup rules can rule out their (public) Leader as a special role.
