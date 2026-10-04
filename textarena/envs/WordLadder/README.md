# Word Ladder Environment Documentation

## Overview

Word Ladder is a single-player puzzle game where the player aims to transform a starting word into a target word by changing one letter at a time. Each step must yield a valid word that differs by exactly one letter from the previous word, forming a chain from the start word to the target. The environment provides both a standard and a hardcore mode, impacting the word list difficulty. Players are guided by a prompt detailing the rules and gameplay, and their move history is displayed to track progress.

## Action Space
- **Format**: Submit the next word itself.
- **Examples**:
    - To say that the next word after "sain" is "main": `main`
- **Notes**: Submit one word at a time.

## Observation Space
**Reset Observation:**
On reset, the observation provides the initial prompt and the starting words and target words. For example:
```plaintext
[GAME] You are Player 0. You are playing Word Ladder (easy).
The objective of the game is to convert the start word to the target word by changing one letter at a time.
The start word is: man
The target word is: put
Submit one word at a time, e.g. `word`.
As you play, the history of your choices will be appended below. Use the information to win the game.
```

** Step Observation: **
After each step, the environment returns the action and the updated Word Ladder text as the observation. For example:
```plaintext
[Player 0] To form a word ladder from "man" to "put," I'll change one letter at a time, ensuring each intermediate step is still a valid word. Here's the first word in the sequence:

pan
[GAME] You've selected a valid word.
('Word Ladder History: man -> pan. Target Word: put\n',)
```

By default, the environment returns observations in the following format:
```python
{
  player_id: int : [
    (sender_id: int, message: str),
    (sender_id: int, message: str),
    ...
  ]
}
```

## Gameplay
**Word Length:** The length of the words is customizable, with a default setting of four-letter words. Both the starting and target words are of this length, with other words in the chain matching this requirement.

**Turns:** The player submits one word per turn. Each word must differ from the previous one by exactly one letter. Play continues until the target word is reached or the turn limit expires.

**Word Graph:** All words of the specified length are represented as nodes in a graph, with edges connecting words that differ by one letter. The start and target words are selected to ensure a valid path exists between them.

**Winning Condition: **The game is won when the player reaches the target word within the allowed number of turns, transforming the start word into the target word through a chain of valid single-letter changes.

## Key Rules
- **Valid Moves**:
    - The player must enter a word that:
        - Is exactly one letter different from the current word.
        - Exists within the game's word list and matches the length of the target word.

- **Invalid Moves**:
    - Entering a word that is not in the list of valid words.
    - Entering a word that does not match the target word length.

- **Incorrect Tries:**
    - Entering a word that differs by more than one letter from the current word.

## Rewards
| Outcome          | Reward for Player  |
|------------------|:------------------:|
| **Win**          |       `+1`         |
| **Lose**         |       `self._get_percentage_completion()`          |
| **Invalid Move** |       `self._get_percentage_completion()`         |

## Parameters

- `hardcore` (`bool`):
    - **Description:** Determines the type of words to spot
    - **Impact:**
        - **False:** Hidden words follow basic english.
        - **True**: Hidden words would be uncommon and challenging words.

- `word_len` (`int`):
    - **Description:** Determines the length of the words used in the word graph.
    - **Impact:** Longer words are typically more challenging. 

## Variants

| Env-id                      | Difficulty | Approximate One-Letter Differences |
|-----------------------------|:----------:|:--------:|
| `WordLadder-v0-easy`        | `Easy`     | `5 to 7`      |
| `WordLadder-v0-medium`      | `Medium`   | `8 to 12`     |
| `WordLadder-v0-hard`        | `Hard`     | `13 to 15`     |

### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg