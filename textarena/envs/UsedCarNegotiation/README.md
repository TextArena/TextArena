# Used Car Negotiation

A buyer and a seller haggle over the price of a used 2006 Toyota Prius, each with a private background that gives them
a strong or weak alternative to making a deal; the agreed price determines how the surplus is split. It is based on the
classroom exercise by Beenen and Barbuto ([paper](https://doi.org/10.1080/08832323.2013.794121)) and tests bargaining
under symmetric or asymmetric bargaining power.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `UsedCarNegotiation-v0` | `max_rounds=10` |
| `UsedCarNegotiation-v0-balanced` | `max_rounds=10`, `batna=('strong', 'strong')` |
| `UsedCarNegotiation-v0-strong-buyer` | `max_rounds=10`, `batna=('strong', 'weak')` |
| `UsedCarNegotiation-v0-strong-seller` | `max_rounds=10`, `batna=('weak', 'strong')` |

Append `-mdp` to any ID for the state-complete variant (e.g. `UsedCarNegotiation-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- One player is randomly made the buyer and the other the seller; Player 0 always moves first.
- Each role gets a private background with either a strong or a weak alternative to a deal (its BATNA). A strong buyer
  could avoid owning a car altogether, while a weak buyer urgently needs one; a strong seller sees rising demand and
  might keep the car, while a weak seller needs the cash. Both see the same Blue Book price chart.
- On a turn, a player can make an offer, accept or reject the opponent's pending offer, or make a statement. Offers
  must be between $7,000 and $10,000, and a new offer by either player replaces any pending offer.
- Offers and statements pass the turn to the opponent. Rejecting does not, so the rejecting player then has to offer or
  make a statement.
- The game ends when a player accepts the pending offer, or as a no-deal draw after `max_rounds` actions in total.

## Actions

Reply with exactly one command (case-insensitive) and nothing else:

- `Offer: <price>` proposes a price in whole dollars without separators, e.g. `Offer: 8500` or `Offer: $8500`.
- `Accept` accepts the opponent's pending offer.
- `Reject` rejects the opponent's pending offer.
- `Discuss: <message>` makes a statement, e.g. `Discuss: My mechanic found dings and stains, so $10,000 is too high.`

Prices outside $7,000–$10,000 (or written with commas), accepting or rejecting when the opponent has no pending offer,
and replies that are not a single command are invalid.

## Observations

Each player first receives their role-specific background (including their alternative to a deal), the Blue Book
chart, the turn limit, and the commands. After every action, both players see a description such as `The buyer
proposed a price of $8500.`, `The seller rejected the offer.`, or `The seller says: ...`, and the acting player also
gets their raw reply echoed back. The opponent's background and alternative are never shown.

## Rewards

| Outcome | Reward |
| --- | --- |
| Offer accepted at price `p` | Buyer `(10000 - p) / 3000`, seller `(p - 7000) / 3000` (each between `0` and `1`, summing to `1`) |
| `max_rounds` actions without an accepted offer | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `max_rounds` (default `10`): total number of actions by both players (including rejections) before the game ends
  without a deal.
- `batna` (default `None`): the `(buyer, seller)` strength of each role's alternative, each `"strong"` or `"weak"`.
  `None` picks `("strong", "weak")`, `("weak", "strong")`, or `("strong", "strong")` at random.

## Notes

- Reference: G. Beenen and J. E. Barbuto Jr., "Let's make a deal: A dynamic exercise for practicing negotiation
  skills", *Journal of Education for Business* 89(3), 2014.
- The strong and weak backgrounds of a role give the same dollar alternative: the buyer can still buy a comparable
  Prius for $10,000, and the seller can still sell to another buyer for $7,000. A no-deal ending scores `0` for both
  players, which is exactly what those alternatives are worth on the reward scale, so walking away is never better than
  accepting a legal offer. The backgrounds differ only in reasons to walk away (not needing a car, keeping it as a
  second car) or to settle quickly, and those have no dollar value, so BATNA strength changes the narrative but not
  the payoffs.
