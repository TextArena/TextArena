"""Deterministic game-logic tests for Coup."""
import copy
import random

import pytest

import textarena as ta
from textarena.envs.Coup.env import CARDS, CoupEnv
from textarena.envs.Coup.coup_types import CoupActionType, GamePhase


def make_env(num_players=2, seed=42):
    env = CoupEnv()
    env.reset(num_players=num_players, seed=seed)
    return env


def play(env, *actions):
    done, info = False, {}
    for action in actions:
        assert done is False, f"game ended before {action!r}"
        done, info = env.step(action)
    return done, info


def deal(env, hands, revealed=None):
    """Give players specific cards and rebuild the Court deck so the 15-card deck stays intact."""
    gs = env.state.game_state
    for pid, cards in hands.items():
        gs["hidden_hand"][pid] = list(cards)
    for pid, cards in (revealed or {}).items():
        gs["revealed_hand"][pid] = list(cards)
    pile = list(CARDS) * 3
    for pid in gs["hidden_hand"]:
        for card in gs["hidden_hand"][pid] + gs["revealed_hand"][pid]:
            pile.remove(card)
    gs["pile"] = pile
    return gs


def give_coins(env, player_id, coins):
    gs = env.state.game_state
    gs["treasury_coins"] -= coins - gs["coins"][player_id]
    gs["coins"][player_id] = coins


def assert_awaiting_reveal(env, player_id):
    gs = env.state.game_state
    assert gs["phase"] == GamePhase.QueryWhichToReveal
    assert env.state.current_player_id == player_id
    assert gs["pending_influence_loss"]["player_id"] == player_id


def assert_conserved(env):
    gs = env.state.game_state
    assert _influence_card_count(env) == 15
    assert sum(gs["coins"].values()) + gs["treasury_coins"] == 50


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
    gs = env.state.game_state
    # Tax is unblockable but challengeable, so the other player must PASS each time.
    play(env,
         "tax", "pass",      # p0: 2 -> 5
         "tax", "pass",      # p1: 2 -> 5
         "tax", "pass",      # p0: 5 -> 8
         "tax", "pass",      # p1: 5 -> 8
         "coup 1")           # p0 coups p1 (p0: 8 -> 1)
    assert_awaiting_reveal(env, 1)  # p1 chooses which of their two cards to lose
    lost, kept = gs["hidden_hand"][1]
    play(env, f"reveal {lost}")
    assert gs["revealed_hand"][1] == [lost] and gs["hidden_hand"][1] == [kept]

    play(env,
         "tax", "pass",      # p1: 8 -> 11
         "income",           # p0: 1 -> 2
         "coup 0")           # p1 forced coup (11 -> 4)
    assert_awaiting_reveal(env, 0)
    play(env, f"reveal {gs['hidden_hand'][0][1]}")

    done, info = play(env,
                      "income",           # p0: 2 -> 3
                      "tax", "pass",      # p1: 4 -> 7
                      "income",           # p0: 3 -> 4
                      "coup 0")           # p1 coups p0's last card -> eliminated without a prompt, p1 wins
    assert done is True
    assert info == {"winner": 1}
    assert gs["hidden_hand"][0] == []
    assert len(gs["revealed_hand"][0]) == 2
    assert env.state.rewards == {0: -1, 1: 1}
    assert_conserved(env)


def test_honest_tax_challenge_costs_challenger_a_card():
    env = make_env(num_players=2, seed=42)
    # Fix the hands so player 0 genuinely holds a Duke.
    env.state.game_state["hidden_hand"][0] = ["Duke", "Contessa"]
    env.state.game_state["hidden_hand"][1] = ["Assassin", "Captain"]
    env.step("tax")
    done, _ = env.step("BULLSHIT")
    assert done is False
    # The challenger chooses the influence to lose before the proven tax resolves.
    assert_awaiting_reveal(env, 1)
    assert env.state.game_state["coins"][0] == 1
    done, _ = env.step("reveal captain")
    assert done is False
    # The tax succeeded, the challenger lost an influence, the honest player drew a replacement.
    assert env.state.game_state["coins"][0] == 4
    assert env.state.game_state["revealed_hand"][1] == ["Captain"]
    assert env.state.game_state["hidden_hand"][1] == ["Assassin"]
    assert len(env.state.game_state["hidden_hand"][0]) == 2
    assert env.state.game_state["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1


def test_dishonest_tax_challenge_costs_bluffer_a_card():
    env = make_env(num_players=2, seed=42)
    # Fix the hands so player 0 does NOT hold a Duke.
    env.state.game_state["hidden_hand"][0] = ["Assassin", "Contessa"]
    env.state.game_state["hidden_hand"][1] = ["Duke", "Captain"]
    env.step("tax")
    done, _ = env.step("BULLSHIT")
    assert done is False
    assert_awaiting_reveal(env, 0)
    done, _ = env.step("reveal contessa")
    assert done is False
    # The tax was cancelled and the bluffer lost the influence they chose.
    assert env.state.game_state["coins"][0] == 1
    assert env.state.game_state["revealed_hand"][0] == ["Contessa"]
    assert env.state.game_state["hidden_hand"][0] == ["Assassin"]
    assert env.state.game_state["hidden_hand"][1] == ["Duke", "Captain"]
    assert env.state.current_player_id == 1


def test_invalid_format_is_rejected_and_player_retries():
    env = make_env(num_players=2, seed=42)
    done, info = env.step("not a real command")
    assert done is False
    assert env.state.current_player_id == 0  # same player retries
    assert env.state.game_state["coins"] == {0: 1, 1: 2}
    # then a valid move still works
    done, _ = env.step("income")
    assert done is False
    assert env.state.game_state["coins"][0] == 2
    assert env.state.current_player_id == 1


def test_coup_without_enough_coins_is_rejected():
    env = make_env(num_players=2, seed=42)
    done, _ = env.step("coup 1")  # only has 1 coin, needs 7
    assert done is False
    assert env.state.current_player_id == 0
    assert env.state.game_state["coins"] == {0: 1, 1: 2}
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
    assert env.state.game_state["coins"] == {0: 1, 1: 2}
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
    assert_awaiting_reveal(env, 0)
    env.step("reveal assassin")
    assert gs["coins"] == {0: 1, 1: 2}
    assert gs["revealed_hand"][0] == ["Assassin"]
    assert len(gs["hidden_hand"][1]) == 2
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1


def test_steal_pays_out_before_dishonest_blocker_is_exiled_and_game_ends():
    env = make_env()
    gs = deal(env, {0: ["Captain", "Duke"], 1: ["Duke"]}, revealed={1: ["Contessa"]})
    give_coins(env, 1, 3)
    treasury = gs["treasury_coins"]
    env.step("steal 1")
    env.step("block steal captain")
    done, _ = env.step("bullshit")
    assert done
    # The blocker's last card is lost without a prompt; the steal is paid from the exiled
    # player's coins first and only the remainder returns to the Treasury.
    assert gs["revealed_hand"][1] == ["Contessa", "Duke"]
    assert gs["coins"] == {0: 3, 1: 0}
    assert gs["treasury_coins"] == treasury + 1
    assert env.state.rewards == {0: 1, 1: -1}
    assert_conserved(env)


def test_steal_pays_out_from_exiled_blocker_with_remainder_to_treasury_in_multiplayer():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Duke"], 1: ["Duke"], 2: ["Assassin", "Contessa"]}, revealed={1: ["Contessa"]})
    give_coins(env, 1, 5)
    treasury = gs["treasury_coins"]
    play(env, "steal 1", "block steal ambassador", "pass", "bullshit")
    assert 1 in env.state.eliminated
    assert gs["coins"] == {0: 4, 1: 0, 2: 2}
    assert gs["treasury_coins"] == treasury + 3
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_proven_steal_pays_out_from_target_exiled_by_failed_challenge():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Duke"], 1: ["Duke"], 2: ["Assassin", "Contessa"]}, revealed={1: ["Contessa"]})
    give_coins(env, 1, 4)
    treasury = gs["treasury_coins"]
    play(env, "steal 1", "bullshit")
    assert 1 in env.state.eliminated
    assert gs["coins"] == {0: 4, 1: 0, 2: 2}
    assert gs["treasury_coins"] == treasury + 2
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_steal_target_forfeiting_returns_coins_without_paying_the_steal():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Duke"], 1: ["Duke", "Assassin"], 2: ["Ambassador", "Contessa"]})
    give_coins(env, 1, 4)
    treasury = gs["treasury_coins"]
    env.step("steal 1")
    for _ in range(4):
        env.step("gibberish")
    assert 1 in env.state.eliminated
    assert gs["coins"] == {0: 2, 1: 0, 2: 2}
    assert gs["treasury_coins"] == treasury + 4
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_steal_takes_up_to_two_coins():
    env = make_env()
    env.state.game_state["coins"][1] = 1
    env.step("steal 1")
    env.step("pass")
    assert env.state.game_state["coins"] == {0: 2, 1: 0}


def test_successfully_challenged_assassination_refunds_cost():
    env = make_env()
    gs = deal(env, {0: ["Duke", "Contessa"], 1: ["Assassin", "Captain"]})
    give_coins(env, 0, 5)
    treasury = gs["treasury_coins"]
    env.step("assassinate 1")
    assert gs["coins"][0] == 2
    env.step("bullshit")
    assert_awaiting_reveal(env, 0)
    # The cost is returned as soon as the bluff is exposed, before the bluffer chooses a card.
    assert gs["coins"][0] == 5
    env.step("reveal duke")
    assert gs["coins"][0] == 5
    assert gs["treasury_coins"] == treasury
    assert gs["revealed_hand"][0] == ["Duke"]
    assert gs["hidden_hand"][1] == ["Assassin", "Captain"]
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_refund_is_announced_when_assassination_bluff_is_caught():
    env = make_env(num_players=3)
    deal(env, {0: ["Duke", "Contessa"], 1: ["Assassin", "Captain"], 2: ["Ambassador", "Duke"]})
    give_coins(env, 0, 3)
    env.step("assassinate 1")
    env.step("bullshit")
    observations = env.state.observations[2]
    assert any("3 coins paid for the assassination are returned" in text for _, text, _ in observations)


def test_contessa_blocked_assassination_keeps_cost_spent():
    env = make_env()
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Contessa", "Captain"]})
    give_coins(env, 0, 4)
    treasury = gs["treasury_coins"]
    play(env, "assassinate 1", "block assassinate", "pass")
    assert gs["coins"][0] == 1
    assert gs["treasury_coins"] == treasury + 3
    assert gs["hidden_hand"][1] == ["Contessa", "Captain"]
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_honestly_blocked_assassination_keeps_cost_spent_after_block_challenge():
    env = make_env()
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Contessa", "Captain"]})
    give_coins(env, 0, 4)
    play(env, "assassinate 1", "block assassinate", "bullshit")
    assert_awaiting_reveal(env, 0)
    play(env, "reveal duke")
    assert gs["coins"][0] == 1
    assert len(gs["hidden_hand"][1]) == 2
    assert_conserved(env)


def test_two_player_start_gives_starting_player_one_coin():
    env = make_env(num_players=2)
    gs = env.state.game_state
    assert env.state.current_player_id == 0
    assert gs["coins"] == {0: 1, 1: 2}
    assert gs["treasury_coins"] == 47
    assert_conserved(env)


@pytest.mark.parametrize("num_players", [3, 4, 5, 6])
def test_multiplayer_start_gives_everyone_two_coins(num_players):
    env = make_env(num_players=num_players)
    gs = env.state.game_state
    assert gs["coins"] == {pid: 2 for pid in range(num_players)}
    assert gs["treasury_coins"] == 50 - 2 * num_players
    assert_conserved(env)


@pytest.mark.parametrize("command", ["income", "tax", "foreign aid", "steal 1", "assassinate 1", "exchange"])
def test_ten_or_more_coins_forces_a_coup(command):
    env = make_env()
    gs = deal(env, {0: ["Duke", "Assassin"], 1: ["Captain", "Contessa"]})
    give_coins(env, 0, 10)
    before = copy.deepcopy(gs)
    done, _ = env.step(command)
    assert not done
    assert gs == before
    assert env.state.current_player_id == 0
    assert any("10 or more coins" in text for _, text, _ in env.state.observations[0][-3:])
    play(env, "coup 1")
    assert gs["coins"][0] == 3
    assert_awaiting_reveal(env, 1)
    assert_conserved(env)


def test_nine_coins_does_not_force_a_coup():
    env = make_env()
    give_coins(env, 0, 9)
    play(env, "income")
    assert env.state.game_state["coins"][0] == 10
    assert env.state.current_player_id == 1


@pytest.mark.parametrize(
    "command",
    ["coup 1 now", "block", "block assassinate extra", "[income] [tax]", "reveal duke", "reveal"],
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
    assert_awaiting_reveal(env, 1)
    env.step("reveal captain")
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
    env.step("reveal contessa")
    assert env.state.current_player_id == 1
    assert gs["phase"] == GamePhase.QueryForBlockOrChallenge
    before = (dict(gs["coins"]), list(gs["hidden_hand"][1]), list(gs["revealed_hand"][1]))
    done, _ = env.step("bullshit")
    assert not done
    assert env.state.error_count == 1
    assert (gs["coins"], gs["hidden_hand"][1], gs["revealed_hand"][1]) == before


# ---------------------------------------------------------------------------
# Choosing which influence to lose (QueryWhichToReveal)
# ---------------------------------------------------------------------------
def test_coup_target_chooses_which_influence_to_reveal():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Duke", "Contessa"], 2: ["Duke", "Captain"]})
    give_coins(env, 0, 7)
    treasury = gs["treasury_coins"]
    play(env, "coup 2")
    assert_awaiting_reveal(env, 2)
    assert gs["coins"][0] == 0 and gs["treasury_coins"] == treasury + 7
    assert gs["hidden_hand"][2] == ["Duke", "Captain"]  # nothing is revealed until they choose
    play(env, "reveal captain")
    assert gs["hidden_hand"][2] == ["Duke"]
    assert gs["revealed_hand"][2] == ["Captain"]
    assert gs["phase"] == GamePhase.Play and gs["pending_influence_loss"] is None
    assert env.state.current_player_id == 1  # next player after the coup's source
    assert_conserved(env)


def test_losing_last_influence_needs_no_choice_and_returns_coins():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Duke", "Contessa"], 1: ["Duke"]}, revealed={1: ["Captain"]})
    give_coins(env, 0, 7)
    give_coins(env, 1, 3)
    treasury = gs["treasury_coins"]
    done, _ = play(env, "coup 1")
    assert not done
    assert gs["phase"] == GamePhase.Play and gs["pending_influence_loss"] is None
    assert gs["revealed_hand"][1] == ["Captain", "Duke"]
    assert 1 in env.state.eliminated
    assert gs["coins"][1] == 0 and gs["treasury_coins"] == treasury + 7 + 3
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_identical_cards_still_require_a_choice():
    # Skipping the prompt for a pair would tell every other player the hand is a pair.
    env = make_env()
    deal(env, {0: ["Duke", "Contessa"], 1: ["Captain", "Captain"]})
    give_coins(env, 0, 7)
    play(env, "coup 1")
    assert_awaiting_reveal(env, 1)
    call_to_action = env.render(1)
    assert "Player #0 launched a coup against you" in call_to_action
    assert call_to_action.count("'reveal Captain'") == 1


def test_assassination_target_chooses_which_influence_to_reveal():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Duke", "Captain"], 2: ["Contessa", "Ambassador"]})
    give_coins(env, 0, 3)
    play(env, "assassinate 2", "pass", "pass")  # the target is asked first, then the bystander
    assert_awaiting_reveal(env, 2)
    play(env, "reveal ambassador")
    assert gs["hidden_hand"][2] == ["Contessa"]
    assert gs["revealed_hand"][2] == ["Ambassador"]
    assert gs["coins"][0] == 0
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_failed_challenge_by_bystander_then_steal_resolves():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Duke"], 1: ["Contessa", "Assassin"], 2: ["Ambassador", "Duke"]})
    play(env, "steal 1", "pass", "bullshit")  # the target declines; the bystander challenges and loses
    assert_awaiting_reveal(env, 2)
    assert gs["coins"] == {0: 2, 1: 2, 2: 2}
    play(env, "reveal duke")
    assert gs["revealed_hand"][2] == ["Duke"]
    assert gs["coins"] == {0: 4, 1: 0, 2: 2}
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_failed_challenge_then_exchange_proceeds():
    env = make_env()
    gs = deal(env, {0: ["Ambassador", "Duke"], 1: ["Captain", "Contessa"]})
    play(env, "exchange", "bullshit")
    assert_awaiting_reveal(env, 1)
    play(env, "reveal contessa")
    assert gs["phase"] == GamePhase.QueryWhichToKeep
    assert env.state.current_player_id == 0
    assert len(gs["hidden_hand"][0]) == 4
    kept = gs["hidden_hand"][0][:2]
    play(env, f"keep {kept[0]} {kept[1]}")
    assert gs["hidden_hand"][0] == kept
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_failed_challenge_of_assassin_costs_challenger_then_target():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Captain", "Contessa"], 2: ["Duke", "Ambassador"]})
    give_coins(env, 0, 3)
    play(env, "assassinate 1", "pass", "bullshit")  # the target declines; the bystander challenges and loses
    assert_awaiting_reveal(env, 2)
    play(env, "reveal ambassador")
    # The proven assassination still resolves against its target.
    assert_awaiting_reveal(env, 1)
    play(env, "reveal captain")
    assert gs["revealed_hand"] == {0: [], 1: ["Captain"], 2: ["Ambassador"]}
    assert gs["coins"][0] == 0
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_target_who_loses_challenge_and_passes_loses_both_influences():
    env = make_env()
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Captain", "Contessa"]})
    give_coins(env, 0, 3)
    play(env, "assassinate 1", "bullshit", "reveal captain")
    # The target keeps its separate chance to block before the assassination lands.
    assert gs["phase"] == GamePhase.QueryForBlockOrChallenge
    assert env.state.current_player_id == 1
    done, info = play(env, "pass")
    assert done and info == {"winner": 0}
    assert gs["revealed_hand"][1] == ["Captain", "Contessa"]
    assert env.state.rewards == {0: 1, 1: -1}
    assert_conserved(env)


def test_assassination_fizzles_when_failed_challenge_eliminates_target():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Captain"], 2: ["Duke", "Ambassador"]}, revealed={1: ["Contessa"]})
    give_coins(env, 0, 3)
    give_coins(env, 1, 4)
    treasury = gs["treasury_coins"]
    done, _ = play(env, "assassinate 1", "bullshit")
    assert not done
    assert gs["revealed_hand"][1] == ["Contessa", "Captain"]
    assert 1 in env.state.eliminated
    assert gs["phase"] == GamePhase.Play and gs["pending_influence_loss"] is None
    assert gs["coins"][0] == 0 and gs["coins"][1] == 0
    assert gs["treasury_coins"] == treasury + 3 + 4
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_caught_bluffer_chooses_reveal_and_action_fails():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Duke", "Contessa"], 1: ["Captain", "Assassin"], 2: ["Ambassador", "Duke"]})
    play(env, "steal 1", "bullshit")
    assert_awaiting_reveal(env, 0)
    play(env, "reveal duke")
    assert gs["revealed_hand"][0] == ["Duke"]
    assert gs["coins"] == {0: 2, 1: 2, 2: 2}
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


@pytest.mark.parametrize(
    "action,block,block_card,source_coins",
    [
        ("steal 1", "block steal captain", "Captain", 3),
        ("steal 1", "block steal ambassador", "Ambassador", 3),
        ("assassinate 1", "block assassinate", "Contessa", 0),
    ],
)
def test_failed_challenge_of_honest_block_costs_challenger(action, block, block_card, source_coins):
    env = make_env()
    gs = deal(env, {0: ["Assassin", "Captain"], 1: [block_card, "Duke"]})
    give_coins(env, 0, 3)
    play(env, action, block, "bullshit")
    assert_awaiting_reveal(env, 0)
    play(env, "reveal captain")
    assert gs["revealed_hand"] == {0: ["Captain"], 1: []}
    assert len(gs["hidden_hand"][1]) == 2
    assert gs["coins"] == {0: source_coins, 1: 2}
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_failed_challenge_of_honest_block_by_bystander():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Assassin"], 1: ["Duke", "Captain"], 2: ["Assassin", "Contessa"]})
    play(env, "foreign aid", "block foreign aid", "pass", "bullshit")
    assert_awaiting_reveal(env, 2)
    play(env, "reveal contessa")
    assert gs["revealed_hand"][2] == ["Contessa"]
    assert gs["coins"] == {0: 2, 1: 2, 2: 2}
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_caught_foreign_aid_blocker_reveals_then_aid_resolves():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Assassin"], 1: ["Contessa", "Ambassador"], 2: ["Duke", "Duke"]})
    play(env, "foreign aid", "block foreign aid", "bullshit")
    assert_awaiting_reveal(env, 1)
    play(env, "reveal ambassador")
    assert gs["revealed_hand"][1] == ["Ambassador"]
    assert gs["coins"] == {0: 4, 1: 2, 2: 2}
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_caught_steal_blocker_reveals_then_steal_resolves():
    env = make_env()
    gs = deal(env, {0: ["Captain", "Duke"], 1: ["Assassin", "Contessa"]})
    play(env, "steal 1", "block steal ambassador", "bullshit")
    assert_awaiting_reveal(env, 1)
    play(env, "reveal assassin")
    assert gs["hidden_hand"][1] == ["Contessa"]
    assert gs["coins"] == {0: 3, 1: 0}
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_bluffed_contessa_block_costs_two_influences():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Assassin", "Duke"], 1: ["Duke", "Captain"], 2: ["Ambassador", "Contessa"]})
    give_coins(env, 0, 3)
    give_coins(env, 1, 5)
    treasury = gs["treasury_coins"]
    play(env, "assassinate 1", "block assassinate", "bullshit")
    assert_awaiting_reveal(env, 1)
    done, _ = play(env, "reveal duke")
    assert not done
    # The failed block lets the assassination through, which takes the last card automatically.
    assert gs["revealed_hand"][1] == ["Duke", "Captain"]
    assert 1 in env.state.eliminated
    assert gs["coins"][1] == 0 and gs["treasury_coins"] == treasury + 3 + 5
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_bystander_eliminated_by_failed_challenge_is_skipped_in_turn_order():
    env = make_env(num_players=4)
    gs = deal(
        env,
        {0: ["Duke", "Contessa"], 1: ["Captain"], 2: ["Assassin", "Ambassador"], 3: ["Duke", "Captain"]},
        revealed={1: ["Contessa"]},
    )
    give_coins(env, 1, 4)
    treasury = gs["treasury_coins"]
    done, _ = play(env, "tax", "bullshit")
    assert not done
    assert 1 in env.state.eliminated
    assert gs["revealed_hand"][1] == ["Contessa", "Captain"]
    assert gs["coins"][0] == 5 and gs["coins"][1] == 0
    assert gs["treasury_coins"] == treasury - 3 + 4
    assert env.state.current_player_id == 2
    assert_conserved(env)


@pytest.mark.parametrize(
    "command",
    ["reveal contessa", "pass", "income", "bullshit", "keep duke", "reveal", "reveal duke captain", "reveal joker"],
)
def test_invalid_reveals_are_atomic(command):
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Assassin", "Duke"], 2: ["Duke", "Captain"]})
    give_coins(env, 0, 7)
    play(env, "coup 2")
    before = copy.deepcopy(gs)
    done, _ = env.step(command)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before
    assert_awaiting_reveal(env, 2)


@pytest.mark.parametrize("command", ["reveal captain", "REVEAL Captain", "[reveal captain]"])
def test_reveal_command_is_case_insensitive(command):
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Assassin", "Duke"], 2: ["Duke", "Captain"]})
    give_coins(env, 0, 7)
    play(env, "coup 2", command)
    assert gs["revealed_hand"][2] == ["Captain"]


def test_invalid_limit_during_challenge_reveal_still_resolves_proven_action():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Duke", "Contessa"], 1: ["Captain", "Assassin"], 2: ["Ambassador", "Captain"]})
    play(env, "tax", "bullshit")
    assert_awaiting_reveal(env, 1)
    for _ in range(4):
        done, _ = env.step("gibberish")
    assert not done
    assert 1 in env.state.eliminated
    assert gs["revealed_hand"][1] == ["Captain", "Assassin"]
    assert gs["coins"] == {0: 5, 1: 0, 2: 2}
    assert gs["phase"] == GamePhase.Play and gs["pending_influence_loss"] is None
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_invalid_limit_by_coup_target_during_reveal_ends_game():
    env = make_env()
    gs = deal(env, {0: ["Duke", "Contessa"], 1: ["Captain", "Assassin"]})
    give_coins(env, 0, 7)
    play(env, "coup 1")
    for _ in range(3):
        assert env.step("pass") == (False, {})
    done, _ = env.step("pass")
    assert done
    assert gs["revealed_hand"][1] == ["Captain", "Assassin"]
    assert env.state.rewards == {0: 1, 1: -1}
    assert_conserved(env)


def test_invalid_limit_by_caught_blocker_during_reveal_lets_action_resolve():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Captain", "Assassin"], 1: ["Contessa", "Ambassador"], 2: ["Duke", "Duke"]})
    play(env, "foreign aid", "block foreign aid", "bullshit")
    assert_awaiting_reveal(env, 1)
    for _ in range(4):
        env.step("reveal duke")  # they hold no Duke
    assert 1 in env.state.eliminated
    assert gs["coins"] == {0: 4, 1: 0, 2: 2}
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 2
    assert_conserved(env)


def test_snapshot_restore_during_pending_reveal():
    env = make_env(num_players=3)
    deal(env, {0: ["Assassin", "Duke"], 1: ["Captain", "Contessa"], 2: ["Duke", "Ambassador"]})
    give_coins(env, 0, 3)
    play(env, "assassinate 1", "pass", "bullshit")  # the challenger and then the target must reveal
    snapshot = env.snapshot()
    play(env, "reveal ambassador", "reveal captain")
    expected = copy.deepcopy(env.state.game_state)

    env.restore(snapshot)
    assert_awaiting_reveal(env, 2)
    play(env, "reveal ambassador", "reveal captain")
    assert env.state.game_state == expected

    env.restore(snapshot)
    play(env, "reveal duke")
    assert env.state.game_state["revealed_hand"][2] == ["Duke"]
    assert_awaiting_reveal(env, 1)


def test_reveal_choice_keeps_hidden_cards_private():
    env = make_env(num_players=3)
    deal(env, {0: ["Duke", "Contessa"], 1: ["Duke", "Contessa"], 2: ["Ambassador", "Captain"]})
    give_coins(env, 0, 7)
    start = len(env.state.events)
    play(env, "coup 2")
    assert "Ambassador" not in str(env._render_board(viewer_id=0))
    assert "Player #2 must choose an influence to reveal" in str(env._render_board(viewer_id=0))
    play(env, "reveal duke", "reveal captain")  # the first attempt is rejected: they hold no Duke

    def visible_to(pid):
        return "\n".join(message for _, message, _, to_id in env.state.events[start:] if to_id in (-1, pid))

    for observer in (0, 1):
        text = visible_to(observer)
        assert "Ambassador" not in text
        assert "reveal duke" not in text and "reveal captain" not in text
        assert "Player #2 revealed and lost a Captain influence" in text
    assert "'reveal Ambassador' or 'reveal Captain'" in visible_to(2)


def test_prompts_explain_how_to_reveal():
    env = make_env()
    assert "reveal <card>" in env.prompt(0)
    deal(env, {0: ["Duke", "Contessa"], 1: ["Assassin", "Captain"]})
    play(env, "tax", "bullshit")
    call_to_action = env.render(1)
    assert "your challenge of Player #0's Duke claim failed" in call_to_action
    assert "'reveal Assassin' or 'reveal Captain'" in call_to_action


# ---------------------------------------------------------------------------
# Invalid-move escalation (upstream's _set_invalid_move policy is covered by on_invalid_limit)
# ---------------------------------------------------------------------------
def test_invalid_limit_during_exchange_forfeits_only_real_influence():
    env = make_env(num_players=3)
    gs = deal(env, {0: ["Ambassador", "Duke"], 1: ["Captain", "Contessa"], 2: ["Assassin", "Captain"]})
    play(env, "exchange", "pass", "pass")
    assert gs["phase"] == GamePhase.QueryWhichToKeep and len(gs["hidden_hand"][0]) == 4
    for _ in range(4):
        env.step("income")
    # The two drawn Court cards go back to the deck instead of being revealed.
    assert gs["revealed_hand"][0] == ["Ambassador", "Duke"]
    assert len(gs["pile"]) == 15 - 2 * 3
    assert 0 in env.state.eliminated and gs["coins"][0] == 0
    assert gs["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1
    assert_conserved(env)


def test_invalid_limit_by_targeted_player_passes_turn_after_source():
    env = make_env(num_players=4)
    play(env, "steal 2")
    for _ in range(4):
        env.step("income")
    assert 2 in env.state.eliminated
    assert env.state.game_state["coins"][0] == 2
    assert env.state.game_state["phase"] == GamePhase.Play
    assert env.state.current_player_id == 1  # not Player 3: the turn passes after the action's source
    assert_conserved(env)


# ---------------------------------------------------------------------------
# Randomized invariants
# ---------------------------------------------------------------------------
def _random_action(env, rng):
    gs = env.state.game_state
    pid = env.state.current_player_id
    if rng.random() < 0.1:
        return rng.choice(["nonsense", "reveal", "reveal joker", "pass", "income", "bullshit", "keep duke", "coup 0"])
    phase = gs["phase"]
    others = [p for p in range(env.state.num_players) if p != pid and gs["hidden_hand"][p]]
    hand = gs["hidden_hand"][pid]
    if phase == GamePhase.Play:
        if gs["coins"][pid] >= 10:
            return f"coup {rng.choice(others)}"
        options = ["income", "foreign aid", "tax", "exchange", f"steal {rng.choice(others)}"]
        if gs["coins"][pid] >= 3:
            options.append(f"assassinate {rng.choice(others)}")
        if gs["coins"][pid] >= 7:
            options.append(f"coup {rng.choice(others)}")
        return rng.choice(options)
    if phase == GamePhase.QueryForBlockOrChallenge:
        metadata = gs["action_metadata"]
        options = ["pass", "pass", "bullshit"]
        if metadata.action_type is CoupActionType.ForeignAid:
            options.append("block foreign aid")
        elif metadata.target_player_id == pid and metadata.action_type is CoupActionType.Steal:
            options += ["block steal captain", "block steal ambassador"]
        elif metadata.target_player_id == pid and metadata.action_type is CoupActionType.Assassinate:
            options.append("block assassinate")
        return rng.choice(options)
    if phase == GamePhase.QueryToChallengeTheBlocker:
        return rng.choice(["pass", "pass", "bullshit"])
    if phase == GamePhase.QueryWhichToKeep:
        return "keep " + " ".join(rng.sample(hand, 2 - len(gs["revealed_hand"][pid])))
    return f"reveal {rng.choice(hand)}"


@pytest.mark.parametrize("num_players", [2, 3, 4, 5, 6])
def test_random_games_conserve_cards_and_coins_and_terminate(num_players):
    for seed in range(20):
        env = make_env(num_players=num_players, seed=seed)
        rng = random.Random(seed)
        done = False
        for _ in range(2000):
            gs = env.state.game_state
            before, errors = copy.deepcopy(gs), env.state.error_count
            done, _ = env.step(_random_action(env, rng))
            if env.state.error_count > errors:
                assert env.state.game_state == before
            assert_conserved(env)
            out = {pid for pid in range(num_players) if not gs["hidden_hand"][pid]}
            assert out == set(env.state.eliminated)
            assert all(gs["coins"][pid] == 0 for pid in out)
            assert all(len(gs["revealed_hand"][pid]) <= 2 for pid in range(num_players))
            if done:
                break
        assert done, f"seed {seed} did not finish"
        survivors = [pid for pid in range(num_players) if gs["hidden_hand"][pid]]
        assert len(survivors) == 1
        assert env.state.rewards[survivors[0]] == 1
