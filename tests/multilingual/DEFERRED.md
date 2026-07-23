# Games intentionally NOT localized in this PR

Two categories are out of scope for the `self.m(...)` localization pattern used here.
They need design work beyond string externalization and are flagged for a separate track.

## 1. Level-2 — shared-language communication games
Games that relay **player-authored free text** to other players (conversation / negotiation /
message phases). Cross-lingual play isn't meaningful — if two players use different languages
they can't understand each other's messages — so these need *same-language enforcement* plus a
language-mismatch warning. That's a deliberate product change we don't want to bolt onto core
TextArena yet.

Examples: IteratedStagHunt, Negotiation, VendorNegotiation, UsedCarNegotiation, TwoDollar,
NewRecruit, Debate, Diplomacy, SecretMafia, TwoRoomsAndABoom, CharacterConclave,
ScenarioPlanning, ScorableGames, SettlersOfCatan, TruthAndDeception, and (pending per-env vetting)
several auction/bargaining games.

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

Done (Tier 1, all 7 langs ar de en es fr he ms — no zh): **Wordle, Hangman, WordChains, WordLadder**.

Still to do on this track: Codenames, Taboo, GuessWho, DontSayIt (Tier 2, curated per-language
banks); WordSearch, Crosswords, SpellingBee, Anagram, LetterAuction (Tier 3,
generation/letter-frequency).

Still genuinely deferred (content is *generated English sentences/missions*, not word data —
needs per-language generators, out of scope here): LogicPuzzle, BabyAiText.
