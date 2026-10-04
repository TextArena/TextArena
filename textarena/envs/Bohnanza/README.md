# Bohnanza

Players plant, trade, and harvest beans for coins without ever rearranging their hand, so trading away
awkward beans with the active player is the heart of the game ([rules](https://www.riograndegames.com/wp-content/uploads/2013/02/Bohnanza-Rules.pdf)).

<!-- BEGIN GENERATED: variants -->
**Players:** 3–5

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `Bohnanza-v0` | `deck_cycles=3`, `max_trade_rounds=None`, `max_turns=3000` |
| `Bohnanza-v0-short` | `deck_cycles=1`, `max_trade_rounds=3`, `max_turns=1000` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Bohnanza-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- **Cards:** 104 bean cards of 8 types. Everyone starts with 5 cards; the hand order is fixed (plant from
  the front, new cards go to the back). With 3 players each has 3 fields, with 4–5 players 2 fields. A field
  holds any number of beans of a single kind.
- **Turn** (Player 0 starts, then seat order):
  1. **Plant:** the active player must plant the front card of their hand and may plant the next one too
     (at most two). Skipped if the hand is empty.
  2. **Turn over and trade:** two cards are turned face up; they belong to the active player. Only trades
     with the active player are allowed, using hand cards from any position (plus the face-up cards for the
     active player). Any number of beans for any number, or a gift; the receiver must accept. Received beans
     are set aside and cannot be traded again. The floor passes around the table until the active player
     ends trading.
  3. **Plant traded beans:** everyone plants their set-aside beans, the active player also the face-up cards
     they kept, in any order (active player first, then clockwise).
  4. **Draw:** the active player automatically draws three cards.
- **Harvesting:** a whole field, whenever you have the move. Bean protection rule: a single-bean field cannot
  be harvested while another of your fields holds two or more beans. As many cards as the beanometer pays
  become coins and leave the game; the rest are discarded.

| Bean | Cards | Beans for 1 / 2 / 3 / 4 coins |
| --- | :-: | --- |
| Blue | 20 | 4 / 6 / 8 / 10 |
| Chili | 18 | 3 / 6 / 8 / 9 |
| Stink | 16 | 3 / 5 / 7 / 8 |
| Green | 14 | 3 / 5 / 6 / 7 |
| Soy | 12 | 2 / 4 / 6 / 7 |
| BlackEyed | 10 | 2 / 4 / 5 / 6 |
| Red | 8 | 2 / 3 / 4 / 5 |
| Garden | 6 | – / 2 / 3 / – |

- **Game end:** when the last card of the draw pile is drawn, the discard pile is reshuffled into a new pile.
  The game ends when the pile runs out for the `deck_cycles`-th time (3 officially). If that happens while
  turning cards over, the turn still finishes phases 2 and 3; during phase 4 it ends at once. All fields are
  then harvested; cards in hand are worth nothing.

## Actions

Submit exactly one bare command (case-insensitive).

- **Any phase, when you have the move:** `harvest <field>` (e.g. `harvest 2`; does not use up your move).
- **Phase 1:** `plant <field>` plants the front card (e.g. `plant 1`); `pass` stops after one card.
- **Phase 2 (trading):**
  - `trade <offer> for <want>`, e.g. `trade 2 Chili for 1 Blue`, `trade Soy for nothing` (gift),
    `trade nothing for Red` (ask for a gift). The active player's offers are open to everyone unless
    addressed with `with Player N` (`trade 1 Soy for 1 Red with Player 2`); other players' offers always go
    to the active player.
  - `accept <id>` (e.g. `accept 4`), `cancel <id>` to withdraw your own offer, `pass` to give the floor on.
  - `end trading` (active player only).
  - Any other text is table talk shown to all players; text starting with a command word that doesn't parse
    is rejected.
- **Phase 3:** `plant <bean> <field>` (e.g. `plant Blue 2`); `plant <field>` works if all your set-aside
  beans are the same kind.

Bean lists look like `2 Blue, 1 Red`, `Blue and Soy` or `nothing`; names accept plurals and `black-eyed`.

## Observations

Each player first receives the rules, beanometers and action list. Before every move, the acting player sees
the public table (fields, coins, hand sizes, face-up cards, open offers, set-aside beans, pile sizes, deck
cycles) plus their own private hand front to back, and a list of currently legal moves. Every valid move is
announced to all; raw actions are echoed only to their author, and invalid attempts are reported only to the
player who made them. Cards drawn in phase 4 are told only to the drawing player.

## Rewards

| Outcome | Reward |
| --- | --- |
| Game end (deck cycles done) | Most coins `+1`, everyone else `-1`; ties go to the tied player furthest clockwise from Player 0 |
| Turn limit (`max_turns`) reached | Fields harvested and scored the same way |
| Too many consecutive invalid moves | Offender `-1`, everyone else `0` (game ends) |

## Parameters

- `deck_cycles` (default `3`): the game ends when the draw pile runs out this many times.
- `max_trade_rounds` (default `None`): if set, trading ends automatically after the floor has gone around the
  table this many times; `None` lets the active player decide, as in the official rules.
- `max_turns` (default `3000`): step budget before the game is scored early. A full game takes about 200
  steps without trading and up to about 1,500 with lively trading.
- `error_allowance` (default `3`): consecutive invalid moves allowed before the offender forfeits.

## Notes

- Originally contributed upstream by cstorm125 (TextArena PR #150), with later fixes by leshem; ported to
  the `GameEnv` engine here.
- Compared with the upstream version: coin cards now leave the game, the deck reshuffles on its last card
  and the game ends on the third run-out, an empty hand skips phase 1, the active player trades face-up
  cards before matching hand cards, and drawing in phase 4 is automatic.
- Harvesting "at any time, even off-turn" is approximated as "whenever you have the move".
- When trading, the front-most copy of a duplicate hand bean is given; you cannot choose another copy, and
  the active player cannot give a hand card instead of a matching face-up card.
- House rule: if both the draw and discard piles are empty when a card is needed, the draw pile counts as
  having run out, so the game cannot stall.
- The default variant keeps trading unlimited (official rules), so a stubborn active player can use up the
  step budget; set `max_trade_rounds` to cap it.
