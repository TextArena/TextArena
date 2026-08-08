

Game Count 99

TODO = implemented but not updated

general todos:
- add readme for three player IPD
- add readme for babyai-text
- add readme for two rooms and a boom


# Single-player Environments (28)
| Game Nr | Env-id                                            | Play Online | skills | Final Sign-off Bobby | Final Sign-off Leon | Comments |
| ------- | ------------------------------------------------- | :---------: | ------ |:--------------------:|:-------------------:| -------- |
| 1       | [`2048-v0`](#2048)                                |      ✗      |        |          ✓           |          ✓          |          |
| 2       | [`BabyAiText-v0`](#babyaitext)                    |      ✗      |        |          ✓           |          ✓          |          |
| 3       | [`Bandit-v0`](#bandit)                            |      ✗      |        |          ✓           |          ✓          |          |
| 4       | [`Blackjack-v0`](#blackjack)                      |      ✗      |        |          ✓           |          ✓          |          |
| 5       | [`Countdown-v0`](#countdown)                      |      ✗      |        |          ✓           |          ✓          |          |
| 6       | [`Crosswords-v0`](#crosswords)                    |      ✗      |        |          ✓           |          ✓          | simplified the board viewing to work with the GameMessagesAndCurrentBoardObservationWrapper|
| 7       | [`Cryptarithm-v0`](#crytarithm)                   |      ✗      |        |          ✓           |          ✓          |          |
| 8       | [`FifteenPuzzle-v0`](#fifteenpuzzle)              |      ✗      |        |          ✓           |          ✓          |  I was not able to finish within 40 moves. I propose we increase to 200|
| 9       | [`FrozenLake-v0`](#frozenlake)                    |      ✗      |        |          ✓           |          ✓          |  added proper turn-limit checking|
| 10      | [`GuessTheNumber-v0`](#guessthenumber)            |      ✗      |        |          ✓           |          ✓          |          |
| 11      | [`GuessWho-v0`](#guesswho)                        |      ✗      |        |          ✓           |          ✓          |          |
| 12      | [`Hangman-v0`](#hangman)                          |      ✗      |        |          ✓           |          ✓          |          |
| 13      | [`LightsOut-v0`](lightsout)                       |      ✗      | TODO   |          ✓           |                     |          |
| 14      | [`LogicPuzzle-v0`](#logicpuzzle)                  |      ✗      |        |          ✓           |          ✓          |          |
| 15      | [`Mastermind-v0`](#mastermind)                    |      ✗      |        |          ✓           |          ✓          |          |
| 16      | [`Minesweeper-v0`](#minesweeper)                  |      ✗      |        |          ✓           |          ✓          |  Made bomb moves as invalid moves, otherwise game ends too quickly  |
| 17      | [`PegJump-v0`](#pegjump)                          |      ✗      |        |          ✓           |          ✓          |          |
| 18      | [`RushHour-v0`](#rushhour)                        |      ✗      |        |          ✓           |          ✓          | There were overlapping car pieces and a fixed game board. Revised both |
| 19      | [`Secretary-v0`](#secretary)                      |      ✗      |        |          ✓           |          ✓          |          |
| 20      | [`Slitherlink-v0`](#slitherlink)                  |      ✗      | TODO   |          ✓           |                     |   Added a board generator and revised the gameboard render   |
| 21      | [`Sokoban-v0`](#sokoban)                          |      ✗      |        |          ✓           |          ✓          |          |
| 22      | [`Sudoku-v0`](#sudoku)                            |      ✗      |        |          ✓           |          ✓          |          |
| 23      | [`ThreeCardMonte-v0`](#threecardmonte)            |      ✗      |        |          ✓           |          ✓          |  Replaced the O with X so that it's more legible, e.g. 0 O 2 vs 0 X 2  |
| 24      | [`TowerOfHanoi-v0`](#towerofhanoi)                |      ✗      |        |          ✓           |          ✓          |          |
| 25      | [`TwentyQuestions-v0`](#twentyquestions)          |      ✗      |        |          ✓           |          ✓          |          |
| 26      | [`WordLadder-v0`](#wordladder)                    |      ✗      |        |          ✓           |          ✓          |          |
| 27      | [`Wordle-v0`](#wordle)                            |      ✗      |        |          ✓           |          ✓          |          |
| 28      | [`WordSearch-v0`](#wordsearch)                    |      ✗      |        |          ✓           |          ✓          |  updated with the v0.6.9 branch  |




# Two-player Environments (52)
| Game Nr | Env-id                                                       | Play Online | skills                                     | Final Sign-off Bobby | Final Sign-off Leon | Comments |
| ------- | ------------------------------------------------------------ | :---------: | ------------------------------------------ |:--------------------:|:-------------------:| -------- |
| 1       | [`Alquerque-v0`](#alquerque)                                 |      ✗      | Needs Testing                              |         ✓            |          ✓          |          |
| 2       | [`Battleship-v0`](#battleship)                               |      ✗      |                                            |         ✓            |          ✓          |          |
| 3       | [`Breakthrough-v0`](#breakthrough)                           |      ✗      |                                            |         ✓            |          ✓          |          |
| 4       | [`Briscola-v0`](#briscola)                                   |      ✗      | TODO                                       |         ✓            |                     |  I think we need to adjust the _prompt        |
| 5       | [`Checkers-v0`](#checkers)                                   |      ✗      |                                            |         ✓            |          ✓          |          |
| 6       | [`Chess-v0`](#chess)                                         |      ✗      |                                            |         ✓            |          ✓          |          |
| 7       | [`Chopsticks-v0`](#chopsticks)                               |      ✗      |                                            |         ✓            |          ✓          |          |
| 8       | [`ColonelBlotto-v0`](#colonelblotto)                         |      ✗      |                                            |                      |          ✓          |          |
| 9       | [`ConnectFour-v0`](#connectfour)                             |      ✗      |                                            |         ✓            |          ✓          |          |
| 10      | [`Coup-v0`](#coup)                                           |      ✗      | TODO                                       |                      |                     |          |
| 11      | [`Crusade-v0`](#crusade)                                     |      ✗      |                                            |                      |          ✓          |          |
| 12      | [`Debate-v0`](#debate)                                       |      ✗      |                                            |         ✓            |          ✓          |          |
| 13      | [`DontSayIt-v0`](#dontsayit)                                 |      ✗      |                                            |         ✓            |          ✓          |          |
| 14      | [`GameOfPureStrategy-v0`](#gameofpurestrategy)               |      ✗      |                                            |         ✓            |          ✓          |          |
| 15      | [`GermanWhist-v0`](#germanwhist)                             |      ✗      |                                            |         ✓            |                     |          |
| 16      | [`Golf-v0`](#golf)                                           |      ✗      |                                            |         ✓            |                     |          |
| 17      | [`HighSociety-v0`](#highsociety)                             |      ✗      |                                            |         ✓            |          ✓          | Added `to_id=pid` in the player_action |
| 18      | [`IndianPoker-v0`](#indianpoker)                             |      ✗      |                                            |                      |          ✓          |          |
| 19      | [`IteratedMatchingPennies-v0`](#iteratedmatchingpennies)     |      ✗      |                                            |         ✓            |          ✓          |          |
| 20      | [`IteratedPrisonersDilemma-v0`](#iteratedprisonersdilemma)   |      ✗      |                                            |                      |          ✓          |          |
| 21      | [`IteratedRockPaperScissors-v0`](#iteratedrockpaperscissors) |      ✗      |                                            |         ✓            |          ✓          |          |
| 22      | [`IteratedTwoThirdsAverage-v0`](#iteratedtwothirdsaverage)   |      ✗      |                                            |         ✓            |          ✓          |          |
| 23      | [`IteratedStagHunt-v0`](#iteratedstaghunt)                   |      ✗      |                                            |                      |          ✓          |          |
| 24      | [`KuhnPoker-v0`](#kuhnpoker)                                 |      ✗      |                                            |                      |          ✓          |          |
| 25      | [`LeducHoldem-v0`](#leducholdem)                             |      ✗      | TODO                                       |                      |                     |          |
| 26      | [`LeTruc-v0`](#letruc)                                       |      ✗      | TODO                                       |                      |                     |          |
| 27      | [`LinesOfAction-v0`](#linesofaction)                         |      ✗      | needs extra testing                        |                      |                     |          |
| 28      | [`LetterAuction-v0`](#letterauction)                         |      ✗      | TODO                                       |                      |                     |          |
| 29      | [`LiarsDice-v0`](#liarsdice)                                 |      ✗      |                                            |                      |          ✓          |          |
| 30      | [`MemoryGame-v0`](#memorygame)                               |      ✗      |                                            |         ✓            |          ✓          |          |
| 31      | [`Nim-v0`](#nim)                                             |      ✗      |                                            |         ✓            |          ✓          |          |
| 32      | [`Othello-v0`](#othello)                                     |      ✗      |                                            |         ✓            |          ✓          |          |
| 33      | [`PigDice-v0`](#pigdice)                                     |      ✗      |                                            |         ✓            |          ✓          |          |
| 34      | [`Poker-v0`](#poker)                                         |      ✗      |                                            |                      |          ✓          |          |
| 35      | [`QuantumTicTacToe-v0`](#quantumtictactoe)                   |      ✗      |                                            |                      |          ✓          |          |
| 36      | [`ReverseTicTacToe-v0`](#reversetictactoe)                   |      ✗      |                                            |                      |          ✓          |          |
| 37      | [`ScenarioPlanning-v0`](#scenarioplanning)                   |      ✗      |                                            |                      |          ✓          |          |
| 38      | [`Santorini-v0`](#santorini)                                 |      ✗      | TODO                                       |                      |                     |          |
| 39      | [`SimpleBlindAuction-v0`](#simpleblindauction)               |      ✗      |                                            |                      |          ✓          |          |
| 40      | [`SimpleNegotiation-v0`](#simplenegotiation)                 |      ✗      |                                            |         ✓            |          ✓          |          |
| 41      | [`SimpleTak-v0`](#simpletak)                                 |      ✗      |                                            |         ✓            |          ✓          |          |
| 42      | [`Snake-v0`](#snake)                                         |      ✗      |                                            |         ✓            |          ✓          |          |
| 43      | [`SpellingBee-v0`](#spellingbee)                             |      ✗      |                                            |         ✓            |          ✓          |          |
| 44      | [`SpiteAndMalice-v0`](#spiteandmalice)                       |      ✗      | TODO                                       |                      |                     |          |
| 45      | [`Stratego-v0`](#stratego)                                   |      ✗      | TODO                                       |         ✓            |                     |  available moves now include Scouts moving >1 step till an obstacle  |
| 46      | [`Surround-v0`](#surround)                                   |      ✗      |                                            |                      |          ✓          |          |
| 47      | [`Tak-v0`](#tak)                                             |      ✗      |                                            |                      |                     |          |
| 48      | [`TicTacToe-v0`](#tictactoe)                                 |      ✗      |                                            |                      |          ✓          |          |
| 49      | [`TruthAndDeception-v0`](#truthanddeception)                 |      ✗      |                                            |                      |          ✓          |          |
| 50      | [`TwoDollar-v0`](#twodollar)                                 |      ✗      |                                            |         ✓            |          ✓          |          |
| 51      | [`UltimateTicTacToe-v0`](#ultimatetictactoe)                 |      ✗      |                                            |                      |          ✓          |          |
| 52      | [`WildTicTacToe-v0`](#wildtictactoe)                         |      ✗      |                                            |                      |          ✓          |          |
| 53      | [`WordChains-v0`](#wordchains)                               |      ✗      |                                            |                      |          ✓          |          |



# Multi-player Environments (19)
| Game Nr | Env-id                                                       | num-players | Play Online | skills | Final Sign-off Bobby | Final Sign-off Leon | Comments |
| ------- | ------------------------------------------------------------ | ----------- | :---------: | ------ |:--------------------:|:-------------------:| -------- |
| 1       | [`Santorini-v0`](#santorini)                                 | 2-3         |      ✗      | TODO   |                      |                     |          |
| 2       | [`Briscola-v0`](#briscola)                                   | 2-4         |      ✗      | TODO   |                      |                     |          |
| 3       | ['Golf-v0'](#golf)                                           | 2-4         |      ✗      |        |                      |                     |          |
| 4       | [`Coup-v0`](#coup)                                           | 2-6         |      ✗      | TODO   |                      |                     |          |
| 5       | [`LiarsDice-v0`](#liarsdice)                                 | 2-15        |      ✗      |        |                      |          ✓          |          |
| 6       | [`Negotiation-v0`](#negotiation)                             | 2-15        |      ✗      | TODO   |                      |                     |          |
| 7       | [`Poker-v0`](#poker)                                         | 2-15        |      ✗      |        |                      |          ✓          |          |
| 8       | [`Snake-v0`](#snake)                                         | 2-15        |      ✗      |        |                      |          ✓          |          |
| 9       | [`Surround-v0`](#surround)                                   | 2-15        |      ✗      |        |                      |          ✓          |          |
| 10      | [`ThreePlayerGOPS-v0`](#threeplayerGOPS)                     | 3           |      ✗      |        |                      |          ✓          |          |
| 11      | [`ThreePlayerTicTacToe-v0`](#threeplayertictactoe)           | 3           |      ✗      |        |                      |          ✓          |          |
| 12      | [`ThreePlayerIPD-v0`](#threeplayeripd)                       | 3           |      ✗      |        |                      |                     |          |
| 13      | [`Diplomacy-v0`](#diplomacy)                                 | 3-7         |      ✗      | TODO   |                      |                     |          |
| 14      | [`BlindAuction-v0`](#blindauction)                           | 3-15        |      ✗      | TODO   |                      |                     |          |
| 15      | [`CharacterConclave-v0`](#characterconclave)                 | 3-15        |      ✗      |        |                      |                     |          |
| 16      | [`Codenames-v0`](#codenames)                                 | 4           |      ✗      |        |                      |          ✓          |          |
| 17      | [`Taboo-v0`](#taboo)                                         | 4-8         |      ✗      | TODO   |                      |                     |          |
| 18      | [`SecretMafia-v0`](#secretmafia)                             | 6-15        |      ✗      |        |                      |          ✓          |          |
| 19      | [`TwoRoomsAndABoom-v0`](#tworoomsandaboom)                   | 6-20        |      ✗      | TODO   |                      |                     | still needs to be updated to v0.6.9 |




# Other TODOS:
- sort the below section according to the table (i.e. by num players and then alphabetically)
- update Online availability in the table above




<br>

# Single-Player

<details><summary><strong>2048 [Single Player]</strong></summary><a id="2048"></a><hr>

## `2048`

**2048** is a 4 × 4 sliding-tile puzzle: issue `[Up]`, `[Down]`, `[Left]`, or `[Right]` to slide the board; identical tiles that collide merge and double. Reach the **target tile** (default 2048) before no moves remain.

| **Reward Setting**        | **Reward**                              |
|---------------------------|-----------------------------------------|
| Invalid / no-effect move  | `current_max / target_tile`             |
| Win (reach target)        | `1.0`                                   |
| Lose (no moves left)      | `current_max / target_tile`             |

**Env-ids** 
`target_tile` determines how tile has to be reached to win.

| **Env-ID**           |**target_tile**|
|----------------------| :-----------: |
| `2048-v0-super-easy` |      128      |
| `2048-v0-very-easy`  |      256      |
| `2048-v0-easy`       |     1 024     |
| `2048-v0`            |     2 048     |
| `2048-v0-hard`       |     4 096     |
| `2048-very-hard`     |     8 192     |
| `2048-extreme`       |     16 384    |

| **Full Env-ID format** | **Default Wrappers**                                                           |
|------------------------|--------------------------------------------------------------------------------|
| `2048-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                             |
| `2048-v0-{...}-raw`    | *None*                                                                         |
| `2048-v0-{...}-train`  | `GameMessageAndCurrentBoardStateObservationWrapper`, `ActionFormattingWrapper` |


**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **[guertlerlo@cfar.a-star.edu.sg](mailto:guertlerlo@cfar.a-star.edu.sg)**



<hr></details><details><summary><strong>Bandit [Single Player]</strong></summary><a id="bandit"></a><hr>

## `Bandit`

The task in the Bandit environment is Best-Arm Identification. The agent pushes buttons and observes rewards for a fixed number of turns. Afterward, the player tries to deduce the button with the highest average return. The game encourages strategic exploration. 

**Action Space:** Actions must be valid buttons of the form `[Button]` (i.e. `[blue]`)
**Reward Setting:** Regret

**Env-ids** 
`buttons` determines the number and labels of buttons, `p_gap`, `num_turns`, 

| **Env-ID**       |                                       **buttons**                                        | **p_gap** | **num_turns** |
|------------------| :--------------------------------------------------------------------------------------: | :-------: | :-----------: |
| `Bandit-v0`      | ['red', 'blue', 'green', 'yellow', 'purple']                                             |    0.1    |      20       |
| `Bandit-v0-hard` | ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'pink', 'brown', 'gray', 'black'] |    0.05   |      40       |

| **Full Env-ID format**   | **Default Wrappers**                                       |
|--------------------------|------------------------------------------------------------|
| `Bandit-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`         |
| `Bandit-v0-{...}-raw`    | *None*                                                     |
| `Bandit-v0-{...}-train`  | `GameMessageObservationWrapper`, `ActionFormattingWrapper` |


**Contact:** If you have questions or face issues with this specific environment, please reach out directly to # TODO tim



<hr></details><details><summary><strong>Blackjack [1 Player]</strong></summary><a id="blackjack"></a><hr>

## `Blackjack`  
**Blackjack** is a single-player card game where the player competes against a dealer to score as close to 21 as possible without going over. The player may choose to `[Hit]` to draw a card or `[Stand]` to end their turn. Aces are worth either 1 or 11, depending on which is more favorable to the hand. The player competes over multiple hands, and the final reward is based on their win rate. This environment supports both short and extended formats to test probabilistic reasoning and decision-making under uncertainty.

**Action Space:**  
Players issue commands in square brackets: `[Hit]` or `[Stand]`  
- `[Hit]`: Draw another card  
- `[Stand]`: End turn and reveal dealer's full hand  
Actions are case-insensitive.

| **Reward Setting**       | **Player**     | **Reward**                           |
|--------------------------|----------------|--------------------------------------|
| Invalid move             | Player         | `self._get_percentage_completion()`  |
| Valid game outcome       | Player         | `% of hands won (0.0 to 1.0)`        |

**Env-ids:**  
Each variant is defined by the number of hands and whether wrappers are used.

| **Env-ID**                | **num_hands** |
|---------------------------|:-------------:|
| `Blackjack-v0`            | `5`           |
| `Blackjack-v0-long`       | `15`          |


|**Full Env-ID Format**        | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
|`Blackjack-v0-{...}`          | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
|`Blackjack-v0-{...}-raw`      | `None`                                                                     |
|`Blackjack-v0-{...}-train`    | `[GameMessagesObservationWrapper, ActionFormattingWrapper]` |

### Contact  
If you have questions or face issues with this specific environment, please reach out directly to **guertlerlo@cfar.a-star.edu.sg**




<hr></details><details><summary><strong>Countdown [Single Player]</strong></summary><a id="countdown"></a><hr>

## `Countdown`

Combine a given set of numbers using **addition, subtraction, multiplication, or exact division** to reach a randomly chosen **target (100 – 999)**. Each action consumes two numbers and appends the result until the target is hit or only one number remains.

| **Reward Setting**              | **Reward**                                                                    |
|---------------------------------|-------------------------------------------------------------------------------|
| Invalid move                    | current `progress = 1 − |best − target| / 1000`                               |
| Exact target achieved           | `1.0`                                                                         |
| End of episode (no exact hit)   | same `progress` value                                                          |

**Action Space:** `[i j op]` combine numbers[i] (index i) and numbers[j] (index j); # op ∈ { + , - , * , / } — division must divide exactly; Indices are **0-based** and must be distinct; result is appended to the list.

**Env-ids:** 
`max_turns` determines the turn-limit, `target` denotes the target number to reach with the available `numbers`.

| **Env-ID**        |      **numbers**      | **max_turns** | **target** |
|-------------------|:---------------------:|:-------------:|------------|
| `Countdown-v0`    | [100, 75, 6, 4, 3, 2] |      12       | 532        |

| **Full Env-ID format** | **Default Wrappers**                                                       |
|------------------------|----------------------------------------------------------------------------|
| `Countdown-v0`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Countdown-v0-raw`     | *None*                                                                     |
| `Countdown-v0-train`   | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |




<hr></details><details><summary><strong>Crosswords [1 Player]</strong></summary><hr>

## `Crosswords` <a id="crosswords"></a>
**Crosswords** is a single-player puzzle game where the player fills in a crossword grid using clues. The objective is to correctly place all the letters to complete each word, based on the positions and hints given. Words are aligned either across or down, and players must deduce the correct word letter by letter.

**Action Space:** Actions are strings in the format `[row col letter]`, where `row` and `col` are 0-indexed positions in the crossword grid, and `letter` is the character to insert at that location.

- Example: `[4 7 A]` places the letter `'A'` at row 4, column 7.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**                   | **Player Role** | **Reward**                          |
|---------------------------------|-----------------|-------------------------------------|
| Completed puzzle                | Player          | `+1`                                |
| Incorrect completion or timeout | Player          | `self._get_percentage_completion()` |
| Invalid move                    | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple variants based on difficulty and number of words.
| **Env-ID**                  | **hardcore** | **max_turns** | **num_words** |
|-----------------------------|:------------:|:-------------:|:-------------:|
| `Crosswords-v0`             |   `False`    |     `30`      |     `3`       |
| `Crosswords-v0-hardcore`    |   `True`     |     `30`      |     `3`       |

| **Full Env-ID Format**       | **Default Wrappers**                                     |
|------------------------------|----------------------------------------------------------|
| `Crosswords-v0-{...}`        | `[LLMObservationWrapper, ActionFormattingWrapper]`       |
| `Crosswords-v0-{...}-raw`    | `None`                                                   |
| `Crosswords-v0-{...}-train`  | `[GameBoardObservationWrapper, ActionFormattingWrapper]` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Chess [2 Player]</strong></summary><a id="chess"></a><hr>

## `Chess` 

**Chess** is a classic two-player strategy game contested on an 8 × 8 board. Each side commands sixteen pieces (King, Queen, Rooks, Bishops, Knights, and Pawns) and aims to **checkmate** the opponent’s King. [Wikipedia](https://en.wikipedia.org/wiki/Chess)  

**Action Space:** Moves are written in Universal Chess Interface (UCI) format inside brackets: `[start end]`. For example, `[e2e4]` advances a pawn from *e2* to *e4*; `[g1f3]` moves the knight from *g1* to *f3*. Only the **first** bracketed move in any message is executed.

| **Reward Setting** | **Player Role** | **Reward** |
| ------------------ | --------------- | ---------- |
| Checkmated enemy   | Winner          | `+1`       |
|                    | Loser           | `-1`       |
| Stalemate / draw   | Both            | `0`        |
| Made an invalid move| Offending Player| `-1`       |

**Env-ids**: The environment supports several variants defined by two parameters: `is_open`, which determines whether the full board is shown after each move, and `max_turns`, the turn limit before an automatic draw; `show_valid` indicates whether the valid actions are shown to the model.
| **Env-ID**          | **is_open** | **max_turns** | **show_valid** |
| --------------------| :---------: | :-----------: | :------------: |
| `Chess-v0`          |   `True`    |     `100`     |     `True`     |
| `Chess-v0-long`     |   `True`    |     `250`     |     `True`     |
| `Chess-v0-blind`    |   `False`   |     `100`     |     `False`    |

| **Full Env-ID Format**  | **Default Wrappers**                                                       |
|-------------------------|----------------------------------------------------------------------------|
| `Chess-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Chess-v0-{...}-raw`    | `None`                                                                     |
| `Chess-v0-{...}-train`  | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to Guertlerlo@cfar.a-star.edu.sg

<hr></details><details><summary><strong>Cryptarithm [Single Player]</strong></summary><a id="cryptarithm"></a><hr>

## `Cryptarithm`

Solve classic alphametic puzzles such as **SEND + MORE = MONEY** by assigning **unique digits (0-9)** to letters until the arithmetic equation holds.

| **Reward Setting**                      | **Reward**                                       |
|-----------------------------------------|--------------------------------------------------|
| Invalid assignment                      | `progress = assigned_letters / total_letters`    |
| All letters mapped, equation incorrect  | `0.0`                                            |
| Equation satisfied                      | `1.0`                                            |

**Action Space** `[A 5]` assign letter A → digit 5; digits must be unique; leading letters ≠ 0; You can re-assign a letter to any free digit at any time.

**Env-ids**

| **Env-ID**              | **equation**        | **max_turns** |
|---------------------|---------------------|:-------------:|
| `Cryptarithm-v0`    | SEND + MORE = MONEY |      100      |

| **Full Env-ID format** | **Default Wrappers**                                        |
|------------------------|-------------------------------------------------------------|
| `Cryptarithm-v0`       | `LLMObservationWrapper`, `ActionFormattingWrapper`          |
| `Cryptarithm-v0-raw`   | *None*                                                      |
| `Cryptarithm-v0-train` | `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** questions/issues → **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Fifteen Puzzle [1 Player]</strong></summary><a id="fifteenpuzzle"></a><hr>

## `Fifteen Puzzle` 
**Fifteen Puzzle** is a single-player sliding tile puzzle game played on a 4×4 board. The objective is to arrange the numbered tiles from 1 to 15 in ascending order, ending with the empty space (`__`) in the bottom-right corner. The player slides tiles adjacent to the empty space in the direction of the gap to solve the puzzle. The game ends when the correct configuration is achieved or the player runs out of moves. [Wikipedia](https://en.wikipedia.org/wiki/15_puzzle)

**Action Space:**  
Actions are strings in the format `[direction]`, where `direction` is one of: `up`, `down`, `left`, or `right`. These indicate the direction in which the player wishes to slide a tile into the empty space. For example:
- `[up]`: Moves the tile below the empty space up.
- `[left]`: Moves the tile to the right of the empty space left.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**     | **Reward**                     |
|------------------|--------------------------------|
| Solved puzzle    | `+1`                            |
| Invalid move     | `self._get_percentage_completion()` |
| Game over (not solved) | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple variants based on the wrappers applied and maximum number of moves.
| **Env-ID**                 | **max_turns** |
|----------------------------|:-------------:|
| `FifteenPuzzle-v0`         |      `200`    |

**Wrapper Variants:** The following suffixes can be appended to the base IDs above to change the default observation wrappers:
| **Full Env-ID Format**       | **Default Wrappers**                                                   |
|------------------------------|------------------------------------------------------------------------|
| `FifteenPuzzle-v0-{...}`     | `[LLMObservationWrapper, ActionFormattingWrapper]`                     |
| `FifteenPuzzle-v0-{...}-raw` | `None`                                                                 |
| `FifteenPuzzle-v0-{...}-train` | `[GameBoardObservationWrapper, ActionFormattingWrapper]`             |

**Contact:**  
If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**




<hr></details><details><summary><strong>Frozen Lake [1 Player]</strong></summary><hr>

## `Frozen Lake` <a id="frozenlake"></a>
**Frozen Lake** is a deterministic, single-player grid-navigation puzzle. The player starts at the top-left corner of an $N\\times N$ grid and must reach the Goal tile (`G`) at the bottom-right, while avoiding Holes (`H`). There is no slipping—each action moves exactly one cell if valid. [Wikipedia](https://en.wikipedia.org/wiki/Frozen_Lake_(reinforcement_learning))

**Action Space:** Actions are case-insensitive strings containing bracketed tokens. Only the first valid token is used.  
| **Primary** | **Alias** | **Example Input**       |
|-------------|-----------|--------------------------|
| `[up]`      | `[w]`     | `go [up] now`            |
| `[down]`    | `[s]`     | `[s]`                    |
| `[left]`    | `[a]`     | `step [left]`            |
| `[right]`   | `[d]`     | `move [d] please`        |

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**                        | **Player Role** | **Reward** |
|-------------------------------------|-----------------|------------|
| Reached goal `G`                    | Player          | `+1`     |
| Stepped into hole `H` or hits wall  | Player          | `self._get_percentage_completion()` |
| Invalid move or timeout             | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple variants defined by number range and difficulty.
| **Env-ID**                      | **size** | **num_holes** | **randomize_start_goal** |
|---------------------------------|:--------------:|:--------------:|:-------------:|
| `FrozenLake-v0`                 |      `4`       |      `3`      |     `False`    |
| `FrozenLake-v0-random`          |      `4`       |      `3`      |     `True`     |
| `FrozenLake-v0-hardcore`        |      `5`       |      `6`      |     `False`    |

**Wrapper Variants:** The following suffixes can be appended to the base IDs above to change the default observation wrappers
| **Full Env-ID Format**      | **Default Wrappers**               |
|-----------------------------|------------------------------------|
| `FrozenLake-v0-{...}`         | `[LLMObservationWrapper, ActionFormattingWrapper]`          |
| `FrozenLake-v0-{...}-raw`     | `None`                             |
| `FrozenLake-v0-{...}-train`   | `[GameBoardObservationWrapper, ActionFormattingWrapper]`    |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**




<hr></details><details><summary><strong>Guess The Number [1 Player]</strong></summary><a id="guessthenumber"></a><hr>

## `Guess The Number` 
**Guess The Number** is a single-player game where the player attempts to guess a randomly chosen number within a specified range. After each guess, the player receives feedback in the form of hints ("higher" or "lower"). The player wins by guessing the number within the allowed number of turns. [Wikipedia](https://en.wikipedia.org/wiki/Bulls_and_Cows)

**Action Space:** Actions are formatted as `[number]`, where `number` is an integer guess within the allowed range. For example, `[7]` is a valid guess in basic mode; `[42]` is valid in hardcore mode.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**      | **Player Role** | **Reward** |
|--------------------|-----------------|------------|
| Guessed correctly  | Player          | `+1`       |
| Guessed incorrectly (game loss) | Player | `self._get_percentage_completion()` |
| Invalid move       | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple variants defined by number range and difficulty.
| **Env-ID**                      | **min_number** | **max_number** | **max_turns** |
|---------------------------------|:--------------:|:--------------:|:-------------:|
| `GuessTheNumber-v0`             |      `1`       |      `20`      |     `10`      |
| `GuessTheNumber-v0-hardcore`    |      `1`       |      `50`      |     `10`      |

| **Full Env-ID Format**            | **Default Wrappers**                                     |
|-----------------------------------|----------------------------------------------------------|
| `GuessTheNumber-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`       |
| `GuessTheNumber-v0-{...}-raw`     | `None`                                                   |
| `GuessTheNumber-v0-{...}-train`   | `GameBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**




<hr></details><details><summary><strong>Guess Who [1 Player]</strong></summary><a id="guesswho"></a><hr>

## `Guess Who` 
**Guess Who** is a single-player question-driven deduction game. The player attempts to determine a secret character selected by the gamemaster by asking yes-or-no questions. The gamemaster replies with "Yes", "No", or "I don't know" based on the character's attributes. The player may guess the character at any point using the format `[Name]`. [Wikipedia](https://en.wikipedia.org/wiki/Guess_Who%3F)

**Action Space:** Actions can either be a free-form question or a final guess enclosed in brackets: `[Name]`. For example, `"Does the character have blue eyes?"` asks a question; `[Tom]` submits a final guess.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**         | **Player Role**     | **Reward**                          |
|-----------------------|---------------------|-------------------------------------|
| Guessed correctly     | Player              | `+1`                                |
| Guessed incorrectly   | Player              | `self._get_percentage_completion()` |
| Game ends w/o guess   | Player              | `self._get_percentage_completion()` |

**Env-ids**: The environment supports several variants defined by wrappers and a turn limit of 20.
| **Env-ID**               | **max_turns** |
|--------------------------|:-------------:|
| `GuessWho-v0`            |      `20`     |

| **Full Env-ID Format**      | **Default Wrappers**               |
|-----------------------------|------------------------------------|
| `GuessWho-v0-{...}`         | `[LLMObservationWrapper]`          |
| `GuessWho-v0-{...}-raw`     | `None`                             |
| `GuessWho-v0-{...}-train`   | `[GameBoardObservationWrapper]`    |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to chengxy@i2r.a-star.edu.sg




<hr></details><details><summary><strong>Hangman [1 Player]</strong></summary><a id="hangman"></a><hr>

## `Hangman` 
**Hangman** is a single-player word-guessing game where the player tries to identify a hidden word by guessing one letter at a time or the entire word. The goal is to guess the word before running out of allowed incorrect guesses. In hardcore mode, words are selected from a larger vocabulary for added difficulty. [Wikipedia](https://en.wikipedia.org/wiki/Hangman_(game))

**Action Space:** Actions are strings in the format `[L]` for guessing a single letter, or `[WORD]` for guessing the entire word. For example:
- `[a]`: Guess the letter 'a'
- `[light]`: Guess the full word 'light'

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**        | **Player Role** | **Reward**                          |
|----------------------|-----------------|-------------------------------------|
| Guessed full word    | Player          | `+1`                                |
| Invalid move         | Player          | `self._get_percentage_completion()` |
| Ran out of attempts  | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports different variants based on vocabulary difficulty and wrapper configurations.
| **Env-ID**                    | **hardcore** |
|-------------------------------|:------------:|
| `Hangman-v0`                  |   `False`    |
| `Hangman-v0-hardcore`         |   `True`     |

| **Full Env-ID Format**         | **Default Wrappers**                                       |
|--------------------------------|------------------------------------------------------------|
| `Hangman-v0-{...}`             | `[LLMObservationWrapper, ActionFormattingWrapper]`         |
| `Hangman-v0-{...}-raw`         | `None`                                                     |
| `Hangman-v0-{...}-train`       | `[GameMessagesAndCurrentBoardObservationWrapper, ActionFormattingWrapper]`   |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>LightsOut [1 Player]</strong></summary><a id="lightsout"></a><hr>

## `LightsOut`
# TODO

<details><summary><strong>Lights Out [1 Player]</strong></summary><a id="lightsout"></a>

## `LightsOut`  
**Lights Out** is a classic logic puzzle game played on a grid of lights. The objective is to turn all lights off by toggling them strategically. Pressing a light toggles its state and that of its orthogonal neighbors (up/down/left/right). The player has a limited number of moves to reach the all-off state. This environment offers full rendering, grid manipulation, and progress tracking. [Wikipedia](https://en.wikipedia.org/wiki/Lights_Out_(game))

**Action Space:**  
Submit a move using a 0-indexed coordinate format: `[row col]`  
Examples:  
- `[1 2]` – Press the light at row 1, column 2  
- `[0 0]` – Press the top-left light

| **Reward Setting**        | **Player Role** | **Reward** |
|---------------------------|-----------------|-----------:|
| All lights turned off     | Player          | `+1`       |
| Moves exhausted            | Player          | `0`        |
| Invalid action            | Player          | % lights off |

**Env-ids:** The environment supports configurable board size and turn limit.

| **Env-ID**              | **size** | **max_turns** |
|-------------------------|:--------:|:-------------:|
| `LightsOut-v0`          | `5`      | `50`          |

| **Full Env-ID Format**           | **Default Wrappers**                                                         |
|----------------------------------|------------------------------------------------------------------------------|
| `LightsOut-v0-{...}`             | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `LightsOut-v0-{...}-raw`         | `None`                                                                       |
| `LightsOut-v0-{...}-train`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**

</details>




<hr></details><details><summary><strong>Logic Puzzle [1 Player]</strong></summary><a id="logicpuzzle"></a><hr>

## `Logic Puzzle` 
**Logic Puzzle** is a single-player deduction game where the player assigns correct associations across multiple categories (e.g., people, locations, times) using clues. Players interact with labeled grids and mark relationships with either 'X' (exclusion) or 'O' (inclusion). The objective is to deduce all correct associations before exhausting the allowed number of turns.

**Action Space:** Actions are strings in the format `[row col mark]`, where `mark` is either `X` (not associated) or `O` (associated). For example:
- `[wednesday Alice O]`: Marks that Wednesday is associated with Alice.
- `[tuesday Bob X]`: Marks that Tuesday is not associated with Bob.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**     | **Player Role** | **Reward** |
|-------------------|-----------------|------------|
| Completed puzzle  | Player          | `+1`       |
| Invalid move      | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple difficulty levels.
| **Env-ID**                | **difficulty** |
|---------------------------|:--------------:|
| `LogicPuzzle-v0`          | `easy`         |
| `LogicPuzzle-v0-hard`     | `hard`         |

**Wrapper Variants:** The following suffixes can be appended to the base IDs above to change the default observation wrappers
| **Full Env-ID Format**         | **Default Wrappers**                                       |
|--------------------------------|------------------------------------------------------------|
| `LogicPuzzle-v0-{...}`             | `[LLMObservationWrapper]`         |
| `LogicPuzzle-v0-{...}-raw`         | `None`                                                     |
| `LogicPuzzle-v0-{...}-train`       | `[GameMessagesAndCurrentBoardObservationWrapper]`   |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Mastermind [1 Player]</strong><a id="mastermind"></a></summary><hr>

## `Mastermind` 
**Mastermind** is a code-breaking puzzle game where the player tries to guess a hidden sequence of digits. After each guess, feedback is given in the form of black and white pegs — black indicates correct digit in correct position, white indicates correct digit in wrong position. The goal is to deduce the exact code within the given number of attempts. [Wikipedia](https://en.wikipedia.org/wiki/Mastermind_(board_game))

**Action Space:** Actions are bracketed sequences of digits. For example: `[2 1 4 5]`: A guess for a 4-digit code.

The length of the guess must match the code length.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**        | **Player Role** | **Reward** |
|----------------------|-----------------|------------|
| Correct code guessed | Player          | `+1`       |
| Invalid move         | Player          | `self._get_percentage_completion()` |
| Ran out of attempts  | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple difficulty variants.
| **Env-ID**                    | **code_length** | **num_numbers** | **max_turns** | **duplicate_numbers**  |
|-------------------------------|:---------------:|:---------------:|:-------------:|:----------------------:|
| `Mastermind-v0`               | `4`             | `6`             | `20`          | `False`                |
| `Mastermind-v0-hard`          | `4`             | `8`             | `30`          | `False`                |
| `Mastermind-v0-extreme`       | `6`             | `12`            | `50`          | `True`                 |

| **Full Env-ID Format**            | **Default Wrappers**                                       |
|-----------------------------------|------------------------------------------------------------|
| `Mastermind-v0-{...}`             | `[LLMObservationWrapper, ActionFormattingWrapper]`         |
| `Mastermind-v0-{...}-raw`         | `None`                                                     |
| `Mastermind-v0-{...}-train`       | `[GameMessagesObservationWrapper, ActionFormattingWrapper]`|

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**





<hr></details><details><summary><strong>Minesweeper [1 Player]</strong><a id="minesweeper"></a></summary><hr>

## `Minesweeper` 
**Minesweeper** is a single-player logic puzzle where the goal is to reveal all non-mine cells on a grid without triggering a mine. Clues are provided in the form of numbers representing the count of adjacent mines. Players may flag suspected mines and must use logic to navigate the board safely.

**Action Space:** Actions are strings in the format `[row col]`, i.e. `[5 6]` selects row 5, column 6

**Reward Setting**  
| **Condition**          | **Player Role** | **Reward**                          |
|------------------------|-----------------|-------------------------------------|
| All safe cells revealed| Player          | `+1`                                |
| Stepped on a mine      | Player          | `self._get_percentage_completion()` |
| Invalid move           | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports multiple grid sizes and difficulty settings.
| **Env-ID**                  | **rows** | **cols** | **num_mines** | **max_turns** |
|-----------------------------|:--------:|:--------:|:-------------:|:-------------:|
| `Minesweeper-v0`            | `8`      | `8`      | `10`          | `100`         |
| `Minesweeper-v0-small`      | `5`      | `5`      | `5`           | `100`         |
| `Minesweeper-v0-medium`     | `10`     | `10`     | `20`          | `100`         |
| `Minesweeper-v0-hard`       | `12`     | `12`     | `30`          | `100`         |

| **Full Env-ID Format**       | **Default Wrappers**                                                      |
|------------------------------|---------------------------------------------------------------------------|
| `Minesweeper-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                        |
| `Minesweeper-v0-{...}-raw`   | `None`                                                                    |
| `Minesweeper-v0-{...}-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`|

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**





<hr></details><details><summary><strong>PegJump [Single Player]</strong></summary><a id="pegjump"></a><hr>

## `PegJump`

Classic triangular peg solitaire (15 holes). Each move **jumps** one peg over an adjacent peg into an empty hole, removing the jumped peg. Finish with **exactly one peg left**.

| **Reward Setting**            | **Reward**                                     |
|-------------------------------|------------------------------------------------|
| Invalid / illegal move        | `progress = 1 − (pegs_left − 1) / 14`          |
| No moves left (>1 peg)        | same `progress` value                          |
| Solved (1 peg left)           | `1.0`                                          |

**Action Space:** `[4 1]` jump peg in hole 4 over 2 into hole 1

**Env-ids:** `initial_empty`, the hole that is initially empty

| **Env-ids**   | **initial_empty** |
|---------------|:-----------------:|
| `PegJump-v0`  |        5          |

| **Full Env-ID format** | **Default Wrappers**                                                       |
|------------------------|----------------------------------------------------------------------------|
| `PegJump-v0`           | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `PegJump-v0-raw`       | *None*                                                                     |
| `PegJump-v0-train`     | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **[guertlerlo@cfar.a-star.edu.sg](mailto:guertlerlo@cfar.a-star.edu.sg)**




<hr></details><details><summary><strong>RushHour [Single Player]</strong></summary><a id="rushhour"></a><hr>

## `RushHour`

A 6 × 6 sliding-block puzzle. Each vehicle occupies 2–3 squares and can move only **forwards (+)** or **backwards (-)** along its orientation. Slide the red car **`X`** to the exit (right edge of row 3) to win.

| **Reward Setting**            | **Reward**                              |
|-------------------------------|-----------------------------------------|
| Invalid / blocked move        | `percentage_completion` (0.0‒1.0)      |
| Puzzle solved (X exits)       | `1.0`                                   |

**Action Space:**  `[A+]` # move car A forward (toward its nose); `[B-]` # move car B backward (opposite direction)

**Env-ids** No env params.

| **Env-id**    |
|---------------|
| `RushHour-v0` |

| **Full Env-ID format** | **Default Wrappers**                                          |
|------------------------|--------------------------------------------------------------|
| `RushHour-v0`          | `LLMObservationWrapper`, `ActionFormattingWrapper`           |
| `RushHour-v0-raw`      | *None*                                                      |
| `RushHour-v0-train`    | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **guertlerlo@cfar.a-star.edu.sg**

<hr></details><details><summary><strong>Slitherlink [Single Player]</strong></summary><a id="slitherlink"></a>

## `Slitherlink`

Draw a **single continuous loop** on a rectangular dot grid so that every numbered cell is bordered by exactly that many edges.  
Toggle edges with `[h r c]` (horizontal) or `[v r c]` (vertical), where `(r,c)` indexes the **upper-left dot** of the edge.

| **Reward Setting**               | **Reward**                                                      |
|----------------------------------|-----------------------------------------------------------------|
| Invalid action / edge outside    | `progress = satisfied_clues / total_clues`                      |
| Move limit reached (unsolved)    | same `progress` value                                           |
| Puzzle solved (one loop formed)  | `1.0`                                                           |

**Action Space:** `[h 3 2]`: toggle horizontal edge above clue-cell (3,2); `[v 1 0]`: toggle vertical edge left of clue-cell (1,0)


**Env-ids**  

| **Env-ID**          |
|---------------------|
| `Slitherlink-v0`    |

| **Full Env-ID format** | **Default Wrappers**                                                       |
|------------------------|----------------------------------------------------------------------------|
| `Slitherlink-v0`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Slitherlink-v0-raw`   | *None*                                                                     |
| `Slitherlink-v0-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |



<hr></details><details><summary><strong>Secretary [Single Player]</strong></summary><a id="secretary"></a><hr>

## `Secretary`

**Secretary** is a single-player decision-making game based on the classic "Secretary Problem" or "Optimal Stopping Problem." The player observes a fixed number of hidden values one-by-one and must decide at each step whether to `[accept]` the current value or `[continue]` to the next. If the player never accepts a value, they are forced to take the final one. The goal is to pick the **maximum** value among all shown. The challenge lies in **balancing risk and opportunity**: waiting too long might mean missing the best option, while stopping too early might result in suboptimal choices. This environment is ideal for testing sequential decision-making, probabilistic reasoning, and understanding threshold strategies.

**Action Space:** Players issue commands in square brackets: `[accept]` or `[continue]`



| **Reward Setting** | **Reward**                                   |
| ------------------ | -------------------------------------------- |
| Invalid move       | `0.0` and invalid move penalty               |
| Valid game outcome | `1.0` if chosen value is maximum, else `0.0` |

**Env-ids:**
`N`specifies the number of steps

| **Env-ID**          | **N** |
| ------------------- | :---: |
| `Secretary-v0`      | `5`   |
| `Secretary-v0-long` | `10`  |

| **Full Env-ID Format**     | **Default Wrappers**                                        |
| -------------------------- | ----------------------------------------------------------- |
| `Secretary-v0-{...}`       | `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |
| `Secretary-v0-{...}-raw`   | `None`                                                      |
| `Secretary-v0-{...}-train` | `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **[guertlerlo@cfar.a-star.edu.sg](mailto:guertlerlo@cfar.a-star.edu.sg)**



<hr></details><details><summary><strong>Sokoban [1 Player]</strong></summary><a id="sokoban"></a><hr>

## `Sokoban`  
**Sokoban** is a classic single-player puzzle game where the player (a warehouse keeper) pushes boxes onto designated goal tiles within a grid-based warehouse. The player must plan moves carefully as boxes can only be pushed (not pulled), and only one box can be pushed at a time. The objective is to place all boxes on goal tiles using the fewest moves possible.

**Action Space:**  
Actions are specified using movement commands in square brackets: `[up]`, `[down]`, `[left]`, `[right]`, corresponding to the direction in which the player intends to move.

- Example moves:
  - `[up]` — move up (or push box up if adjacent)
  - `[left]` — move left

Invalid actions such as moving into a wall or trying to push two boxes simultaneously are penalized.

| **Reward Setting**         | **Player**     | **Reward**                        |
|---------------------------|----------------|------------------------------------|
| All boxes on goal tiles   | Player         | `+1`                               |
| Max steps exceeded        | Player         | `self._get_percentage_completion()`|
| Invalid move              | Player         | `self._get_percentage_completion()`|

**Env-ids:**  
Each environment variant differs by board size and layout complexity.

| **Env-ID**             | **dim_room** | **num_boxes** | **max_turns** |
|------------------------|:------------:|:-------------:|:-------------:|
| `Sokoban-v0`           | `(6,6)`      | `3`          | `30`          |
| `Sokoban-v0-medium`    | `(8,8)`      | `5`          | `50`          |


|**Full Env-ID Format**        | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
|`Sokoban-v0-{...}`            | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
|`Sokoban-v0-{...}-raw`        | `None`                                                                     |
|`Sokoban-v0-{...}-train`      | `[GameMessagesAndCurrentBoardObservationWrapper, ActionFormattingWrapper]` |

### Contact  
If you have questions or face issues with this specific environment, please reach out directly to **tim.grams339@outlook.de**



<hr></details><details><summary><strong>Sudoku [1 Player]</strong></summary><a id="sudoku"></a><hr>

## `Sudoku`  
**Sudoku** is a single-player logic-based number placement puzzle played on a 9×9 grid. The objective is to fill all empty cells with digits from 1 to 9 such that each row, column, and 3×3 subgrid contains all digits without repetition. This environment generates puzzles with a guaranteed unique solution and configurable difficulty via the number of starting clues.

**Action Space:**  
Actions are specified using a 1-indexed format in square brackets: `[row column number]`. The action represents placing `number` into the grid at `(row, column)`.  
- Example:  
  - `[5 3 7]` places the number 7 at row 5, column 3  
  - `[9 8 4]` places the number 4 at row 9, column 8  
Only valid moves that adhere to Sudoku rules are accepted.

| **Reward Setting**           | **Player**     | **Reward**                        |
|-----------------------------|----------------|-----------------------------------|
| Completed full grid         | Player         | `+1`                              |
| Failed to complete in time  | Player         | `self._get_percentage_completion()` |
| Made an invalid move        | Player         | `self._get_percentage_completion()` |

**Env-ids:**  
Each environment variant is defined by its initial clue count and max turns allowed.

| **Env-ID**           | **clues** | **max_turns** |
|----------------------|:---------:|:-------------:|
| `Sudoku-v0`          | `60`      | `100`         |
| `Sudoku-v0-medium`   | `40`      | `100`         |
| `Sudoku-v0-hard`     | `20`      | `100`         |

|**Full Env-ID Format**        | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
|`Sudoku-v0-{...}`             | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
|`Sudoku-v0-{...}-raw`         | `None`                                                                     |
|`Sudoku-v0-{...}-train`       | `[GameBoardObservationWrapper, ActionFormattingWrapper]` |

### Contact  
If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Tower of Hanoi [1 Player]</strong></summary><a id="towerofhanoi"></a><hr>

## `Tower of Hanoi` 
**Tower of Hanoi** is a classic single-player puzzle game involving three rods and a number of disks of different sizes. The player must move the stack of disks from the first rod to the third, obeying two rules: only one disk can be moved at a time, and a larger disk may never be placed on top of a smaller one. The challenge increases with the number of disks.

**Action Space:** Actions are formatted as `[from to]`, where `from` and `to` are the indices of the rods (0-based). For example:
- `[0 2]`: Move the top disk from rod 0 to rod 2.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**           | **Player Role** | **Reward** |
|--------------------------|-----------------|------------|
| Puzzle completed         | Player          | `+1`       |
| Invalid move             | Player          | `-1`       |
| Puzzle incomplete at max turns | Player   | `0`        |

**Env-ids**: The environment supports multiple variants based on the number of disks and allowed turns.
| **Env-ID**                  | **num_disks** | **max_turns** |
|-----------------------------|:-------------:|:-------------:|
| `TowerOfHanoi-v0`           |      `3`      |     `14`      |
| `TowerOfHanoi-v0-medium`    |      `4`      |     `30`      |
| `TowerOfHanoi-v0-hard`      |      `5`      |     `62`      |
| `TowerOfHanoi-v0-extreme`   |      `7`      |    `254`      |

| **Full Env-ID Format**          | **Default Wrappers**                                                         |
|---------------------------------|------------------------------------------------------------------------------|
| `TowerOfHanoi-v0-{...}`         | `[LLMObservationWrapper, ActionFormattingWrapper]`                           |
| `TowerOfHanoi-v0-{...}-raw`     | `None`                                                                       |
| `TowerOfHanoi-v0-{...}-train`   | `[GameMessagesAndCurrentBoardObservationWrapper, ActionFormattingWrapper]`   |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**




<hr></details><details><summary><strong>Three Card Monte [1 Player]</strong></summary><a id="threecardmonte"></a><hr>

## `Three Card Monte` 
# TODO




<hr></details><details><summary><strong>Twenty Questions [1 Player]</strong></summary><hr>

## `Twenty Questions` <a id="twentyquestions"></a>
**Twenty Questions** is a single-player, question-driven guessing game where the player attempts to identify a hidden object or word chosen by a gamemaster. The player may ask up to 20 yes-or-no questions before making a final guess. In hardcore mode, the game uses a more difficult vocabulary with longer or uncommon nouns. [Wikipedia](https://en.wikipedia.org/wiki/Twenty_Questions)

**Action Space:** Actions can be either a question or a final guess in brackets `[word]`. For example:
- `"Is it alive?"`: A yes-or-no question.
- `[elephant]`: A final guess for the target word.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**      | **Player Role** | **Reward** |
|--------------------|-----------------|------------|
| Guessed correctly  | Player          | `+1`       |
| Guessed incorrectly or ran out of questions | Player | `0`        |
| Invalid move       | Player          | `0`        |

**Env-ids**: The environment supports difficulty-based variants.
| **Env-ID**                      | **hardcore** |
|---------------------------------|:------------:|
| `TwentyQuestions-v0`            |   `False`    |
| `TwentyQuestions-v0-hardcore`   |   `True`     |

**Wrapper Variants:** The following suffixes can be appended to the base IDs above to change the default observation wrappers
| **Full Env-ID Format**          | **Default Wrappers**                 |
|---------------------------------|--------------------------------------|
| `TowerOfHanoi-v0-{...}`         | `[LLMObservationWrapper]`            |
| `TowerOfHanoi-v0-{...}-raw`     | `None`                               |
| `TowerOfHanoi-v0-{...}-train`   | `[GameMessagesObservationWrapper]`   |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Word Ladder [1 Player]</strong></summary><hr>

## `Word Ladder` <a id="wordladder"></a>
**Word Ladder** is a single-player puzzle game where the player transforms a start word into a target word by changing one letter at a time. Each intermediate word must be valid and differ by exactly one letter from the previous word. The game challenges the player’s vocabulary and logical reasoning. [Wikipedia](https://en.wikipedia.org/wiki/Word_ladder)

**Action Space:** Actions are strings in the format `[word]`, where `word` is the player’s guess for the next valid word in the ladder. For example:
- `[main]`: A one-letter change from a previous word like `sain`.

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**           | **Player Role** | **Reward** |
|--------------------------|-----------------|------------|
| Reached target word      | Player          | `+1`       |
| Invalid move             | Player          | `self._get_percentage_completion()` |
| Game incomplete (timeout)| Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports difficulty-based variants based on word graph connectivity.
| **Env-ID**                | **One-letter Diff Estimates** |
|---------------------------|:-----------------------------:|
| `WordLadder-v0-easy`      | `5 to 7`                      |
| `WordLadder-v0-medium`    | `8 to 12`                     |
| `WordLadder-v0-hard`      | `13 to 15`                    |

**Wrapper Variants:** The following suffixes can be appended to the base IDs above to change the default observation wrappers
| **Full Env-ID Format**          | **Default Wrappers**                 |
|---------------------------------|--------------------------------------|
| `TowerOfHanoi-v0-{...}`         | `[LLMObservationWrapper, ActionFormattingWrapper]`            |
| `TowerOfHanoi-v0-{...}-raw`     | `None`                               |
| `TowerOfHanoi-v0-{...}-train`   | `[GameMessagesObservationWrapper, ActionFormattingWrapper]`   |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Wordle [1 Player]</strong></summary><a id="wordle"></a><hr>

## `Wordle` 
**Wordle** is a single-player word-guessing game where the player attempts to deduce a hidden English word of fixed length (e.g., 5 or 7 letters) within a limited number of guesses. After each attempt, players receive structured feedback for each letter: correct and in-place (green), correct but misplaced (yellow), or incorrect (gray). [Wikipedia](https://en.wikipedia.org/wiki/Wordle)

**Action Space:** Actions must be wrapped in square brackets and consist of a guessed word of valid length. For example: `[apple]` or `[shines]`

**Reward Setting**  
The environment provides rewards based on the following conditions:
| **Condition**             | **Player Role** | **Reward**                          |
|---------------------------|-----------------|-------------------------------------|
| Guessed full word         | Player          | `+1`                                |
| Ran out of guesses        | Player          | `self._get_percentage_completion()` |
| Invalid move              | Player          | `self._get_percentage_completion()` |

**Env-ids**: The environment supports several variants based on word length, vocabulary difficulty, and guess limits.
| **Env-ID**                    | **hardcore** | **word_length** | **num_guesses** |
|-------------------------------|:------------:|:---------------:|:---------------:|
| `Wordle-v0`                   |   `False`    |       `5`       |       `6`       |
| `Wordle-v0-hardcore`          |   `True`     |       `5`       |       `6`       |
| `Wordle-v0-long`              |   `False`    |       `7`       |       `9`       |
| `Wordle-v0-long-hardcore`     |   `True`     |       `7`       |       `9`       |

| **Full Env-ID Format**          | **Default Wrappers**                                    |
|---------------------------------|---------------------------------------------------------|
| `Wordle-v0-{...}`         | `[LLMObservationWrapper, ActionFormattingWrapper]`            |
| `Wordle-v0-{...}-raw`     | `None`                                                        |
| `Wordle-v0-{...}-train`   | `[GameMessagesObservationWrapper, ActionFormattingWrapper]`   |

**Contact:** For questions or improvements, please reach out to **ananyabalehithlu@gmail.com**




<hr></details><details><summary><strong>Word Search [1 Player]</strong></summary><a id="wordsearch"></a><hr>

## `WordSearch`  
**Word Search** is a single-player puzzle game in which the player finds hidden words in a grid of letters. The player is provided a list of words to locate, and each word appears either horizontally (across) or vertically (down) in the grid. The objective is to correctly identify all word locations by specifying the start and end coordinates.

**Action Space:**  
Actions are submitted in square brackets using coordinate format: `[start_row start_col end_row end_col]`.

- **Examples**:
  - `[8 2 8 12]` — finds a word across row 8 from column 2 to 12.
  - `[3 10 9 10]` — finds a word down column 10 from row 3 to 9.

Only correctly formatted, non-repeating guesses within bounds are accepted.

| **Reward Setting**     | **Player**     | **Reward**                        |
|------------------------|----------------|-----------------------------------|
| Found all words        | Player         | `+1`                              |
| Ran out of attempts    | Player         | `self._get_percentage_completion()` |
| Invalid or repeated move | Player       | `self._get_percentage_completion()` |

**Env-ids:**  
Variants are defined by the difficulty of hidden words.

| **Env-ID**                  | **hardcore** |
|-----------------------------|:------------:|
| `WordSearch-v0`             | `False`      |
| `WordSearch-v0-hardcore`    | `True`       |

|**Full Env-ID Format**        | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
|`WordSearch-v0-{...}`         | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
|`WordSearch-v0-{...}-raw`     | `None`                                                                     |
|`WordSearch-v0-{...}-train`   | `[GameMessagesAndCurrentBoardObservationWrapper, ActionFormattingWrapper]` |

### Contact  
If you have questions or face issues with this specific environment, please reach out directly to **chengxy@i2r.a-star.edu.sg**



<hr></details>

<br>

# 2 Player


<details><summary><strong>Alquerque [2 Player]</strong></summary><a id="alquerque"></a><hr>

## `Alquerque`
**Alquerque** is a game played on an 5x5 grid.  Red pieces on the bottom two rows of the board and black pieces on the top two rows of the board.  Pieces can move forward one step along lines connecting vertices or can jump over and capture an opponent's piece provided there is an empty square on the opposite side.  Each player gets 10 points for each piece captured.  The game terminates on move 60 or when one of the players has no more pieces to move. Game idea and description take from [Gamemaster Stanford](http://gamemaster.stanford.edu/homepage/showgames.php)

**Action Space:** Moves are given in **bracketed chess-style coordinates**: `[from to]`. I.e. `[a2 a3]`

**Scoring:** capturing and enemy piece gives 10 points.

| **Reward Setting**              | Player        | Reward |
|---------------------------------|---------------|--------|
| Has higher score at termination | Winner        | `+1`   |
|                                 | Loser         | `-1`   |
| Makes an invalid move           | Offender      | `-1`   |


**Env-ids**
No env params.

| **Env-ID**     |
|----------------|
| `Alquerque-v0` |

| **Full Env-ID format** | **Default Wrappers**                                                       |
|------------------------|--------------------------------------------------------------------------- |
| `Alquerque-v0`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Alquerque-v0-raw`     | `None`                                                                     |
| `Alquerque-v0-train`   | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues, email **Guertlerlo@cfar.a-star.edu.sg**.




<hr></details><details><summary><strong>Battleship [2 Player]</strong></summary><a id="battleship"></a><hr>

## `Battleship`  
**Battleship** is a two-player turn-based strategy game played on hidden grids, where players aim to locate and sink the opposing fleet. Players take turns firing at coordinates to deduce and destroy the opponent's ships. Hits and misses are shown using 'X' and 'O' respectively. Victory is achieved by sinking all of the opponent’s ships. [Wikipedia](https://en.wikipedia.org/wiki/Battleship_(game))

**Action Space:** Specify missile target coordinates using capital letter rows and 0–9 columns inside square brackets: `[A4]`. For example, `[C5]` fires at row C, column 5.

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Sunk all opponent ships | Winner           | `+1`       |
|                         | Loser            | `-1`       |
| Made an invalid move    | Offending player | `-1`       |

**Env-ids:** Multiple grid sizes are available. All are functionally similar, differing only in board dimensions.

| **Env-ID**                 | **grid_size** |
|----------------------------|:-------------:|
| `Battleship-v0`            |     `5`       |
| `Battleship-v0-standard`   |     `10`      |
| `Battleship-v0-large`      |     `14`      |
| `Battleship-v0-extreme`    |     `20`      |

| **Full Env-ID Format**      | **Default Wrappers**                                                         |
|-----------------------------|------------------------------------------------------------------------------|
| `Battleship-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `Battleship-v0-{...}-raw`   | `None`                                                                       |
| `Battleship-v0-{...}-train` | `GameMessagesObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Breakthrough [2 Player]</strong></summary><a id="breakthrough"></a><hr>

## `Breakthrough` 
**Breakthrough** is a two-player abstract strategy game played on an n×n board. Each player starts with two rows of pawns, with White occupying rows 0 and 1 and Black occupying rows 6 and 7. The objective is to either move one of your pawns to the opponent's home row or capture all of your opponent's pawns. [Wikipedia](https://en.wikipedia.org/wiki/Breakthrough_(board_game))

**Action Space:** Actions are specified using a chess-like UCI format in brackets: `[start end]`, where `start` and `end` are the starting and ending positions of a pawn. For example, `[a2a3]` moves the pawn from square `a2` to `a3` (straight forward); `[c2b3]` moves the pawn diagonally forward from `c2` to `b3` to capture an opponent's piece.


| **Reward Setting**               | **Player Role**  | **Reward** |
| --------------------------- | ---------------- | ---------- |
| Reached opponent's home row | Winner           | `+1`       |
|                             | Loser            | `-1`       |
| Captured all opponent pawns | Winner           | `+1`       |
|                             | Loser            | `-1`       |
| Made an invalid move        | Offending Player | `-1`       |

**Env-ids**: The environment supports several variants defined by two parameters: `board_size`, which sets the dimensions of the play board (e.g., 6×6, 8×8, etc.), and `is_open`, a flag indicating whether the full board is visible (True) or hidden (False, showing only past moves).
| **Env-ID**                    | **board\_size** | **is\_open** |
| ----------------------------- | :-------------: | :----------: |
| `Breakthrough-v0`             |       `8`       |    `True`    |
| `Breakthrough-v0-tiny`        |       `4`       |    `True`    |
| `Breakthrough-v0-small`       |       `6`       |    `True`    |
| `Breakthrough-v0-large`       |       `10`      |    `True`    |
| `Breakthrough-v0-blind`       |       `8`       |    `False`   |
| `Breakthrough-v0-long`        |       `8`       |    `True`    |

|**Full Env-ID Format**        | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
|`Breakthrough-v0-{...}`       | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
|`Breakthrough-v0-{...}-raw`   | `None`                                                                     |
|`Breakthrough-v0-{...}-train` | `[GameMessagesAndCurrentBoardObservationWrapper, ActionFormattingWrapper]` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to Guertlerlo@cfar.a-star.edu.sg




<hr></details><details><summary><strong>Briscola [2 Player]</strong></summary><a id="briscola"></a><hr>

## `Briscola` 


<hr></details><details><summary><strong>Checkers [2 Player]</strong></summary><a id="checkers"></a><hr>

## `Checkers` 
**Checkers** (or **Draughts**) is a two-player strategy game played on an 8 × 8 board. Each side starts with 12 pieces; the goal is to **capture** or **block** all opponent pieces. Pieces move diagonally forward; reaching the far rank “kings” the piece, allowing backward moves as well. [Wikipedia](https://en.wikipedia.org/wiki/Draughts)

**Action Space:** Specify moves in 0-indexed row/column coordinates inside brackets: `[r1 c1 r2 c2]`. For example, `[2 1 3 2]` moves a piece from (2,1) to (3,2).

| **Reward Setting**          | **Player Role**  | **Reward** |
|-----------------------------|------------------|-----------:|
| Captured / blocked opponent | Winner           | `+1`       |
|                             | Loser            | `-1`       |
| Draw / max-turns hit        | Both             | `0`        |
| Made an invalid move        | Offending player | `-1`       |

**Env-ids:** Only one canonical variant is exposed; you may change `max_turns` when registering custom IDs.

| **Env-ID**        | **max_turns** |
|-------------------|:-------------:|
| `Checkers-v0`     |     `100`     |
| `Checkers-v0-long`|     `300`     |

| **Full Env-ID Format** | **Default Wrappers**                                                         |
|------------------------|------------------------------------------------------------------------------|
| `Checkers-v0-{...}`    | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `Checkers-v0-{...}-raw`| `None`                                                                       |
| `Checkers-v0-{...}-train`| `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Chess [2 Player]</strong></summary><a id="chess"></a><hr>

## `Chess` 

**Chess** is a classic two-player strategy game contested on an 8 × 8 board. Each side commands sixteen pieces (King, Queen, Rooks, Bishops, Knights, and Pawns) and aims to **checkmate** the opponent’s King. [Wikipedia](https://en.wikipedia.org/wiki/Chess)  

**Action Space:** Moves are written in Universal Chess Interface (UCI) format inside brackets: `[start end]`. For example, `[e2e4]` advances a pawn from *e2* to *e4*; `[g1f3]` moves the knight from *g1* to *f3*. Only the **first** bracketed move in any message is executed.

| **Reward Setting** | **Player Role** | **Reward** |
| ------------------ | --------------- | ---------- |
| Checkmated enemy   | Winner          | `+1`       |
|                    | Loser           | `-1`       |
| Stalemate / draw   | Both            | `0`        |
| Made an invalid move| Offending Player| `-1`       |

**Env-ids**: The environment supports several variants defined by two parameters: `is_open`, which determines whether the full board is shown after each move, and `max_turns`, the turn limit before an automatic draw; `show_valid` indicates whether the valid actions are shown to the model.
| **Env-ID**          | **is_open** | **max_turns** | **show_valid** |
| --------------------| :---------: | :-----------: | :------------: |
| `Chess-v0`          |   `True`    |     `100`     |     `True`     |
| `Chess-v0-long`     |   `True`    |     `250`     |     `True`     |
| `Chess-v0-blind`    |   `False`   |     `100`     |     `False`    |

| **Full Env-ID Format**  | **Default Wrappers**                                                       |
|-------------------------|----------------------------------------------------------------------------|
| `Chess-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Chess-v0-{...}-raw`    | `None`                                                                     |
| `Chess-v0-{...}-train`  | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to Guertlerlo@cfar.a-star.edu.sg




<hr></details><details><summary><strong>Chopsticks [2 Player]</strong></summary><a id="chopsticks"></a><hr>

## `Chopsticks` 
**Chopsticks** is a fast-paced finger-counting duel in which each player manages two “hands.” On your turn you may **attack** with one hand to add its fingers to an opponent hand (wrapping to 0 at 5), or **split** to redistribute your own fingers.  
The first player to leave both opponent hands at 0 wins. [Wikipedia](https://en.wikipedia.org/wiki/Chopsticks_(hand_game))  

**Action Space:** Use one of the bracketed commands below (0-indexed hand indices).  
* Attack – `[attack M O]` adds your hand **M** to opponent hand **O**.  
* Split  – `[split L R]` redistributes your fingers so **L + R** equals your current total. 

| **Reward Setting**            | **Player Role** | **Reward** |
|-------------------------------|-----------------|-----------:|
| Opponent’s hands both reach 0 | Winner          | `+1`       |
|                               | Loser           | `-1`       |
| Turn-limit / draw             | Both            | `0`        |
| Made an invalid move          | Offending player| `-1`       |

**Env-ids**: `max_turns` determines the number of turns played before the game ends in a draw.

| **Env-ID**             | **max_turns** |
|------------------------|:-------------:|
| `Chopsticks-v0`        |     `40`      |
| `Chopsticks-v0-medium` |     `60`      |
| `Chopsticks-v0-long`   |     `80`      |

| **Full Env-ID Format**      | **Default Wrappers**                                                       |
|-----------------------------|----------------------------------------------------------------------------|
| `Chopsticks-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Chopsticks-v0-{...}-raw`   | `None`                                                                     |
| `Chopsticks-v0-{...}-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to guertlerlo@cfar.a-star.edu.sg


<hr></details><details><summary><strong>ColonelBlotto [2 Player]</strong></summary><a id="colonelblotto"></a><hr>

## `ColonelBlotto`

**Colonel Blotto** is a strategic two-player zero-sum game that presents a conflict between two players (officers) who are tasks to simultaneously allocate limited units across multiple battlefields[1]. In each round, players have to allocate all of their units across all fields. The outcome of each battlefield skirmish is based on who has the most units on that battlefield gaining a point for each such majority, and the outcome of the round is set according to who has won the most battlefields. The game does not allow communications between the agents before each allocation, and only allows the player to learn and improve it's understanding of its opponent based on  previous rounds. 

**Action Space:** `[A7 B7 C6]` or `[A:7, b:7, c:6]` or `[a15]` etc. (Missing fields are filled with `0` troops.)

| **Reward Setting**         | **Player Role**  | **Reward** |
| -------------------------- | ---------------- | ---------: |
| Won the game (more rounds) | Winner           |       `+1` |
|                            | Loser            |       `-1` |
| Overall draw               | Both             |        `0` |
| Made an invalid move       | Offending player |       `-1` |

**Env‑ids**: `num_fields` specifies the number of battle fields, `num_total_units` the number of available untis each round and `num_rounds` the total number of battle rounds.

| **Env‑ID**                 | **num_fields**  | **num_total_units**   | **num_rounds**  |
| -------------------------- | :-------------: | :-------------------: | :-------------: |
| `ColonelBlotto-v0`         |       `3`       |          `20`         |       `9`       |
| `ColonelBlotto-v0-small    |       `3`       |          `20`         |       `5`       |
| `ColonelBlotto-v0-large    |       `5`       |          `50`         |       `15`      |
| `ColonelBlotto-v0-extreme` |       `7`       |          `75`         |       `25`      |

| **Full Env‑ID Format**         | **Default Wrappers**                                                       |
| ------------------------------ | -------------------------------------------------------------------------- |
| `ColonelBlotto-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `ColonelBlotto-v0-{...}-raw`   | `None`                                                                     |
| `ColonelBlotto-v0-{...}-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |


## References
__[1]__ Borel, Emile. “The Theory of Play and Integral Equations with Skew Symmetric Kernels.” *Econometrica*, vol. 21, no. 1, 1953, pp. 97–100. [https://doi.org/10.2307/1906946](https://doi.org/10.2307/1906946).







<hr></details><details><summary><strong>ConnectFour [2 Player]</strong></summary><a id="connectfour"></a><hr>

## `ConnectFour` 
**Connect Four** is a two-player connection game played on a vertical grid. Players drop discs into columns, and each disc falls to the lowest available cell. The first player to align **four discs in a row**—vertically, horizontally, or diagonally—wins. [Wikipedia](https://en.wikipedia.org/wiki/Connect_Four)  

**Action Space:** Actions are written as `[col x]`, where `x` is a valid column index (0 … `num_cols − 1`). Example: `[col 3]` (or just '[3]') drops a disc into column 3. Only the **first** bracketed token in a message is parsed.

| **Reward Setting**    | **Player Role** | **Reward** |
|-----------------------|-----------------|-----------:|
| Connected four discs  | Winner          | `+1`       |
|                       | Loser           | `-1`       |
| Draw (board full)     | Both            | `0`        |
| Made an invalid move  | Offending player| `-1`       |

**Env-ids**: The environment supports several variants defined by three parameters; `num_rows`, `num_cols`, and `is_open`, which toggles full board visibility.

| **Env-ID**                | **num_rows** | **num_cols** | **is_open** |
|---------------------------|:------------:|:------------:|:-----------:|
| `ConnectFour-v0`          | `6`          | `7`          | `True`      |
| `ConnectFour-v0-blind`    | `6`          | `7`          | `False`     |
| `ConnectFour-v0-large`    | `12`         | `15`         | `True`      |

| **Full Env-ID Format**       | **Default Wrappers**                                                        |
|------------------------------|-----------------------------------------------------------------------------|
| `ConnectFour-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                          |
| `ConnectFour-v0-{...}-raw`   | `None`                                                                      |
| `ConnectFour-v0-{...}-train` | `[GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** If you have questions or face issues with this specific environment, please reach out directly to guertlerlo@cfar.a-star.edu.sg



<hr></details><details><summary><strong>Crusade [2 Player]</strong></summary><a id="crusade"></a><hr>

## `Crusade`
**Crusade** Crusade is a game played on an 8x8 rectangular board. White pieces on the bottom two rows of the board and and black pieces on the top two rows of the board. Pieces move like chess knights. The goal of the game is to take as many of the opponent's pieces as possible. The game ends after 40 moves, and each player receives a score based on the number of pieces captured. Game idea and description take from [Gamemaster Stanford](http://gamemaster.stanford.edu/homepage/showgames.php)

**Action Space:** Legal moves are bracketed source→target in chess-knight style, using either algebraic coords (`a1`–`h8`) or numeric cell IDs (`0`–`63`): `[b1 c3] or [1 18]`


| **Reward Setting**                                                 | **Winner** | **Loser** |
|--------------------------------------------------------------------|-----------:|----------:|
| Higher score / surviving when opponent can’t move                  | `+1`       | `-1`      |
| Draw (equal score at move limit)                                   | `0`        | `0`       |
| Invalid move (bad format, not a knight move, landing on own piece) | Opponent `+1` | Offender `-1` |

**Env-ids**
No env params

| **Env-ID**        |
|-------------------|
| `Crusade-v0`      |


| **Full Env-ID Format**    | **Default Wrappers**                                                      |
|---------------------------|---------------------------------------------------------------------------|
| `Crusade-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                        |
| `Crusade-v0-{...}-raw`    | `None`                                                                    |
| `Crusade-v0-{...}-train`  | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`|

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Debate [2 Player]</strong></summary><a id="debate"></a><hr>

## `Debate` 
**Debate** pits two speakers - **Affirmative** and **Negative** - against one another on a randomly chosen topic. After a fixed number of alternating turns, a simulated jury re-votes; the side that shifts the most jurors wins.

**Action Space:** No restrictions.

| **Reward Setting**                  | **Aff./Neg. Winner** | **Loser** |
|-------------------------------------|---------------------:|----------:|
| Greater post-debate vote swing      | `+1`                 | `-1`      |
| Equal swing (draw)                  | `0`                  | `0`       |


**Env-ids**
`max_turns` turns per speaker; `jury_size` many simulated jurors; `jury_class` LLM-based jury model (`OpenRouterJury` by default); `topics_path` optional JSON file with custom debate topics.

| **Env-ID**          | **max_turns** | **jury_size** | **jury_class**   |
|---------------------|--------------:|--------------:|------------------|
| `Debate-v0`         | `6`           | `7`           | `OpenRouterJury` |
| `Debate-v0-medium`  | `12`          | `9`           | `OpenRouterJury` |
| `Debate-v0-long`    | `30`          | `13`          | `OpenRouterJury` |

**Wrapper Variants**

| **Full Env-ID Format**  | **Default Wrappers**                                   |
|-------------------------|--------------------------------------------------------|
| `Debate-v0-{...}`       | `LLMObservationWrapper`                                |
| `Debate-v0-{...}-raw`   | `None`                                                 |
| `Debate-v0-{...}-train` | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Dont Say It [2 Player]</strong></summary><a id="dontsayit"></a><hr>

## `DontSayIt` 
**Don’t Say It** is a conversational duel; each player receives a **secret word** and tries to coax the other into saying it - while trying not to say the opponents secret word.  

**Action Space:** No restriction.

| **Reward Setting**           | **Player Role** | **Reward** |
|------------------------------|-----------------|-----------:|
| Opponent says your word      | Winner          | `+1`       |
|                              | Loser           | `-1`       |
| Turn-limit / draw            | Both            | `0`        |

**Env-ids:** Variants differ by `hardcore`(includes more difficult words) and `max_turns` (the number of turns before the game is declared a draw).

| **Env-ID**                | **hardcore** | **max_turns** |
|---------------------------|:------------:|:-------------:|
| `DontSayIt-v0`            | `False`      | `20`          |
| `DontSayIt-v0-hardcore`   | `True`       | `30`          |
| `DontSayIt-v0-unlimited`  | `False`      | `None`        |

| **Full Env-ID Format**       | **Default Wrappers**                                   |
|------------------------------|--------------------------------------------------------|
| `DontSayIt-v0-{...}`         | `LLMObservationWrapper`                                |
| `DontSayIt-v0-{...}-raw`     | `None`                                                 |
| `DontSayIt-v0-{...}-train`   | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Game Of Pure Strategy (GOPS) [2 Player]</strong></summary><a id="gameofpurestrategy"></a><hr>

## `GameOfPureStrategy` 
**Game of Pure Strategy** - also called **GOPS** or *One-Card War* - is a simultaneous-bidding card duel played with the 13 cards **A–K**. Each round reveals a prize card; both players secretly bid one of their remaining cards. Higher bid wins the prize **plus** any carry-over pot from tied rounds. After all 13 prizes the higher total score wins. [Wikipedia](https://en.wikipedia.org/wiki/Game_of_Pure_Strategy)

**Action Space:** On your turn send a message containing **exactly one** bracketed card token such as `[Q]`, `[10]`, `[2]`, `[A]`, `[K]`. Only the **first** bracketed token in the message is processed, and each card may only be used once.

| **Reward Setting**                     | **Player Role** | **Reward** |
|----------------------------------------|-----------------|-----------:|
| Higher score after 13 rounds           | Winner          | `+1`       |
|                                        | Loser           | `-1`       |
| Scores tied                            | Both            | `0`        |
| Invalid move (bad token / reused card) | Offending player| `-1`       |

**Env-ids**
No instance specific parameters.

| **Env-ID**              |
|-------------------------|
| `GameOfPureStrategy-v0` |

| **Full Env-ID Format**              | **Default Wrappers**                                                       |
|-------------------------------------|----------------------------------------------------------------------------|
| `GameOfPureStrategy-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `GameOfPureStrategy-v0-{...}-raw`   | `None`                                                                     |
| `GameOfPureStrategy-v0-{...}-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>GermanWhist [2 Player]</strong></summary><a id="germanwhist"></a><hr>

## `GermanWhist`  
**German Whist** is a two-player trick-taking game played in two phases over 26 rounds. In the first 13 tricks, known as the learning phase, players draw cards from the deck after each trick. In the final 13 tricks, hands are fixed and players compete based on what they've acquired. The objective is to win the **majority of tricks (14 or more)**. Trump suit is revealed at the start and remains fixed throughout. [Wikipedia (Whist)](https://en.wikipedia.org/wiki/Whist)

**Action Space:** Specify a card to play using its 1-based index in your hand: `[play X]`. For example, `[play 3]` plays the third card in your hand.

| **Reward Setting**    | **Player Role**  | **Reward** |
|-----------------------|------------------|-----------:|
| Won ≥ 14 tricks       | Winner           | `+1`       |
|                       | Loser            | `-1`       |
| Tie (13–13)           | Both             | `0`        |
| Made an invalid move  | Offending player | `-1`       |

**Env-ids:** One canonical variant is exposed for two-player German Whist.

| **Env-ID**         | 
|--------------------|
| `GermanWhist-v0`   | 

| **Full Env-ID Format**         | **Default Wrappers**                                                         |
|--------------------------------|------------------------------------------------------------------------------|
| `GermanWhist-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `GermanWhist-v0-{...}-raw`     | `None`                                                                       |
| `GermanWhist-v0-{...}-train`   | `GameMessagesObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>HighSociety [2 Player]</strong></summary><a id="highsociety"></a><hr>

## `HighSociety` 
A streamlined, two-player take on Reiner Knizia’s **High Society**. Ten prestige cards (values 1 - 10) are auctioned, one at a time. Each auction, players secretly choose a **single money card** (1 – 11) to bid. **Higher bid** wins the prestige card **and discards** that money card. Lower bid keeps their card. Ties return both bids and the same prestige card is re-auctioned. After all ten auctions, each player adds **prestige points**; higher net-worth wins.

**Action Space** Bid your cards via `[x]` where x is the card int (i.e. 1-11)

| **Reward Setting**      | **Player Role** | **Reward** |
|-------------------------|-----------------|-----------:|
| Higher net-worth at end | Winner          | `+1`       |
|                         | Loser           | `-1`       |
| Exact tie               | Both            | `0`        |
| Invalid move            | Offender        | `-1`       |

**Env-ids**
No env params.

| **Env-ID**          |
|---------------------|
| `HighSociety-v0`    |


| **Full Env-ID Format**        | **Default Wrappers**                                                       |
|-------------------------------|----------------------------------------------------------------------------|
| `HighSociety-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `HighSociety-v0-{...}-raw`    | `None`                                                                     |
| `HighSociety-v0-{...}-train`  | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Indian Poker [2 Player]</strong></summary><a id="indianpoker"></a><hr>

## `IndianPoker` 
**Indian Poker** - also called *Blind-Man’s-Bluff* - is a two-player no-limit hold-a-single-card showdown. Each round both players ante, receive **one hidden card visible only to their opponent**, then play a single betting street with unlimited raises. Highest card at showdown—or the last player still in—wins the pot. [Wikipedia](https://en.wikipedia.org/wiki/Blind_man%27s_bluff_(poker))

**Action Space:** Send exactly one bracketed token per turn: `[check]`, `[bet X]`, `[call]`, `[raise X]`, or `[fold]` where `X` is a positive integer ≤ your chip stack. Only the **first** bracketed token in a message is parsed.

| **Reward Setting**      | **Player Role** | **Reward** |
|-------------------------|-----------------|-----------:|
| Most chips at game end  | Winner          | `+1`       |
|                         | Loser           | `-1`       |
| Invalid move            | Offending player| `-1`       |

**Env-ids**
Variants differ by `max_rounds` (the number of hands played).

| **Env-ID**               | **max_rounds** |
|--------------------------|:--------------:|
| `IndianPoker-v0`         | `5`            |
| `IndianPoker-v0-short`   | `3`            |
| `IndianPoker-v0-medium`  | `9`            |
| `IndianPoker-v0-long`    | `15`           |
| `IndianPoker-v0-extreme` | `25`           |

| **Full Env-ID Format**           | **Default Wrappers**                                                       |
|----------------------------------|----------------------------------------------------------------------------|
| `IndianPoker-v0-{...}`           | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `IndianPoker-v0-{...}-raw`       | `None`                                                                     |
| `IndianPoker-v0-{...}-train`     | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>IteratedMatchingPennies [2 Player]</strong></summary><a id="iteratedmatchingpennies"></a><hr>

## `IteratedMatchingPennies`
**Iterated Matching Pennies** is a multi-round zero-sum game between two players. Player 0 plays the **Matcher** role: they win if both players pick the same value. Player 1 plays the **Mismatcher** role: they win if the values differ. Each round, both players simultaneously choose either `[heads]` or `[tails]`. Shorthand `[h]` and `[t]` are also accepted. The player whose role aligns with the outcome wins that round. After a fixed number of rounds (default: 5), the player with the most wins is declared the overall winner.

**Action Space:**  Submit `[heads]`/`[h]`, `[tails]`/`[t]`.  

**Round Resolution Example:**  If Player 0 chooses `[heads]` and Player 1 chooses `[heads]`, Player 0 wins the round. If Player 0 chooses `[tails]` and Player 1 chooses `[heads]`, Player 1 wins the round.


| **Reward Setting**        | **Player Role** | **Reward** |
|---------------------------|-----------------|-----------:|
| Highest score at game end | Winner          | `+1`       |
|                           | Loser           | `-1`       |
| Draw Round                | Both            | `0`        |
| Invalid Move              | Invalid player  | `-1`       |

**Env-ids**
'num_rounds' the number of rounds played

| **Env-ID**                              | **num_rounds** |
|-----------------------------------------|:--------------:|
| `IteratedMatchingPennies-v0`            | `10`           |

**Wrapper Variants**

| **Full Env-ID Format**                   | **Default Wrappers**                                        |
|------------------------------------------|-------------------------------------------------------------|
| `IteratedMatchingPennies-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`          |
| `IteratedMatchingPennies-v0-{...}-raw`   | `None`                                                      |
| `IteratedMatchingPennies-v0-{...}-train` | `[GameMessagesObservationWrapper, ActionFormattingWrapper]` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**


<hr></details><details><summary><strong>IteratedPrisonersDilemma [2 Player]</strong></summary><a id="iteratedprisonersdilemma"></a><hr>

## `IteratedPrisonersDilemma (not finished)` 
**Iterated Prisoner's Dilemma** is a repeated negotiation game with 2 players. Each round consists of 3 **communication turns**, followed by 1 **decision turn**.  On decision turns, players choose to `"cooperate"` or `"defect"`. [Wikipedia](https://en.wikipedia.org/wiki/Prisoner's_dilemma)

**Action Space:**  
- Communication Turns: any message  
- Decision Turn: one of `"cooperate"` or `"defect"` (case-insensitive, quotes optional)

**Payoff Matrix:**

| Player 0 | Player 1 | Player 0 Reward | Player 1 Reward |
|----------|----------|-----------------|-----------------|
| cooperate| cooperate| `3`             | `3`             |
| cooperate| defect   | `0`             | `5`             |
| defect   | cooperate| `5`             | `0`             |
| defect   | defect   | `1`             | `1`             |


| **Reward Setting**       | **Player Role** | **Reward** |
|--------------------------|-----------------|-----------:|
| Higher score at game end | Winner          | `+1`       |
|                          | Loser           | `-1`       |
| Draw                     | Both            | `0`        |
| Invalid Move             | Culprit         | `-1`       |

**Env-ids**

| **Env-ID**                      |
|---------------------------------|
| `IteratedPrisonersDilemma-v0`  |

**Wrapper Variants**

| **Full Env-ID Format**                    | **Default Wrappers**                                   |
|-------------------------------------------|--------------------------------------------------------|
| `IteratedPrisonersDilemma-v0-{...}`       | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |
| `IteratedPrisonersDilemma-v0-{...}-raw`   | `None`                                                 |
| `IteratedPrisonersDilemma-v0-{...}-train` | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**


<hr></details><details><summary><strong>IteratedRockPaperScissors [2 Player]</strong></summary><a id="iteratedrockpaperscissors"></a><hr>

## `IteratedRockPaperScissors` 
**Iterated Rock-Paper-Scissors** is a multi-round version of the classic hand game. Players play one of `[rock]`, `[paper]`, or `[scissors]` for each round (or `[r]`, `[p]`, `[s]` as shorthand).  After 5 rounds (default), the player with the most round wins is declared the overall match winner. [Wikipedia](https://en.wikipedia.org/wiki/Rock_paper_scissors)

**Action Space:**  Submit one of `[rock]`/`[r]`, `[paper]`/`[p]`, `[scissors]`/`[s]`.  

**Round Results:**
| Player 0 | Player 1 | Outcome           | P0 Reward | P1 Reward |
|----------|----------|-------------------|-----------|-----------|
| rock     | scissors | Player 0 wins     | `+1`      | `-1`      |
| scissors | rock     | Player 1 wins     | `-1`      | `+1`      |
| same     | same     | Draw              | `0`       | `0`       |


| **Reward Setting**        | **Player Role** | **Reward** |
|---------------------------|-----------------|-----------:|
| Highest score at game end | Winner          | `+1`       |
|                           | Loser           | `-1`       |
| Draw Round                | Both            | `0`        |
| Invalid Move              | Invalid player  | `-1`       |

**Env-ids**
`num_rounds` is the number of rounds played.

| **Env-ID**                          | **num_rounds** |
|-------------------------------------|:--------------:|
| `IteratedRockPaperScissors-v0`      | `9`            |

| **Full Env-ID Format**                            | **Default Wrappers**                                                       |
|---------------------------------------------------|----------------------------------------------------------------------------|
| `IteratedRockPaperScissors-v0-{...}`              | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `IteratedRockPaperScissors-v0-{...}-raw`          | `None`                                                                     |
| `IteratedRockPaperScissors-v0-{...}-train`        | `GameMessagesObservationWrapper`, `ActionFormattingWrapper`                |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**


<hr></details><details><summary><strong>IteratedTwoThirdsAverage [2 Player]</strong></summary><a id="iteratedtwothirdsaverage"></a><hr>

## `IteratedTwoThirdsAverage` 
**Iterated Two-Thirds of the Average** is a multi-round game where both players simultaneously submit numeric guesses in each round. The target value is calculated as **two-thirds of the average** of the two guesses. The player whose guess is closest to the target wins the round. After a fixed number of rounds (default: 5), the player with the most round-wins wins the overall game.

**Action Space:**  Submit one floating-point number inside square brackets, e.g. `[42.0]`  

**Round Resolution Example:** If Player 0 guesses `20` and Player 1 guesses `80`, the target is `2/3 × (20 + 80)/2 = 66.67`. Player 1 wins the round since `|80 - 66.67| < |20 - 66.67|`.

| **Reward Setting**        | **Player Role** | **Reward** |
|---------------------------|-----------------|-----------:|
| Highest score at game end | Winner          | `+1`       |
|                           | Loser           | `-1`       |
| Draw Round                | Both            | `0`        |
| Invalid Move              | Invalid player  | `-1`       |

**Env-ids**
'num_rounds' the number of rounds played; 'min_guess', 'max_guess' the lower and upper bounds.

| **Env-ID**                             | **num_rounds** | **min_guess** | **max_guess** |
|----------------------------------------|:--------------:|:-------------:|:-------------:|
| `IteratedTwoThirdsAverage-v0`          | `10`           | `0.0`         | `100.0`       |

| **Full Env-ID Format**                                | **Default Wrappers**                                         |
|--------------------------------------------------------|------------------------------------------------------------ |
| `IteratedTwoThirdsAverage-v0-{...}`                    | `LLMObservationWrapper`, `ActionFormattingWrapper`          |
| `IteratedTwoThirdsAverage-v0-{...}-raw`                | `None`                                                      |
| `IteratedTwoThirdsAverage-v0-{...}-train`              | `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>IteratedStagHunt [2 Player]</strong></summary><a id="iteratedstaghunt"></a><hr>

## `IteratedStagHunt`

**Iterated Stag Hunt** is a two‑player social‑dilemma game that balances *trust* against *risk*. [1] In every round, players first exchange a fixed number of free‑form **conversation turns**, then simultaneously choose to hunt a **Stag** (high reward only if both cooperate) or a **Hare** (modest but safe reward).

**Action Space:**
* __Conversation phase:__ any text you like.
* __Decision phase:__ include either `[Stag]` or `[Hare]` in your message. (stag will be selected by default is '[hare]' is not found in the submitted action.)


| **Reward Setting**              | **Player Role**  | **Reward** |
| ------------------------------- | ---------------- | ---------- |
| Higher total payoff at game end | Winner           | `+1`       |
|                                 | Loser            | `-1`       |
| Equal total payoff              | Both             | `0`        |

> *Note :* Round‑level payoffs are specified by the environment parameters `mutual_stag_reward`, `mutual_hare_reward`, `single_hare_reward`, and `single_stag_reward`. If `randomize_payoff=True`, these values may change every round while preserving the usual Stag‑Hunt ordering `mutual_stag > single_hare ≥ mutual_hare > single_stag`.

**Env‑ids**: Three common presets (feel free to register your own).

| **Env‑ID**                   |**num_rounds**|**conversation_rounds**|**mutual_stag_reward**|**single_hare_reward**|**single_stag_reward**|**mutual_hare_reward**| **randomize_payoff** |
| ---------------------------- | ------------ | --------------------- | -------------------- | -------------------- | -------------------- | -------------------- | -------------------- |
| `IteratedStagHunt-v0`        | `5`          | `3`                   |  `10`                | `8`                  | `1`                  | `5`                  | `False`              |
| `IteratedStagHunt-v0-random` | `5`          | `3`                   |  `8`                 | `8`                  | `1`                  | `5`                  | `True`               |

| **Full Env‑ID Format**            | **Default Wrappers**                                   |
| --------------------------------- | ------------------------------------------------------ |
| `IteratedStagHunt-v0-{...}`       | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |
| `IteratedStagHunt-v0-{...}-raw`   | `None`                                                 |
| `IteratedStagHunt-v0-{...}-train` | `LLMObservationWrapper, `ClipCharactersActionWrapper`  |


## References
[1] Miller, Jean‑Jacques Rousseau; translated by Donald A. Cress; introduced by James (1992). *Discourse on the Origin of Inequality.* Indianapolis: Hackett Publishing. ISBN 978‑0‑87220‑150‑7.






<hr></details><details><summary><strong>Kuhn Poker [2 Player]</strong></summary><a id="kuhnpoker"></a><hr>

## `KuhnPoker` 
**Kuhn Poker** is a minimalist two-player poker variant played with the three-card deck **J Q K**. Each player antes one chip, receives a single hidden card, then takes turns **betting, checking, calling, or folding** in a single betting round. The higher card at showdown - or the last player still in - wins the pot. Despite its simplicity, Kuhn Poker is a textbook example of a zero-sum imperfect-information game with a mixed-strategy Nash equilibrium. [Wikipedia](https://en.wikipedia.org/wiki/Kuhn_poker)

**Action Space:** Send exactly one bracketed token per turn: `[Check]`, `[Bet]`, `[Call]`, or `[Fold]`.  

| **Reward Setting**         | **Player Role** | **Reward** |
|----------------------------|-----------------|-----------:|
| Highest score a turn limit | Winner          | `+1`       |
|                            | Loser           | `-1`       |
| Scores tied                | Both            | `0`        |
| Invalid move               | Offending player| `-1`       |

**Env-ids** 
`max_rounds` dictates how many hands are played before the game ends.

| **Env-ID**             | **max_rounds** |
|----------------------- |:--------------:|
| `KuhnPoker-v0`         | `5`            |
| `KuhnPoker-v0-short`   | `3`            |
| `KuhnPoker-v0-medium`  | `9`            |
| `KuhnPoker-v0-long`    | `15`           |
| `KuhnPoker-v0-extreme` | `25`           |

| **Full Env-ID Format**        | **Default Wrappers**                                                       |
|-------------------------------|----------------------------------------------------------------------------|
| `KuhnPoker-v0-{...}`          | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `KuhnPoker-v0-{...}-raw`      | `None`                                                                     |
| `KuhnPoker-v0-{...}-train`    | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**


<hr></details><details><summary><strong>LeducHoldem [2 Player]</strong></summary><a id="leducholdem"></a><hr>

## `LeducHoldem` 
# TODO


<hr></details><details><summary><strong>LeTruc [2 Player]</strong></summary><a id="letruc"></a><hr>

## `LeTruc` 
# TODO


<hr></details><details><summary><strong>Letter Auction [2 Player]</strong></summary><a id="letterauction"></a><hr>

## `LetterAuction`  
**Letter Auction** is a two-player bidding game where players compete to acquire letters through auctions. Each player starts with a fixed number of coins and takes turns bidding or passing on a revealed letter. After all letters are auctioned, players use their collected letters to form an English word. The player whose word has the highest total coin value (based on the coins spent on the letters used) wins. Ties result in a draw. [Wikipedia: Auction Game](https://en.wikipedia.org/wiki/Auction) *(conceptual reference)*

**Action Space:**  
Specify actions using one of the following bracketed formats:
- Bid for a letter: `[bid X]` (e.g., `[bid 10]`)
- Pass on the letter: `[pass]`
- Submit a final word: `[word]` (e.g., `[see]`)

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Word value is higher    | Winner           | `+1`       |
|                         | Loser            | `-1`       |
| Word value tie          | Both             | `0`        |
| Made an invalid move    | Offending player | `-1`       |

**Env-ids:** Multiple difficulty levels are exposed based on starting coin count.

| **Env-ID**                  | **starting_coins** |
|-----------------------------|:------------------:|
| `LetterAuction-v0`          | `100`              |
| `LetterAuction-v0-medium`   | `50`               |
| `LetterAuction-v0-hard`     | `25`               |

| **Full Env-ID Format**           | **Default Wrappers**                                                         |
|----------------------------------|------------------------------------------------------------------------------|
| `LetterAuction-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `LetterAuction-v0-{...}-raw`     | `None`                                                                       |
| `LetterAuction-v0-{...}-train`   | `GameMessagesObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**


<hr></details><details><summary><strong>LinesOfAction [2 Player]</strong></summary><a id="linesofaction"></a><hr>

## `LinesOfAction`

**Lines of Action (LOA)** is a classic connection game invented by Claude Soucie (popularised by Sid Sackson). Pieces start on the board’s perimeter; on every turn you move one piece **exactly** as many squares as there are pieces (either colour) in that row, column, or diagonal. You may leap over your **own** pieces but **never** over an opponent’s. Capture by landing on an enemy piece. The winner is the first player to form a single 8-neighbour-connected group of all their pieces.

**Action Space:** Submit moves as coordinate pairs (case-insensitive). Accepted forms: `e2e4`, `e2 e4`, `e2>e4`, `[e2e4]`.

| **Reward Setting**        | **Player Role** | **Reward** |
| ------------------------- | --------------- | ---------: |
| Win Game                  | Winner          |       `+1` |
| Lose Game                 | Loser           |       `-1` |
| Draw (60 moves or 3-fold) | Both            |        `0` |
| Invalid Move              | Invalid player  |       `-1` |

**Env-ids**
No env params.
| **Env-ID**         |
| ------------------ |
| `LinesOfAction-v0` |

| **Full Env-ID Format**   | **Default Wrappers**                                                       |
| ------------------------ | -------------------------------------------------------------------------- |
| `LinesOfAction-v0`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `LinesOfAction-v0-raw`   | *None*                                                                     |
| `LinesOfAction-v0-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **[guertlerlo@cfar.a-star.edu.sg](mailto:guertlerlo@cfar.a-star.edu.sg)**



<hr></details><details><summary><strong>Memory Game [2 Player]</strong></summary><a id="memorygame"></a><hr>

## `MemoryGame`  
**Memory Game** (also known as Concentration) is a two-player game played on a grid of face-down cards. Players take turns flipping two cards to find matching pairs. If the cards match, they remain face-up and the player scores a point. The game ends when all pairs have been found. The player with the most matches wins. [Wikipedia](https://en.wikipedia.org/wiki/Concentration_(card_game))

**Action Space:** Specify two cards to flip using row and column coordinates in the format `[r1 c1 r2 c2]`. For example, `[0 1 1 0]` flips the cards at (0,1) and (1,0).

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| More matched pairs      | Winner           | `+1`       |
| Fewer matched pairs     | Loser            | `-1`       |
| Equal matches (draw)    | Both             | `0`        |
| Made an invalid move    | Offending player | `-1`       |

**Env-ids:** Variants differ by grid size, increasing difficulty with larger boards.

| **Env-ID**                  | **grid_size** |
|-----------------------------|:-------------:|
| `MemoryGame-v0`             | `4`           |
| `MemoryGame-v0-medium`      | `6`           |
| `MemoryGame-v0-hard`        | `8`           |

| **Full Env-ID Format**          | **Default Wrappers**                                                         |
|---------------------------------|------------------------------------------------------------------------------|
| `MemoryGame-v0-{...}`           | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `MemoryGame-v0-{...}-raw`       | `None`                                                                       |
| `MemoryGame-v0-{...}-train`     | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Nim [2 Player]</strong></summary><a id="nim"></a><hr>

## `Nim` 
**Nim** is a classic impartial-combinatorial game played with several piles of objects. Players alternate turns; on each turn a player removes **one or more** objects from **exactly one** pile. The player who takes the **last object** wins. [Wikipedia](https://en.wikipedia.org/wiki/Nim)

**Action Space:** Provide one bracketed token `[pile_index quantity]`, e.g. `[2 3]` removes three objects from pile 2. 

| **Reward Setting**   | **Player Role** | **Reward** |
|----------------------|-----------------|-----------:|
| Took the last object | Winner          | `+1`       |
|                      | Loser           | `-1`       |
| Invalid move         | Offending player| `-1`       |

**Env-ids** 
`piles` the actual piles to be used in the game

| **Env-ID**        | **piles**          |
|-------------------|--------------------|
| `Nim-v0`          | `[3, 4, 5]`        |
| `Nim-v0-medium`   | `[4, 2, 3, 7]`     |
| `Nim-v0-large`    | `[5, 7, 9, 11, 2]` |

| **Full Env-ID Format**    | **Default Wrappers**                                                       |
|---------------------------|----------------------------------------------------------------------------|
| `Nim-v0-{...}`            | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Nim-v0-{...}-raw`        | `None`                                                                     |
| `Nim-v0-{...}-train`      | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Othello [2 Player]</strong></summary><a id="othello"></a><hr>

## `Othello`
**Othello** ( *Reversi* ) is an n × n perfect-information board game where each move “flips” enclosed opponent pieces to your colour. The goal is to finish with the **majority of pieces** showing your colour. [Wikipedia](https://en.wikipedia.org/wiki/Reversi)

**Action Space:** Submit one bracketed coordinate `[row col]` (0-indexed). A move is legal only if it flips at least one opponent piece.

| **Reward Setting**      | **Player Role** | **Reward** |
|-------------------------|-----------------|-----------:|
| More pieces at game end | Winner          | `+1`       |
|                         | Loser           | `-1`       |
| Draw                    | Both            | `0`        |
| Invalid move            | Offending player| `-1`       |

**Env-ids**
`board_size` determines the size of the game board, whilst `show_valid` indicates whether the current valid moves are shown to the player.

| **Env-ID**           | **board_size** | **show_valid** |
|----------------------|:--------------:|:--------------:|
| `Othello-v0`         | `8`            | `True`         |
| `Othello-v0-tiny`    | `4`            | `True`         |
| `Othello-v0-small`   | `6`            | `True`         |
| `Othello-v0-large`   | `10`           | `True`         |
| `Othello-v0-huge`    | `14`           | `True`         |
| `Othello-v0-extreme` | `8`            | `False`        |


| **Full Env-ID Format**        | **Default Wrappers**                                                       |
|-------------------------------|----------------------------------------------------------------------------|
| `Othello-v0-{...}`            | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Othello-v0-{...}-raw`        | `None`                                                                     |
| `Othello-v0-{...}-train`      | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Pig Dice [2 Player]</strong></summary><a id="pigdice"></a><hr>

## `PigDice`
**Pig Dice** is a press-your-luck dice race: on each turn you may **roll** a six-sided die to build a turn subtotal or **hold** to bank it - roll a **1** and you lose everything for that turn. First player to reach the target score wins. [Wikipedia](https://en.wikipedia.org/wiki/Pig_(dice_game))

**Action Space:** Submit exactly one bracketed command per turn: `[roll]` or `[hold]`.  

| **Reward Setting**     | **Player Role** | **Reward** |
|------------------------|-----------------|-----------:|
| Reached target score   | Winner          | `+1`       |
|                        | Loser           | `-1`       |
| Turn-limit             | Both            | `0`        |
| Invalid move           | Offending player| `-1`       |

**Env-ids**
`winning_score` (or traget_score) denotes which banked score needs to be reached to win. `max_turns` is after how many turns the game ends in a draw.

| **Env-ID**         | **winning_score** | **max_turns** |
|--------------------|:-----------------:|:-------------:|
| `PigDice-v0`       | `100`             | `100`         |
| `PigDice-v0-short` | `50`              | `25`          |
| `PigDice-v0-long`  | `500`             | `500`         |

| **Full Env-ID Format**        | **Default Wrappers**                                                       |
|-------------------------------|----------------------------------------------------------------------------|
| `PigDice-v0-{...}`            | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `PigDice-v0-{...}-raw`        | `None`                                                                     |
| `PigDice-v0-{...}-train`      | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>QuantumTicTacToe [2 Player]</strong></summary><a id="quantumtictactoe"></a><hr>

## `QuantumTicTacToe` 
**Quantum Tic Tac Toe** extends the classic 3 × 3 grid with quantum superposition. Each turn a player places a **spooky mark** entangling **two empty cells**. When an entanglement cycle forms, all marks in that cycle **collapse** into classical marks, potentially triggering chain reactions. First to show three classical marks in a row wins. [Wiki](https://en.wikipedia.org/wiki/Quantum_tic-tac-toe)

**Action Space:**   Submit one entangled pair per move: `[a,b]` where `a` ≠ `b` and both cells are currently uncollapsed.  

| **Reward Setting**    | **Player Role** | **Reward** |
|-----------------------|-----------------|-----------:|
| Three-in-a-row (solo) | Winner          | `+1`       |
|                       | Loser           | `-1`       |
| Draw (filled board)   | Both            | `0`        |
| Invalid move          | Offender        | `-1`       |

**Env-ids**
No env params

| **Env-ID**                |
|---------------------------|
| `QuantumTicTacToe-v0`     |


| **Full Env-ID Format**            | **Default Wrappers**                                                       |
|---------------------------------- |----------------------------------------------------------------------------|
| `QuantumTicTacToe-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `QuantumTicTacToe-v0-{...}-raw`   | `None`                                                                     |
| `QuantumTicTacToe-v0-{...}-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>ReverseTicTacToe [2 Player]</strong></summary><a id="reversetictactoe"></a><hr>

## `ReverseTicTacToe`
**ReverseTicTacToe** inverts the classic game: the goal is to **avoid** completing a line of three identical marks. If you accidentally place your third 'X' or 'O' in a row, **you lose**, and your opponent wins. [Wikipedia](https://en.wikipedia.org/wiki/Misere#Mis%C3%A9re_tic-tac-toe)

**Action Space:** Select a cell by number using square brackets, e.g. `[4]` places your mark in the center.  


| **Reward Setting**       | **Player Role** | **Reward** |
|--------------------------|-----------------|-----------:|
| Opponent created line    | Winner          | `+1`       |
| Created own line         | Loser           | `-1`       |
| Draw (full board)        | Both            | `0`        |
| Invalid move             | Offending player| `-1`       |

**Env-ids**
No env params.

| **Env-ID**                |
|---------------------------|
| `ReverseTicTacToe-v0`     |

| **Full Env-ID Format**               | **Default Wrappers**                                                       |
|--------------------------------------|----------------------------------------------------------------------------|
| `ReverseTicTacToe-v0-{...}`          | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `ReverseTicTacToe-v0-{...}-raw`      | `None`                                                                     |
| `ReverseTicTacToe-v0-{...}-train`    | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>ScenarioPlanning [2 Player]</strong></summary><a id="scenarioplanning"></a><hr>

## `ScenarioPlanning` 
**Scenario Planning** challenges two players to craft the best survival (or solution) strategy for a randomly chosen hypothetical scenario. After both strategies are submitted, an LLM-powered jury votes on which plan is more **effective, feasible, creative, and thorough**.

**Action Space:** No restrictions.


| **Reward Setting**    | **Winner** | **Loser** |
|-----------------------|-----------:|----------:|
| Jury-majority victory | `+1`       | `-1`      |
| Draw (equal votes)    | `0`        | `0`       |

**Env-ids**
`jury_size` many simulated jurors
| **Env-ID**                 | **jury_size** | **jury_class** |
|----------------------------|--------------:|----------------|
| `ScenarioPlanning-v0`      | `11`          | `OpenRouterJury` |

**Wrapper Variants**

| **Full Env-ID Format**               | **Default Wrappers**                                                       |
|--------------------------------------|----------------------------------------------------------------------------|
| `ScenarioPlanning-v0-{...}`          | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
| `ScenarioPlanning-v0-{...}-raw`      | `None`                                                                     |
| `ScenarioPlanning-v0-{...}-train`    | `[GameMessagesObservationWrapper, ActionFormattingWrapper]`                |

**Parameters**

| Name            | Type | Default | Description                                                       |
|-----------------|------|---------|-------------------------------------------------------------------|
| `jury_class`    | any  | `OpenRouterJury` | Class implementing jury logic                                 |
| `jury_size`     | int  | `5`     | Number of jurors (vote granularity vs. cost)                      |
| `scenarios_path`| str  | `None`  | Optional JSON file of custom scenarios                            |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>SimpleBlindAuction [2 Player]</strong></summary><a id="simpleblindauction"></a><hr>

## `SimpleBlindAuction` 
A concise two-phase auction game. During the **Conversation** phase, players freely chat in public for a fixed number of rounds. Subsequently during the  **Bidding** phase, players submit simultaneous **blind bids** for each item. Each player starts with the same capital and a private valuation for every item (±20 % variation). Highest **net-worth** after the auction (remaining coins + value of won items) wins.

**Action Space**  
| Phase              | Command Format                                    | Example                                    |
|--------------------|---------------------------------------------------|--------------------------------------------|
| Conversation       | Plain text                                        | `I'm eyeing the Gold Statue—thoughts?`     |
| Bidding            | `[Bid on Item X: amount]` *(positive integer)*    | `[Bid on Item 0: 250] [Bid on Item 3: 175]`|

Multiple bid tokens may appear in the same message; only bids you can afford are accepted.  
Only the **first** well-formed bid for a given item is counted.

| **Reward Setting** | **Winner(s)** | **Loser** |
|--------------------|--------------:|----------:|
| Higher net-worth   | `+1`          | `-1`      |
| Exact tie          | `0`           | `0`       |
| Invalid move       | Ofender (`-1`)|           |

Invalid bid (over budget / bad format) – offender: **`-1`**, opponent: **`0`**.

**Env-ids**
`starting_capital`: Coins each player begins with; `num_items`: Items up for auction; `conversation_rounds`: Public chat rounds before bidding; `base_item_values`: Optional fixed base values for items.
| **Env-ID**                    | **starting_capital** | **num_items** | **conversation_rounds** |
|-------------------------------|---------------------:|--------------:|------------------------:|
| `SimpleBlindAuction-v0`       | `1000`               | `5`           | `3`                     |
| `SimpleBlindAuction-v0-quick` | `750`                | `3`           | `1`                     |
| `SimpleBlindAuction-v0-rich`  | `2000`               | `5`           | `5`                     |


| **Full Env-ID Format**              | **Default Wrappers**                                   |
|-------------------------------------|--------------------------------------------------------|
| `SimpleBlindAuction-v0-{...}`       | `LLMObservationWrapper`                                |
| `SimpleBlindAuction-v0-{...}-raw`   | `None`                                                 |
| `SimpleBlindAuction-v0-{...}-train` | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |

---

### Parameters (summary)

| Name                   | Type | Default | Description                                  |
|------------------------|------|---------|----------------------------------------------|
| `starting_capital`     | int  | `1 000` | Coins each player begins with                |
| `num_items`            | int  | `5`     | Items up for auction                         |
| `conversation_rounds`  | int  | `3`     | Public chat rounds before bidding            |
| `base_item_values`     | list | `None`  | Optional fixed base values for items         |

---

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>SimpleNegotiation [2 Player]</strong></summary><a id="simplenegotiation"></a><hr>

## `SimpleNegotiation` 
**SimpleNegotiation** is a two-player barter game. Each player begins with five resources—**Wheat, Wood, Sheep, Brick, Ore**—and their own private valuation for each. Players negotiate by sending free-form messages and **structured trade commands**. After a fixed number of turns, the player whose inventory value (using their personal prices) has grown the most wins.

**Action Space**  
Send conversational text and **optionally** one command in your turn:

| Command                             | Purpose                                                                    | Example                       |
|-------------------------------------|----------------------------------------------------------------------------|-------------------------------|
| `[Offer: 3 Sheep, 2 Ore -> 5 Wood]` | Propose a trade (give → receive)                                           | `[Offer: 1 Brick -> 4 Wheat]` |
| `[Accept]`                          | Accept the current pending offer (only the recipient may do this)          | `[Accept]`                    |
| `[Deny]`                            | Reject the current pending offer (or implicitly by making a counter-offer) | `Sorry, no. [Deny]`           |

| **Reward Setting**     | **Winner** | **Loser**       |
|------------------------|-----------:|----------------:|
| Higher inventory gain  | `+1`       | `-1`            |
| Draw (equal gain)      | `0`        | `0`             |
| Invalid action         | `+1`       | `-1` (offender) |

**Env-ids**
`max_turns`: the number of turns

| **Env-ID**                   | **max_turns** |
|------------------------------|---------------|
| `SimpleNegotiation-v0`       | `10`          |
| `SimpleNegotiation-v0-short` | `6`           |
| `SimpleNegotiation-v0-long`  | `30`          |

| **Full Env-ID Format**            | **Default Wrappers**                                        |
|-----------------------------------|-------------------------------------------------------------|
| `SimpleNegotiation-v0-{...}`      | `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |
| `SimpleNegotiation-v0-{...}-raw`  | `None`                                                      |
| `SimpleNegotiation-v0-{...}-train`| `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>SimpleTak [2 Player]</strong></summary><a id="simpletak"></a><hr>

## `SimpleTak` 
**SimpleTak** is a minimalist variant of the Tak board game. Players alternate placing stones on an empty NxN grid. The first player to form an unbroken path connecting **two opposite edges** of the board wins.

**Action Space:** Submit your move using square-bracketed cell numbers: `[12]`, `[0]`, etc.  

| **Reward Setting** | **Player Role** | **Reward** |
|--------------------|-----------------|-----------:|
| Win Game           | Winner          | `+1`       |
| Lose Game          | Loser           | `-1`       |
| Draw               | Both            | `0`        |
| Invalid Move       | Invalid player  | `-1`       |

**Env-ids**
The `board_size` determines the board size ... shocking.

| **Env-ID**       | **board_size** |
|------------------|----------------|
| `Tak-v0`         | `4`            |
| `Tak-v0-medium`  | `5`            |
| `Tak-v0-large`   | `6`            |
| `Tak-v0-extreme` | `8`            |

| **Full Env-ID Format** | **Default Wrappers**                                                       |
|------------------------|----------------------------------------------------------------------------|
| `Tak-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Tak-v0-{...}-raw`     | `None`                                                                     |
| `Tak-v0-{...}-train`   | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Spelling Bee [2 Player]</strong></summary><a id="spellingbee"></a><hr>

## `SpellingBee` 
**Spelling Bee** Given a fixed set of unique letters, players alternate submitting valid English words - each **at least as long as the previous one** - until one player fails. Letter sets are drawn with frequency weighting for playability.

**Action Space:** Send exactly one bracketed word each turn, e.g. `[example]`. The word must use **only allowed letters**, be at least as long as the last word, and not repeat any previously played word.


| **Reward Setting**             | **Player Role** | **Reward** |
|--------------------------------|-----------------|-----------:|
| Opponent fails to supply word  | Winner          | `+1`       |
|                                | Loser           | `-1`       |

**Env-ids**
`num_letters` determines the size of the letter pool.

| **Env-ID**              | **num_letters** |
|-------------------------|:---------------:|
| `SpellingBee-v0`        | `7`             |
| `SpellingBee-v0-small`  | `4`             |
| `SpellingBee-v0-large`  | `10`            |

| **Full Env-ID Format**        | **Default Wrappers**                                                       |
|-------------------------------|----------------------------------------------------------------------------|
| `SpellingBee-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `SpellingBee-v0-{...}-raw`    | `None`                                                                     |
| `SpellingBee-v0-{...}-train`  | `GameMessagesObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Spite and Malice [2 Player]</strong></summary><a id="spiteandmalice"></a><hr>

## `SpiteAndMalice`  
**Spite and Malice** is a two-player competitive card game blending solitaire mechanics with strategic play. Each player tries to empty their **payoff pile** by building up shared **center piles** in ascending order. Kings act as wild cards. Players manage their hand, discard piles, and payoff pile while blocking opponents from progressing. The first to empty their payoff pile wins. [Wikipedia](https://en.wikipedia.org/wiki/Spite_and_Malice)

**Action Space:**  
Specify your move using bracketed commands:
- Draw cards: `[draw]`  
- Play card to center pile: `[play Card CenterPileIndex]` (e.g., `[play A♠ 0]`)  
- Discard card to discard pile: `[discard Card DiscardPileIndex]` (e.g., `[discard Q♠ 2]`)  

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Emptied payoff pile     | Winner           | `+1`       |
|                         | Loser            | `-1`       |
| Made an invalid move    | Offending player | `-1`       |

**Env-ids:** One canonical variant is exposed.

| **Env-ID**             |
|------------------------|
| `SpiteAndMalice-v0`    |

| **Full Env-ID Format**             | **Default Wrappers**                                                         |
|------------------------------------|------------------------------------------------------------------------------|
| `SpiteAndMalice-v0-{...}`          | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `SpiteAndMalice-v0-{...}-raw`      | `None`                                                                       |
| `SpiteAndMalice-v0-{...}-train`    | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Stratego [2 Player]</strong></summary><a id="stratego"></a><hr>

## `Stratego`  
**Stratego** is a two-player strategy game where players aim to capture their opponent's Flag or eliminate all their movable pieces. The game is played on a 10×10 grid with hidden information: piece identities are hidden until battles occur. Special pieces like Bombs, Scouts, and Spies add unique tactical depth. The game simulates full Stratego rules with movement, battle resolution, and board rendering for agent-based gameplay. [Wikipedia](https://en.wikipedia.org/wiki/Stratego)

**Action Space:** Specify your move with source and destination coordinates in square brackets: `[A0 B0]`. For example, `[D0 E0]` moves a piece from row 3, col 0 to row 4, col 0.

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Captured Flag / eliminated opponent | Winner           | `+1`       |
|                                      | Loser            | `-1`       |
| Made an invalid move                | Offending player | `-1`       |

**Env-ids:** One canonical variant is exposed for standard Stratego gameplay.

| **Env-ID**     |
|----------------|
| `Stratego-v0`  |

| **Full Env-ID Format**        | **Default Wrappers**                                                         |
|-------------------------------|------------------------------------------------------------------------------|
| `Stratego-v0-{...}`           | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `Stratego-v0-{...}-raw`       | `None`                                                                       |
| `Stratego-v0-{...}-train`     | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Tak [2 Player]</strong></summary><a id="tak"></a><hr>

## `Tak`  
**Tak** is a two-player abstract strategy game where players attempt to build a connected road of flat stones or capstones across the board. With flexible piece types and stack movement rules, players must strategically place, move, and flatten stones while preventing their opponent from doing the same. The game ends when a player completes a valid road or when the board fills up, triggering a flat-stone count tiebreaker. [Wikipedia](https://en.wikipedia.org/wiki/Tak_(game))

**Action Space:**  
Submit moves using the format:  
- Place: `[place () {(row, col): [Piece]}]`  
- Move: `[move (source_row, source_col) {(target1): [...], (target2): [...]}]`  
Examples:  
- `[place () {(0,1): [F0]}]`  
- `[move (2,2) {(2,3): [F0, F1], (2,4): [F0]}]`  

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Completed road or won by flat count | Winner  | `+1`       |
|                                      | Loser   | `-1`       |
| Made an invalid move                | Offending player | `-1` |

**Env-ids:** Variants support multiple board sizes and difficulty levels.

| **Env-ID**             | **board_size** | **stones** | **capstones** |
|------------------------|:--------------:|:----------:|:-------------:|
| `Tak-v0`          | `4`            |  `15`      |  `1`          |
| `Tak-v0-medium`        | `5`            |  `21`      |  `1`          |
| `Tak-v0-hard`          | `6`            |  `30`      |  `1`          |

| **Full Env-ID Format**      | **Default Wrappers**                                                         |
|-----------------------------|------------------------------------------------------------------------------|
| `Tak-v0-{...}`              | `LLMObservationWrapper`                        |
| `Tak-v0-{...}-raw`          | `None`                                         |
| `Tak-v0-{...}-train`        | `GameMessagesAndCurrentBoardObservationWrapper`|

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>TicTacToe [2 Player]</strong></summary><a id="tictactoe"></a><hr>

## `TicTacToe` 
**TicTacToe** ( *Noughts & Crosses* ) is a 3 × 3 grid race to align **three symbols in a row** - horizontally, vertically, or diagonally. Player 0 plays **O**, Player 1 plays **X**. [Wikipedia](https://en.wikipedia.org/wiki/Tic-tac-toe)

**Action Space:** Submit one bracketed cell index `[0-8]`, e.g. `[4]` marks the centre. Only the **first** bracketed number in the message is executed and must target an empty cell.

| **Reward Setting**      | **Player Role** | **Reward** |
|-------------------------|-----------------|-----------:|
| Formed a three-in-a-row | Winner          | `+1`       |
|                         | Loser           | `-1`       |
| Draw (board full)       | Both            | `0`        |
| Invalid move            | Offending player| `-1`       |

**Env-ids**
No env params.
| **Env-ID**    |
|---------------|
| `TicTacToe-v0`|

| **Full Env-ID Format**       | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
| `TicTacToe-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `TicTacToe-v0-{...}-raw`     | `None`                                                                     |
| `TicTacToe-v0-{...}-train`   | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>TruthAndDeception [2 Player]</strong></summary><a id="truthanddeception"></a><hr>

## `TruthAndDeception` 
**TruthAndDeception** is a two-player social deduction game. One player is the **Deceiver** (Player 0), whose goal is to convince the **Guesser** (Player 1) to choose the wrong fact from a pair of facts. After a set number of conversational turns, the Guesser selects either `[Fact 1]` or `[Fact 2]`.

**Player Roles:**  
- Player 0: **Deceiver** (knows which fact is true and aims to mislead)
- Player 1: **Guesser** (must determine which fact is correct)

**Action Space:**  No restrictions during the conversation phase; final move by Guesser: `[Fact 1]` or `[Fact 2]` (required format)

| **Reward Setting**          | **Deceiver (P0)** | **Guesser (P1)** |
|-----------------------------|------------------:|-----------------:|
| Guesser chooses correctly   | `-1`              | `+1`             |
| Guesser chooses incorrectly | `+1`              | `-1`             |
| Invalid final format        | `0`               | `-1`             |

**Env-ids**
`max_turns` the number of conversation turns.

| **Env-ID**                       | **max_turns** |
|----------------------------------|---------------|
| `TruthAndDeception-v0`           | `6`           |
| `TruthAndDeception-v0-long`      | `12`          |
| `TruthAndDeception-v0-extreme`   | `50`          |

| **Full Env-ID Format**             | **Default Wrappers**                                   |
|------------------------------------|--------------------------------------------------------|
| `TruthAndDeception-v0-{...}`       | `LLMObservationWrapper`                                |
| `TruthAndDeception-v0-{...}-raw`   | `None`                                                 |
| `TruthAndDeception-v0-{...}-train` | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**

<hr></details><details><summary><strong>Two Dollar [2 Player]</strong></summary><a id="twodollar"></a><hr>

## `TwoDollar`
**Two Dollar** Negotiation is a classic two-player bargaining game where both players must agree on how to split $2.00. Each player has secret role instructions (constraints or stylistic behaviors) unknown to the opponent, introducing asymmetric information and strategic tension. Resource: [ocw.mit.edu](https://ocw.mit.edu/courses/15-667-negotiation-and-conflict-management-spring-2001/pages/lecture-notes/)

**Action Space:** 
Players communicate freely but must include exactly one bracketed action per turn.
Examples:
- [Propose] $X.XX → offer $X.XX for self, remainder goes to opponent
- [Accept] → accept current proposal
- [Reject] → reject current proposal

Only the first valid bracketed action is executed; rationale text before the action is allowed.

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Deal accepted, role satisfied         | Both           | `+1`       |
| Reached max rounds  | Both            | `0`       |
| Made an invalid move    | Offending player | `-1`       |

**Env-ids:** 
The environment supports configurable parameters for `max_rounds`, `total_amount`, and `error_allowance`.

| **Env-ID**               | **total_amount** | **max_rounds** | **error_allowance** |
|--------------------------|------------------|----------------|---------------------|
| `TwoDollar-v0`           | `$2.00`          |`20`            | `3`                 |

| **Full Env-ID Format**             | **Default Wrappers**                                   |
|------------------------------------|--------------------------------------------------------|
| `TruthAndDeception-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`     |
| `TruthAndDeception-v0-{...}-raw`   | `None`                                                 |
| `TruthAndDeception-v0-{...}-train` | `LLMObservationWrapper`, `ClipCharactersActionWrapper` |

### Role System

Each player is secretly assigned a **role** at the start of the game. Roles introduce asymmetric information and strategic variety:

- **Enforceable Roles** → rules enforced by the environment  
  - *say_little*: Max 15 words before each action  
  - *high_tension*: Can only reduce proposals by ≤ $0.01  
  - *50_cents*, *80_cents*, *1_dollar*, etc.: Must receive at least the threshold amount or end with $0.00  
  - *x_rounds*: Must reach a deal by a certain deadline round  

- **Non-Enforceable Roles** → behavioral or stylistic prompts  
  - *battle_ax*: Aggressive competitor  
  - *dependent*: Focused on long-term relationships  
  - *public_figure*: Concerned about fairness/reputation  
  - *vanilla*: Standard negotiator with no special constraints  

**Usage:**
- By default, roles are assigned randomly:  
  ```python
  env = ta.make(env_id="TwoDollar-v0")
  env.reset(num_players=2)
  ```
- Or specify roles explicitly:
  ```python
  env = ta.make(enc_id="TwoDollar-v0", player_roles=["dependent", "50_cents"])
  env.reset(num_players=2)
  ```

### Testing

The Two Dollar environment includes a dedicated test suite (currently in `test_env.py`).  
It covers:  
- Action validation (proposal formats, accept/reject rules)  
- Role enforcement (word limits, concession limits, thresholds)  
- Turn structure and round counting  
- Game end conditions (deal accepted, timeout, invalid moves)  

Run the full suite:  
```bash
# Run all tests
python -m pytest textarena/envs/TwoDollar/test_env.py -v

# Run specific test categories
python -m pytest textarena/envs/TwoDollar/test_env.py::TestTwoDollarValidation -v
python -m pytest textarena/envs/TwoDollar/test_env.py::TestTwoDollarRoles -v
```

**Contact:** For issues or questions regarding this environment, please reach out to **charipol@amazon.com**.


<hr></details><details><summary><strong>Ultimate Tic Tac Toe [2 Player]</strong></summary><a id="ultimatetictactoe"></a><hr>

## `UltimateTicTacToe`  
**Ultimate Tic Tac Toe** adds a macro-level twist to the classic game by embedding nine micro Tic Tac Toe boards into one larger meta-game. Each move dictates where the opponent must play next. The goal is to win three micro boards in a row on the macro board. This environment enforces legal move rules, micro/macro win conditions, and strategic dynamics. [Wikipedia](https://en.wikipedia.org/wiki/Ultimate_tic-tac-toe)

**Action Space:**  
Submit a move using the format `[micro_board row col]`.  
Examples:  
- `[0 1 0]` – Mark row 1, col 0 in micro board 0  
- `[3 0 2]` – Mark row 0, col 2 in micro board 3  

| **Reward Setting**      | **Player Role**  | **Reward** |
|-------------------------|------------------|-----------:|
| Won macro board         | Winner           | `+1`       |
|                         | Loser            | `-1`       |
| Made an invalid move    | Offending player | `-1`       |

**Env-ids:** One canonical variant is exposed.

| **Env-ID**                 |
|----------------------------|
| `UltimateTicTacToe-v0`     |

| **Full Env-ID Format**               | **Default Wrappers**                                                         |
|--------------------------------------|------------------------------------------------------------------------------|
| `UltimateTicTacToe-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `UltimateTicTacToe-v0-{...}-raw`     | `None`                                                                       |
| `UltimateTicTacToe-v0-{...}-train`   | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>WildTicTacToe [2 Player]</strong></summary><a id="wildtictactoe"></a><hr>

## `WildTicTacToe` 
**WildTicTacToe** is a variant of TicTacToe where players can choose to place **either 'X' or 'O'** on any turn. You win by completing a line of **three identical symbols** (all Xs or all Os)—regardless of who placed the earlier ones. [Wikipedia](https://en.wikipedia.org/wiki/Wild_tic-tac-toe)

**Action Space:** Submit a symbol and cell number in square brackets, e.g. `[X 4]` places an **X** in the center.  

| **Reward Setting**                | **Player Role** | **Reward** |
|-----------------------------------|-----------------|-----------:|
| Completed three-in-a-row (X or O) | Winner          | `+1`       |
|                                   | Loser           | `-1`       |
| Draw (board full)                 | Both            | `0`        |
| Invalid move                      | Offending player| `-1`       |

**Env-ids**
No env params.

| **Env-ID**             |
|------------------------|
| `WildTicTacToe-v0`     |

| **Full Env-ID Format**             | **Default Wrappers**                                                       |
|------------------------------------|----------------------------------------------------------------------------|
| `WildTicTacToe-v0-{...}`           | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `WildTicTacToe-v0-{...}-raw`       | `None`                                                                     |
| `WildTicTacToe-v0-{...}-train`     | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**


<hr></details><details><summary><strong>WordChains [2 Player]</strong></summary><a id="word-chains"></a><hr>

## `WordChains` 
**WordChains** is a turn-based game where players alternate supplying valid English words. Each word must start with the last letter of the previous word, cannot be repeated, and must be a real English word. The game ends when a player fails to provide a valid word or when the maximum number of turns is reached.

**Action Space:** Submit a valid word in square brackets, e.g. `[apple]`  

| **Reward Setting**             | **Player Role** | **Reward** |
|--------------------------------|-----------------|-----------:|
| Opponent fails to supply word  | Winner          | `+1`       |
|                                | Loser           | `-1`       |

**Env-ids**
No env params.

| **Env-ID**                |
|---------------------------|
| `WordChains-v0`           |

| **Full Env-ID Format**      | **Default Wrappers**                                                       |
|---------------------------- |----------------------------------------------------------------------------|
| `WordChains-v0-{...}`       | `[LLMObservationWrapper, ActionFormattingWrapper]`                         |
| `WordChains-v0-{...}-raw`   | `None`                                                                     |
| `WordChains-v0-{...}-train` | `[GameMessagesObservationWrapper, ActionFormattingWrapper]`                |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details>


<br>

# Multi-Player



















<details><summary><strong>Briscola [2–4 Player]</strong></summary><a id="briscola"></a><hr>

## `Briscola`  
**Briscola** is a traditional Italian trick-taking card game played with a 40-card deck. Players take turns playing cards to win tricks and collect points based on card values. Trump cards beat all non-trumps, and the game ends when all cards are played. The player or team with the most total points wins. [Wikipedia](https://en.wikipedia.org/wiki/Briscola)

**Action Space:** Specify a card to play using its 1-based index in your hand: `[play X]`. For example, `[play 2]` plays the second card in hand.

| **Reward Setting**    | **Player Role**  | **Reward** |
|-----------------------|------------------|-----------:|
| Most total points     | Winner           | `+1`       |
|                       | Loser            | `-1`       |
| Made an invalid move  | Offending player | `-1`       |

**Env-ids:** Only one canonical variant is exposed for standard Briscola gameplay.

| **Env-ID**      |
|-----------------|
| `Briscola-v0`   |

| **Full Env-ID Format**     | **Default Wrappers**                                                         |
|----------------------------|------------------------------------------------------------------------------|
| `Briscola-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `Briscola-v0-{...}-raw`    | `None`                                                                       |
| `Briscola-v0-{...}-train`  | `GameMessagesObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**


<hr></details><details><summary><strong>Character Conclave [3-15 Player]</strong></summary><a id="characterconclave"></a><hr>

## `CharacterConclave` 
**Character Conclave** is a two-phase social game that tests concise communication. Players have a **fixed character budget** in the discussion phase, then cast a single vote for the most impressive participant (not themselves) after. The player(s) with the most votes win.

**Action Space:** No restrictions during the discussion phase; `[player_id]` during voting phase


**Reward Setting**
Players are ranked by the number of votes they received and the reward is linearly scaled between `+1` and `-1` (inclusive) based on the rank. 


**Env-ids**
`character_budget` determines how many characters in total can be used by each player during the discussion phase.

| **Env-ID**                       | **character_budget** |
|----------------------------------|----------------------|
| `CharacterConclave-v0`           | `1 000`              |
| `CharacterConclave-v0-long`      | `5 000`              |
| `CharacterConclave-v0-extreme`   | `10 000`             |


| **Full Env-ID Format**                   | **Default Wrappers**    |
|------------------------------------------|-------------------------|
| `CharacterConclave-v0-{...}`             | `LLMObservationWrapper` |
| `CharacterConclave-v0-{...}-raw`         | `None`                  |
| `CharacterConclave-v0-{...}-train`       | `LLMObservationWrapper` |


**Contact:** For questions or issues with this environment, email **simone.m.romeo@gmail.com**



<hr></details><details><summary><strong>Codenames [4 Player]</strong></summary><a id="codenames"></a><hr>

## `Codenames`
A 4-player word-association battle: two teams - **Red** and **Blue** - each consist of a **Spymaster** and an **Operative**. Spymasters see the secret map of the 25-word board and give one-word clues describing a number of words; Operatives guess words. First team to reveal all of its words wins - unless someone uncovers the single **Assassin**, which causes an instant loss.

**Action Space**
| Role                | Command format                                       | Example      |
|---------------------|------------------------------------------------------|-------------|
| Spymaster (P0 & P2) | `[clue N]` – one word + number                       | `[animal 3]`|
| Operative (P1 & P3) | `[word]` – guess a board word or `[pass]` your turn  | `[lion]`    |

Operatives may guess up to **N + 1** words in that turn.


| **Reward Setting**           | Winning team    | Losing team |
|------------------------------|-------------:   |------------:|
| All own words guessed first  | `+1`            | `-1`        |
| Opponent hits Assassin       | `+1`            | `-1`        |

If the gamemaster doesn't describe a word in the valid format, that teams turn is skipped.


**Env-ids**
if `hardcore` is True, a set of more difficult words is used. 

| **Env-ID**             | **hardcore** |
|------------------------|:------------:|
| `Codenames-v0`         | `False`      |
| `Codenames-v0-hardcore`| `True`       |

| **Full Env-ID Format**     | **Default Wrappers**                                                       |
|----------------------------|----------------------------------------------------------------------------|
| `Codenames-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Codenames-v0-{...}-raw`   | `None`                                                                     |
| `Codenames-v0-{...}-train` | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **ananyabalehithlu@gmail.com**



<hr></details><details><summary><strong>Golf [2–4 Player]</strong></summary><a id="golf"></a><hr>

## `Golf`  
**Golf** simulates the 6-card version of the classic card game *Golf*. Each player manages a 2×3 grid of hidden cards, aiming to minimize their final score through drawing, swapping, and revealing cards. Vertical pairs cancel each other to zero. The game ends when all cards are revealed. The lowest score wins. [Wikipedia](https://en.wikipedia.org/wiki/Golf_(card_game))

**Action Space:**  
Submit actions using one of the following formats:  
- `[draw]` – Draw a card from the face-down deck  
- `[take]` – Take the top discard card  
- `[swap X Y]` – Swap drawn card with card at row X, column Y  
- `[discard]` – Discard the drawn card (only allowed after `[draw]`)  
- `[peek X Y]` – Optional: Peek at a face-down card (if rule enabled)  
- `[knock]` – Optional: Trigger final round  

| **Reward Setting**       | **Player Role**  | **Reward** |
|--------------------------|------------------|-----------:|
| Lowest final score       | Winner           | `+1`       |
| Higher score             | Loser            | `-1`       |
| Made an invalid move     | Offending player | `-1`       |

**Env-ids:** Supports different configurations via number of cards and columns.

| **Env-ID**         | **num_cards** | **num_columns** |
|--------------------|:-------------:|:---------------:|
| `Golf-v0`          | `6`           | `3`             |
| `Golf-v0-medium`   | `9`           | `3`             |

| **Full Env-ID Format**        | **Default Wrappers**                                                         |
|-------------------------------|------------------------------------------------------------------------------|
| `Golf-v0-{...}`               | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `Golf-v0-{...}-raw`           | `None`                                                                       |
| `Golf-v0-{...}-train`         | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>Liar's Dice [2-15 Player]</strong></summary><a id="liarsdice"></a><hr>

## `LiarsDice` 
**Liar’s Dice** is a simultaneous-reveal bluffing game. Each round the active player may either **raise** the current bid `[Bid: <quantity>, <face>]` or **challenge** with `[Call]`. All dice are then revealed; the loser of the challenge removes one die. The last player with dice remaining wins.

**Action Space**

| Command | Format Example | Notes                                     |
|---------|----------------|-------------------------------------------|
| Bid     | `[Bid: 3, 4]`  | Must raise quantity **or** face (or both) |
| Call    | `[Call]`       | Challenges the previous bid               |


**Reward Setting**
Players are ranked by when they ran out of dice and the reward is linearly scaled between `+1` and `-1` (inclusive) based on the rank. Draws are not possible and invalid moves count as running out of dice. 


**Env-ids**
`num_dice` determines how many dice each player starts the game with.

| **Env-ID**            | **num_dice** |
|-----------------------|----------------------------|
| `LiarsDice-v0`        | `5` |
| `LiarsDice-v0-large`  | `12`|


| **Full Env-ID Format**     | **Default Wrappers**                                        |
|----------------------------|-------------------------------------------------------------|
| `LiarsDice-v0-{...}`       | `[LLMObservationWrapper, ActionFormattingWrapper]`          |
| `LiarsDice-v0-{...}-raw`   | `None`                                                      |
| `LiarsDice-v0-{...}-train` | `[GameMessagesObservationWrapper, ActionFormattingWrapper]` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details></details><details><summary><strong>ThreePlayerGOPS [3 Player]</strong></summary><a id="threeplayergops"></a><hr>

## `ThreePlayerGOPS`
A three-player extension of the GameOfPureStrategy game. Each round reveals a prize card (1–13). Players secretly bid one of their remaining cards (A–K). Highest bid wins the prize plus any carry-over pot; ties roll the prize into the next round. Invalid moves **eliminate** that player. If two players are eliminated at any time, the lone survivor wins. Otherwise the game runs 13 rounds, with final payouts determined by total prizes won and tie rules.

**Action Space:** Submit exactly one bid in bracketed face notation: `[A]`, `[10]`, `[Q]`, etc.  


**Reward Setting:** If two players make invalid moves, the remaining player wins. Otherwise, players are ranked by score and receive `+1`, `0`, `-1` rewards (ties result in either `+1`, `+1`, `-1` or `+1`, `-1`, `-1` depending on the type of tie).  

**Env-ids**
No env params.

| **Env-ID**                 |
|----------------------------|
| `ThreePlayerGOPS-v0`       |


| **Full Env-ID Format**             | **Default Wrappers**                                                       |
|------------------------------------|----------------------------------------------------------------------------|
| `ThreePlayerGOPS-v0-{...}`         | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `ThreePlayerGOPS-v0-{...}-raw`     | `None`                                                                     |
| `ThreePlayerGOPS-v0-{...}-train`   | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Poker (Texas Hold’em) [2-15 Player]</strong></summary><a id="poker"></a><hr>


## `Poker` 
Heads-up **Texas Hold’em** played for a fixed number of hands. Each player starts with a stack of chips, posts blinds, and competes through the usual betting rounds: **Pre-flop → Flop → Turn → River**. Win the pot by showing the best 5-card hand or by making your opponent fold.

**Action Space**

| Command                | Example            | Notes                                 |
|------------------------|--------------------|---------------------------------------|
| `[Check]`              | `[Check]`          | Only when there is no bet to call     |
| `[Call]`               | `[Call]`           | Match current bet                     |
| `[Fold]`               | `[Fold]`           | Surrender the hand                    |
| `[Bet <amt>]`          | `[Bet 100]`        | Must be ≥ big blind and within stack  |
| `[Raise <amt>]`        | `[Raise 200]`      | Adds *amt* on top of current bet      |


**Reward Setting**
At the end of the game players are ranked by how much money they have and the reward is linearly scaled between `+1` and `-1` (inclusive) based on the rank. Invalid moves instantly give you the last rank.

**Env-ids**
The is played for `num_rounds` hands. Players start with `starting_chips` many chips and at each round have to pay the `small_blind` and `big_blind`.

| **Env-ID**         | **num_rounds** | **starting_chips** | **small_blind** | **big_blind** |
|--------------------|---------------:|-------------------:|----------------:|--------------:|
| `Poker-v0`         | `5`            | `1000`             | `10`            | `20`          |
| `Poker-v0-small`   | `10`           | `1000`             | `10`            | `20`          |
| `Poker-v0-long`    | `15`           | `1000`             | `10`            | `20`          |
| `Poker-v0-extreme` | `50`           | `1000`             | `10`            | `20`          |


| **Full Env-ID Format**          | **Default Wrappers**                                                       |
|---------------------------------|----------------------------------------------------------------------------|
| `Poker-v0-{...}`                | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `Poker-v0-{...}-raw`            | `None`                                                                     |
| `Poker-v0-{...}-train`          | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**


<hr></details><details><summary><strong>SecretMafia [6-15 Player]</strong></summary><a id="secretmafia"></a><hr>

## `SecretMafia`
A classic social-deduction showdown between the **Village** and the hidden **Mafia**. Play cycles through **Night** (secret role actions) and **Day** (open discussion → vote). Villagers win by eliminating every Mafia member; Mafia win once they equal or outnumber the Village.


**Action Space**

| Phase / Role             | Command format                         | Example              |
|--------------------------|----------------------------------------|----------------------|
| **Day – Discussion**     | Free text (auto-broadcast)             | `I trust P4, vote P2`|
| **Day – Voting (all)**   | `[X]` or `[Player X]`                  | `[3]`                |
| **Night – Mafia**        | `[X]` (target to kill)                 | `[1]`                |
| **Night – Doctor**       | `[X]` (protect)                        | `[0]`                |
| **Night – Detective**    | `[X]` (investigate)                    | `[4]`                |



| **Reward Setting**           | Winning team | Losing team |
|------------------------------|-------------:|------------:|
| Village eliminates all Mafia | `+1`         | `-1`        |
| Mafia reach ≥ parity         | `+1`         | `-1`        |

If somebody makes an invalid move, they are considered eliminated.

**Env-ids**
`mafia_ratio`: Fraction of players initially assigned to Mafia; `include_special_roles`: Adds Doctor & Detective roles when enabled; `discussion_rounds`: Number of discussion turns before each day vote.

| **Env-ID**        | **mafia_ratio** | **discussion_rounds** |
|-------------------|:---------------:|:---------------------:|
| `SecretMafia-v0`  | `0.25`          | `3` |

| **Full Env-ID Format**       | **Default Wrappers**                                                       |
|------------------------------|----------------------------------------------------------------------------|
| `SecretMafia-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `SecretMafia-v0-{...}-raw`   | `None`                                                                     |
| `SecretMafia-v0-{...}-train` | `GameMessagesObservationWrapper`, `ActionFormattingWrapper`                |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Snake [2-15 Player]</strong></summary><a id="snake"></a><hr>

## `Snake` 
**Snake** is a simultaneous-move, multi-player adaptation of the classic arcade game. Each player controls a snake on a shared grid, growing by eating apples and dying on collisions. Last snake alive—or highest score at the turn limit—wins.

**Action Space:**  The direction you want to move into next: `[up]`/`[w]`, `[down]`/`[s]`, `[left]`/`[l]`, `[right]`/`[r]` .

**Reward Setting**
Players are rank by score; and the lognest surviving player is placed in the first place. Rewards are then learnerly allcated based on the rank. (i.e. for three players, the winning player with get reward `1`, the second place `0` and the third place `-1`; whilst in a four player game the first and last place will get `+1` and `-1` respecitively, whilst the second place will get `+0.5` and the third place `-0.5`). If all snakes die at the exact same time and with the same score, everybody gets 0. Importantly, invalid moves do not end the game, the culprit will just be counted as dead.

**Env-ids**
The game board is initialized as a `width`x`height` grid and will always have `num_apples` apples. If at least two snakes survive, the game will conclude after `max_turns` turns, where the surviving players will be ranked by score.

| **Env-ID**             | **width** | **height** | **num_apples** | **max_turns** |
|------------------------|:---------:|:----------:|:--------------:|:-------------:|
| `Snake-v0`             | `5`       | `5`        | `2`            | `40`          | 
| `Snake-v0-standard`    | `10`      | `10`       | `3`            | `100`         |
| `Snake-v0-large`       | `15`      | `15`       | `5`            | `250`         |


| **Full Env-ID Format**     | **Default Wrappers**                                     |
|----------------------------|----------------------------------------------------------|
| `Snake-v0-{...}`           | `LLMObservationWrapper', 'ActionFormattingWrapper`       |
| `Snake-v0-{...}-raw`       | `None`                                                   |
| `Snake-v0-{...}-train`     | `GameBoardObservationWrapper', 'ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Surround [2-15 Player]</strong></summary><a id="surround"></a><hr>

## `Surround`
**Surround** is a simultaneous-move arena game inspired by the classic “light‐cycle” mode. Each player begins on a shared grid and leaves a **solid trail** behind as they move. Crashing into a wall, any trail, or colliding head-on eliminates a snake. The **last player alive** wins - or, if everyone dies, the one(s) who lasted longest.

**Action Space:** Choose a direction each turn `[up]`/`[w]`, `[down]`/`[s]`, `[left]`/`[a]`, `[right]`/`[d]`

**Reward Setting:** Players are ranked by how long they survived and rewards are scaled linearly accordingly (in range `-1`,`+1` inclusively).   

**Env-ids**  
The board is a `width × height` grid. If >1 players remain, play stops after `max_turns`.

| **Env-ID**             | **width** | **height** | **max_turns** |
|------------------------|:---------:|:----------:|:-------------:|
| `Surround-v0`          | `5`       | `5`        | `40`          |
| `Surround-v0-small`    | `10`      | `10`       | `100`         |
| `Surround-v0-large`    | `15`      | `15`       | `250`         |

| **Full Env-ID Format**    | **Default Wrappers**                                     |
|---------------------------|----------------------------------------------------------|
| `Surround-v0-{...}`       | `LLMObservationWrapper`, `ActionFormattingWrapper`       |
| `Surround-v0-{...}-raw`   | `None`                                                   |
| `Surround-v0-{...}-train` | `GameBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details><details><summary><strong>Taboo [4-8 Player]</strong></summary><a id="taboo"></a><hr>

## `Taboo`  
**Taboo** is a team-based communication game where teams compete to guess as many words as possible. Each team has 1 Clue Giver who provide hints and 1 or more Guessers who identify secret words without the clue giver using any of the associated taboo words. Teams alternate turns with a fixed number of attempts per round. The team with the highest score after all rounds wins. [Wikipedia](https://en.wikipedia.org/wiki/Taboo_(game))

**Action Space:**  
- **Clue Giver**: Any free-text clue (excluding the target word or taboo words)  
- **Guesser**: A guess enclosed in square brackets, e.g. `[apple]`

| **Game Outcome**            | **Team Result**   | **Reward** |
|----------------------------|-------------------|-----------:|
| Highest score after max rounds | Winning team    | `+1`       |
| Tied highest score         | All tied teams    | `0`        |
| Lower score                | Losing team       | `-1`       |


**Env-ids:** Variants support different categories, round limits, and attempts per player.

| **Env-ID**                 | **max_rounds** | **max_attempts_per_player** | **categories**                   |
|----------------------------|:--------------:|:---------------------------:|----------------------------------|
| `Taboo-v0`                 | `2`            | `6`                         | `things`                         |
| `Taboo-v0-animals`         | `2`            | `6`                         | `animals`                        |
| `Taboo-v0-cars`            | `2`            | `6`                         | `cars`                           |
| `Taboo-v0-city/country`    | `2`            | `6`                         | `city/country`                   |
| `Taboo-v0-food`            | `2`            | `6`                         | `food`                           |
| `Taboo-v0-literature`      | `2`            | `6`                         | `literature`                     |
| `Taboo-v0-people`          | `2`            | `6`                         | `people`                         |
| `Taboo-v0-tv`             | `2`            | `6`                         | `tv`                             |
| `Taboo-v0-long`            | `5`            | `24`                        | `things`                         |
| `Taboo-v0-full`            | `2`            | `6`                         | `things, animals, cars, city/country, food, literature, people, tv` |

| **Full Env-ID Format**        | **Default Wrappers**                                                         |
|-------------------------------|------------------------------------------------------------------------------|
| `Taboo-v0-{...}`              | `LLMObservationWrapper`, `ActionFormattingWrapper`                           |
| `Taboo-v0-{...}-raw`          | `None`                                                                       |
| `Taboo-v0-{...}-train`        | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper`  |

**Contact:** For questions or issues with this environment, email **chengxy@i2r.a-star.edu.sg**



<hr></details><details><summary><strong>ThreePlayerTicTacToe [3 Player]</strong></summary><a id="threeplayertictactoe"></a><hr>

## `ThreePlayerTicTacToe` 
**Three-Player Tic Tac Toe** is played on a **5 × 5** grid with three symbols: Player 0 → `A`, Player 1 → `B`, Player 2 → `C`. On your turn you mark one empty cell; the first player to align **four identical symbols** horizontally, vertically, or diagonally wins.

**Action Space:** Submit the target cell index in square brackets, e.g. `[7]`.  

| **Reward Setting**           | **Player Role** | **Reward** |
|------------------------------|-----------------|-----------:|
| Completed a 4-in-a-row       | Winner          | `+1`       |
|                              | Others          | `-1`       |
| Draw (board full, no winner) | All             | `0`        |
| Invalid move                 | Offender        | `-1`       |

**Env-ids**
No env params.

| **Env-ID**                       |
|----------------------------------|
| `ThreePlayerTicTacToe-v0`        |

| **Full Env-ID Format**                 | **Default Wrappers**                                                       |
|----------------------------------------|----------------------------------------------------------------------------|
| `ThreePlayerTicTacToe-v0-{...}`        | `LLMObservationWrapper`, `ActionFormattingWrapper`                         |
| `ThreePlayerTicTacToe-v0-{...}-raw`    | `None`                                                                     |
| `ThreePlayerTicTacToe-v0-{...}-train`  | `GameMessagesAndCurrentBoardObservationWrapper`, `ActionFormattingWrapper` |

**Contact:** For questions or issues with this environment, email **guertlerlo@cfar.a-star.edu.sg**



<hr></details>

