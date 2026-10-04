"""Deterministic offline tests for Kuhn Poker.

Two-player, 3-card deck (J<Q<K). With ``max_rounds=1`` the game ends after one
hand. Cards are dealt randomly; we read ``game_state['player_cards']`` to script
guaranteed outcomes. Note: the non-dealer/starting player is player 1.
"""
import copy

import pytest

from textarena.envs.KuhnPoker.env import KuhnPokerEnv


def _fresh(max_rounds=1):
    env = KuhnPokerEnv(max_rounds=max_rounds)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_starting_player_and_cards():
    env = _fresh()
    # _init_round flips starting_player from 0 to 1.
    assert env.state.current_player_id == 1
    cards = env.state.game_state["player_cards"]
    assert set(cards.keys()) == {0, 1}
    assert cards[0] != cards[1]


def test_check_check_showdown_high_card_wins():
    env = _fresh()
    cards = env.state.game_state["player_cards"]
    expected_winner = 0 if cards[0] > cards[1] else 1
    env.step("check")   # player 1 (starter)
    done, _ = env.step("check")  # player 0 -> showdown
    assert done is True
    loser = 1 - expected_winner
    assert env.state.rewards == {expected_winner: 1, loser: -1}
    assert env.state.game_state["current_round"] == 1


def test_bet_fold_folder_loses():
    env = _fresh()
    starter = env.state.current_player_id  # player 1
    env.step("bet")            # starter bets
    done, _ = env.step("fold")  # other player folds
    assert done is True
    other = 1 - starter
    # Folder (other) loses, starter wins the pot.
    assert env.state.rewards == {starter: 1, other: -1}


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("I check maybe")  # not a bare action token
    assert done is False
    assert env.state.error_count == 1


def test_illegal_action_rejected():
    env = _fresh()
    # No bet on the table yet, so 'call' is not in the legal tree.
    done, _ = env.step("call")
    assert done is False
    assert env.state.error_count == 1


def test_bet_call_showdown():
    env = _fresh()
    cards = env.state.game_state["player_cards"]
    expected_winner = 0 if cards[0] > cards[1] else 1
    env.step("bet")            # starter bets
    done, _ = env.step("call")  # other calls -> showdown
    assert done is True
    loser = 1 - expected_winner
    assert env.state.rewards == {expected_winner: 1, loser: -1}


def test_bet_and_call_move_chips_before_showdown():
    env = _fresh()
    gs = env.state.game_state
    env.step("bet")
    assert gs["pot"] == 3
    assert gs["player_chips"] == {0: -1, 1: -2}
    assert sum(gs["player_chips"].values()) + gs["pot"] == 0
    env.step("call")
    assert gs["pot"] == 0
    assert sum(gs["player_chips"].values()) == 0


def test_round_starter_alternates_and_pot_is_conserved():
    env = _fresh(max_rounds=2)
    env.step("bet")
    done, _ = env.step("fold")
    assert not done
    gs = env.state.game_state
    assert gs["current_round"] == 2
    assert env.state.current_player_id == 0
    assert gs["pot"] == 2
    assert sum(gs["player_chips"].values()) + gs["pot"] == 0


@pytest.mark.parametrize(
    "max_rounds, final_chips, rewards",
    [(3, {0: -1, 1: 1}, {0: -1, 1: 1}), (2, {0: 0, 1: 0}, {0: 0, 1: 0})],
)
def test_final_round_ends_match_without_dealing_or_anteing_another(max_rounds, final_chips, rewards):
    env = _fresh(max_rounds=max_rounds)
    gs = env.state.game_state
    for _ in range(max_rounds):
        env.step("bet")
        done, _ = env.step("fold")  # the round's starter wins a pot of 3
    assert done
    assert gs["current_round"] == max_rounds
    assert gs["pot"] == 0
    assert gs["player_chips"] == final_chips
    assert env.state.rewards == rewards
    assert not any(f"Starting round {max_rounds + 1}" in message for _, message, _, _ in env.state.events)


def test_illegal_action_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("call")
    assert env.state.game_state == before


def test_private_renderer_never_exposes_opponent_card():
    env = _fresh()
    cards = env.state.game_state["player_cards"]
    public_board = env.get_board_str()
    private_board = env.render(0)
    own_face = env._rank_to_str(cards[0])
    opponent_face = env._rank_to_str(cards[1])
    assert public_board.count("│  │ ?       │") == 2
    assert own_face in private_board
    assert f"│  │ {opponent_face}       │" not in private_board


def test_mdp_observation_shows_the_actors_legal_actions():
    import textarena as ta

    env = ta.make("KuhnPoker-v1-mdp")
    env.reset(num_players=2, seed=1)
    _, observation = env.get_observation()
    assert observation.rstrip().endswith("Your available actions are: 'check', 'bet'")
    env.step("bet")
    _, observation = env.get_observation()
    assert observation.rstrip().endswith("Your available actions are: 'fold', 'call'")
