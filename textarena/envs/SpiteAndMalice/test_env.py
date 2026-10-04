"""Offline, deterministic tests for the Spite and Malice environment.

Spite and Malice is a two-player card game. A full scripted win is impractical
because it depends on a shuffled deck, so these tests focus on reset structure,
turn mechanics, and the invalid-move handling paths, plus a dynamically-computed
valid play. All randomness is pinned via ``seed=42``.
"""

import copy

from textarena.envs.SpiteAndMalice.env import SpiteAndMaliceEnv


def _fresh():
    env = SpiteAndMaliceEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_reset_structure():
    env = _fresh()
    assert set(env.players.keys()) == {0, 1}
    for pid in (0, 1):
        assert len(env.players[pid]["payoff"]) == 20
        assert len(env.players[pid]["hand"]) == 5
        assert len(env.players[pid]["discard"]) == 4
    assert len(env.center_piles) == 4
    assert all(pile == [] for pile in env.center_piles)
    assert env.state.current_player_id == 0  # K♣ against 7♠ for seed 42


def test_higher_payoff_top_card_starts_and_ties_go_to_player_0():
    ranks = "A23456789JQK"
    starters = set()
    for seed in range(30):
        env = SpiteAndMaliceEnv()
        env.reset(num_players=2, seed=seed)
        top_0, top_1 = (ranks.index(env.players[pid]["payoff"][-1][0]) for pid in (0, 1))
        expected = 1 if top_1 > top_0 else 0
        assert env.state.current_player_id == env.game_state["first_player"] == expected
        prompts = [message for _, message, _, to_id in env.state.events[:2]]
        assert all(f"This game, Player {expected} goes first." in prompt for prompt in prompts)
        starters.add(expected)
    assert starters == {0, 1}
    env = SpiteAndMaliceEnv()
    env.reset(num_players=2, seed=2)  # 3♠ against 3♥
    assert env.state.current_player_id == 0


def _exhaust_deck_with_cleared_cards(env, cleared):
    gs = env.state.game_state
    gs["completed_cards"] = list(gs["deck"][:cleared])
    gs["deck"] = gs["deck"][cleared:cleared + 2]
    return gs


def test_draw_shuffles_cleared_cards_into_an_empty_draw_pile():
    env = _fresh()
    gs = _exhaust_deck_with_cleared_cards(env, cleared=11)
    gs["players"][0]["hand"] = []
    total = len(_all_cards(env))
    done = env.step("draw")
    assert not done and env.state.error_count == 0
    assert len(gs["players"][0]["hand"]) == 5
    assert gs["completed_cards"] == []
    assert len(gs["deck"]) == 11 + 2 - 5
    assert len(_all_cards(env)) == total
    messages = [message for _, message, _, to_id in env.state.events if to_id == -1]
    assert "The draw pile ran out, so the 11 cleared center cards were shuffled to form a new draw pile." in messages


def test_reshuffle_is_seeded():
    def hand_after_reshuffle(seed):
        env = SpiteAndMaliceEnv()
        env.reset(num_players=2, seed=seed)
        env.set_current_player(0)
        gs = env.state.game_state
        gs["completed_cards"] = [f"{rank}♠" for rank in "A23456789JQ"]
        gs["deck"] = []
        gs["players"][0]["hand"] = []
        env.step("draw")
        return list(gs["players"][0]["hand"])

    assert hand_after_reshuffle(1) == hand_after_reshuffle(1)
    assert len({tuple(hand_after_reshuffle(seed)) for seed in range(5)}) > 1


def test_refill_after_playing_the_whole_hand_uses_cleared_cards():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"] = []
    gs["completed_cards"] = ["7♦", "7♣", "8♦", "8♣", "9♦", "9♣"]
    gs["players"][0]["hand"] = ["A♠", "2♠", "3♠", "4♠", "5♠"]
    done = env.step("draw play A♠ 0 play 2♠ 0 play 3♠ 0 play 4♠ 0 play 5♠ 0")
    assert not done and env.state.error_count == 0
    assert len(gs["players"][0]["hand"]) == 5
    assert len(gs["deck"]) == 1 and gs["completed_cards"] == []
    assert env.state.current_player_id == 0


def test_rejected_reply_after_a_reshuffle_restores_cards_and_randomness():
    env = _fresh()
    gs = _exhaust_deck_with_cleared_cards(env, cleared=11)
    gs["players"][0]["hand"] = []
    before = copy.deepcopy(env.state.game_state)
    rng_before = env.rng.getstate()
    done = env.step("draw play 5♠ 0 play 5♠ 0")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before
    assert env.rng.getstate() == rng_before


def test_no_deadlock_while_cleared_cards_remain():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"] = []
    gs["completed_cards"] = [f"{rank}♠" for rank in "A23456789JQ"]
    gs["center_piles"] = [["A♥"], ["A♦"], ["A♣"], ["A♠"]]
    for pid in (0, 1):
        gs["players"][pid]["hand"] = []
        gs["players"][pid]["payoff"] = ["5♠"]
        gs["players"][pid]["discard"] = [[] for _ in range(4)]
    done = env.step("draw")
    assert not done
    assert len(gs["players"][0]["hand"]) == 5


def test_bad_format_is_invalid():
    env = _fresh()
    done = env.step("I have no idea what to do")
    assert not done
    assert env.state.error_count == 1
    # No rotation on an invalid move.
    assert env.state.current_player_id == 0


def test_illegal_play_rejected():
    # Playing a non-Ace/King onto an empty center pile is always illegal.
    env = _fresh()
    env.step("draw")
    done = env.step("play 5\u2660 0")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_valid_discard_rotates_turn():
    env = _fresh()
    card = env.players[0]["hand"][0]
    done = env.step(f"draw discard {card} 0")
    assert not done
    # Discarding ends the turn -> rotates to player 1.
    assert env.state.current_player_id == 1
    assert env.players[0]["discard"][0][-1] == card
    assert card not in env.players[0]["hand"]


def test_discard_messages_address_the_actor_correctly():
    env = _fresh()
    card = env.players[0]["hand"][0]
    start = len(env.state.events)
    env.step(f"draw discard {card} 0")
    events = env.state.events[start:]
    actor_messages = [message for _, message, _, to_id in events if to_id == 0]
    assert f"You discarded {card} to discard pile 0 and ended your turn." in actor_messages
    assert not any("their turn" in message for message in actor_messages)
    assert not any("is considered" in message for _, message, _, _ in events)


def test_valid_play_updates_center_pile_if_available():
    """If the current player can legally start a center pile, playing works."""
    env = _fresh()

    def find_start_move(pid):
        # An empty center pile can be started only by an Ace or King.
        sources = list(env.players[pid]["hand"])
        if env.players[pid]["payoff"]:
            sources.append(env.players[pid]["payoff"][-1])
        for card in sources:
            if card[0] in ("A", "K"):
                return card
        return None

    card = find_start_move(0)
    if card is None:
        # No opening move available for this seed; nothing to assert here.
        return
    done = env.step(f"draw play {card} 0")
    assert not done
    assert env.center_piles[0] and env.center_piles[0][-1] == card
    # A play (without discard) does not rotate the turn.
    assert env.state.current_player_id == 0


def test_two_consecutive_invalids_end_game():
    env = _fresh()
    done = env.step("garbage move")
    assert not done and env.state.error_count == 1
    done = env.step("garbage move again")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def _all_cards(env):
    cards = list(env.deck)
    cards.extend(env.game_state["completed_cards"])
    for pile in env.center_piles:
        cards.extend(pile)
    for player in env.players.values():
        cards.extend(player["payoff"])
        cards.extend(player["hand"])
        for pile in player["discard"]:
            cards.extend(pile)
    return cards


def test_draw_is_required_once_at_turn_start():
    env = _fresh()
    card = env.players[0]["hand"][0]
    done = env.step(f"discard {card} 0")
    assert not done and env.state.error_count == 1
    env.step("draw")
    done = env.step("draw")
    assert not done and env.state.error_count == 1


def test_invalid_command_chain_rolls_back_every_mutation():
    env = _fresh()
    env.players[0]["hand"] = ["A♠", "5♠", "6♠", "7♠", "8♠"]
    before = copy.deepcopy(env.state.game_state)
    done = env.step("draw play A♠ 0 play 5♠ 1")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_unmatched_text_and_commands_after_discard_are_rejected_atomically():
    env = _fresh()
    card = env.players[0]["hand"][0]
    before = copy.deepcopy(env.state.game_state)
    env.step(f"draw nonsense discard {card} 0")
    assert env.state.game_state == before
    env.state.error_count = 0
    env.step(f"draw discard {card} 0 draw")
    assert env.state.game_state == before


def test_completed_center_cards_are_conserved():
    env = _fresh()
    assert len(_all_cards(env)) == 96
    gs = env.state.game_state
    gs["center_piles"][0] = [
        "A♣", "2♣", "3♣", "4♣", "5♣", "6♣", "7♣", "8♣", "9♣", "J♣"
    ]
    # Remove the injected sequence from their original zones before asserting
    # conservation after the completion move.
    for injected in gs["center_piles"][0]:
        for zone in [gs["deck"]] + [
            player["payoff"] for player in gs["players"].values()
        ] + [player["hand"] for player in gs["players"].values()]:
            if injected in zone:
                zone.remove(injected)
                break
    gs["players"][0]["hand"].append("Q♣")
    for zone in [gs["deck"], gs["players"][0]["payoff"], gs["players"][1]["payoff"], gs["players"][1]["hand"]]:
        if "Q♣" in zone:
            zone.remove("Q♣")
            break
    env.step("draw play Q♣ 0")
    assert gs["center_piles"][0] == []
    assert len(gs["completed_cards"]) == 11
    assert len(_all_cards(env)) == 96


def test_empty_payoff_wins_immediately_in_chained_turn():
    env = _fresh()
    gs = env.state.game_state
    gs["players"][0]["payoff"] = ["A♠"]
    gs["players"][0]["hand"] = ["5♠"]
    done = env.step("draw play A♠ 0")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_playing_entire_hand_refills_and_continues_same_turn():
    env = _fresh()
    gs = env.state.game_state
    gs["players"][0]["hand"] = ["A♠", "2♠", "3♠", "4♠", "5♠"]
    deck_before = len(gs["deck"])
    done = env.step(
        "draw play A♠ 0 play 2♠ 0 play 3♠ 0 play 4♠ 0 play 5♠ 0"
    )
    assert not done
    assert len(gs["players"][0]["hand"]) == 5
    assert len(gs["deck"]) == deck_before - 5
    assert env.state.current_player_id == 0
    assert gs["turn_has_drawn"][0] is True


def test_deadlock_tie_is_a_draw_not_current_player_win():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"] = []
    gs["center_piles"] = [[] for _ in range(4)]
    for pid in (0, 1):
        gs["players"][pid]["hand"] = []
        gs["players"][pid]["payoff"] = ["5♠"]
        gs["players"][pid]["discard"] = [[] for _ in range(4)]
    done = env.step("draw")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_empty_hand_with_no_play_automatically_ends_turn():
    env = _fresh()
    gs = env.state.game_state
    gs["deck"] = []
    gs["players"][0]["hand"] = []
    gs["players"][0]["payoff"] = ["5♠"]
    gs["players"][0]["discard"] = [[] for _ in range(4)]
    gs["players"][1]["hand"] = ["7♠"]
    done = env.step("draw")
    assert not done
    assert env.state.current_player_id == 1
    assert gs["turn_has_drawn"][0] is False


def test_emoji_style_suit_symbols_are_accepted():
    env = _fresh()
    env.players[0]["hand"] = ["A♥", "5♠", "6♠", "7♠", "8♠"]
    done = env.step("draw play A\u2665\ufe0f 0")
    assert not done
    assert env.state.error_count == 0
    assert env.center_piles[0] == ["A♥"]


def test_board_shows_the_draw_pile_size():
    env = _fresh()
    assert f"Draw pile: {len(env.deck)} card(s)" in env.render(0)
    assert f"Draw pile: {len(env.deck)} card(s)" in env.state.game_state["rendered_board"]


def test_public_terminal_board_hides_hands():
    env = _fresh()
    public_board = env.state.game_state["rendered_board"]
    assert "hidden card(s)" in public_board
    assert "Hand: ['" not in public_board


def test_private_render_includes_opponent_public_piles_but_not_hand():
    env = _fresh()
    gs = env.state.game_state
    opponent_top = gs["players"][1]["payoff"][-1]
    opponent_hand = list(gs["players"][1]["hand"])
    board = env.render(0)
    assert opponent_top in board
    assert "Player 1 (Public View)" in board
    assert f"Hand: {len(opponent_hand)} hidden card(s)" in board
    assert f"Hand: {opponent_hand}" not in board
