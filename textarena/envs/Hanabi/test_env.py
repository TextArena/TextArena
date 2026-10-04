"""Offline deterministic tests for Hanabi (cooperative team game).

Hands are hidden from the acting player but readable from game_state, so we can
script exact plays. We test the core mechanics (play/discard/reveal token
accounting and the invalid-move "skip turn" behaviour) rather than a full 25/25
solve, which would require a very long scripted sequence.
"""
import pytest
import textarena as ta

from textarena.envs.Hanabi.env import Card, HanabiEnv, Suit


def _fresh(num_players=2, **kwargs):
    env = HanabiEnv(**kwargs)
    env.reset(num_players=num_players, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["info_tokens"] == 8
    assert gs["fuse_tokens"] == 3
    assert env.hand_size == 5  # 2-3 players -> hand size 5
    assert len(gs["player_hands"][0]) == 5
    assert len(gs["player_hands"][1]) == 5
    assert all(v == 0 for v in gs["fireworks"].values())
    assert env.state.current_player_id == 0


def test_registered_default_and_mdp_variants():
    assert ta.make("Hanabi-v0").env.__class__ is HanabiEnv
    assert ta.make("Hanabi-v0-mdp").env.__class__ is HanabiEnv


def test_registered_env_starts_with_three_fuse_tokens():
    env = ta.make("Hanabi-v0")
    env.reset(num_players=2, seed=0)
    assert env.state.game_state["fuse_tokens"] == 3


def test_play_card_updates_fireworks_or_fuse():
    env = _fresh()
    gs = env.state.game_state
    pid = env.state.current_player_id
    card = gs["player_hands"][pid][0]
    suit, rank = card.suit, card.rank
    fuse_before = gs["fuse_tokens"]

    done, _ = env.step("Play 0")
    assert not done
    if rank == 1:  # all fireworks start at 0, so a rank-1 is always playable
        assert gs["fireworks"][suit] == 1
        assert gs["fuse_tokens"] == fuse_before
    else:
        assert gs["fireworks"][suit] == 0
        assert gs["fuse_tokens"] == fuse_before - 1
    # A successful action rotates to the next player.
    assert env.state.current_player_id == 1


def test_reveal_consumes_info_token():
    env = _fresh()
    gs = env.state.game_state
    # Player 0 hints player 1 about card 0 using its true color.
    target_color = gs["player_hands"][1][0].suit.value
    done, _ = env.step(f"Reveal player 1 card 0 color {target_color}")
    assert not done
    assert gs["info_tokens"] == 7
    assert env.state.current_player_id == 1


def test_reveal_identifies_every_card_matching_the_clue():
    env = _fresh()
    gs = env.state.game_state
    target_hand = gs["player_hands"][1]
    color = target_hand[0].suit.value
    expected_indices = [
        idx for idx, card in enumerate(target_hand) if card.suit.value == color
    ]
    event_start = len(env.state.events)
    env.step(f"Reveal player 1 card 0 color {color}")
    messages = [message for _, message, _, _ in env.state.events[event_start:]]
    assert any(
        f"indices {expected_indices}" in message and f"All {color} cards" in message
        for message in messages
    )


def test_false_hint_is_rejected_without_spending_token():
    env = _fresh()
    gs = env.state.game_state
    actual_color = gs["player_hands"][1][0].suit
    false_color = next(suit.value for suit in Suit if suit != actual_color)

    done, _ = env.step(f"Reveal player 1 card 0 color {false_color}")

    assert not done
    assert gs["info_tokens"] == 8
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_discard_replenishes_info_token():
    env = _fresh()
    gs = env.state.game_state
    # First spend a token via a reveal so we're below the cap of 8.
    target_color = gs["player_hands"][1][0].suit.value
    env.step(f"Reveal player 1 card 0 color {target_color}")
    assert gs["info_tokens"] == 7
    # Player 1 discards -> gains a token back.
    discards_before = len(gs["discard_pile"])
    done, _ = env.step("Discard 0")
    assert not done
    assert gs["info_tokens"] == 8
    assert len(gs["discard_pile"]) == discards_before + 1


def test_discard_respects_configured_info_token_cap():
    env = _fresh(info_tokens=3)
    gs = env.state.game_state
    gs["info_tokens"] = 2
    env.step("Discard 0")
    assert gs["info_tokens"] == 3


def test_empty_deck_shrinks_hand_without_adding_placeholder():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"].clear()
    gs["info_tokens"] -= 1
    hand = gs["player_hands"][0]
    before = len(hand)

    done, _ = env.step("Discard 0")

    assert not done
    assert len(hand) == before - 1
    assert None not in hand


def test_deck_exhaustion_returns_normalized_team_score():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"].clear()
    gs["last_round"] = env.state.current_player_id
    gs["fireworks"][Suit.WHITE] = 3
    gs["info_tokens"] -= 1

    done, _ = env.step("Discard 0")

    assert done
    assert env.state.rewards == {0: 3 / 25, 1: 3 / 25}


def test_default_game_ends_on_the_third_misplay():
    env = _fresh()
    gs = env.state.game_state
    for misplay in (1, 2, 3):
        card = gs["player_hands"][env.state.current_player_id][0]
        gs["fireworks"][card.suit] = card.rank  # that rank is already on the firework
        done, _ = env.step("Play 0")
        assert gs["fuse_tokens"] == 3 - misplay
        assert done == (misplay == 3)
    assert env.state.rewards == {0: 0, 1: 0}


def test_using_last_fuse_ends_game():
    env = _fresh()
    gs = env.state.game_state
    card = gs["player_hands"][0][0]
    gs["fireworks"][card.suit] = card.rank
    gs["fuse_tokens"] = 1

    done, _ = env.step("Play 0")

    assert done
    assert gs["fuse_tokens"] == 0
    assert env.state.rewards == {0: 0, 1: 0}


def test_invalid_action_does_not_end_game_and_holds_turn():
    env = _fresh()
    done, _ = env.step("Frobnicate 0")  # unrecognized action
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # turn held for resubmission


def test_action_parser_rejects_trailing_text_atomically():
    env = _fresh()
    hand_before = list(env.state.game_state["player_hands"][0])
    done, _ = env.step("Play 0 and then discard 1")
    assert not done
    assert env.state.game_state["player_hands"][0] == hand_before
    assert env.state.current_player_id == 0


def test_huge_card_index_is_rejected_without_integer_parse_failure():
    env = _fresh()
    done, _ = env.step(f"Play {'9' * 5000}")
    assert not done
    assert env.state.error_count == 1
    assert len(env.state.game_state["player_hands"][0]) == 5


def test_repeated_invalid_skips_turn_without_ending():
    # Hanabi treats two invalid moves in a row as a skipped turn, not a loss.
    env = _fresh()
    env.step("Frobnicate 0")
    done, _ = env.step("Frobnicate 0")
    assert not done  # game does not end on repeated invalid moves
    assert env.state.rewards is None
    assert env.state.current_player_id == 1  # turn advanced to next player


@pytest.mark.parametrize("num_players", [2, 5])
def test_a_full_round_of_skipped_turns_ends_the_game_with_the_current_score(num_players):
    env = _fresh(num_players=num_players)
    env.state.game_state["fireworks"][Suit.GREEN] = 2
    steps = 0
    done = False
    while not done and steps < 1_000:
        done, _ = env.step("Frobnicate 0")
        steps += 1
    assert done
    assert steps == num_players * (env.error_allowance + 1)
    assert env.state.rewards == {pid: 2 / 25 for pid in range(num_players)}
    assert "Every player skipped a turn" in env.state.game_info[0]["reason"]


def test_a_valid_action_resets_the_skipped_turn_count():
    env = _fresh()
    gs = env.state.game_state
    env.step("Frobnicate 0")
    env.step("Frobnicate 0")  # Player 0 skips
    target_color = gs["player_hands"][0][0].suit.value
    env.step(f"Reveal player 0 card 0 color {target_color}")  # Player 1 acts
    env.step("Frobnicate 0")
    done, _ = env.step("Frobnicate 0")  # Player 0 skips again, but not twice in a row
    assert not done
    assert gs["skips_in_a_row"] == 1
    assert env.state.current_player_id == 1


def test_render_shows_own_hand_size_deck_size_and_hint_knowledge():
    env = _fresh()
    gs = env.state.game_state
    board = env.render(1)
    assert "you hold 5 cards (positions 0 to 4)" in board
    assert f"there are {len(gs['deck'])} cards left to draw" in board

    hand = gs["player_hands"][1]
    color = hand[0].suit.value
    env.step(f"Reveal player 1 card 0 color {color}")
    matching = [i for i, card in enumerate(hand) if card.suit.value == color]
    board = env.render(1)
    for i in range(5):
        expected = f"known: {color}" if i in matching else f"not {color}"
        assert f"card {i}: {expected}" in board

    env.step("Discard 0")  # Player 1 discards the hinted card; the rest shift down
    board = env.render(1)
    for new_index, old_index in enumerate(range(1, 5)):
        expected = f"known: {color}" if old_index in matching else f"not {color}"
        assert f"card {new_index}: {expected}" in board
    assert "card 4: no hints" in board  # the replacement card


def test_reveal_about_self_is_invalid():
    env = _fresh()
    done, _ = env.step("Reveal player 0 card 0 color red")
    assert not done
    assert env.state.error_count == 1


def test_completing_a_firework_replenishes_one_info_token():
    env = _fresh()
    gs = env.state.game_state
    gs["fireworks"][Suit.RED] = 4
    gs["info_tokens"] = 7
    gs["player_hands"][0][0] = Card(Suit.RED, 5)
    done, _ = env.step("Play 0")
    assert not done
    assert gs["fireworks"][Suit.RED] == 5
    assert gs["info_tokens"] == 8


def test_completing_a_firework_respects_info_token_cap():
    env = _fresh(info_tokens=3)
    gs = env.state.game_state
    gs["fireworks"][Suit.BLUE] = 4
    gs["player_hands"][0][0] = Card(Suit.BLUE, 5)
    env.step("Play 0")
    assert gs["info_tokens"] == 3


def test_discard_at_full_information_tokens_is_illegal_and_atomic():
    env = _fresh()
    gs = env.state.game_state
    hand_before = list(gs["player_hands"][0])
    deck_before = list(gs["deck"])
    done, _ = env.step("Discard 0")
    assert not done
    assert env.state.error_count == 1
    assert gs["player_hands"][0] == hand_before
    assert gs["deck"] == deck_before
    assert gs["discard_pile"] == []


def test_card_count_is_conserved_across_play_and_discard():
    env = _fresh(num_players=5)
    gs = env.state.game_state

    def represented_cards():
        return (
            len(gs["deck"])
            + sum(len(hand) for hand in gs["player_hands"].values())
            + len(gs["discard_pile"])
            + sum(gs["fireworks"].values())
        )

    assert represented_cards() == 50
    env.step("Play 0")
    assert represented_cards() == 50
    gs["info_tokens"] = max(0, gs["info_tokens"] - 1)
    env.step("Discard 0")
    assert represented_cards() == 50


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"info_tokens": -1}, "info_tokens"),
        ({"info_tokens": True}, "info_tokens"),
        ({"fuse_tokens": 0}, "fuse_tokens"),
        ({"fuse_tokens": False}, "fuse_tokens"),
    ],
)
def test_invalid_token_configuration_is_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        HanabiEnv(**kwargs)
