# Logic Puzzle Environment Documentation

## _TODO_
- can the prompt be improved?
- should we add more boards as part of increasing the difficulty?
- should there be more clues to make it easier? Maybe 5 is too little.

## Overview
The Logic Puzzle Environment is a single-player logic-based game where the player deduces the correct associations between items across multiple categories, such as people, locations, and times. The goal is to solve the puzzle by marking each item’s relationship accurately based on a set of clues. Players receive a board layout with categories on each axis and are prompted to mark relationships using ‘X’ or ‘O’ for each item’s status in the grid. The environment verifies each move, provides feedback for invalid or repeated moves, and updates the rendered board layout. Clues, player move history, and the current board state are available to assist players in working toward the puzzle’s solution within a structured and interactive gameplay environment.

## Action Space
- **Format:** Submit `row col marker`, where marker is `X` or `O`.
- **Example:** Mark the relationship between `wednesday` and `Alice` with `wednesday Alice O`.
- **Notes:** Submit one move at a time.

## Observation Space
**Reset Observation:**
On reset, the observation provides the initial prompt and the initial puzzle grid. For example:
```plaintext
[GAME] You are Player 0 in the Logic Puzzle game.
Your goal is to solve the puzzle by correctly assigning items to categories based on the clues provided.

To make a move, specify the row and column for each item in the shown tables, followed by the mark ('X' or 'O').
Use the format: 'row col X' or 'row col O', where:
- 'O' indicates the item is assigned to the category.
- 'X' indicates the item is not assigned to the category.

Example: To mark an item in the 'people_locations' grid, enter 'park Alice X' or 'park Alice O'.
Only items shown in the current grids can be marked, and you can update a cell if needed.

Note:
- You may revisit and update previously marked cells as your understanding evolves. As long as the update is a mark that is different from the previous.
- Each move will be recorded in the history.

Here are the clues to assist you:
- Alice plays soccer.
- Bob does not play tennis.
- Charlie plays tennis.
- Wednesday is not Charlie's day.
- Bob plays basketball on Monday.

Current state of the puzzle:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday            |           |           |
monday               |           |           |
tuesday              |           |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
```

**Step Observations:**
After each step, the environment returns the action and the updated puzzle grid as the observation. For example:
```plaintext
[Player 0] Let's analyze the clues step by step to fill in the grids.

1. **Alice plays soccer.**
   - This means Alice is assigned to the soccer category.

2. **Bob does not play tennis.**
   - This means we cannot mark Bob under tennis.

3. **Charlie plays tennis.**
   - This means Charlie is assigned to the tennis category.

4. **Wednesday is not Charlie's day.**
   - Since Charlie does not play on Wednesday, we can eliminate Wednesday for Charlie.

5. **Bob plays basketball on Monday.**
   - This means Bob is assigned to basketball on Monday.

Now, let's fill in the grids based on these clues.

1. For Alice:
   - She plays soccer, so I will mark her under soccer.
   - Therefore, I will make the move `tuesday Alice O`.

2. For Charlie:
   - He plays tennis, but cannot be assigned to Wednesday. Thus, he can only be assigned to Monday or Tuesday for tennis.
   - Since Monday is taken by Bob (who plays basketball), Charlie must be assigned to tennis on Tuesday.
   - Therefore, I will make the move `tuesday Charlie O`.

3. For Bob:
   - He plays basketball on Monday, which we can now mark. This means he cannot play on Tuesday or Wednesday for tennis.
   - Therefore, I will make the move `monday Bob O`.

Now, let's execute these moves:

1. Mark Alice for soccer on Tuesday:
   - `tuesday Alice O`

2. Mark Bob for basketball on Monday:
   - `monday Bob O`

3. Mark Charlie for tennis on Tuesday:
   - `tuesday Charlie O`

Updating the grid:
- Alice is assigned soccer on Tuesday.
- Bob is assigned basketball on Monday.
- Charlie is assigned tennis on Tuesday.

Here are the moves:

\```
tuesday Alice O
monday Bob O
tuesday Charlie O
\```

Now let's make these moves.

**Final Moves:**
1. `tuesday Alice O`
2. `monday Bob O`
3. `tuesday Charlie O`
[GAME] tuesday Charlie O is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday            |           |           |
monday               |           |           |
tuesday        O     |           |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] tuesday Alice O is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday            |           |           |
monday               |           |           |
tuesday        O     |     O     |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] wednesday Alice X is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday            |     X     |           |
monday               |           |           |
tuesday        O     |     O     |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] monday Bob O is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday            |     X     |           |
monday               |           |     O     |
tuesday        O     |     O     |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] monday Charlie X is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday            |     X     |           |
monday         X     |           |     O     |
tuesday        O     |     O     |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] wednesday Charlie X is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday      X     |     X     |           |
monday         X     |           |     O     |
tuesday        O     |     O     |           |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] tuesday Bob X is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday      X     |     X     |           |
monday         X     |           |     O     |
tuesday        O     |     O     |     X     |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] monday Alice X is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday      X     |     X     |           |
monday         X     |     X     |     O     |
tuesday        O     |     O     |     X     |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
[GAME] wednesday Bob X is valid. Game Board:

==============================================
                  day_people
==============================================
            Charlie  |   Alice   |    Bob    |
----------------------------------------------
wednesday      X     |     X     |     X     |
monday         X     |     X     |     O     |
tuesday        O     |     O     |     X     |
==============================================

=======================================================
                       day_sport
=======================================================
              soccer    |  basketball  |    tennis    |
-------------------------------------------------------
wednesday               |              |              |
monday                  |              |              |
tuesday                 |              |              |
=======================================================
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
**Board Configuration:** The game begins with a grid layout displaying various items across categories like people, locations, and times, depending on the puzzle’s difficulty. Each category pair forms a grid where the player marks items to establish their relationships based on given clues. Items are initially unmarked, allowing the player to deduce correct associations using a process of elimination and logical inference.

**Turns:** Players mark cells with `X` or `O` using `row col mark`, where row and column are labels in the current grids.

**Objective:** To solve the puzzle, the player must correctly associate all items in line with the clues provided. By interpreting and applying these clues, the player can gradually deduce the relationships and fill the grid with accurate marks.

**Winning Condition:** The game is won when the player completes all item-category associations accurately, consistent with the provided solution. Feedback is provided when all marks align correctly, confirming the player has solved the puzzle.

## Key Rules

- **Valid Moves:**
    - Each move follows `row col mark`.
    - Use `X` to exclude or `O` to include an item.
    - Example moves include `Alice park X` or `Bob school O`.
    - It is possible for the player to revisit a past move, as long as it is changing it to a different marker.

- **Invalid Moves:**
    - Selecting a cell that does not exist within the grid’s row or column limits.
    - Re-entering a mark for an item that already has the same value.
    - Providing a command that does not follow `row col mark` or uses an unsupported marker.

## Rewards
| Outcome          | Reward for Player  |
|------------------|:------------------:|
| **Win**          |       `+1`         |
| **Lose**         |       `self._get_percentage_completion()`         |
| **Invalid Move** |       `self._get_percentage_completion()`         |

## Variants

| Env-id                    |   difficulty   |
|---------------------------|:--------------:|
| `LogicPuzzle-v0`        |    `easy`      |
| `LogicPuzzle-v0-hard`   |    `hard`      |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg