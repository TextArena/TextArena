# Logic Puzzle

Work out which person goes with which item in each of two other categories by marking grids with O and X from a short
list of clues ([rules](https://en.wikipedia.org/wiki/Logic_puzzle)). Easy puzzles state facts directly; hard puzzles
use conditional clues.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LogicPuzzle-v0` | `difficulty="easy"` |
| `LogicPuzzle-v0-hard` | `difficulty="hard"` |

Append `-mdp` to any ID for the state-complete variant (e.g. `LogicPuzzle-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("LogicPuzzle-v0", difficulty=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, one puzzle of the chosen difficulty is drawn from `game_board_clues.jsonl`, which holds 20 easy and 20
  hard puzzles. Each puzzle has three categories of three items: the people Alice, Bob, and Charlie, plus one pair
  of locations and times, cars and fuels, foods and drinks, or sports and days. Each comes with five clues. Easy
  clues are mostly direct facts ("Bob drives a blue car."). Hard clues are conditionals and relations ("If Alice
  drives a gasoline car, then Bob's car must be blue.").
- Every puzzle has exactly one solution; the tests prove it by checking a formal reading of every clue against all
  36 possible assignments.
- The board has two 3×3 grids. One category, chosen at random, labels the rows of both grids; each of the other two
  labels the columns of one grid, in shuffled order.
- Mark a cell `O` if its row item and column item belong together and `X` if they do not. Each row and each column of
  a grid has exactly one `O`. You can change a mark by marking the cell with the other symbol; repeating a cell's
  current mark is invalid.
- You win when all 18 cells hold the correct mark, including an `X` in every non-matching cell. Marks are not checked
  one by one, so a wrong mark is only revealed by the game not ending.
- Every submission uses one turn, whether it holds one mark or several, and the game ends after `max_turns`
  submissions.
- An unknown label, a repeated mark, or a malformed reply makes the whole submission invalid, and none of its marks
  are applied. If the row and column labels are swapped, the feedback shows the correct order. Two invalid
  submissions in a row end the game.

## Actions

Reply with `row col O` or `row col X`: a row label, a column label from the same grid, and the mark (labels and marks
are case-insensitive). Separate several marks with commas to submit them together.

Examples, for a board whose rows are foods and whose `food_people` grid has people as columns: `pizza alice O`, or
`pizza alice O, pizza bob X, pizza charlie X`.

## Observations

The player first receives the rules, an example built from a cell of the actual board, the win condition, and the
turn limit. Before every move, the player sees both grids (named `rowcategory_columncategory`, such as `food_people`)
with the marks placed so far, followed by the clues. After an accepted submission, the player gets one confirmation
per mark, such as `Marked 'pizza alice O'.`, which does not say whether the mark is correct.

## Rewards

| Outcome | Reward |
| --- | --- |
| Every cell marked correctly | `1` |
| `max_turns` submissions made | Fraction of the 18 cells whose mark matches the solution |
| Second consecutive invalid submission | Fraction of the 18 cells whose mark matches the solution |

## Parameters

- `difficulty` (default `"easy"`): `"easy"` or `"hard"`, the set of bundled puzzles to draw from.
- `max_turns` (default `30`): the maximum number of submissions.

## Notes

- With only 40 bundled puzzles over four category sets, the same puzzles recur often across episodes.
- The formal clue readings live in `test_env.py` (`CLUE_LOGIC`). A new or edited clue needs a matching entry, which
  keeps every bundled puzzle provably unique.
