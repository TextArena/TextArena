# Games intentionally NOT localized in this PR

Two categories are out of scope for the `self.m(...)` localization pattern used here.
They need design work beyond string externalization and are flagged for a separate track.

## 1. Level-2 — shared-language communication games
Games that relay **player-authored free text** to other players (conversation / negotiation /
message phases). Cross-lingual play isn't meaningful — if two players use different languages
they can't understand each other's messages — so these need *same-language enforcement* plus a
language-mismatch warning. That's a deliberate product change we don't want to bolt onto core
TextArena yet.

All remaining unlocalized games were vetted per-env (looking at whether raw player text is relayed
between players, e.g. a "conversation phase" or `{message}` action). Confirmed Level-2:
IteratedStagHunt, Negotiation, VendorNegotiation, UsedCarNegotiation, TwoDollar, NewRecruit,
Debate, Diplomacy, SecretMafia, TwoRoomsAndABoom, CharacterConclave, ScenarioPlanning,
ScorableGames, SettlersOfCatan, TruthAndDeception, and the auction/economic games
**BlindAuction, SimpleBlindAuction, PublicGoodsGame, MarketEntryGame, WinAsMuchAsYouCan** (each has
an explicit free-text communication phase alongside its structured bids/decisions).

> `ImTheBoss` is an empty stub (`env.py` is 0 bytes) — not implemented, nothing to localize.

> Note: `SimpleNegotiation`, `IteratedPrisonersDilemma`, and `ThreePlayerIPD` were already
> localized on this branch before this policy was set; they are Level-2 by this definition but
> were left as-is (pre-existing).

## 2. Language-core games
Games where the **language itself is the gameplay**. Localizing only the UI while the puzzle
content stayed English would be misleading — these need per-language *word data*, not just string
translation. They are now being localized on the **word-games track** using the optional
`wordfreq` backend for word validity/sampling (see `textarena/envs/utils/word_lists.py`;
`pip install textarena[wordgames]`). Word games are **single-content-language per episode** (the
secret/target word is in one language; per-player UI language still varies). Per-letter games
(Wordle, Hangman, SpellingBee) exclude logographic **zh** — declared per game via
`locales/_supported_langs.json`.

Done (all 7 langs ar de en es fr he ms — no zh, since these are per-letter games): **Wordle,
Hangman, WordChains, WordLadder, SpellingBee, LetterAuction, WordSearch**. Per-language alphabets
and letter frequencies for SpellingBee/LetterAuction/WordSearch are derived from each language's
own wordfreq pool (`WordFreqDictionary.alphabet()` / `.letter_frequencies()`), so no extra
letter-frequency resource is bundled.

The remaining word games are NOT localized here, for principled reasons:
- **Codenames, Taboo, DontSayIt** — Level-2 communication games (clues / descriptions / free chat
  are player-authored and relayed between players). Belong on the Level-2 track (section 1).
- **GuessWho** — the player asks free-text yes/no questions that a gamemaster must *understand*;
  needs natural-language comprehension in the target language, not just word data.
- **Crosswords** — its content is English clue *sentences* (definitions like "Acquiring knowledge
  or skills…"); localizing needs per-language clue generation (no permissive resource).
- **LogicPuzzle, BabyAiText** — content is generated English sentences / navigation missions.

Still genuinely deferred (content is *generated English sentences/missions*, not word data —
needs per-language generators, out of scope here): LogicPuzzle, BabyAiText.
