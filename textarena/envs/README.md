# TextArena Environments

Every game lives in its own folder under `textarena/envs/<Game>/`: the environment (`env.py`), its registered
ids (`__init__.py`), its tests (`test_env.py`), and a `README.md` with the rules, action format, rewards,
registered variants, and parameters. Translations live in the separate `textarena-locales` package
(`locales/textarena_locales/envs/<Game>.json`). This page explains the conventions shared by all games and lists
them; follow a game's link for details.

## Playing a game

```python
import textarena as ta

agents = {
    0: ta.agents.OpenRouterAgent(model_name="openai/gpt-5-mini"),
    1: ta.agents.OpenRouterAgent(model_name="qwen/qwen3.8-27b"),
}

env = ta.make(env_id="TicTacToe-v1")
env.reset(num_players=len(agents), seed=42)

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done = env.step(action=action)

rewards, game_info = env.close()
```

`get_observation()` returns the id of the player who must act next and the text they should see, `step()` returns
whether the game is over, and `close()` returns the reward per player and per-player game info (role, final
reason, turn count, whether the game ended because of their invalid moves).

## Actions

Environments take **bare actions** such as `4`, `roll`, `e2e4`, or `bid 3 5s` — no square brackets. Models
are prompted to reason freely and put their final move inside `<action>...</action>` tags; the built-in
agents call `ta.extract_action`, so only the tag contents reach `env.step`. Custom agents should do the same:

```python
action = ta.extract_action(model_response)  # "...so the center is best. <action>4</action>" -> "4"
```

Each game's README lists its exact commands. Matching is case-insensitive unless the README says otherwise.
Surrounding whitespace and one pair of enclosing square brackets are ignored, so `[e2e4]` is read as `e2e4`.

## Two views of every configuration

| ID | What the acting player sees | Wrapper |
| --- | --- | --- |
| `Game-v1` | Only the messages produced since their previous turn; the agent keeps the history | `CurrentTurnObservationWrapper` |
| `Game-v1-mdp` | Everything needed to act in one observation, so each step is an MDP step | `MDPObservationWrapper` |

The `-mdp` observation holds the prompt, every game message so far, and the latest board. In conversation games
the dialogue is part of the state, so it also includes every player message; board games set
`mdp_includes_actions = False` because their board and game messages already capture the state, and each game's
README states which applies. Named configurations put `-mdp` last: `Chess-v1-blind-mdp`.

Only a few configurations are registered per game. Any other is one keyword away, since `ta.make` passes extra
arguments to the environment: `ta.make("Chess-v1", max_turns=250)`. Each game's README lists its parameters and
the values they accept; anything else raises an error when the environment is made.

The `-v1` in every id is the game's version. When a game's rules change, its version goes up and the old id is
retired (`ta.make` names the replacement), so results are only comparable within one version.

## Rules shared by every game

- **Hidden information** is only ever sent to the players allowed to see it.
- **Invalid moves** are never applied. The player is told why and may try again once; a second invalid move in a
  row escalates, the same in every game. By default the offender is then eliminated: in a two-player game they
  lose (`-1`, opponent `+1`), in a multi-player game play continues without them, and a single-player game ends
  with `0`. Some games escalate differently (a forfeited turn, a default vote, or the progress made so far); their
  README says so.
- **Rewards** follow one scale per kind of game, and each README has the exact table:
  - competitive games: `+1` win, `-1` loss, `0` draw (multi-player rankings spread between `-1` and `+1`);
  - single-player games: a score from `0` (nothing achieved) to `1` (solved);
  - cooperative and mixed-motive games (Hanabi, PublicGoodsGame, VendorNegotiation, UsedCarNegotiation): each
    player's own score from `0` to `1`.
- **Turn limits** (`max_turns`) end the game as a draw unless the game defines another result, such as
  comparing scores.
- **Player counts**: `env.reset` raises `ValueError` for a player count the game does not support (each
  README lists the allowed counts). Games with a fixed or configured default count can be reset without
  `num_players`.
- **Seeding and replays**: `env.reset(num_players, seed=...)` seeds a private random generator (a random seed is
  drawn when none is given), so the same seed and the same actions always replay the same game. `env.record()`
  captures the parameters, seed, and actions, and `ta.replay(record)` rebuilds the game from it. Environments
  never touch Python's global random state.
- **External models**: Debate, ScenarioPlanning (LLM juries), GuessWho, and TwentyQuestions (LLM game
  masters) call `qwen/qwen3.8-27b` through OpenRouter and need `OPENROUTER_API_KEY` and
  `pip install "textarena[agents]"`. The model is part of these games' rules, so changing it is a version bump.
  If the service fails, the action is not counted and the player is asked to retry, up to five times in a row;
  the sixth failure makes `env.step` raise a `RuntimeError` instead of letting the episode stall. Each failure is
  logged as a warning with its cause (such as a juror's invalid answer), which the player never sees. Records keep
  the models' answers, so replays never call them again.
- **Snapshots**: `env.snapshot()` and `env.restore(snapshot)` capture and restore the complete state,
  including hidden cards and answers, for search and replay. Never show a snapshot to a player.

## Adding a game

1. Create `textarena/envs/<Game>/env.py` with a `ta.GameEnv` subclass. Set `min_players`/`max_players`,
   declare each setting as a `ta.Param` (the engine validates it and the docs list it), and implement `setup`
   (initial state), `prompt` (per-player instructions), and `apply` (validate and apply one bare action), plus
   optionally `render`, `roles`, `on_turn_limit`, `on_invalid_limit`, and `check_num_players` (player-count rules
   beyond the range, such as even teams). Use `self.rng` for all randomness, call outside services through
   `self.ask`, and set `mdp_includes_actions = False` if the board and game messages capture the whole state.
   Games never override `reset` or `step`:

   ```python
   class MyGameEnv(ta.GameEnv):
       min_players = max_players = 2
       max_turns = ta.Param(50, "The number of moves before the game ends in a draw.", min=1)
   ```

2. Register its ids in `textarena/envs/<Game>/__init__.py`; every game folder is picked up automatically:

   ```python
   from textarena.envs.registration import register

   register(id="MyGame-v1", entry_point="textarena.envs.MyGame.env:MyGameEnv", max_turns=50)
   ```

3. Add `test_env.py` with tests of the game's rules. `tests/test_conformance.py` already checks every registered
   game for termination, reward shape, determinism, observation routing, rejected moves leaving the game
   unchanged, snapshots, replays, and long inputs, so game tests need not repeat those.
4. Write `README.md` from an existing game's README, keeping the empty generated blocks, then run
   `python scripts/generate_env_docs.py` to fill in the variants and parameters and update this catalog.

## Catalog

<!-- BEGIN GENERATED: catalog -->
**108 games, 141 registered configurations.**

### Single-player (30)

| Game | Players | Description | Env IDs |
| --- | :---: | --- | --- |
| [Multi-Armed Bandit](Bandit/README.md) | 1 | Press buttons that pay out 1 or 0 with hidden probabilities for a fixed number of turns, then name the button with the highest payout probability. | `Bandit-v1`, `Bandit-v1-hard` |
| [Blackjack](Blackjack/README.md) | 1 | Play a series of Blackjack hands against a dealer, hitting or standing to finish closer to 21 than the dealer without going over. | `Blackjack-v1` |
| [Countdown](Countdown/README.md) | 1 | Combine a handful of numbers with addition, subtraction, multiplication, and exact division to make a target, as in the numbers round of the British game show Countdown. | `Countdown-v1` |
| [Crosswords](Crosswords/README.md) | 1 | Fill in a small crossword grid one letter at a time, using clues that give each word's starting cell and direction. | `Crosswords-v1`, `Crosswords-v1-hardcore` |
| [Cryptarithm](Cryptarithm/README.md) | 1 | Solve an alphametic such as SEND + MORE = MONEY by giving each letter a different digit so that the sum is correct. | `Cryptarithm-v1` |
| [Fifteen Puzzle](FifteenPuzzle/README.md) | 1 | Slide numbered tiles around a 4×4 board until they read 1 to 15 in order with the gap in the bottom-right corner. | `FifteenPuzzle-v1` |
| [Frozen Lake](FrozenLake/README.md) | 1 | Walk from one corner of a frozen grid to the goal in the opposite corner without falling into a hole. | `FrozenLake-v1`, `FrozenLake-v1-hardcore`, `FrozenLake-v1-random` |
| [2048](Game2048/README.md) | 1 | Slide and merge numbered tiles on a square board to build a target tile, such as 2048. | `2048-v1`, `2048-v1-3x3`, `2048-v1-easy` |
| [Guess The Number](GuessTheNumber/README.md) | 1 | Find a hidden integer within a limited number of guesses, using the higher-or-lower hint given after every wrong guess. | `GuessTheNumber-v1`, `GuessTheNumber-v1-hardcore` |
| [Guess Who](GuessWho/README.md) | 1 | Identify a secret character from a lineup of 24 by asking an LLM game master yes-or-no questions, then name them with a single guess before the question budget runs out. | `GuessWho-v1` |
| [Hangman](Hangman/README.md) | 1 | Reveal a hidden English word by guessing one letter at a time, or the whole word, before six wrong guesses run out. | `Hangman-v1`, `Hangman-v1-hardcore` |
| [Klondike Solitaire](Klondike/README.md) | 1 | Build all 52 cards onto four foundation piles, Ace to King by suit, by moving cards between seven tableau piles, a stock, and a waste pile. | `Klondike-v1` |
| [Lights Out](LightsOut/README.md) | 1 | Turn off every light on a square grid, where pressing a light toggles it and its four orthogonal neighbors. | `LightsOut-v1` |
| [Logic Puzzle](LogicPuzzle/README.md) | 1 | Work out which person goes with which item in each of two other categories by marking grids with O and X from a short list of clues. | `LogicPuzzle-v1`, `LogicPuzzle-v1-hard` |
| [Mastermind](Mastermind/README.md) | 1 | Crack a hidden code of numbers by guessing and reading black-and-white peg feedback after each guess. | `Mastermind-v1`, `Mastermind-v1-hard` |
| [Minesweeper](Minesweeper/README.md) | 1 | Reveal every safe cell of a hidden minefield, using the count of neighboring mines shown on each revealed cell to work out where the mines are. | `Minesweeper-v1`, `Minesweeper-v1-hard` |
| [Peg Jump](PegJump/README.md) | 1 | Jump pegs over one another on a 15-hole triangular board until only one peg is left. | `PegJump-v1` |
| [Rush Hour](RushHour/README.md) | 1 | Slide cars and trucks around a 6×6 parking lot to clear a path for the red car `X` and drive it out of the exit on the right. | `RushHour-v1` |
| [Secretary](Secretary/README.md) | 1 | See hidden values one at a time and decide on the spot whether to accept each one, winning only if you accept the largest of them all. | `Secretary-v1` |
| [Set](Set/README.md) | 1 | Find as many Sets as you can in 20 turns, where a Set is three cards whose four attributes are each all the same or all different. | `Set-v1` |
| [Slitherlink](Slitherlink/README.md) | 1 | Draw a single closed loop along the edges of a dot grid so that every numbered cell has exactly that many of its sides on the loop. | `Slitherlink-v1` |
| [Sokoban](Sokoban/README.md) | 1 | Push every box onto a goal in a randomly generated warehouse, walking one square at a time and never pulling a box. | `Sokoban-v1`, `Sokoban-v1-medium` |
| [Sudoku](Sudoku/README.md) | 1 | Fill a 9×9 grid so that every row, column, and 3×3 box contains each digit from 1 to 9 exactly once, one cell per turn. | `Sudoku-v1`, `Sudoku-v1-hard` |
| [Three Card Monte](ThreeCardMonte/README.md) | 1 | Track a ball hidden under one of several cups through a series of announced swaps, then name the cup it ends up under. | `ThreeCardMonte-v1` |
| [Tower of Hanoi](TowerOfHanoi/README.md) | 1 | Move a stack of disks from tower A to tower C one disk at a time, never placing a larger disk on a smaller one. | `TowerOfHanoi-v1`, `TowerOfHanoi-v1-hard` |
| [Twenty Questions](TwentyQuestions/README.md) | 1 | Identify a hidden word from a known theme (a place, a person, or a thing) by asking an LLM game master up to 20 yes-or-no questions, then make a single final guess. | `TwentyQuestions-v1`, `TwentyQuestions-v1-hardcore` |
| [Ultimate Texas Hold'em](UltimateTexasHoldem/README.md) | 1 | A single player plays the casino game against the dealer, choosing when to make one Play bet per round, and must survive a fixed number of rounds without going broke. | `UltimateTexasHoldem-v1` |
| [Word Ladder](WordLadder/README.md) | 1 | Transform a start word into a target word by changing one letter at a time, where every step must be an English word of the same length. | `WordLadder-v1`, `WordLadder-v1-hard` |
| [Wordle](Wordle/README.md) | 1 | Guess a secret English word in a limited number of tries, using per-letter feedback that marks each letter as correct, misplaced, or absent. | `Wordle-v1`, `Wordle-v1-hardcore` |
| [Word Search](WordSearch/README.md) | 1 | Find five listed words hidden across or down in a grid of random letters by naming the start and end cells of each word. | `WordSearch-v1`, `WordSearch-v1-hardcore` |

### Two-player (52)

| Game | Players | Description | Env IDs |
| --- | :---: | --- | --- |
| [Alquerque](Alquerque/README.md) | 2 | A checkers ancestor on a 5×5 grid of points where pieces step forward along the lines and capture by jumping, and the player who captures more within 60 moves wins. | `Alquerque-v1` |
| [Battleship](Battleship/README.md) | 2 | Two players each hide five ships on a grid and take turns firing at the opponent's grid; whoever sinks the entire enemy fleet first wins. | `Battleship-v1`, `Battleship-v1-standard` |
| [Bomberman](Bomberman/README.md) | 2 | A turn-based two-player Bomberman: move around a walled arena, drop bombs that explode after a fixed number of moves, and be the last player standing. | `Bomberman-v1` |
| [Breakthrough](Breakthrough/README.md) | 2 | Two players race rows of pawn-like pieces across a square board; the first to reach the opponent's home row, or to capture every opposing piece, wins. | `Breakthrough-v1`, `Breakthrough-v1-blind` |
| [Checkers](Checkers/README.md) | 2 | Two players move pieces diagonally across an 8×8 board, capturing by jumping over opposing pieces, and win by capturing or blocking every enemy piece. | `Checkers-v1` |
| [Chess](Chess/README.md) | 2 | Two players alternate moves on an 8×8 board, each trying to checkmate the opponent's king. | `Chess-v1`, `Chess-v1-blind` |
| [Chopsticks](Chopsticks/README.md) | 2 | Each player has two hands of raised fingers and takes turns adding fingers to an opponent's hand or redistributing their own; the first to knock out both of the opponent's hands wins. | `Chopsticks-v1` |
| [Colonel Blotto](ColonelBlotto/README.md) | 2 | Each round, two commanders secretly split the same number of units across several battlefields; whoever wins more battlefields takes the round, and whoever wins more rounds takes the game. | `ColonelBlotto-v1`, `ColonelBlotto-v1-large` |
| [Connect Four](ConnectFour/README.md) | 2 | Two players take turns dropping discs into the columns of an upright grid; the first to line up four of their own discs horizontally, vertically, or diagonally wins. | `ConnectFour-v1`, `ConnectFour-v1-blind` |
| [Crusade](Crusade/README.md) | 2 | Two armies of sixteen pieces that all move like chess knights try to capture as many enemy pieces as possible within 40 moves. | `Crusade-v1` |
| [Debate](Debate/README.md) | 2 | Two players argue opposite sides of a random topic in alternating turns, and an AI jury that votes before and after the debate decides the winner: the side that gains more of the jury's support. | `Debate-v1` |
| [Don't Say It](DontSayIt/README.md) | 2 | Two players each hold a secret word and chat freely, each trying to get the other to say their word without ever saying the opponent's word. | `DontSayIt-v1`, `DontSayIt-v1-hardcore` |
| [Game of Pure Strategy (GOPS)](GameOfPureStrategy/README.md) | 2 | Two players each hold the thirteen cards from ace to king and spend one per round on a sealed bid for a randomly revealed prize card; the higher card wins the prize, and the higher prize total after thirteen rounds wins. | `GameOfPureStrategy-v1` |
| [German Whist](GermanWhist/README.md) | 2 | Two players use 13 tricks to win cards from the stock, then play 13 more tricks with their improved hands, and the majority of those last tricks wins. | `GermanWhist-v1` |
| [High Society](HighSociety/README.md) | 2 | Two players bid one sealed money card at a time for ten prestige cards, and the higher net worth (money left plus prestige won) after ten auctions wins. | `HighSociety-v1` |
| [Indian Poker](IndianPoker/README.md) | 2 | Two players each hold one card on their forehead, seeing only the opponent's card, and bet in a single no-limit round on whose card is higher. | `IndianPoker-v1` |
| [Iterated Matching Pennies](IteratedMatchingPennies/README.md) | 2 | Two players simultaneously pick heads or tails for a fixed number of rounds; the Matcher (Player 0) wins a round when the picks match, the Mismatcher (Player 1) wins when they differ, and whoever wins more rounds wins. | `IteratedMatchingPennies-v1` |
| [Iterated Prisoner's Dilemma](IteratedPrisonersDilemma/README.md) | 2 | Two players chat and then simultaneously choose to cooperate or defect for a fixed number of rounds, scoring points from a prisoner's dilemma payoff matrix, and the higher total wins. | `IteratedPrisonersDilemma-v1` |
| [Iterated Rock-Paper-Scissors](IteratedRockPaperScissors/README.md) | 2 | Two players simultaneously throw rock, paper, or scissors for a fixed number of rounds, and whoever wins more rounds wins. | `IteratedRockPaperScissors-v1` |
| [Iterated Stag Hunt](IteratedStagHunt/README.md) | 2 | Two players chat and then simultaneously choose to hunt a stag or a hare for a fixed number of rounds; a stag pays the most but only if both hunt it, a hare pays less but safely, and the higher total wins. | `IteratedStagHunt-v1`, `IteratedStagHunt-v1-randomized` |
| [Iterated Two-Thirds of the Average](IteratedTwoThirdsAverage/README.md) | 2 | Each round, two players simultaneously guess a number and the guess closer to two-thirds of the average of both guesses wins the round; whoever wins more rounds wins the game. | `IteratedTwoThirdsAverage-v1` |
| [Iterated Ultimatum Game](IteratedUltimatumGame/README.md) | 2 | Each round, a proposer offers the responder a share of a fixed pool, which the responder accepts (both get their shares) or rejects (both get nothing); whoever has collected more money after the last round wins. | `IteratedUltimatumGame-v1`, `IteratedUltimatumGame-v1-alternate` |
| [JoJoJoin](JoJoJoin/README.md) | 2 | Two players take turns placing marks on a 5×5 board; the first to get four of their own marks in a row horizontally, vertically or diagonally wins. | `JoJoJoin-v1` |
| [Kuhn Poker](KuhnPoker/README.md) | 2 | Two players play repeated hands of the simplest poker game, with a three-card deck, one card each and a single betting round. | `KuhnPoker-v1` |
| [Leduc Hold'em](LeducHoldem/README.md) | 2 | Two players play a match of a six-card, two-round fixed-limit poker game that is a standard benchmark for imperfect-information games. | `LeducHoldem-v1` |
| [Le Truc](LeTruc/README.md) | 2 | Two players play three-card hands of single-card tricks to 12 points, raising the value of each hand ("truc") to bluff or press an advantage. | `LeTruc-v1` |
| [Letter Auction](LetterAuction/README.md) | 2 | Two players bid coins on the 26 letters of the alphabet, one letter at a time, and then each spells an English word from the letters they won; the word whose letters cost the most wins. | `LetterAuction-v1`, `LetterAuction-v1-hard` |
| [Lines of Action](LinesOfAction/README.md) | 2 | Claude Soucie's connection game: each piece moves exactly as far as there are pieces on its line, and the first player to join all of their pieces into one connected group wins. | `LinesOfAction-v1` |
| [Memory Game](MemoryGame/README.md) | 2 | Two players take turns turning over two face-down cards, keeping matching pairs and moving again after each match, and whoever collects more pairs wins. | `MemoryGame-v1`, `MemoryGame-v1-hard` |
| [New Recruit](NewRecruit/README.md) | 2 | A recruiter and a job candidate negotiate an eight-term employment package, each scoring deals with a private point table, and once a proposal is accepted the player with the higher score wins. | `NewRecruit-v1` |
| [Nim](Nim/README.md) | 2 | Players take turns removing one or more objects from a single pile, and whoever takes the last object wins. | `Nim-v1` |
| [Othello](Othello/README.md) | 2 | Two players place discs on a square board, flipping every line of opposing discs they enclose; whoever owns more discs when neither side can move wins. | `Othello-v1`, `Othello-v1-hard` |
| [Pig Dice](PigDice/README.md) | 2 | Two players race to a target score by rolling a die to build up a turn total and deciding when to bank it, since rolling a 1 wipes out the points from that turn. | `PigDice-v1` |
| [Quantum Tic-Tac-Toe](QuantumTicTacToe/README.md) | 2 | Tic-tac-toe in which every move places a pair of entangled "spooky" marks that only turn into ordinary marks when a cycle of entanglements collapses. | `QuantumTicTacToe-v1` |
| [Retro Space Duel](RetroSpaceDuel/README.md) | 2 | A turn-based two-player space shooter: steer your ship through an asteroid field, grab power-ups, and shoot the enemy ship down without ever firing into a wall. | `RetroSpaceDuel-v1` |
| [Reverse Tic Tac Toe](ReverseTicTacToe/README.md) | 2 | Two players take turns marking cells of a 3×3 grid, and the first to complete a row, column, or diagonal of their own marks loses. | `ReverseTicTacToe-v1` |
| [Scenario Planning](ScenarioPlanning/README.md) | 2 | Two players each write a survival strategy for the same hypothetical crisis without seeing each other's plan, and an AI jury votes for the more effective and feasible one. | `ScenarioPlanning-v1` |
| [Simple Blind Auction](SimpleBlindAuction/README.md) | 2 | Two players chat openly and then submit one round of sealed bids on items that each of them values differently; the higher final net worth wins. | `SimpleBlindAuction-v1` |
| [Simple Negotiation](SimpleNegotiation/README.md) | 2 | Two players barter five resources that each of them values privately, and whoever increases the value of their own inventory more by the turn limit wins. | `SimpleNegotiation-v1` |
| [Simple Tak](SimpleTak/README.md) | 2 | Two players take turns placing stones on a square grid; the first to connect two opposite edges with an orthogonally connected path of their own stones wins. | `SimpleTak-v1` |
| [Spelling Bee](SpellingBee/README.md) | 2 | Two players take turns naming English words built only from a shared set of letters, each word at least as long as the previous one, until one of them cannot continue or the turn limit is reached. | `SpellingBee-v1` |
| [Spite and Malice](SpiteAndMalice/README.md) | 2 | Two players race to empty their payoff piles by building shared center piles from Ace up to Queen, with Kings wild. | `SpiteAndMalice-v1` |
| [Stratego](Stratego/README.md) | 2 | Two armies whose ranks are hidden from each other battle on a 10×10 board; capture the enemy Flag, or leave the opponent without a legal move, to win. | `Stratego-v1` |
| [Tak](Tak/README.md) | 2 | Two players place and stack stones on a square board, racing to build a road of their own pieces that connects two opposite edges. | `Tak-v1`, `Tak-v1-hard` |
| [Tic Tac Toe](TicTacToe/README.md) | 2 | Two players take turns marking cells of a 3×3 grid; the first to complete a row, column, or diagonal of their own marks wins. | `TicTacToe-v1` |
| [Truth and Deception](TruthAndDeception/README.md) | 2 | The Deceiver knows which of two similar-sounding facts is true and chats with the Guesser, who must then pick the true one; a correct guess wins for the Guesser and a wrong one for the Deceiver. | `TruthAndDeception-v1` |
| [Two Dollar](TwoDollar/README.md) | 2 | Two players negotiate in free text over how to split $2.00, each following secret role instructions such as a minimum acceptable share or a strict word limit. | `TwoDollar-v1` |
| [Ultimate Tic Tac Toe](UltimateTicTacToe/README.md) | 2 | Two players play tic-tac-toe on nine small boards arranged in a 3×3 grid, where each move dictates the opponent's next board and three won boards in a row win the game. | `UltimateTicTacToe-v1` |
| [Used Car Negotiation](UsedCarNegotiation/README.md) | 2 | A buyer and a seller haggle over the price of a used 2006 Toyota Prius, each with a private background that gives them a strong or weak alternative to making a deal; the agreed price determines how the surplus is split. | `UsedCarNegotiation-v1` |
| [Vendor Negotiation](VendorNegotiation/README.md) | 2 | A Brand Specialist and a Vendor negotiate discount rates for several products ahead of a sales event, each with private forecasts and a private target. | `VendorNegotiation-v1` |
| [Wild Tic Tac Toe](WildTicTacToe/README.md) | 2 | Two players take turns placing either an X or an O on a 3×3 grid, and whoever completes a line of three identical marks wins, no matter who placed the other two. | `WildTicTacToe-v1` |
| [Word Chains](WordChains/README.md) | 2 | Two players take turns naming English words that start with the last letter of the previous word and are exactly one letter longer; the first player who cannot continue loses. | `WordChains-v1` |

### Multi-player (26)

| Game | Players | Description | Env IDs |
| --- | :---: | --- | --- |
| [Blind Auction](BlindAuction/README.md) | 3–15 | Players talk in public and in private, then submit sealed bids on items that each of them values differently; the player with the highest final net worth wins. | `BlindAuction-v1` |
| [Bohnanza](Bohnanza/README.md) | 3–5 | Players plant, trade, and harvest beans for coins without ever rearranging their hand, so trading away awkward beans with the active player is the heart of the game. | `Bohnanza-v1`, `Bohnanza-v1-short` |
| [Briscola](Briscola/README.md) | 2–4 | Two to four players play the Italian trick-taking card game Briscola with a 40-card deck, trying to capture the most of its 120 card points, alone or, with four players, in two partnerships. | `Briscola-v1` |
| [Character Conclave](CharacterConclave/README.md) | 3–15 | Players hold a free-form discussion under a strict per-player character budget, then each secretly votes for the most impressive other player; the most-voted player wins. | `CharacterConclave-v1` |
| [Codenames](Codenames/README.md) | 4 | Two teams of two race to uncover their own words on a 25-word board, with each team's Spymaster giving one-word clues that their Operative turns into guesses. | `Codenames-v1`, `Codenames-v1-hardcore` |
| [Coup](Coup/README.md) | 2–6 | Players bluff about the court characters they secretly hold to gain coins and knock out rivals' influence; the last player with influence wins. | `Coup-v1` |
| [Diplomacy](Diplomacy/README.md) | 3–7 (default 7) | Players command great powers of pre-WWI Europe, negotiate in public and in private, and then issue simultaneous military orders; the first power to control 18 of the 34 supply centers wins. | `Diplomacy-v1` |
| [Golf](Golf/README.md) | 2–4 | Two to four players draw and swap cards to build the lowest-scoring grid, where a column of equal ranks scores zero. | `Golf-v1`, `Golf-v1-medium` |
| [Hanabi](Hanabi/README.md) | 2–5 | Two to five players cooperate to build five fireworks from 1 to 5 while seeing every hand except their own, which they learn about only through a limited supply of hints. | `Hanabi-v1` |
| [Liar's Dice](LiarsDice/README.md) | 2–15 | Players bid on how many dice of a face are showing across everyone's hidden dice or call the last bid a lie; every lost challenge costs a die, and the last player with dice wins. | `LiarsDice-v1` |
| [Market Entry Game](MarketEntryGame/README.md) | 2–15 | Each round, players exchange public messages and then simultaneously decide whether to enter a market that only pays off if few enough of them enter; the highest total score after all rounds wins. | `MarketEntryGame-v1` |
| [Negotiation](Negotiation/README.md) | 2–15 | Players trade five resources that each of them values differently, using public messages, private messages, and targeted trade offers; whoever holds the most valuable inventory when the turns run out wins. | `Negotiation-v1` |
| [Texas Hold'em Poker](Poker/README.md) | 2–15 | Two to fifteen players play a fixed number of no-limit Texas Hold'em hands and are ranked by their final chip counts. | `Poker-v1` |
| [Public Goods Game](PublicGoodsGame/README.md) | 2–15 | Each round, players exchange public messages and then simultaneously decide how many tokens to put into a shared pot that is multiplied and split equally; each player is scored on their own total payoff. | `PublicGoodsGame-v1` |
| [Santorini](Santorini/README.md) | 2–3 | Two or three players move builders around a 5×5 island and raise towers, winning by stepping a worker up onto the third level. | `SantoriniBaseFixed-v1` |
| [Scorable Games](ScorableGames/README.md) | 2–15 | Stakeholders with secret scoring sheets negotiate a multi-issue agreement by proposing complete deals and voting on them; a deal passes once enough parties, including every veto holder, accept it. | `ScorableGames-v1` |
| [Secret Mafia](SecretMafia/README.md) | 6–15 | A hidden Mafia team kills off villagers at night while the village, helped by a Doctor and a Detective, tries to vote every Mafia member out by day. | `SecretMafia-v1` |
| [Settlers of Catan](SettlersOfCatan/README.md) | 3–4 | Three or four players gather resources from dice rolls, trade with each other in private one-on-one negotiations, and build roads, settlements, and cities on the beginner Catan board until someone reaches the target number of victory points. | `SettlersOfCatan-v1` |
| [Snake](Snake/README.md) | 2–15 | Two to fifteen snakes move simultaneously on a shared grid and grow by eating apples; the last snake alive wins, and snakes that survive to the round limit are ranked by apples eaten. | `Snake-v1` |
| [Surround](Surround/README.md) | 2–15 | Two to fifteen light cycles move simultaneously on a grid, each leaving a permanent trail; whoever crashes into a wall or a trail is out, and the last player moving wins. | `Surround-v1` |
| [Taboo](Taboo/README.md) | 4+ | Two teams take turns in which a Clue Giver describes a secret word without saying it or any of its taboo words while teammates try to guess it; the team with more correct guesses wins. | `Taboo-v1` |
| [Three-Player Game of Pure Strategy (GOPS)](ThreePlayerGOPS/README.md) | 3 | Three players each hold the thirteen cards from ace to king and spend one per round on a sealed bid for a randomly revealed prize card; the single highest card wins the prize, and players are ranked by their prize totals after thirteen rounds. | `ThreePlayerGOPS-v1` |
| [Three-Player Iterated Prisoner's Dilemma](ThreePlayerIPD/README.md) | 3 | Three players chat and then privately decide, for each opponent separately, whether to cooperate or defect; every pair of players scores a prisoner's dilemma each round, and players are ranked by their totals after a fixed number of rounds. | `ThreePlayerIPD-v1` |
| [Three-Player Tic Tac Toe](ThreePlayerTicTacToe/README.md) | 3 | Three players take turns marking a 5×5 grid with their own symbol, and the first to get four in a row horizontally, vertically, or diagonally wins. | `ThreePlayerTicTacToe-v1` |
| [Two Rooms and a Boom](TwoRoomsAndABoom/README.md) | 6–20 | Two hidden teams are split across two rooms whose leaders trade hostages every round; the Red Team wins if its Bomber ends up in the same room as the Blue Team's President. | `TwoRoomsAndABoom-v1` |
| [Win as Much as You Can](WinAsMuchAsYouCan/README.md) | 4 | Four players secretly choose X or Y in each of ten rounds of a multi-player prisoner's dilemma, negotiating publicly and privately before the 3×, 5×, and 10× rounds. | `WinAsMuchAsYouCan-v1` |
<!-- END GENERATED: catalog -->
