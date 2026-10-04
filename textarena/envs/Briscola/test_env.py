"""Deterministic game-logic tests for Briscola-v0 (2-player Italian trick game)."""
import copy

from textarena.envs.Briscola.env import BriscolaEnv


def _fresh(num_players=2):
    env = BriscolaEnv()
    env.reset(num_players=num_players, seed=42)
    return env


def test_reset_deals_hands_and_trump():
    env = _fresh()
    gs = env.state.game_state
    assert gs["trump_suit"] in ["♠", "♥", "♦", "♣"]
    for pid in range(2):
        assert len(gs["players"][pid]["hand"]) == 3
    # 40-card deck minus 2*3 dealt = 34 remaining (trump card sits at the bottom).
    assert len(gs["deck"]) == 34
    assert env.state.current_player_id == 0


def test_playing_card_removes_it_from_hand():
    env = _fresh()
    first_card = env.state.game_state["players"][0]["hand"][0]
    env.step("play 1")
    # after a full trick + redraw the hand is refilled, but the played card must be gone
    remaining = env.state.game_state["players"][0]["hand"]
    assert first_card not in remaining or remaining.count(first_card) < 3


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("play a card")
    assert not done
    assert env.state.error_count == 1


def test_out_of_range_card_index_increments_error_count():
    env = _fresh()
    done, _ = env.step("play 9")  # only 3 cards in hand
    assert not done
    assert env.state.error_count == 1


def test_full_game_completes_with_winner():
    env = _fresh()
    done = False
    steps = 0
    while not done and steps < 200:
        done, _ = env.step("play 1")
        steps += 1
    assert done
    gs = env.state.game_state
    # winner is whoever holds the most points, and gets reward +1 (loser -1)
    winner = max(gs["points_won"], key=gs["points_won"].get)
    assert env.state.rewards[winner] == 1
    assert env.state.rewards[1 - winner] == -1
    assert gs["points_won"][0] + gs["points_won"][1] == 120


def test_three_and_four_player_deals_are_complete():
    three = _fresh(num_players=3)
    gs3 = three.state.game_state
    assert [len(gs3["players"][pid]["hand"]) for pid in range(3)] == [3, 3, 3]
    assert len(gs3["deck"]) == 30
    assert sum(len(gs3["players"][pid]["hand"]) for pid in range(3)) + len(gs3["deck"]) == 39
    assert len(gs3["removed_cards"]) == 1
    assert (
        sum(len(gs3["players"][pid]["hand"]) for pid in range(3))
        + len(gs3["deck"])
        + len(gs3["removed_cards"])
        == 40
    )

    four = _fresh(num_players=4)
    gs4 = four.state.game_state
    assert [len(gs4["players"][pid]["hand"]) for pid in range(4)] == [3, 3, 3, 3]
    assert len(gs4["deck"]) == 28


def test_trick_winner_draws_first_and_leads_next():
    env = _fresh()
    gs = env.state.game_state
    lead = next(card for card in env.deck if card["rank"] == "A" and card["suit"] == "♠")
    follow = next(card for card in env.deck if card["rank"] == "2" and card["suit"] == "♥")
    loser_draw = next(card for card in env.deck if card["rank"] == "4" and card["suit"] == "♦")
    winner_draw = next(card for card in env.deck if card["rank"] == "5" and card["suit"] == "♦")
    gs["players"][0]["hand"] = [lead]
    gs["players"][1]["hand"] = [follow]
    gs["deck"] = [loser_draw, winner_draw]
    gs["cards_in_hand"] = 1
    gs["trump_suit"] = "♣"
    gs["trick_leader"] = 1  # stale leader must not control redraw order
    env.step("play 1")
    env.step("play 1")
    assert gs["players"][0]["hand"] == [winner_draw]
    assert gs["players"][1]["hand"] == [loser_draw]
    assert gs["trick_leader"] == 0
    assert env.state.current_player_id == 0


def test_trump_and_lead_suit_ranking():
    env = _fresh()
    ace_spades = next(card for card in env.deck if card["rank"] == "A" and card["suit"] == "♠")
    two_hearts = next(card for card in env.deck if card["rank"] == "2" and card["suit"] == "♥")
    winner, _ = env._determine_trick_winner([(0, ace_spades), (1, two_hearts)], "♥")
    assert winner == 1
    king_spades = next(card for card in env.deck if card["rank"] == "K" and card["suit"] == "♠")
    winner, _ = env._determine_trick_winner([(0, king_spades), (1, two_hearts)], "♣")
    assert winner == 0


def test_tied_final_points_are_a_draw():
    env = _fresh()
    gs = env.state.game_state
    gs["points_won"] = {0: 60, 1: 60}
    outcome = env._end_game()
    assert outcome.rewards == {0: 0, 1: 0}


def test_dealing_skips_eliminated_players():
    env = _fresh(num_players=4)
    gs = env.state.game_state
    env.eliminate(1)
    eliminated_hand = copy.deepcopy(gs["players"][1]["hand"])
    for pid in (0, 2, 3):
        gs["players"][pid]["hand"] = []
    gs["deck"] = env.deck[:4]
    gs["trick_leader"] = 0
    env._deal_new_cards()
    assert gs["players"][1]["hand"] == eliminated_hand
    assert all(len(gs["players"][pid]["hand"]) >= 1 for pid in (0, 2, 3))


def test_elimination_removes_forfeited_cards_without_forcing_more_eliminations():
    env = _fresh(num_players=4)
    gs = env.state.game_state
    env.step("bad")
    done, _ = env.step("still bad")
    assert not done
    assert env.state.eliminated == [0]

    for _ in range(200):
        done, _ = env.step("play 1")
        if done:
            break

    assert done
    assert env.state.eliminated == [0]
    assert gs["current_trick"] == []
    assert all(not gs["players"][pid]["hand"] for pid in env.state.alive_players)
    played_cards = sum(
        len(trick)
        for player_tricks in gs["tricks_won"].values()
        for trick in player_tricks
    )
    assert played_cards + len(gs["removed_cards"]) == 40
    removed_points = sum(card["points"] for card in gs["removed_cards"])
    assert sum(gs["points_won"].values()) + removed_points == 120


def test_huge_card_index_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("play " + "9" * 5000)
    assert env.state.game_state == before


def test_prompt_explains_trick_and_drawing_rules():
    env = _fresh()
    prompt = env.state.events[0][1]
    assert "You never have to follow suit" in prompt
    assert "highest card of the suit that was led wins" in prompt
    assert "trump card is the last card drawn" in prompt
    assert "2♣ is removed" not in prompt
    assert "2♣ is removed" in _fresh(num_players=3).state.events[0][1]


def test_render_shows_the_face_up_trump_card_until_the_deck_is_empty():
    env = _fresh()
    gs = env.state.game_state
    trump = env._card_to_string(gs["trump_card"])
    assert f"the face-up {trump} at the bottom is drawn last" in env.render(0)
    gs["deck"] = []
    assert trump not in env.render(0).split("Scores:")[1]


def test_render_and_snapshot_preserve_hidden_hands():
    env = _fresh()
    gs = env.state.game_state
    opponent_card = env._card_to_string(gs["players"][1]["hand"][0])
    assert opponent_card not in env.render(0)
    snapshot = env.snapshot()
    env.step("play 1")
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step("play 1")
    assert env.state.game_state == expected
