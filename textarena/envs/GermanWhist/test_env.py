"""Offline deterministic tests for GermanWhist (2-player trick-taking).

Hands are readable from game_state, letting us always choose a legal card and
drive a full 26-trick game to a deterministic terminal state. Cards are played
with 'play X' (1-based index into the current hand).
"""
import copy

from textarena.envs.GermanWhist.env import GermanWhistEnv


def _fresh():
    env = GermanWhistEnv()
    env.reset(num_players=2, seed=42)
    return env


def _legal_index(env) -> int:
    """Return a 1-based index of a legal card for the current player."""
    gs = env.state.game_state
    pid = env.state.current_player_id
    hand = gs["players"][pid]["hand"]
    trick = gs["current_trick"]
    if trick:
        lead_suit = trick[0][1]["suit"]
        for i, card in enumerate(hand):
            if card["suit"] == lead_suit:
                return i + 1  # must follow suit if possible
    return 1  # leading, or void in lead suit -> any card


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["players"][0]["hand"]) == 13
    assert len(gs["players"][1]["hand"]) == 13
    assert len(gs["deck"]) == 26
    assert gs["phase"] == "learning"
    assert gs["trump_suit"] in ["♠", "♥", "♦", "♣"]
    assert gs["tricks_won"] == {0: 0, 1: 0}
    assert env.state.current_player_id == 0


def test_single_trick_resolves_and_redraws():
    env = _fresh()
    env.step(f"play {_legal_index(env)}")   # player 0 leads
    done, _ = env.step(f"play {_legal_index(env)}")  # player 1 follows -> resolve
    gs = env.state.game_state
    assert not done
    # Exactly one trick has been won in total.
    assert gs["tricks_won"][0] + gs["tricks_won"][1] == 1
    # Learning phase: each player drew a replacement, so hands are 13 again.
    assert len(gs["players"][0]["hand"]) == 13
    assert len(gs["players"][1]["hand"]) == 13


def test_full_game_reaches_terminal_with_consistent_winner():
    env = _fresh()
    done = False
    for _ in range(200):
        done, _ = env.step(f"play {_legal_index(env)}")
        if done:
            break
    assert done
    gs = env.state.game_state
    t0, t1 = gs["tricks_won"][0], gs["tricks_won"][1]
    assert t0 + t1 == 26
    if t0 > t1:
        assert env.state.rewards == {0: 1, 1: -1}
    elif t1 > t0:
        assert env.state.rewards == {0: -1, 1: 1}
    else:
        assert env.state.rewards == {0: 0, 1: 0}
    played = [
        (card["rank"], card["suit"])
        for trick in gs["completed_tricks"]
        for _, card in trick
    ]
    assert len(played) == 52
    assert len(set(played)) == 52


def test_invalid_format_does_not_end_game():
    env = _fresh()
    done, _ = env.step("I lead a card")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_out_of_range_index_is_invalid():
    env = _fresh()
    done, _ = env.step("play 99")
    assert not done
    assert env.state.error_count == 1


def test_follow_suit_violation_is_invalid():
    env = _fresh()
    gs = env.state.game_state
    # Player 0 leads their card 1.
    lead_card = gs["players"][0]["hand"][0]
    env.step("play 1")
    lead_suit = lead_card["suit"]
    p1_hand = gs["players"][1]["hand"]
    has_lead = any(c["suit"] == lead_suit for c in p1_hand)
    off_idx = next((i for i, c in enumerate(p1_hand) if c["suit"] != lead_suit), None)
    if has_lead and off_idx is not None:
        done, _ = env.step(f"play {off_idx + 1}")  # refuse to follow suit
        assert not done
        assert env.state.error_count == 1
    else:
        # Seed-dependent: player 1 is void in / all-in the lead suit; just make a
        # legal play so the test remains meaningful without a false failure.
        done, _ = env.step(f"play {_legal_index(env)}")
        assert not done


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    offender = env.state.current_player_id
    env.step("garbage")
    done, _ = env.step("more garbage")
    assert done
    assert env.state.rewards[offender] == -1
    assert env.state.rewards[1 - offender] == 1


def test_card_conservation_after_learning_trick():
    env = _fresh()
    env.step(f"play {_legal_index(env)}")
    env.step(f"play {_legal_index(env)}")
    gs = env.state.game_state
    accounted = (
        len(gs["deck"])
        + sum(len(player["hand"]) for player in gs["players"].values())
        + len(gs["current_trick"])
        + sum(len(trick) for trick in gs["completed_tricks"])
    )
    assert accounted == 52


def test_learning_phase_transitions_after_exactly_thirteen_tricks():
    env = _fresh()
    for _ in range(26):
        done, _ = env.step(f"play {_legal_index(env)}")
        assert not done
    gs = env.state.game_state
    assert gs["phase"] == "playing"
    assert gs["tricks_in_learning"] == 13
    assert gs["tricks_in_playing"] == 0
    assert len(gs["deck"]) == 0
    assert [len(gs["players"][pid]["hand"]) for pid in (0, 1)] == [13, 13]


def test_trump_and_lead_suit_ranking():
    env = _fresh()
    ace_spades = next(card for card in env.deck if card["rank"] == "A" and card["suit"] == "♠")
    two_hearts = next(card for card in env.deck if card["rank"] == "2" and card["suit"] == "♥")
    winner, _ = env._determine_trick_winner([(0, ace_spades), (1, two_hearts)], "♥")
    assert winner == 1
    king_spades = next(card for card in env.deck if card["rank"] == "K" and card["suit"] == "♠")
    winner, _ = env._determine_trick_winner([(0, king_spades), (1, two_hearts)], "♣")
    assert winner == 0


def test_face_down_draw_is_private_to_loser():
    env = _fresh()
    env.step(f"play {_legal_index(env)}")
    env.step(f"play {_legal_index(env)}")
    private_draws = [
        event for event in env.state.events
        if event[1].startswith("You received a face-down card:")
    ]
    assert len(private_draws) == 1
    _, message, _, loser_id = private_draws[0]
    card_name = message.rsplit(": ", 1)[1]
    assert loser_id in (0, 1)
    assert not any(
        card_name in public_message
        for _, public_message, _, to_id in env.state.events
        if to_id == -1 and public_message != message
    )


def test_huge_card_index_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("play " + "9" * 5000)
    assert env.state.game_state == before


def test_snapshot_restore_replays_identically():
    env = _fresh()
    snapshot = env.snapshot()
    action = f"play {_legal_index(env)}"
    env.step(action)
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step(action)
    assert env.state.game_state == expected
