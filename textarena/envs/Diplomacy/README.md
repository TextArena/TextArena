# Diplomacy

Players command great powers of pre-WWI Europe, negotiate in public and in private, and then issue simultaneous
military orders; the first power to control 18 of the 34 supply centers wins
([rules](https://en.wikipedia.org/wiki/Diplomacy_%28game%29)). It tests negotiation, alliance management, deception,
and multi-unit tactical planning.

<!-- BEGIN GENERATED: variants -->
**Players:** 3–7

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `Diplomacy-v1` | `max_game_years=30` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Diplomacy-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Diplomacy-v1", max_game_years=...)`.
<!-- END GENERATED: variants -->

## Rules

- Each player is randomly assigned one of the seven powers (Austria, England, France, Germany, Italy, Russia, Turkey)
  with its standard starting units and home centers on the standard 75-province map. Powers that are not in play are
  removed from the board, leaving their home centers unowned.
- Play starts in Spring 1901. Every game year has five phases, all of which are always played: Spring Movement, Spring
  Retreats, Fall Movement, Fall Retreats, and Winter Adjustments.
- Each phase consists of `negotiations_per_phase` rounds in which every active player takes one turn, in player order.
  Orders are accepted only in the final round of a phase, where every player must submit them; once all have, the
  orders resolve simultaneously.
- Movement follows the standard rules: every unit has strength 1, each valid support adds 1, equal strengths bounce,
  an attack cuts a support unless it comes from the province the support is aimed at, and a power cannot dislodge its
  own unit. Units without orders hold.
- A dislodged unit retreats to an empty adjacent province that its attacker did not come from and that was not left
  empty by a bounce, or is disbanded. Units retreating to the same province, and dislodged units without an order, are
  disbanded.
- Supply-center ownership is updated at the end of each Fall, after the Fall Retreats phase: every occupied center
  passes to the occupying power, so a unit that retreats into a center in the Fall captures it. In Winter, each power
  builds units in vacant home centers it still owns, or disbands units, until its unit count matches its center count.
  Unordered builds are waived; if a power orders too few disbands, the units farthest from its home centers are
  disbanded automatically.
- A power with no units and no centers is eliminated. The game ends when a power controls 18 or more supply centers
  (checked after every phase), when only one power remains, or after `max_game_years` complete game years.

## Actions

A reply may combine several commands, each starting on its own line. A command runs until the next line that starts a
command, so messages may span several lines.

- `Broadcast: <message>` sends a message to every player.
- `Whisper to <player id>: <message>` sends a private message, e.g. `Whisper to 2: Shall we split the Balkans?`. The
  recipient can also be named by power (`Whisper to FRANCE: ...`). Adding the power after an id, as in
  `Whisper to 3 (ITALY): ...`, makes the whisper invalid if Player 3 is not Italy.
- `Submit Orders:` followed by one order per line submits your orders. It is required in the final round of each phase;
  an empty section is valid, and lines starting with `#` are skipped. In earlier rounds the section is not recorded:
  the reply still counts (its messages are sent) and the player is told privately that the orders were not recorded.

| Order | Phase | Example |
| --- | --- | --- |
| Hold | Movement | `A PAR H` |
| Move (optionally `VIA` convoy) | Movement | `A PAR - BUR`, `A LON - BEL VIA` |
| Support a hold or a move | Movement | `A MAR S A PAR`, `A MAR S A PAR - BUR` |
| Convoy | Movement | `F NTH C A LON - BEL` |
| Retreat | Retreats | `A PAR R BUR` |
| Disband | Retreats, Adjustments | `A PAR D` |
| Build | Adjustments | `A PAR B`, `F STP(NC) B` |
| Waive a build | Adjustments | `WAIVE` |

Units are `A` (army) or `F` (fleet), provinces use three-letter codes, and the split coasts of SPA, STP, and BUL are
written `STP(NC)` or `STP/NC`; a fleet moving to a split-coast province must name the coast. A reply is invalid if a
line starting with `Broadcast` or `Whisper` cannot be read as that command (for example `Whisper to 2 hello`, which
lacks the colon), or if it whispers to yourself, to an unknown or eliminated player, or with an empty message. In the
final round it is also invalid if it has no order section or more than one, contains an order that is illegal in the
current position or phase (for example a hold during Retreats, or two orders for one unit), or orders more builds
(including `WAIVE`) or disbands than the power is allowed. An invalid reply is rejected as a whole, so none of its
messages are sent, and the rejection names the offending order or line. A reply with no command at all is accepted in
negotiation rounds, and the player is told that nothing was sent.

## Observations

Each player first receives the rules, the list of players and their powers, the order and message syntax, and
strategy advice for their power. Before every turn the acting player privately receives a board summary with:

- the season, year, phase, game year, negotiation round, and turn order;
- every power's supply centers with counts, and the unowned centers;
- every unit by power and location, with each dislodged unit's retreat options;
- their own legal orders: during Movement, each unit's moves, moves by convoy, supports, and convoys; during Retreats,
  each dislodged unit's retreats; during Adjustments, the allowed builds or required disbands;
- what is expected now: messages only, or (in the final round) the orders that are due and what happens to units
  without orders.

Broadcasts reach every player as `(to all) <message>`; a whisper reaches only its recipient, as
`(privately to you) <message>`, and both appear under the sender's power name. A player's full reply is echoed only to
them, and accepted orders are confirmed privately, so no one sees another player's orders before they resolve. The
game announces each new phase and negotiation round. After every adjudication, all players receive the same results
summary: every power's orders and units without orders, each with its outcome (moved, bounced, failed for lack of a
convoy, held, support given, cut, or void, convoyed, dislodged, retreated, disbanded, built, or waived), the dislodged
units with their retreat options, and, after Fall Retreats, the supply centers that changed hands and the new center
counts. The game ends with an announcement of every power's final center count.

## Rewards

| Outcome | Reward |
| --- | --- |
| A power controls 18 or more supply centers | Winner `+1`, everyone else `-1` |
| Only one power remains | Survivor `+1`, everyone else `-1` |
| `max_game_years` game years completed without a winner | Everyone `0` |
| Second consecutive invalid move | Offender is eliminated: they stop acting and their units hold in place, but they still receive the final result (`-1` if anyone wins, `0` in a draw) |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_game_years` (default `30`): The number of complete game years before the game ends in a draw. Accepts an integer of at least 1.
- `negotiations_per_phase` (default `3`): The turns each player takes per phase. Orders are due in the last one. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- The per-power strategy texts are adapted from [AI_Diplomacy](https://github.com/Alx-AI/AI_Diplomacy).
- Games are long: every phase, including Retreats and Adjustments with nothing to order, takes
  `negotiations_per_phase` full rounds, so one game year is 15 turns per player by default.
- A fleet moving to a split-coast province must name the coast even when only one coast is reachable
  (`F GAS - SPA(NC)`, not `F GAS - SPA`); the board summary lists moves in that form.
