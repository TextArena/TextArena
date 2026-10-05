# Le Truc

Two players play three-card hands of single-card tricks to 12 points, raising the value of each hand ("truc") to
bluff or press an advantage ([rules](https://www.pagat.com/put/truc.html)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LeTruc-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `LeTruc-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The deck has 40 cards: a 52-card deck without the 8s, 9s and 10s. Ranks from highest to lowest are
  3 2 A K Q J 7 6 5 4; suits never matter.
- The match is played in hands, and the first player to reach 12 match points wins. Each hand both players get 3
  cards. Player 1 deals the first hand, so Player 0 (the non-dealer) leads it; the deal alternates every hand.
- **Tricks:** the leader plays a card and the other player answers with any card. The higher rank wins the trick and
  its winner leads the next one. Equal ranks spoil (tie) the trick, and the same player leads again.
- **Winning a hand:** take two tricks, or take the first decided trick when another trick is spoilt (for example
  won–spoilt, spoilt–won, or won–lost–spoilt for the first trick's winner). If all three tricks are spoilt, nobody
  scores. Tricks are only played until the hand is decided; unplayed cards are not shown.
- **Stakes:** a hand is worth 1 point. On your turn, before playing a card, you may raise ("truc"): from 1 to 2, then
  by 2 at a time up to 12. Your opponent must accept (the hand is now worth the new value and the player whose card
  play was interrupted continues), fold (conceding the hand, which scores the value from before that raise for the
  raiser), or raise again (accepting the offer and proposing the next value). Either player may make the first raise of
  a hand; after that, only the player who accepted the most recent raise may make the next one, so nobody can raise
  twice in a row.
- The winner of a hand scores its value. There is no turn limit unless `max_turns` is set; then, if that many actions
  pass before anyone reaches 12, the player with more match points wins and equal points are a draw.

## Actions

Reply with exactly one command (case-insensitive); your legal actions are listed on every turn.

- `play <rank>` plays a card of that rank from your hand, for example `play K`, `play 3` or `play A`.
- `raise` raises the value of the hand.
- `accept` accepts your opponent's raise.
- `fold` refuses your opponent's raise and concedes the hand.

While a raise is pending you must answer it before any card is played. There is no `play 8`, `play 9` or `play 10`.

## Observations

Each player privately receives their three cards at every deal. Before every action the acting player sees the match
points, the hand number with its dealer and leader, the value of the hand, any pending raise or who alone may raise
next, the tricks played so far this hand, the card led to the current trick, their own cards, and their legal actions.
Both players see every card played, every raise, acceptance and fold, and the result of each trick and hand.

## Rewards

| Outcome | Reward |
| --- | --- |
| First to 12 match points | Winner `+1`, loser `-1` |
| `max_turns` reached with different match points | Leader `+1`, other `-1` |
| `max_turns` reached with equal match points | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_turns` (default `None`): If set, the total number of accepted actions (every `play`, `raise`, `accept` and `fold` by either player) after which the match is decided on match points. Accepts an integer of at least 1 or None.
<!-- END GENERATED: parameters -->

## Notes

- Truc is played with different regional rules. This version uses the Catalan card ranking on a French deck, but
  voids a hand whose three tricks are all spoilt as in French Trut (in Catalan Truc the non-dealer wins it). Its stake
  ladder of 1, 2, 4, …, 12 differs from both Catalan Truc (2 and 3 only) and French Truc (raises of any size). As in
  both, only the player who accepted the most recent raise may raise next. The Catalan rule for a side on 11 points is
  not used.
