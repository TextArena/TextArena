# Multi-Armed Bandit

Press buttons that pay out 1 or 0 with hidden probabilities for a fixed number of turns, then name the button with the
highest payout probability ([best-arm identification](https://en.wikipedia.org/wiki/Multi-armed_bandit)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Bandit-v0` | `buttons=['red', 'blue', 'green', 'yellow', 'purple']`, `p_gap=0.1`, `num_turns=20` |
| `Bandit-v0-hard` | `buttons=['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'p...`, `p_gap=0.05`, `num_turns=40` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Bandit-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Bandit-v0", buttons=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, one button is chosen at random as the best button, with a mean reward of `0.5 + p_gap / 2`. Every other
  button gets a mean drawn uniformly between `0.1` and `0.5 - p_gap / 2`, so the best button leads every other button
  by at least `p_gap`. The means stay fixed for the whole game and are never shown.
- For the first `num_turns` turns, you press one button per turn and receive a reward of `1.0` with probability equal
  to that button's mean, and `0.0` otherwise.
- After the last press, the game announces that the budget is used up. Your next reply is your final answer, the button
  you believe has the highest mean, and it ends the game.
- Only the final answer is scored; the rewards collected while exploring do not count.
- A reply that does not name a button is rejected without using a turn. Two rejected replies in a row end the game.

## Actions

Reply with the name of one button, for example `red`. Names are matched case-insensitively (`Red` and `RED` also press
`red`) unless two buttons differ only in case. The final answer uses the same format.

## Observations

The prompt lists the buttons, the number of presses, and how the final answer is scored. After each press you see the
outcome, for example `You pressed the red button and received a reward of 1.0.`; with `include_summary=True` you also
see every button's average reward and press count so far. A rejected reply is answered with the reason; an unknown
name also gets the list of valid buttons.

## Rewards

| Outcome | Reward |
| --- | --- |
| Final answer is the best button | `+1` |
| Final answer is another button | Minus the gap between the best mean and the chosen button's mean, from `-p_gap` down to `-(0.4 + p_gap / 2)` |
| Second consecutive rejected reply | `-1` |

The final answer always ends the game, so there is no separate turn-limit outcome.

## Parameters

- `buttons` (default `red`, `blue`, `green`, `yellow`, `purple`): the button names. They must be unique, non-empty, at
  most 128 characters long, and free of square brackets, line breaks, and leading or trailing spaces.
- `p_gap` (default `0.2`, from `0` to `0.8`): the minimum lead of the best button's mean over every other button.
  Smaller gaps make the best button harder to identify.
- `num_turns` (default `20`): the number of presses before the final answer. With `0`, your first reply is the final
  answer.
- `include_summary` (default `False`): show the per-button averages after every press.
