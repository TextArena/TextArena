# Truth and Deception

The Deceiver knows which of two similar-sounding facts is true and chats with the Guesser, who must then pick the
true one; a correct guess wins for the Guesser and a wrong one for the Deceiver.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `TruthAndDeception-v0` | `max_turns=6` |

Append `-mdp` to any ID for the state-complete variant (e.g. `TruthAndDeception-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("TruthAndDeception-v0", max_turns=...)`.
<!-- END GENERATED: variants -->

## Rules

- Player 0 is the Deceiver and Player 1 the Guesser.
- A pair of facts, one true and one false, is drawn from the bundled set of 260 pairs (or from `data_path`) and shown
  in random order as Fact 1 and Fact 2.
- The players alternate, starting with the Deceiver. The first `max_turns − 1` turns are free conversation, so the
  Deceiver sends `max_turns / 2` messages and the Guesser `max_turns / 2 − 1`.
- On the final turn the Guesser names the fact they believe is true.

## Actions

- **Conversation:** any text. Before the final turn, even `Fact 1` is just a message.
- **Final guess (Guesser):** exactly `Fact 1` or `Fact 2`. Case, surrounding spaces, and Unicode look-alikes such as
  full-width characters are tolerated; a sentence like `I think Fact 1 is true` is invalid.

## Observations

Both players see the two facts and the conversation, and the role names (`Deceiver`, `Guesser`) label every message.
Only the Deceiver's prompt marks which fact is correct. When the Deceiver sends their last message, both players are
told that the Guesser must now guess, and the final message reveals whether the guess was correct.

## Rewards

| Outcome | Reward |
| --- | --- |
| Guesser picks the true fact | Guesser `+1`, Deceiver `-1` |
| Guesser picks the false fact | Deceiver `+1`, Guesser `-1` |
| Second consecutive invalid move (in practice, a malformed final guess) | Offender `-1`, opponent `+1` |

There is no draw.

## Parameters

- `max_turns` (default `6`): turns in the whole game; must be an even number of at least 2 so the Guesser takes the
  final turn.
- `data_path` (default: the bundled `facts.json`): JSON list of entries of the form
  `{"facts": {"fact1": "...", "fact2": "..."}, "correct_fact": "fact1"}` with two distinct facts each.
