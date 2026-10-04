"""Offline, deterministic tests for the Klondike Solitaire environment.

Single-player card game: move all 52 cards to the four foundation piles.
Actions are bare commands such as ``draw``, ``move W T1`` or
``forfeit``; multiple comma-separated actions may be given per turn.
"""
import random

import pytest

from textarena.envs.Klondike.env import KlondikeEnv
from textarena.envs.Klondike.klondike import Card


def _fresh(max_turns=200, draw_count=1):
    env = KlondikeEnv(max_turns=max_turns, draw_count=draw_count)
    env.reset(num_players=1, seed=42)
    return env


def test_reset_deals_valid_layout():
    env = _fresh()
    # Tableau piles of sizes 1..7, each with only the last card face up
    assert len(env.klondike.tableau) == 7
    for i, pile in enumerate(env.klondike.tableau):
        assert len(pile) == i + 1
        assert all(not face_up for _, face_up in pile[:-1])
        assert pile[-1][1] is True
    # Remaining 24 cards in stock, foundations and waste empty
    assert len(env.klondike.stock) == 24
    assert all(len(pile) == 0 for pile in env.klondike.foundations)
    assert env.klondike.waste == []
    assert env.state.game_state["turn_count"] == 0
    assert env.state.current_player_id == 0


def test_draw_moves_card_from_stock_to_waste():
    env = _fresh()
    done, _ = env.step("draw")
    assert not done
    assert len(env.klondike.stock) == 23
    assert len(env.klondike.waste) == 1
    assert env.state.game_state["turn_count"] == 1


def test_bad_format_is_invalid_move():
    env = _fresh()
    done, _ = env.step("do something cool")  # unknown command
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["turn_count"] == 0


def test_unknown_command_is_invalid_move():
    env = _fresh()
    done, _ = env.step("fly to the moon")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["turn_count"] == 0


def test_illegal_move_consumes_turn_but_is_not_invalid():
    env = _fresh()
    # Waste is empty right after reset, so this legal-but-impossible move fails
    done, _ = env.step("move W T1")
    assert not done
    assert env.state.error_count == 0
    assert env.state.game_state["turn_count"] == 1


def test_forfeit_ends_game_with_foundation_score():
    env = _fresh()
    done, _ = env.step("forfeit")
    assert done
    assert env.state.rewards == {0: 0}  # no cards in foundations yet
    assert "forfeited" in env.state.game_info[0]["reason"].lower()


def test_turn_limit_terminates_with_partial_reward():
    env = KlondikeEnv(max_turns=3)
    env.reset(num_players=1, seed=42)
    done = False
    for _ in range(3):
        done, _ = env.step("draw")
    assert done
    assert env.state.rewards == {0: 0}
    assert "maximum" in env.state.game_info[0]["reason"].lower()


def test_win_detection_awards_full_reward():
    env = _fresh()
    # Force a won position, then take any successful action to trigger the check
    env.klondike.foundations = [
        [Card(rank, suit) for rank in range(1, 14)]
        for suit in ("♣️", "♦️", "♥️", "♠️")
    ]
    done, _ = env.step("draw")
    assert done
    assert env.state.game_state["game_won"] is True
    assert env.state.rewards == {0: 52}


def _card_state(env):
    game = env.klondike
    return (
        tuple(tuple((str(card), up) for card, up in pile) for pile in game.tableau),
        tuple(str(card) for card, _ in game.stock),
        tuple(str(card) for card, _ in game.waste),
        tuple(tuple(str(card) for card in pile) for pile in game.foundations),
    )


@pytest.mark.parametrize("seed", range(20))
def test_generated_decks_are_complete_and_deterministic(seed):
    first = KlondikeEnv()
    second = KlondikeEnv()
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert _card_state(first) == _card_state(second)

    cards = [
        card for pile in first.klondike.tableau for card, _ in pile
    ] + [card for card, _ in first.klondike.stock]
    assert len(cards) == 52
    assert len({(card.rank, card.suit) for card in cards}) == 52


def test_reset_does_not_consume_global_random_state():
    random.seed(8675309)
    expected = random.getstate()
    env = KlondikeEnv()
    env.reset(num_players=1, seed=7)
    assert random.getstate() == expected


@pytest.mark.parametrize(
    "action",
    [
        "draw now",
        "forfeit later",
        "move W T1 1 extra",
        "[draw",
        "draw]",
        "draw,,move W T1",
        "move W T99",
    ],
)
def test_malformed_commands_are_exactly_rejected_without_mutation(action):
    env = _fresh()
    before = _card_state(env)
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["turn_count"] == 0
    assert _card_state(env) == before


def test_malformed_later_batch_action_rolls_back_entire_invalid_action():
    env = _fresh()
    before = _card_state(env)
    done, _ = env.step("draw, move W T1 extra words")
    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert _card_state(env) == before


def test_forfeit_cannot_be_batched_with_state_changes():
    env = _fresh()
    before = _card_state(env)
    done, _ = env.step("draw, forfeit")
    assert not done
    assert env.state.error_count == 1
    assert _card_state(env) == before


def test_draw_three_and_recycle_preserve_card_order():
    env = _fresh(draw_count=3)
    original_draw_order = [str(card) for card, _ in reversed(env.klondike.stock)]
    env.step("draw")
    assert [str(card) for card, _ in env.klondike.waste] == original_draw_order[:3]
    while env.klondike.stock:
        env.klondike.draw()
    env.klondike.draw()
    assert str(env.klondike.waste[0][0]) == original_draw_order[0]


def test_tableau_move_rejects_malformed_face_up_run_atomically():
    env = _fresh()
    env.klondike.tableau[0] = [
        (Card(9, "♣️"), True),
        (Card(7, "♥️"), True),
    ]
    env.klondike.tableau[1] = [(Card(10, "♦️"), True)]
    before = _card_state(env)
    assert not env.klondike.move_tableau_to_tableau(0, 2, 1)
    assert _card_state(env) == before


def test_ascii_suit_cards_use_the_documented_colors():
    assert Card(7, "H").color == "red"
    assert Card(7, "D").color == "red"
    assert Card(7, "C").color == "black"
    assert Card(7, "S").color == "black"


def test_oversized_action_is_invalid_without_card_mutation():
    env = _fresh()
    before = _card_state(env)
    done, _ = env.step("9" * (env.max_action_chars + 1))
    assert not done
    assert env.state.error_count == 1
    assert _card_state(env) == before


def test_snapshot_restore_keeps_klondike_property_on_restored_state():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("draw")
    assert env.klondike.waste
    env.restore(snapshot)
    assert env.klondike.waste == []
    assert env.get_board_str() == env.render(0)


def test_render_hides_face_down_cards_and_remains_available_at_terminal():
    env = _fresh()
    hidden_card = str(env.klondike.tableau[6][0][0])
    board = env.render(0)
    assert "XX" in board
    assert hidden_card not in board
    env.step("forfeit")
    assert "KLONDIKE SOLITAIRE" in env.render(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"draw_count": 2},
        {"draw_count": True},
        {"max_turns": 0},
        {"max_turns": True},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        KlondikeEnv(**kwargs)
