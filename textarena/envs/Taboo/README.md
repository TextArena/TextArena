# Taboo Environment Documentation

## Overview

**Taboo** is a classic two-player word game where one player, the **Clue Giver**, provides verbal clues to help the other player, the **Guesser**, identify a secret word without using a set of forbidden "taboo" words. The game emphasizes creativity and effective communication under constraints.



## Action Space

- **Format:**
  - **Clue Giver:** Any string representing the clue, **excluding** the taboo words and the word to guess.
  - **Guesser:** Provide only the guessed word. For example: `apple`.

- **Examples:**
  - **Clue Giver:** `"It's something you might eat for breakfast."`
  - **Guesser:** `"toast"`

- **Notes:**
  - Clue Givers must avoid using any taboo words or the word to guess in their clues.
  - Guessers should reply with only their guess.


## Observation Space

### Observations

Each player receives a series of messages exchanged during the game, along with their specific roles and objectives.


**Reset Observation:**
On reset, each player receives a prompt tailored to their role. For example:

- **Clue Giver (Player 0):**
```plaintext
[Game]: You are Player 0, the Clue Giver in the Taboo game.
The word to guess is 'apple'.
Taboo words: fruit, red, pie.
Your goal is to provide clues to the Guesser without using the taboo words or the word to guess.
You have 30 turns to help the Guesser guess the word.
On your turn, simply type your clue.
```

- **Guesser (Player 1):**
```plaintext
[Game]: You are Player 1, the Guesser in the Taboo game.
Your goal is to guess the secret word based on the clues provided by the Clue Giver.
You have 30 turns to guess the word.
On your turn, reply with only your guess. For example: 'apple'.
```


**Step Observation:**
After each step, players receive the latest action taken by their opponent. For example:
```plaintext
[Clue Giver (Player 0)]: It's something you might eat for breakfast.
[Guesser (Player 1)]: toast
```


## Gameplay
- **Players**: 2
- **Roles**: Player 0 plays as the Clue Giver, Player 1 plays as the Guesser.
- **Turns**: Players alternate turns based on their roles.
- **Target Word**: The Clue Giver is assigned a secret word along with a list of taboo words that cannot be used in clues.
- **Objective**:
    - **Clue Giver**: Provide effective clues to help the Guesser identify the secret word without using any taboo words or the word itself.
    - **Guesser**: Deduce the secret word based on the clues provided by the Clue Giver.
- **Turn Limit:** The game can be configured with a maximum number of turns. If the Guesser does not correctly guess the word within this limit, the game ends.

## Key Rules
1. Clue Giver's Rules:
    - Must not use any of the taboo words or the word to guess in their clues.
    - Clues should be clear enough to help the Guesser but subtle to avoid using forbidden terms.

2. Guesser's Rules:
    - Must reply with only the guessed word (e.g., `apple`).

3. Winning Conditions:
    - **Win:** Both players win if the word is guessed correctly.
    - **Draw:** The game ends in a draw if the turn limit is reached.
    - **Invalid Move:** If a player makes an invalid move they lose with a -1 reward.

4. Game Termination:
    - The game ends immediately upon a win or an invalid move.
    - If the turn limit is reached without a correct guess, the game ends in a draw.

## Rewards

| Outcome          | Reward for Player | Reward for Opponent |
|------------------|:-----------------:|:-------------------:|
| **Win**          | `+1`              | `-1`                |
| **Draw**         |  `0`              |  `0`                |
| **Invalid Move** | `-1`              |  `0`                |


## Parameters

- `categories` (`List[str]`):
    - **Description**: Specifies the categories from which words are selected (e.g., [`"animals"`]).
    - **Impact**: Determines the pool of words and taboo words used in the game.

- `max_turns` (`int`):
    - **Description**: Sets the maximum number of turns allowed before the game ends in a draw.
    - **Impact**: Limits the duration of the game, encouraging timely clues and guesses.

- `data_path` (`str`):
    - **Description**: Path to the JSON file containing the list of words and their associated taboo words.
    - **Impact**: Allows customization of the word pool used in the game.



## Variants

| Env-id                     | max_turns  | categories                                                                 |
|----------------------------|:----------:|:--------------------------------------------------------------------------:|
| `Taboo-v0`                 | `6`        | `things`                                                                   |
| `Taboo-v0-animals`         | `6`        | `animals`                                                                  |
| `Taboo-v0-cars`            | `6`        | `cars`                                                                     |
| `Taboo-v0-city/country`    | `6`        | `city/country`                                                             |
| `Taboo-v0-food`            | `6`        | `food`                                                                     |
| `Taboo-v0-literature`      | `6`        | `literature`                                                               |
| `Taboo-v0-people`          | `6`        | `people`                                                                   |
| `Taboo-v0-tv`              | `6`        | `tv`                                                                       |
| `Taboo-v0-long`            | `24`       | `things`                                                                   |
| `Taboo-v0-full`            | `6`        | `things`,`animals`,`cars`,`city/country`,`food`,`literature`,`people`,`tv` |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to Guertlerlo@cfar.a-star.edu.sg