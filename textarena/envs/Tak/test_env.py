"""Offline, deterministic tests for the Tak environment.

Tak is a two-player abstract game where you win by connecting two opposite edges
with a road of flat stones/capstones. On a 3x3 board, Player 0 can build a
vertical road in column 0 (rows 0,1,2) while Player 1 harmlessly builds in
column 2. Actions use the ``place () {(r,c): [F0]}`` format.
"""

import re

import pytest

from textarena.envs.Tak.env import TakEnv


def _fresh(board_size=3, stones=10, capstones=1, max_turns=100):
    env = TakEnv(board_size=board_size, stones=stones, capstones=capstones, max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def _play(env, actions):
    done = False
    for action in actions:
        assert not done, "game ended before the scripted line finished"
        done, _ = env.step(action)
        assert env.state.error_count == 0, f"unexpected invalid move: {action}"
    return done


def test_reset_structure():
    env = _fresh()
    assert len(env.board) == 3 and all(len(r) == 3 for r in env.board)
    assert all(cell == [] for row in env.board for cell in row)
    assert env.players[0]["stones"] == 10 and env.players[0]["capstones"] == 1
    assert env.game_state["move_count"] == 0
    assert env.state.current_player_id == 0


def test_opening_placement_uses_opponents_flat_and_reserve():
    env = _fresh()
    done, _ = env.step("place () {(0,0): [F1]}")
    assert not done
    assert env.board[0][0] == ["F1"]
    assert env.players[1]["stones"] == 9
    assert env.players[0]["stones"] == 10
    assert env.game_state["move_count"] == 1
    assert env.state.current_player_id == 1
    assert env.get_board_str() == env._render_board()


@pytest.mark.parametrize(
    "action",
    [
        "place () {(0,0): [F0]}",
        "place () {(0,0): [W1]}",
        "place () {(0,0): [C1]}",
        "move (0,0) {(0,1): [F0]}",
    ],
)
def test_opening_rejects_self_pieces_nonflats_and_movement(action):
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(action)

    assert not done
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]
    assert env.game_state["move_count"] == 0


def test_malformed_placement_is_invalid_without_mutation():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step("place () {(0,0): []}")

    assert not done
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"board_size": 2, "stones": 10, "capstones": 1},
        {"board_size": 9, "stones": 10, "capstones": 1},
        {"board_size": 3, "stones": 0, "capstones": 1},
        {"board_size": 3, "stones": 10, "capstones": 1, "max_turns": 0},
        {"board_size": 3, "stones": 10, "capstones": 1, "max_turns": True},
    ],
)
def test_unplayable_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        TakEnv(**kwargs)


def test_huge_source_coordinate_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"move ({'9' * 5000},0) {{(0,0): [F0]}}")

    assert not done
    assert env.state.error_count == 1
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]


def test_huge_allocation_coordinate_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"place () {{({'9' * 5000},0): [F0]}}")

    assert not done
    assert env.state.error_count == 1
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]


def test_duplicate_allocation_target_is_rejected():
    env = _fresh()

    done, _ = env.step("place () {(0,0): [F0], (0,0): [F0]}")

    assert not done
    assert env.board[0][0] == []
    assert env.players[0]["stones"] == 10


def test_bad_format_is_invalid():
    env = _fresh()
    done, _ = env.step("place a stone somewhere")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("place a stone somewhere")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice
    assert "with rows and columns from 0 to 2," in env.action_format

    def example(game):
        return re.search(r"for example '([^']+)'", game.action_format).group(1)

    opening = _fresh()
    assert example(opening) == "place () {(1,2): [F1]}"  # the opening places the opponent's flat
    _play(opening, [example(opening)])

    midgame = _fresh()
    _play(midgame, ["place () {(0,0): [F1]}", "place () {(0,1): [F0]}"])
    assert example(midgame) == "place () {(1,2): [F0]}"
    _play(midgame, [example(midgame)])


def test_placement_on_occupied_square_rejected():
    env = _fresh()
    env.step("place () {(0,0): [F1]}")  # P0 places P1's opening flat.
    # P1 tries to place onto the same occupied square.
    done, _ = env.step("place () {(0,0): [F0]}")
    assert not done
    assert env.state.error_count == 1


def test_connecting_road_wins():
    env = _fresh()
    sequence = [
        "place () {(1,1): [F1]}",  # P0 places P1's opening flat
        "place () {(0,1): [F0]}",  # P1 places P0's opening flat
        "place () {(0,0): [F0]}",  # P0
        "place () {(0,2): [F1]}",  # P1
        "place () {(1,0): [F0]}",  # P0
        "place () {(2,2): [F1]}",  # P1
        "place () {(2,0): [F0]}",  # P0 completes column-0 road
    ]
    done = False
    for action in sequence:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_stack_spread_must_be_straight_and_within_carry_limit():
    env = _fresh(board_size=3)
    env.game_state["move_count"] = 2
    env.board[1][1] = ["F0", "F0", "F0", "F0"]
    before = [[stack[:] for stack in row] for row in env.board]

    done, _ = env.step("move (1,1) {(1,2): [F0], (2,2): [F0]}")
    assert not done
    assert env.board == before

    done, _ = env.step("move (1,1) {(1,2): [F0, F0, F0, F0]}")
    assert done  # second consecutive invalid move
    assert env.board == before


def test_capstone_can_flatten_wall_only_as_final_single_drop():
    env = _fresh(board_size=4)
    env.game_state["move_count"] = 2
    env.board[1][0] = ["F1", "C0"]
    env.board[1][2] = ["W1"]

    done, _ = env.step("move (1,0) {(1,1): [F1], (1,2): [C0]}")

    assert not done
    assert env.board[1][0] == []
    assert env.board[1][1] == ["F1"]
    assert env.board[1][2] == ["F1", "C0"]


def test_movement_that_uncovers_opponent_road_awards_opponent():
    env = _fresh()
    env.game_state["move_count"] = 2
    env.board[0][0] = ["F1"]
    env.board[0][1] = ["F1", "F0"]
    env.board[0][2] = ["F1"]

    done, _ = env.step("move (0,1) {(1,1): [F0]}")

    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_exhausting_reserve_uses_visible_flat_count():
    env = _fresh(board_size=3, stones=2, capstones=0)

    env.step("place () {(0,0): [F1]}")
    env.step("place () {(2,2): [F0]}")
    done, _ = env.step("place () {(1,2): [F0]}")

    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_exhausting_reserve_draws_on_tied_visible_flat_count():
    env = _fresh(board_size=3, stones=3, capstones=0)

    env.step("place () {(0,0): [F1]}")
    env.step("place () {(2,2): [F0]}")
    env.step("place () {(1,2): [F0]}")
    env.step("place () {(2,0): [F1]}")
    done, _ = env.step("place () {(1,1): [W0]}")

    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_full_board_flat_count_ignores_walls_capstones_and_covered_flats():
    env = _fresh(board_size=3)
    env.game_state["move_count"] = 2
    env.board[0][0], env.board[0][1], env.board[0][2] = ["F0", "F0", "F0", "F1"], ["W0"], ["F1"]
    env.board[1][0], env.board[1][1], env.board[1][2] = ["C0"], ["W0"], ["F1"]
    env.board[2][0], env.board[2][2] = ["F0"], ["W1"]

    done, _ = env.step("place () {(2,1): [W0]}")  # fills the board without completing a road

    assert done
    # Player 0 tops more squares and owns more flats overall, but only flats on top count.
    assert env.state.rewards == {0: -1, 1: 1}
    reason = env.state.game_info[0]["reason"]
    assert "board is full" in reason and "Player 1 wins the flat count 3-1" in reason


def test_road_completed_by_filling_the_board_beats_the_flat_count():
    env = _fresh(board_size=3)
    env.game_state["move_count"] = 2
    env.board[0][0], env.board[0][1], env.board[0][2] = ["C0"], ["F1"], ["F1"]
    env.board[1][0], env.board[1][1], env.board[1][2] = ["F0"], ["F1"], ["W0"]
    env.board[2][1], env.board[2][2] = ["W0"], ["F1"]

    done, _ = env.step("place () {(2,0): [F0]}")  # last empty square; completes column 0

    assert done
    assert env._flat_counts() == {0: 2, 1: 4}
    assert env.state.rewards == {0: 1, 1: -1}


def test_move_completing_both_roads_awards_the_mover():
    env = _fresh(board_size=3)
    env.game_state["move_count"] = 2
    env.board[0][0], env.board[0][1], env.board[0][2] = ["F1"], ["F1", "F0"], ["F1"]
    env.board[1][0], env.board[1][2] = ["F0"], ["F0"]

    done, _ = env.step("move (0,1) {(1,1): [F0]}")  # uncovers row 0 for Player 1, completes row 1

    assert done
    assert env._check_win(0) and env._check_win(1)
    assert env.state.rewards == {0: 1, 1: -1}


def test_turn_limit_is_decided_by_flat_count():
    env = _fresh(board_size=4, max_turns=5)

    done = _play(env, [
        "place () {(0,0): [F1]}",
        "place () {(3,3): [F0]}",
        "place () {(3,2): [F0]}",
        "move (0,0) {(0,1): [F1]}",
        "move (3,2) {(2,2): [F0]}",  # fifth turn reaches the cap
    ])

    assert done
    assert env.state.turn == 5
    assert env.state.rewards == {0: 1, 1: -1}
    assert "turn limit" in env.state.game_info[0]["reason"]


def test_roadless_shuffling_terminates_at_turn_limit_as_tied_flat_count():
    env = _fresh(board_size=4, max_turns=8)

    done = _play(env, [
        "place () {(0,0): [F1]}",
        "place () {(3,3): [F0]}",
        "move (3,3) {(3,2): [F0]}",
        "move (0,0) {(0,1): [F1]}",
        "move (3,2) {(3,3): [F0]}",
        "move (0,1) {(0,0): [F1]}",
        "move (3,3) {(3,2): [F0]}",
        "move (0,0) {(0,1): [F1]}",
    ])

    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_road_completed_on_the_capped_turn_beats_the_flat_count():
    env = _fresh(board_size=3, max_turns=5)

    done = _play(env, [
        "place () {(1,2): [F1]}",
        "place () {(0,0): [F0]}",
        "place () {(1,0): [C0]}",
        "place () {(0,2): [F1]}",
        "place () {(2,0): [F0]}",  # completes column 0 on the capped turn
    ])

    assert done
    assert env._flat_counts() == {0: 2, 1: 2}  # the cap alone would have been a draw
    assert env.state.rewards == {0: 1, 1: -1}


def test_registered_variant_uses_default_turn_cap():
    import textarena as ta

    env = ta.make("Tak-v0")
    env.reset(num_players=2, seed=0)

    assert env.state.max_turns == 100
    assert "after 100 turns" in env.prompt(0)


def test_prompt_explains_flat_count_ending():
    prompt = _fresh(max_turns=60).prompt(0)

    assert "board is full" in prompt
    assert "flat count" in prompt and "draw" in prompt
    assert "walls, capstones, and covered stones do not count" in prompt
    assert "after 60 turns" in prompt


def test_keywords_and_piece_letters_are_case_insensitive():
    env = _fresh()

    done = _play(env, ["Place () {(0,0): [f1]}", "PLACE () {(2,2): ['f0']}", "place () {(1,0): [w0]}"])

    assert not done
    assert env.board[0][0] == ["F1"] and env.board[2][2] == ["F0"] and env.board[1][0] == ["W0"]
    env.step("Move (0,0) {(0,1): [f1]}")
    assert env.state.error_count == 0 and env.board[0][1] == ["F1"]


@pytest.mark.parametrize("board_size", [3, 4, 6, 8])
@pytest.mark.parametrize("capstones", [0, 1])
@pytest.mark.parametrize("player_id", [0, 1])
def test_every_prompt_example_is_a_legal_move(board_size, capstones, player_id):
    prompt = _fresh(board_size=board_size, capstones=capstones).prompt(player_id)
    examples = re.findall(r"^- ((?:place|move) \([^)]*\) \{[^}]*\})", prompt, re.M)
    assert len(examples) >= 4

    for example in examples:
        env = _fresh(board_size=board_size, capstones=capstones)
        env.game_state["move_count"] = 2
        env.state.current_player_id = player_id
        action, source, allocation = env.extract_values(re.search(env.action_pattern, example).groups())
        if action == "move":
            env.board[source[0]][source[1]] = [piece for pieces in allocation.values() for piece in pieces]

        env.step(example)

        assert env.state.error_count == 0, f"prompt example rejected on a {board_size}x{board_size} board: {example}"


def test_prompt_states_carry_limit_and_bottom_to_top_notation():
    prompt = _fresh(board_size=5).prompt(0)

    assert "never more than 5, the board size" in prompt
    assert "pieces from bottom to top" in prompt
    assert "in a straight line" in prompt


def test_render_shows_both_reserves_and_turn_count():
    env = _fresh(board_size=4, stones=15, capstones=1, max_turns=40)
    env.step("place () {(0,0): [F1]}")

    rendered = env.render(1)

    assert "Player 0: 15 stones and 1 capstone left" in rendered
    assert "Player 1: 14 stones and 1 capstone left" in rendered
    assert "Turns played: 1 of 40" in rendered
    assert "place one of Player 0's flat stones (F0)" in rendered


@pytest.mark.parametrize(
    "setup,action,expected",
    [
        (None, "place () {(0,0): [F0]}", "opponent's flat stones (F1)"),
        ("midgame", "place () {(0,0): [F1]}", "only place your own pieces"),
        ("stack", "move (1,1) {(1,2): [F0, F0, F0, F0]}", "carry at most 3 pieces"),
        ("stack", "move (1,1) {(1,2): [F0], (1,0): [F0]}", "consecutive squares in one straight line"),
        ("wall", "move (1,1) {(1,2): [F0]}", "cannot move onto the wall on (1,2)"),
    ],
)
def test_invalid_feedback_names_the_broken_rule(setup, action, expected):
    env = _fresh(board_size=3)
    if setup is not None:
        env.game_state["move_count"] = 2
    if setup == "stack":
        env.board[1][1] = ["F0", "F0", "F0", "F0"]
    if setup == "wall":
        env.board[1][1] = ["F0"]
        env.board[1][2] = ["W1"]

    env.step(action)

    assert env.state.error_count == 1
    feedback = [message for _, message in env.state.logs if "attempted an invalid move" in message]
    assert len(feedback) == 1 and expected in feedback[0]


def test_action_descriptions_name_pieces_squares_and_flattening():
    env = _fresh(board_size=4)
    env.step("place () {(0,0): [F1]}")
    env.game_state["move_count"] = 2
    env.board[1][0] = ["F1", "C1"]
    env.board[1][2] = ["W0"]

    env.step("move (1,0) {(1,1): [F1], (1,2): [C1]}")

    messages = [message for _, message in env.state.logs]
    assert "Player 0 placed F1 on (0,0)." in messages
    assert "Player 1 moved 2 pieces from (1,0): F1 to (1,1); C1 to (1,2), flattening the wall W0." in messages
