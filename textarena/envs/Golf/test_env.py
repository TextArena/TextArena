"""Offline deterministic tests for Golf (card game).

Default layout: 6 cards per player in a 2x3 grid, 2 cards start revealed. Each
turn a player draws ('draw') or takes the discard top ('take'), then must
'swap X Y' or 'discard'. The round ends when a player has all cards revealed
(final round) or the deck empties; lowest score wins.

Card contents are hidden from the acting player but readable from game_state,
which lets us drive a full game to a deterministic terminal state.
"""
import copy

from textarena.envs.Golf.env import GolfEnv


def _fresh(num_players=2):
    env = GolfEnv()  # defaults: num_cards=6, num_columns=3 -> 2 rows
    env.reset(num_players=num_players, seed=42)
    return env


def _first_unrevealed_rowcol(env, pid):
    cards = env.state.game_state["players"][pid]["cards"]
    for idx, info in enumerate(cards):
        if not info["revealed"]:
            row = idx // env.num_columns + 1
            col = idx % env.num_columns + 1
            return row, col
    return None


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["players"][0]["cards"]) == 6
    assert len(gs["players"][1]["cards"]) == 6
    revealed_p0 = sum(c["revealed"] for c in gs["players"][0]["cards"])
    assert revealed_p0 == 2  # num_cards // 3
    assert len(gs["discard_pile"]) == 1
    assert gs["turn_phase"] == "draw"
    assert gs["current_phase"] == "playing"
    assert env.state.current_player_id == 0


def test_draw_then_discard_advances_turn():
    env = _fresh()
    discards_before = len(env.state.game_state["discard_pile"])
    env.step("draw")
    assert env.state.game_state["turn_phase"] == "action_with_card"
    assert env.state.current_player_id == 0
    done, _ = env.step("discard")
    assert not done
    assert len(env.state.game_state["discard_pile"]) == discards_before + 1
    assert env.state.current_player_id == 1
    assert env.state.game_state["turn_phase"] == "draw"


def test_draw_then_swap_reveals_position():
    env = _fresh()
    env.step("draw")
    done, _ = env.step("swap 1 1")
    assert not done
    assert env.state.game_state["players"][0]["cards"][0]["revealed"] is True
    assert env.state.current_player_id == 1


def test_take_then_discard_is_illegal():
    env = _fresh()
    env.step("take")  # take from discard pile
    assert env.state.game_state.get("took_from_discard") is True
    done, _ = env.step("discard")  # cannot discard a taken card
    assert not done
    assert env.state.error_count == 1


def test_invalid_format_does_not_end_game():
    env = _fresh()
    done, _ = env.step("frobnicate")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_swap_out_of_bounds_is_invalid():
    env = _fresh()
    env.step("draw")
    done, _ = env.step("swap 9 9")
    assert not done
    assert env.state.error_count == 1


def test_full_game_terminal_lowest_score_wins():
    """Player 0 keeps swapping into its face-down slots until all are revealed,
    which triggers the end of the game; player 1 just draws/discards."""
    env = _fresh()
    done = False
    for _ in range(80):
        gs = env.state.game_state
        pid = env.state.current_player_id
        if gs["turn_phase"] == "draw":
            done, _ = env.step("draw")
        else:
            if pid == 0:
                rc = _first_unrevealed_rowcol(env, 0)
                assert rc is not None
                done, _ = env.step(f"[swap {rc[0]} {rc[1]}]")  # brackets tolerated
            else:
                done, _ = env.step("discard")
        if done:
            break
    assert done
    scores = {pid: env.state.game_state["players"][pid]["score"] for pid in (0, 1)}
    if scores[0] == scores[1]:
        assert env.state.rewards == {0: 0, 1: 0}
    else:
        winner = min(scores, key=scores.get)
        assert env.state.rewards == {winner: 1, 1 - winner: -1}


def test_knock_gives_each_opponent_exactly_one_final_turn():
    env = _fresh()
    done, _ = env.step("knock")
    gs = env.state.game_state
    assert not done
    assert gs["current_phase"] == "final_round"
    assert gs["knocker"] == 0
    assert gs["final_turns_remaining"] == 1
    assert env.state.current_player_id == 1
    env.step("draw")
    done, _ = env.step("discard")
    assert done
    assert gs["current_phase"] == "finished"


def test_eliminated_opponent_forfeits_exactly_one_final_turn():
    env = _fresh(num_players=3)
    env.step("knock")
    gs = env.state.game_state
    assert gs["final_turns_remaining"] == 2
    assert env.state.current_player_id == 1

    env.step("bad")
    done, _ = env.step("still bad")

    assert not done
    assert env.state.eliminated == [1]
    assert gs["final_turns_remaining"] == 1
    assert env.state.current_player_id == 2
    row, col = _first_unrevealed_rowcol(env, 2)
    done, _ = env.step(f"peek {row} {col}")
    assert done
    assert gs["current_phase"] == "finished"


def test_revealing_last_card_still_gives_opponent_a_final_turn():
    env = _fresh()
    gs = env.state.game_state
    for info in gs["players"][0]["cards"]:
        info["revealed"] = True
    gs["players"][0]["cards"][-1]["revealed"] = False
    env.step("draw")
    done, _ = env.step("swap 2 3")
    assert not done
    assert gs["current_phase"] == "final_round"
    assert gs["final_turns_remaining"] == 1
    assert env.state.current_player_id == 1


def test_final_round_peek_is_private_and_consumes_turn():
    env = _fresh(num_players=3)
    env.step("knock")
    gs = env.state.game_state
    pid = env.state.current_player_id
    row, col = _first_unrevealed_rowcol(env, pid)
    idx = (row - 1) * env.num_columns + (col - 1)
    card_name = env._card_to_string(gs["players"][pid]["cards"][idx]["card"])
    done, _ = env.step(f"peek {row} {col}")
    assert not done
    private_events = [
        event for event in env.state.events
        if "privately peeked" in event[1]
    ]
    assert len(private_events) == 1
    assert private_events[0][3] == pid
    assert card_name not in env.render(env.state.current_player_id)
    assert card_name not in env.get_board_str()


def test_peek_before_final_round_is_illegal_and_atomic():
    env = _fresh()
    row, col = _first_unrevealed_rowcol(env, 0)
    before = copy.deepcopy(env.state.game_state)
    env.step(f"peek {row} {col}")
    assert env.state.game_state == before


def test_cards_are_conserved_through_draw_swap_and_take():
    env = _fresh()
    gs = env.state.game_state

    def accounted_cards():
        return (
            len(gs["deck"])
            + len(gs["discard_pile"])
            + sum(len(player["cards"]) for player in gs["players"].values())
            + (1 if "drawn_card" in gs else 0)
        )

    assert accounted_cards() == 52
    env.step("draw")
    assert accounted_cards() == 52
    env.step("swap 1 1")
    assert accounted_cards() == 52
    env.step("take")
    assert accounted_cards() == 52


def test_placing_final_stock_card_ends_without_a_dummy_draw_turn():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"] = [gs["deck"][-1]]

    env.step("draw")
    done, _ = env.step("discard")

    assert done
    assert gs["current_phase"] == "finished"
    assert len(gs["deck"]) == 0


def test_tied_low_scores_are_a_draw():
    env = _fresh()
    gs = env.state.game_state
    for player in gs["players"].values():
        for card_info in player["cards"]:
            card_info["card"] = {"rank": "K", "suit": "♠", "value": 0}
    outcome = env._end_game()
    assert outcome.rewards == {0: 0, 1: 0}


def test_huge_coordinates_are_invalid_and_atomic():
    env = _fresh()
    env.step("draw")
    before = copy.deepcopy(env.state.game_state)
    env.step("swap " + "9" * 5000 + " 1")
    assert env.state.game_state == before


def test_snapshot_restores_private_draw_and_rng():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("draw")
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step("draw")
    assert env.state.game_state == expected


def test_invalid_layout_configuration_is_rejected():
    for kwargs in (
        {"num_cards": 13, "num_columns": 3},
        {"num_cards": 6, "num_columns": 4},
        {"num_cards": 6, "num_columns": 0},
    ):
        try:
            GolfEnv(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid configuration: {kwargs}")
