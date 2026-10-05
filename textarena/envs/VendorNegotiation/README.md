# Vendor Negotiation

A Brand Specialist and a Vendor negotiate discount rates for several products ahead of a sales event, each with
private forecasts and a private target. It tests multi-issue bargaining under asymmetric information and arguing
with numeric data.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `VendorNegotiation-v1` | `num_products=5`, `max_rounds=20` |

Append `-mdp` to any ID for the state-complete variant (e.g. `VendorNegotiation-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("VendorNegotiation-v1", num_products=...)`.
<!-- END GENERATED: variants -->

## Rules

- Player 0 is the Brand Specialist and Player 1 is the Vendor. At reset, `num_products` products are drawn at random
  from the 10 in `data/product_list.csv`, and both players get the same product order, which proposals must follow.
- Each product can be discounted by 0%, 15%, 20%, or 30%. Deeper discounts sell more units but earn less profit.
- Each side's target lies inside the range of totals the drawn products can actually reach. The low end of a range
  takes each product's worst allowed discount, and the high end takes its best.
  - **Brand objective:** total sales of at least the point `brand_target_fraction` (0.5, the midpoint, by default)
    of the way from the lowest to the highest attainable total sales. The Brand sees prices and sales forecasts, but
    not costs or profits.
  - **Vendor objective:** total profit of at least the point `vendor_target_fraction` (0.5 by default) of the way
    from the lowest to the highest attainable total profit. The Vendor sees prices, unit costs, and profit forecasts,
    and is told never to reveal its costs or profits.
- With the default targets and the bundled data, giving no discount on any product meets only the Vendor's target,
  and the deepest discount on every product meets only the Brand's. With three or more products, using the same
  discount on every product never meets both targets. A deal whose forecasts meet both exists in about half of the
  three-product draws and in nearly every draw with five or more products. It requires trading deep discounts on some
  products for small ones on others, and it usually clears each target by only a few percent of the range.
- Each side also receives negotiation-style instructions, chosen with `brand_role` and `vendor_role`.
- Players alternate messages, starting with the Brand. A message is either pure conversation or conversation followed
  by one decision: propose a full set of discounts, accept the opponent's standing proposal, or reject it. A new
  proposal replaces the standing one, and rejecting clears it. You can only accept or reject the opponent's proposal.
- Every message, including pure conversation, counts as one round. The game ends when a proposal is accepted, or
  with no deal after `max_rounds` rounds. A proposal made in the final round cannot be accepted.
- An accepted deal is scored by Monte Carlo simulation: each product's unit sales are drawn `num_simulations` times
  from a normal distribution with the forecast mean and standard deviation (clipped at zero). Each simulated unit
  earns the forecast's sales and profit per unit, so the expected totals equal the forecasts the players see. Both
  objectives are checked against the average total sales and profit.

## Actions

Any free text is a valid conversational message. To make a decision, end the message with exactly one decision on
its own line. A decision line starts with the command word, matched case-insensitively:

- `Propose X%, Y%, Z%` sets one allowed discount per product, separated by commas, in the product order from your
  prompt. With three products, for example: `Propose 30%, 20%, 15%`. `Propose: 30%, 20%, 15%` also works.
- `Accept` accepts the opponent's standing proposal.
- `Reject` rejects the opponent's standing proposal.

Example:

```
Our traffic doubles during the event, so deeper discounts pay for themselves.
Propose 30%, 30%, 20%
```

A trailing `.` or `!` after a decision is fine. A line counts as a decision only if its first word is exactly the
command. Lines such as `Proposed changes look good`, `Propose that we keep talking`, or `Accept this?` are
conversation, and so are the words "accept" and "reject" inside a sentence. A `Propose` line whose remainder is empty
or starts with a number is a proposal attempt, and it must be well-formed. A message is invalid if it has more than
one decision or any text after the decision. A proposal is invalid if it has the wrong number of discounts, a
discount other than 0/15/20/30, or any other malformed list, such as `Propose 15, 20, 15`. The first invalid message
gets a warning; a second one in a row forfeits the game.

## Observations

Each player first receives their role, their own target with the attainable range it sits in, how they are scored,
their style instructions, the forecast table for every product at every discount level, the product order, the action
format, and the round limit. The forecast table shows units with a 95% interval, plus sales for the Brand or profit for the
Vendor. Neither player is shown the other's target.

Before every move, the acting player sees the round counter (`ROUND 3/20`), the standing proposal, the last three
conversation messages, and the last three decisions. The standing proposal comes with an analysis from the player's
own perspective: expected total sales or profit and the 95% range of the statistic the deal is scored on, which is
the average over `num_simulations` simulated draws. The proposal is labelled `LIKELY MEETS TARGET` when the lower end
of that range reaches the player's target, and `RISKY - MAY MISS TARGET` otherwise. Pure
conversation and each decision are relayed to the opponent. Persuasion text written before a decision reaches them
through the board's recent-conversation section. Invalid messages are never shown to the opponent. At the end, both
players see the simulated units, sales, and profit per product, the totals, and who met their target.

## Rewards

This is a mixed-motive game: each side scores `1` if the final deal meets its own target and `0` otherwise, so a deal
that meets both targets is better for both sides than no deal.

| Outcome | Reward |
| --- | --- |
| Deal meeting both objectives | Both `1` |
| Deal meeting only the Brand's target | Brand `1`, Vendor `0` |
| Deal meeting only the Vendor's target | Vendor `1`, Brand `0` |
| Deal meeting neither objective, or no deal after `max_rounds` rounds | Both `0` |
| Second consecutive invalid move | Offender `0`, opponent `1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `num_products` (default `5`): The number of products to negotiate over, capped at the 10 available. Accepts an integer of at least 1.
- `max_rounds` (default `20`): The number of messages, counting both players, before the game ends without a deal. Accepts an integer of at least 1.
- `brand_target_fraction` (default `0.5`): Where the Brand's target sits between the lowest (`0`) and highest (`1`) total sales the drawn products can reach. Accepts a number from 0 to 1.
- `vendor_target_fraction` (default `0.5`): Where the Vendor's target sits between the lowest (`0`) and highest (`1`) total profit the drawn products can reach. Accepts a number from 0 to 1.
- `num_simulations` (default `1000`): The number of Monte Carlo draws used to score a deal. Accepts an integer of at least 1.
- `brand_role` (default `"default"`): The Brand's style file in `data/roles/brand/`: `default`, `aggressive`, `collaborative`, or `data_driven`. Unknown names fall back to `default`.
- `vendor_role` (default `"default"`): The Vendor's style file in `data/roles/vendor/`: `default`, `profit_focused`, `volume_seeker`, or `relationship_builder`. Unknown names fall back to `default`.
- `product_list_path` (default `"data/product_list.csv"`): An alternative product file in the same format, with one row per product and discount rate. Only the discount rates shared by every product can be proposed, and 0% must be one of them.
<!-- END GENERATED: parameters -->

## Notes

- Profit forecasts come from the `mean_profit` column of the product file and are not derived from the listed price
  and unit cost. For example, the USB cable at 15% shows $3 profit per unit, not $8 × 0.85 − $3 = $3.80. Scoring uses
  the same forecasts, so the Vendor can rely on its table.
- In the bundled data, every product earns its highest profit at 0% and its lowest at 30%, and sells the most at 30%.
  Each product sells the least at 0%, except the luxury watch, which sells slightly less at 15% ($23,800) than at 0%
  ($24,000).
