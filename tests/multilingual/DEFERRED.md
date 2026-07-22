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
Games where the **language itself is the gameplay**, or whose **core content is generated English
text**. Localizing only the UI while the puzzle/content stays English would be misleading — these
belong on a separate per-language-content track (needs per-language word lists / generators).

Examples: Wordle, WordChains, WordLadder, WordSearch, Crosswords, Hangman, SpellingBee,
LetterAuction, Codenames, Taboo, GuessWho, DontSayIt, LogicPuzzle (generated English clue
sentences), BabyAiText (generated English navigation missions).
