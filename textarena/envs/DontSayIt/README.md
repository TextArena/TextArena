# Don't Say It

Two players each hold a secret word and chat freely, each trying to get the other to say their word without ever
saying the opponent's word. It tests conversational steering, subtlety, and inferring a hidden goal from dialogue.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt and the full transcript including every player action

| Env ID | Parameters |
| --- | --- |
| `DontSayIt-v1` | `hardcore=False`, `max_turns=20` |
| `DontSayIt-v1-hardcore` | `hardcore=True`, `max_turns=30` |

Append `-mdp` to any ID for the state-complete variant (e.g. `DontSayIt-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("DontSayIt-v1", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, each player is assigned a different secret word, drawn from the nouns and adjectives of Ogden's Basic
  English (or from every dictionary headword in hardcore mode; see Parameters). Only its owner knows it.
- Players alternate sending messages, starting with Player 0. Every message is visible to both players.
- A player who says the opponent's secret word loses immediately. Saying your own secret word is safe.
- Only whole-word mentions count. Matching ignores case, Unicode width variants, and invisible characters such as
  zero-width spaces: if the opponent's word is `cat`, then `CAT!` and `cat-like` lose, but `cats` and `concatenate`
  do not.
- If nobody slips within `max_turns` messages (counting both players), the game is a draw. With `max_turns=None`,
  the game continues until someone slips.

## Actions

Any free-text message is a valid move; there is no command syntax.

Example: `Have you ever been to a farm? What animals did you see there?`

## Observations

Each player first receives their own secret word, the goal, and the turn limit (or a note that there is none). The
opponent's word is never shown. On each turn, the acting player sees the opponent's latest message.

## Rewards

| Outcome | Reward |
| --- | --- |
| A player says the opponent's secret word | Speaker `-1`, opponent `+1` |
| `max_turns` reached | Both `0` |
| Second consecutive invalid move (only messages over 32,768 characters are invalid) | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_turns` (default `20`): The total number of messages, counting both players, before the game is a draw. `None` means no limit. Accepts an even integer of at least 2 or None.
- `hardcore` (default `False`): Draw secret words from every headword of the bundled dictionaries (about 38,700 base words of 3 or more letters, many of them rare, such as `oakum` or `glyceride`) instead of the Basic English list (750 everyday words, such as `apple`, `bridge`, or `angry`).
<!-- END GENERATED: parameters -->

## Notes

- Both word lists are bundled with TextArena (`textarena/utils/data/`), so the game needs no downloads and a seed
  picks the same secret words on every machine.
- The normal list is Ogden's Basic English (850 words) without its 100 "operations": the verbs, prepositions,
  pronouns, conjunctions, and adverbs such as `the`, `have`, `about`, or `very`, which come up in any conversation.
  That leaves his 600 nouns and 150 adjectives. The hardcore list (`get_headwords()`) holds every base word of 3 or
  more letters in the bundled UK and US dictionaries that takes an affix rule; derived forms, abbreviations, and
  proper nouns are excluded.
