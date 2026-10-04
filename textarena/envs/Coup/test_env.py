"""Deterministic game-logic tests for Coup."""
import pytest

import textarena as ta
from textarena.envs.Coup.env import CoupEnv
from textarena.envs.Coup.coup_types import GamePhase


def make_env(num_players=2, seed=42):
    env = CoupEnv()
    env.reset(num_players=num_players, seed=seed)
    return env


def test_reset_initializes_game_state():
    env = make_env(num_players=4, seed=42)
    gs = env.state.game_state
    assert gs["phase"] == GamePhase.Play
    assert gs["coins"] == {0: 2, 1: 2, 2: 2, 3: 2}
    assert gs["treasury_coins"] == 50 - 2 * 4
    for pid in range(4):
        assert len(gs["hidden_hand"][pid]) == 2
        assert gs["revealed_hand"][pid] == []
    # 15 cards total: 8 dealt, 7 in the pile
    assert len(gs["pile"]) == 15 - 8
    assert env.state.current_player_id == 0


def test_num_players_bounds_enforced():
    env = CoupEnv()
    with pytest.raises(AssertionError):
        env.reset(num_players=1, seed=42)
    with pytest.raises(AssertionError):
        env.reset(num_players=7, seed=42)


def test_income_gives_one_coin_and_advances_turn():
    env = make_env(num_players=3, seed=42)
    done, _ = env.step("income")
    assert done is False
    assert env.state.game_state["coins"][0] == 3
    assert env.state.current_player_id == 1


def test_full_game_tax_and_coup_last_player_standing():
    env = make_env(num_players=2, seed=42)
    # Tax is unblockable but challengeable, so the other player must PASS each time.
    script = [
        "tax", "pass",      # p0: 2 -> 5
        "tax", "pass",      # p1: 2 -> 5
        "tax", "pass",      # p0: 5 -> 8
        "tax", "pass",      # p1: 5 -> 8
        "coup 1",           # p0 coups p1 (p0: 8 -> 1), p1 down to 1 card
        "tax", "pass",      # p1: 8 -> 11
        "income",           # p0: 1 -> 2
        "coup 0",           # p1 forced coup (11 -> 4), p0 down to 1 card
        "income",           # p0: 2 -> 3
        "tax", "pass",      # p1: 4 -> 7
        "income",           # p0: 3 -> 4
        "coup 0",           # p1 coups p0 -> p0 eliminated, p1 wins
    ]
    done = False
    for action in script:
        assert done is False, "game ended earlier than scripted"
        done, info = env.step(action)
    assert done is True
    assert info == {"winner": 1}
    assert env.state.game_state["hidden_hand"][0] == []
    assert env.state.rewards == {0: -1, 1: 1}


def test_honest_tax_challenge_costs_challenger_a_card():
    env = make_env(num_players=2, seed=42)
    # Fix the hands so player 0 genuinely holds a Duke.
    env.state.game_state["hidden_hand"][0] = ["Duke", "Contessa"]
    env.state.game_state["hidden_hand"][1] = ["Assassin", "Captain"]
    env.step("tax")
    done, _ = env.step("BULLSHIT")
    assert done is False
    # The tax succeeded, the challenger lost an influence, the honest player drew a replacement.
    assert env.state.game_state["coins"][0] == 5
    assert len(env.state.game_state["revealed_hand"][1]) == 1
    assert len(env.state.game_state["hidden_hand"][1]) == 1
    assert len(env.state.game_state["hidden_hand"][0]) == 2


def test_dishonest_tax_challenge_costs_bluffer_a_card():
    env = make_env(num_players=2, seed=42)
    # Fix the hands so player 0 does NOT hold a Duke.
    env.state.game_state["hidden_hand"][0] = ["Assassin", "Contessa"]
    env.state.game_state["hidden_hand"][1] = ["Duke", "Captain"]
    env.step("tax")
    done, _ = env.step("BULLSHIT")
    assert done is False
    # The tax was cancelled and the bluffer lost an influence.
    assert env.state.game_state["coins"][0] == 2
    assert len(env.state.game_state["revealed_hand"][0]) == 1
    assert len(env.state.game_state["hidden_hand"][0]) == 1
    assert env.state.game_state["hidden_hand"][1] == ["Duke", "Captain"]


def test_invalid_format_is_rejected_and_player_retries():
    env = make_env(num_players=2, seed=42)
    done, info = env.step("not a real command")
    assert done is False
    assert env.state.current_player_id == 0  # same player retries
    assert env.state.game_state["coins"] == {0: 2, 1: 2}
    # then a valid move still works
    done, _ = env.step("income")
    assert done is False
    assert env.state.game_state["coins"][0] == 3
    assert env.state.current_player_id == 1


def test_coup_without_enough_coins_is_rejected():
    env = make_env(num_players=2, seed=42)
    done, _ = env.step("coup 1")  # only has 2 coins, needs 7
    assert done is False
    assert env.state.current_player_id == 0
    assert env.state.game_state["coins"] == {0: 2, 1: 2}
    assert len(env.state.game_state["hidden_hand"][1]) == 2


def test_repeated_invalid_moves_eliminate_player():
    env = make_env(num_players=2, seed=42)
    # error_allowance is 3: the 4th consecutive invalid move eliminates the player
    done = False
    for _ in range(4):
        assert done is False
        done, _ = env.step("gibberish without a command")
    assert done is True
    assert 0 in env.state.eliminated
    assert env.state.game_state["hidden_hand"][0] == []
    assert env.state.rewards == {0: -1, 1: 1}


def _influence_card_count(env):
    gs = env.state.game_state
    return (
        len(gs["pile"])
        + sum(len(cards) for cards in gs["hidden_hand"].values())
        + sum(len(cards) for cards in gs["revealed_hand"].values())
    )


def test_directed_actions_reject_self_and_eliminated_targets():
    env = make_env()
    env.state.game_state["coins"][0] = 7
    done, _ = env.step("coup 0")
    assert not done and env.state.error_count == 1
    assert env.state.game_state["coins"][0] == 7

    env.state.error_count = 0
    env.state.game_state["hidden_hand"][1] = []
    env.eliminate(1)
    done, _ = env.step("assassinate 1")
    assert not done and env.state.error_count == 1
    assert env.state.game_state["coins"][0] == 7


def test_only_target_can_block_targeted_action():
    env = make_env(num_players=3)
    env.step("steal 1")
    env.step("pass")  # target declines to block/challenge
    done, _ = env.step("block steal captain")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["phase"] == GamePhase.QueryForBlockOrChallenge
    assert env.state.game_state["action_metadata"].blocker_player_id is None


def test_unchallenged_foreign_aid_block_cancels_action():
    env = make_env()
    env.step("foreign aid")
    env.step("block foreign aid")
    env.step("pass")
    assert env.state.game_state["coins"] == {0: 2, 1: 2}
    assert env.state.game_state["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1


def test_honest_foreign_aid_block_survives_challenge():
    env = make_env()
    gs = env.state.game_state
    gs["hidden_hand"][1] = ["Duke", "Contessa"]
    gs["hidden_hand"][0] = ["Captain", "Assassin"]
    env.step("foreign aid")
    env.step("block foreign aid")
    env.step("bullshit")
    assert gs["coins"] == {0: 2, 1: 2}
    assert len(gs["revealed_hand"][0]) == 1
    assert len(gs["hidden_hand"][1]) == 2
    assert gs["phase"] == GamePhase.Play


def test_steal_does_not_take_coins_after_dishonest_blocker_is_eliminated():
    env = make_env()
    gs = env.state.game_state
    gs["hidden_hand"][1] = ["Duke"]
    gs["revealed_hand"][1] = ["Contessa"]
    env.step("steal 1")
    env.step("block steal captain")
    done, _ = env.step("bullshit")
    assert done
    assert gs["coins"] == {0: 2, 1: 2}
    assert env.state.rewards == {0: 1, 1: -1}


def test_steal_takes_up_to_two_coins():
    env = make_env()
    env.state.game_state["coins"][1] = 1
    env.step("steal 1")
    env.step("pass")
    assert env.state.game_state["coins"] == {0: 3, 1: 0}


def test_failed_assassination_claim_does_not_refund_cost():
    env = make_env()
    gs = env.state.game_state
    gs["hidden_hand"][0] = ["Duke", "Contessa"]
    gs["hidden_hand"][1] = ["Assassin", "Captain"]
    gs["coins"][0] = 5
    env.step("assassinate 1")
    env.step("bullshit")
    assert gs["coins"][0] == 2
    assert len(gs["revealed_hand"][0]) == 1
    assert gs["phase"] == GamePhase.Play


@pytest.mark.parametrize(
    "command",
    ["coup 1 now", "block", "block assassinate extra", "[income] [tax]"],
)
def test_malformed_or_mixed_commands_are_rejected_without_crashing(command):
    env = make_env()
    before = dict(env.state.game_state["coins"])
    done, _ = env.step(command)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["coins"] == before


def test_exchange_conserves_cards_and_keeps_selection_private():
    env = make_env()
    assert _influence_card_count(env) == 15
    env.step("exchange")
    env.step("pass")
    gs = env.state.game_state
    assert gs["phase"] == GamePhase.QueryWhichToKeep
    options = list(gs["hidden_hand"][0])
    event_start = len(env.state.events)
    env.step(f"keep {options[0]} {options[1]}")
    assert gs["phase"] == GamePhase.Play
    assert len(gs["hidden_hand"][0]) == 2
    assert _influence_card_count(env) == 15
    keep_echoes = [
        to_id for _, message, _, to_id in env.state.events[event_start:]
        if message.lower().startswith("keep ")
    ]
    assert keep_echoes == [0]


def test_invalid_limit_mid_query_skips_eliminated_responder_and_resolves():
    env = make_env(num_players=3)
    env.step("foreign aid")
    for _ in range(4):
        env.step("income")
    assert 1 in env.state.eliminated
    assert env.state.current_player_id == 2
    assert env.state.game_state["phase"] == GamePhase.QueryForBlockOrChallenge
    env.step("pass")
    assert env.state.game_state["coins"][0] == 4
    assert env.state.game_state["phase"] == GamePhase.Play


def test_board_hides_other_players_influence():
    env = make_env()
    gs = env.state.game_state
    gs["hidden_hand"][0] = ["Duke", "Ambassador"]
    gs["hidden_hand"][1] = ["Captain", "Contessa"]
    board = str(env._render_board(viewer_id=0))
    assert "Duke" in board and "Ambassador" in board
    assert "Captain" not in board and "Contessa" not in board
    assert board.count("Hidden influence") == 2


def test_initial_and_repeat_reset_conserve_fifteen_cards():
    env = make_env(num_players=4)
    first = {
        pid: list(cards)
        for pid, cards in env.state.game_state["hidden_hand"].items()
    }
    assert _influence_card_count(env) == 15
    env.step("income")
    env.reset(num_players=4, seed=42)
    assert _influence_card_count(env) == 15
    assert env.state.game_state["hidden_hand"] == first


def test_snapshot_restore_replays_exchange_shuffle():
    env = make_env()
    env.step("exchange")
    before = env.snapshot()
    env.step("pass")
    expected = env.snapshot()
    env.restore(before)
    env.step("pass")
    assert env.state.game_state == expected["state"].game_state
    assert env.state.current_player_id == expected["state"].current_player_id


def test_target_may_block_after_losing_challenge_to_action_claim():
    env = make_env()
    gs = env.state.game_state
    gs["hidden_hand"][0] = ["Assassin", "Duke"]
    gs["hidden_hand"][1] = ["Contessa", "Captain"]
    gs["coins"][0] = 5

    env.step("assassinate 1")
    env.step("bullshit")
    assert gs["phase"] == GamePhase.QueryForBlockOrChallenge
    assert env.state.current_player_id == 1
    assert gs["hidden_hand"][1] == ["Contessa"]

    env.step("block assassinate")
    env.step("pass")
    assert gs["phase"] == GamePhase.Play
    assert gs["hidden_hand"][1] == ["Contessa"]
    assert gs["revealed_hand"][1] == ["Captain"]
    assert gs["coins"][0] == 2  # assassination cost is never refunded
    assert env.state.current_player_id == 1


def test_proven_action_claim_cannot_be_challenged_twice():
    env = make_env()
    gs = env.state.game_state
    gs["hidden_hand"][0] = ["Captain", "Duke"]
    gs["hidden_hand"][1] = ["Ambassador", "Contessa"]
    env.step("steal 1")
    env.step("bullshit")
    assert env.state.current_player_id == 1
    assert gs["phase"] == GamePhase.QueryForBlockOrChallenge
    before = (dict(gs["coins"]), list(gs["hidden_hand"][1]), list(gs["revealed_hand"][1]))
    done, _ = env.step("bullshit")
    assert not done
    assert env.state.error_count == 1
    assert (gs["coins"], gs["hidden_hand"][1], gs["revealed_hand"][1]) == before
