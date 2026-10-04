"""Deterministic offline tests for IteratedUltimatumGame.

Two-player game. Proposer offers a split of ``pool``; responder accepts or
rejects. ``max_turns`` counts individual turns, so ``max_turns=2`` is a single
round. Winner by total accumulated money (winner {w:1,l:-1}; draw {0:0,1:0}).
"""
import pytest
import textarena as ta

from textarena.envs.IteratedUltimatumGame.env import IteratedUltimatumGameEnv


def _fresh(pool=10, max_turns=2, alternate_roles=False):
    env = IteratedUltimatumGameEnv(
        pool=pool,
        max_turns=max_turns,
        alternate_roles=alternate_roles,
    )
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert env.state.game_state["phase"] == "offering"
    assert env.state.game_state["round_number"] == 1


def test_accept_proposer_wins():
    env = _fresh()
    done = env.step("Offer: $3")
    assert done is False
    assert env.state.game_state["phase"] == "responding"
    assert env.state.current_player_id == 1
    done = env.step("Accept")
    assert done is True
    # P0 keeps 7, P1 gets 3 -> P0 wins.
    assert env.state.game_state["player_totals"] == {0: 7, 1: 3}
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["phase"] == "complete"
    assert "Phase: COMPLETE" in env.get_board_str()
    assert "turn to respond" not in env.get_board_str()


def test_accept_responder_wins():
    env = _fresh()
    env.step("Offer: $8")
    done = env.step("Accept")
    assert done is True
    assert env.state.game_state["player_totals"] == {0: 2, 1: 8}
    assert env.state.rewards == {0: -1, 1: 1}


def test_reject_is_draw():
    env = _fresh()
    env.step("Offer: $3")
    done = env.step("Reject")
    assert done is True
    assert env.state.game_state["player_totals"] == {0: 0, 1: 0}
    assert env.state.rewards == {0: 0, 1: 0}


def test_zero_pool_offer_resolves_and_survives_render_reset_cycle():
    env = _fresh(pool=0)
    env.step("Offer: $0")
    assert "offers: $0" in env.get_board_str()
    done = env.step("Accept")
    assert done
    assert env.state.game_state["player_totals"] == {0: 0, 1: 0}
    assert env.state.rewards == {0: 0, 1: 0}

    env.reset(num_players=2, seed=7)
    assert env.state.game_state["current_offer"] is None
    assert env.state.game_state["round_history"] == []
    assert env.state.current_player_id == 0


def test_proposer_invalid_format():
    env = _fresh()
    done = env.step("Accept")  # not a valid offer
    assert done is False
    assert env.state.error_count == 1
    assert env.state.game_state["phase"] == "offering"
    assert env.state.current_player_id == 0


def test_offer_above_pool_rejected():
    env = _fresh()
    done = env.step("Offer: $20")
    assert done is False
    assert env.state.error_count == 1
    assert env.state.game_state["phase"] == "offering"


def test_responder_invalid_format():
    env = _fresh()
    env.step("Offer: $3")
    done = env.step("I am undecided")  # neither accept nor reject
    assert done is False
    assert env.state.error_count == 1
    assert env.state.game_state["phase"] == "responding"
    assert env.state.current_player_id == 1


def test_two_round_game():
    # max_turns=4 -> 2 rounds; proposer fixed at P0 (alternate_roles=False).
    env = _fresh(max_turns=4)
    env.step("Offer: $2")   # round 1: P0 +8, P1 +2
    env.step("Accept")
    assert env.state.done is False
    assert env.state.game_state["round_number"] == 2
    env.step("Offer: $2")   # round 2: P0 +8, P1 +2
    done = env.step("Accept")
    assert done is True
    assert env.state.game_state["player_totals"] == {0: 16, 1: 4}
    assert env.state.rewards == {0: 1, 1: -1}


def test_alternating_roles_sets_next_actor_and_records_roles():
    env = _fresh(max_turns=4, alternate_roles=True)
    env.step("Offer: $2")
    env.step("Accept")
    assert env.state.current_player_id == 1
    assert env.state.game_state["current_proposer_id"] == 1

    env.step("Offer: $8")
    done = env.step("Accept")
    assert done
    assert [item["proposer"] for item in env.state.game_state["round_history"]] == [0, 1]
    assert env.state.game_state["round_number"] == 2
    assert env.state.turn == 4


@pytest.mark.parametrize("player_id", [-1, 1, 2, True])
def test_unauthorized_offer_is_rejected_atomically(player_id):
    env = _fresh()
    before = env.state.game_state.copy()
    result = env.apply(player_id, "Offer: $3")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


def test_fixed_role_renderer_matches_configuration():
    env = _fresh(max_turns=4, alternate_roles=False)
    board = env.get_board_str()
    assert "Player 0 remains Proposer every round" in board
    assert "Players alternate as Proposer" not in board


@pytest.mark.parametrize("player_id", [0, 1])
def test_prompt_states_how_the_match_is_won(player_id):
    prompt = _fresh(max_turns=4).prompt(player_id)
    assert "the player with more money after the last round wins, and equal totals are a draw" in prompt


def test_responder_prompt_does_not_claim_ownership_of_pool():
    env = _fresh()
    prompt = env.prompt(1)
    assert "You begin as the Responder" in prompt
    assert "You have $10 to split" not in prompt


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_turns": 3},
        {"pool": 10**5000},
        {"max_turns": 10**5000},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        IteratedUltimatumGameEnv(**kwargs)
