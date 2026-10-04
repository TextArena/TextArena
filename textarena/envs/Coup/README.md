# Coup

Players bluff about the court characters they secretly hold to gain coins and knock out rivals' influence; the
last player with influence wins ([rules](https://www.qugs.org/rules/r131357.pdf)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–6

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `Coup-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Coup-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- **Setup:** the Court deck has 15 cards, three each of Duke, Assassin, Captain, Ambassador and Contessa. Each
  player gets 2 face-down influence cards and 2 coins; in a two-player game the starting player (Player 0) gets
  only 1 coin. The Treasury holds the rest of the 50 coins. Player 0 moves first and turns go clockwise.
- **Actions** (one per turn, you may not pass):

  | Action | Effect | Cost | Claims | Can be blocked by |
  | --- | --- | --- | --- | --- |
  | Income | take 1 coin | – | – | – |
  | Foreign aid | take 2 coins | – | – | Duke (any player) |
  | Coup | target loses an influence | 7 | – | – |
  | Tax | take 3 coins | – | Duke | – |
  | Assassinate | target loses an influence | 3 | Assassin | Contessa (target) |
  | Steal | take up to 2 coins from the target | – | Captain | Captain or Ambassador (target) |
  | Exchange | draw 2 Court cards, keep as many cards as your influence, return the rest | – | Ambassador | – |

- **Forced coup:** a player who starts their turn with 10 or more coins must coup.
- **Claims and blocks:** you may claim any character, whether or not you hold it. After a claimed action, the
  other players are asked one at a time (the target first) to `bullshit`, block where allowed, or `pass`. After
  a block, the acting player is asked first whether to challenge it, then the others. A block nobody challenges
  cancels the action; a blocked action's cost stays spent.
- **Challenges:** a challenged player shows the claimed card if they hold it, shuffles it into the Court deck and
  draws a replacement, and the challenger loses an influence. If they don't hold it, they lose an influence and
  their action fails entirely: **coins paid for it are returned** (the 3 coins of a bluffed assassination). A
  target who loses a challenge against a targeted action can still block it afterwards.
- **Losing influence:** the player losing an influence always chooses which hidden card to flip face up. A player
  with one hidden card loses it automatically. One action can cost several influences (e.g. a target who bluffs a
  Contessa block against a real assassin loses both cards).
- **Exile:** a player with no hidden cards is out and returns their coins to the Treasury. If they are the target
  of a steal that still succeeds (e.g. a caught bluffing blocker), the steal is paid from their coins first and
  only the remainder goes back.
- **Game end:** the last player with influence wins.

## Actions

Reply with exactly one bare command (case-insensitive). Replace `X` with a player number.

| When | Commands |
| --- | --- |
| Your turn | `income`, `foreign aid`, `tax`, `exchange`, `coup X`, `assassinate X`, `steal X` |
| Asked about an action | `pass`, `bullshit` (not for foreign aid), `block foreign aid`, and if you are the target `block assassinate`, `block steal captain`, `block steal ambassador` |
| Asked about a block | `pass`, `bullshit` |
| After your exchange | `keep <card> <card>` (or `keep <card>` with one influence left) |
| Losing an influence | `reveal <card>` |

Examples: `steal 2`, `block steal ambassador`, `bullshit`, `keep duke contessa`, `reveal captain`.

## Observations

Each player first receives the rules, the command list and a summary of the table. Before every response, the
acting player sees the summary again plus what is being asked of them (for example "Player #0 is attempting to
assassinate (they have paid 3 coins) on you (claiming Assassin)").

- **Public:** every player's coin count, number of hidden cards and revealed (lost) cards, who is out, every
  action, block, challenge and its result, and other players' `pass`/`bullshit`/action commands.
- **Private:** your own hidden cards, the replacement card you draw after proving a claim, and the cards you
  draw and keep during an exchange. Your `keep` and `reveal` commands and invalid-move warnings are shown only
  to you.
- **Hidden:** other players' hidden cards (until revealed) and the order of the Court deck.

## Rewards

| Outcome | Reward |
| --- | --- |
| Last player with influence | Winner `+1`, every other player `-1` |
| Fourth consecutive invalid move | Offender is out and ends with `-1` |

There is no turn limit and no draw. The first three consecutive invalid moves only earn a private warning and a
retry. On the fourth, the offender reveals all their cards and is out: their coins return to the Treasury and
any action they were the source or target of is cancelled. If that leaves one player, the game ends and that
player wins.

## Notes

- Rulebook: [Coup (Indie Boards & Cards)](https://www.qugs.org/rules/r131357.pdf); handy
  [cheat sheet](https://hexagamers.com/wp-content/uploads/2016/04/Coup-Cheat-Sheet.jpg) and
  [video](https://www.youtube.com/watch?v=xUNWl5fWfEY).
- Unlike the tabletop game, responses are collected in a fixed order instead of whenever someone speaks up.
  For targeted actions the target goes first.
- The optional two-player draft variant from the rulebook is not implemented.
