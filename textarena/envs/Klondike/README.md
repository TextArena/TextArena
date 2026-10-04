# Klondike Solitaire

Build all 52 cards onto four foundation piles, Ace to King by suit, by moving cards between seven tableau piles, a
stock, and a waste pile ([rules](https://en.wikipedia.org/wiki/Klondike_%28solitaire%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Klondike-v1` | `max_turns=200`, `draw_count=1` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Klondike-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Klondike-v1", max_turns=...)`.
<!-- END GENERATED: variants -->

## Rules

- Standard deal: seven tableau piles of 1 to 7 cards with only the top card face up, and the other 24 cards face down
  in the stock.
- Foundations `F1`–`F4` build up by suit from Ace to King. Any empty foundation accepts an Ace; piles are not tied to a
  suit in advance.
- Tableau piles `T1`–`T7` build down in alternating colors (red on black, black on red). Only a King, or a run starting
  with a King, may go on an empty tableau pile. A run of face-up cards moves as a unit if it is itself in descending,
  alternating order. An uncovered face-down card turns face up.
- The top card of the waste can go to a tableau pile or a foundation, and the top card of a foundation can move back to
  a tableau pile.
- `draw` turns `draw_count` cards from the stock onto the waste. When the stock is empty, `draw` first turns the whole
  waste back over into the stock, so you can go through the stock any number of times.
- The game ends when all 52 cards are on the foundations, when you forfeit, or after `max_turns` turns.
- Each reply is one turn and may contain several actions separated by commas. They run in order and stop at the first
  one the rules do not allow (for example, a card that does not fit its destination); the actions before it stay done
  and the turn still counts. If the last card reaches a foundation, the game ends at once and any remaining actions are
  ignored.
- A reply with a syntax error anywhere (an unknown command or pile, a bad count, extra words, or `forfeit` combined with
  other actions) is an invalid move: nothing in it is executed and no turn is used. Two invalid moves in a row end the
  game.

## Actions

- `draw` turns cards from the stock onto the waste.
- `move <source> <destination> [count]` moves cards between piles named `W` (waste), `F1`–`F4` (foundations), and
  `T1`–`T7` (tableau). `count` defaults to 1, can only be larger between two tableau piles, and may be `all` to move
  every face-up card of the source pile. Examples: `move W T3`, `move T1 F2`, `move T3 T5 2`, `move T4 T1 all`.
- `forfeit` ends the game and keeps your current score. It must be the only action in the reply.

Actions can be combined, for example `draw, move W T1, move T2 F1`. Commands are case-insensitive.

## Observations

Before every turn you see the board: the turn counter, the number of cards in the stock, the top waste card, every
foundation pile, and the tableau piles with face-down cards shown as `XX`:

```
=== KLONDIKE SOLITAIRE ===
Turn: 0/200

Stock: 24 cards
Waste (W): --

Foundations:
  F1: --
  F2: --
  F3: --
  F4: --

Tableau:
  T1: A♦️
  T2: XX 4♣️
  T3: XX XX A♥️
  ...
```

After each turn you are told what each action did, or why the first failing action failed.

## Rewards

Every outcome scores the number of cards on the foundations divided by 52.

| Outcome | Reward |
| --- | --- |
| All 52 cards on the foundations | `1` |
| Forfeit | Cards on the foundations / 52 (`0` to `51/52`) |
| `max_turns` turns used | Cards on the foundations / 52 |
| Second consecutive invalid move | Cards on the foundations / 52 |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_turns` (default `200`): The number of turns (replies) before the game ends. Accepts an integer of at least 1.
- `draw_count` (default `1`): How many cards `draw` turns over. Only the top waste card is shown and playable. The deal is fixed by the seed passed to `reset`. Accepts one of 1, 3.
<!-- END GENERATED: parameters -->

## Notes

- Not every deal can be won; `forfeit` stops early and keeps the cards already scored.
