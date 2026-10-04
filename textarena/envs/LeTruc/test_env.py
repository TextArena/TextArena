"""Deterministic offline tests for Le Truc (minimal 2-player).

Two-player trick game to 12 match points. Cards are dealt randomly; we read
``game_state['hands']`` to script legal plays. A fold immediately awards the
hand value to the opponent (``set_winner``).

After a ``raise`` the turn passes to the opponent, who must immediately
respond with ``accept`` or ``fold``.
"""
import textarena as ta

from textarena.envs.LeTruc.env import LeTrucEnv


def _fresh():
    env = LeTrucEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert env.state.game_state["hand_points"] == 1
    assert len(env.state.game_state["hands"][0]) == 3
    assert len(env.state.game_state["hands"][1]) == 3


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("nonsense")
    assert done is False
    assert env.state.error_count == 1


def test_play_rank_not_in_hand_rejected():
    env = _fresh()
    hand_ranks = {c[:-1] for c in env.state.game_state["hands"][0]}
    missing = next(r for r in ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]
                   if r not in hand_ranks)
    done, _ = env.step(f"play {missing}")
    assert done is False
    assert env.state.error_count == 1


def test_accept_without_raise_rejected():
    env = _fresh()
    done, _ = env.step("accept")
    assert done is False
    assert env.state.error_count == 1


def test_play_leads_and_rotates():
    env = _fresh()
    rank = env.state.game_state["hands"][0][0][:-1]
    done, _ = env.step(f"play {rank}")
    assert done is False
    assert env.state.current_player_id == 1
    assert env.state.game_state["led_card"] is not None


def test_raise_increases_hand_points_and_passes_turn():
    env = _fresh()
    done, _ = env.step("raise")
    assert done is False
    assert env.state.game_state["hand_points"] == 1
    assert env.state.game_state["pending_raise_value"] == 2
    assert env.state.game_state["raiser"] == 0
    assert env.state.current_player_id == 1               # opponent must respond


def test_raise_then_fold_awards_hand_and_starts_next_hand():
    env = _fresh()
    env.step("raise")                                   # P0 raises -> P1's turn
    done, _ = env.step("fold")                          # P1 folds immediately
    assert done is False
    assert env.state.game_state["match_points"][0] == 1   # proposed raise was refused
    assert env.state.current_player_id == 1
    assert env.state.game_state["hand_points"] == 1


def test_raise_then_accept_continues_hand():
    env = _fresh()
    env.step("raise")                                   # P0 raises -> P1's turn
    done, _ = env.step("accept")                        # P1 accepts immediately
    assert done is False
    assert env.state.game_state["raiser"] is None
    assert env.state.game_state["hand_points"] == 2
    assert env.state.game_state["pending_raise_value"] is None
    assert env.state.current_player_id == 0               # raiser leads the trick


def test_full_hand_completes_and_redeals():
    env = _fresh()
    gs = env.state.game_state
    for _ in range(6):  # at most 3 tricks * 2 plays
        if env.state.done or sum(gs["match_points"].values()) == 1:
            break
        cur = env.state.current_player_id
        rank = gs["hands"][cur][0][:-1]
        env.step(f"play {rank}")
    # One hand (3 tricks) awards 1 point; game not over (needs 12), new hand dealt.
    assert env.state.done is False
    assert sum(gs["match_points"].values()) == 1
    assert gs["hand_points"] == 1
    assert len(gs["hands"][0]) == 3


def test_stronger_rank_wins_trick():
    env = _fresh()
    gs = env.state.game_state
    gs["hands"] = {0: ["4♣", "5♣", "6♣"], 1: ["3♣", "5♦", "6♦"]}
    env.step("play 4")
    env.step("play 3")
    assert gs["tricks"] == [1]
    assert env.state.current_player_id == 1


def test_pending_raise_only_accepts_accept_or_fold():
    env = _fresh()
    env.step("raise")
    before = list(env.state.game_state["hands"][1])
    done, _ = env.step(f"play {before[0][:-1]}")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["hands"][1] == before
    assert env.state.game_state["raiser"] == 0


def test_non_play_actions_reject_card_arguments():
    env = _fresh()
    done, _ = env.step("raise 3")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["hand_points"] == 1


def test_fold_can_end_match_at_twelve_points():
    env = _fresh()
    env.state.game_state["match_points"][0] = 11
    env.step("raise")
    done, _ = env.step("fold")
    assert done
    assert env.state.game_state["match_points"][0] == 12
    assert env.state.rewards == {0: 1, 1: -1}


def test_card_conservation_and_private_render():
    env = _fresh()
    gs = env.state.game_state
    assert (
        len(gs["hands"][0])
        + len(gs["hands"][1])
        + len(gs["undealt_cards"])
        + len(gs["played_cards"])
        == 40
    )
    board = env.render(0)
    assert all(card in board for card in gs["hands"][0])
    assert all(card not in board for card in gs["hands"][1] if card not in gs["hands"][0])


def test_scripted_complete_match_terminates_at_twelve():
    env = _fresh()
    steps = 0
    while not env.state.done and steps < 200:
        current = env.state.current_player_id
        rank = env.state.game_state["hands"][current][0][:-1]
        env.step(f"play {rank}")
        steps += 1
    assert env.state.done
    assert max(env.state.game_state["match_points"].values()) >= 12
    assert steps <= 200


def test_repeat_reset_replays_same_deal():
    env = _fresh()
    first_hands = {pid: list(cards) for pid, cards in env.state.game_state["hands"].items()}
    env.step(f"play {first_hands[0][0][:-1]}")
    env.reset(num_players=2, seed=42)
    assert env.state.game_state["hands"] == first_hands


def test_snapshot_restore_replays_card_play():
    env = _fresh()
    action = f"play {env.state.game_state['hands'][0][0][:-1]}"
    before = env.snapshot()
    env.step(action)
    expected = env.snapshot()
    env.restore(before)
    env.step(action)
    assert env.state.game_state == expected["state"].game_state
    assert env.state.current_player_id == expected["state"].current_player_id


def test_equal_ranks_tie_and_same_leader_leads_again():
    env = _fresh()
    gs = env.state.game_state
    gs["hands"] = {0: ["4♣", "5♣", "6♣"], 1: ["4♦", "5♦", "6♦"]}
    env.step("play 4")
    env.step("play 4")
    assert gs["tricks"] == [None]
    assert env.state.current_player_id == 0
    assert len(gs["played_cards"]) == 2


def test_tied_trick_makes_earliest_other_trick_decisive():
    env = _fresh()
    gs = env.state.game_state
    gs["hands"] = {0: ["4♣", "3♣", "6♣"], 1: ["4♦", "5♦", "6♦"]}
    env.step("play 4")
    env.step("play 4")
    env.step("play 3")
    env.step("play 5")
    assert gs["match_points"][0] == 1
    assert gs["tricks"] == []  # the hand ended after two tricks and redealt


def test_all_three_tied_tricks_void_hand_without_points():
    env = _fresh()
    gs = env.state.game_state
    gs["hands"] = {0: ["4♣", "5♣", "6♣"], 1: ["4♦", "5♦", "6♦"]}
    for rank in ("4", "4", "5", "5", "6", "6"):
        env.step(f"play {rank}")
    assert gs["match_points"] == {0: 0, 1: 0}
    assert env.state.current_player_id == 1


def test_split_first_two_tricks_is_decided_by_third_trick():
    env = _fresh()
    gs = env.state.game_state
    gs["hands"] = {0: ["3♣", "4♣", "4♥"], 1: ["4♦", "3♦", "5♦"]}
    env.step("play 3")
    env.step("play 4")  # P0 wins the first trick.
    env.step("play 4")
    env.step("play 3")  # P1 wins the second trick.
    env.step("play 5")
    env.step("play 4")  # P1 wins the deciding third trick.
    assert gs["match_points"] == {0: 0, 1: 1}


def test_played_cards_remain_conserved_mid_hand():
    env = _fresh()
    gs = env.state.game_state
    env.step(f"play {gs['hands'][0][0][:-1]}")
    env.step(f"play {gs['hands'][1][0][:-1]}")
    assert (
        len(gs["hands"][0])
        + len(gs["hands"][1])
        + len(gs["undealt_cards"])
        + len(gs["played_cards"])
        == 40
    )


def test_registered_default_and_mdp_variants_are_usable():
    for env_id in ("LeTruc-v0", "LeTruc-v0-mdp"):
        wrapped = ta.make(env_id)
        wrapped.reset(num_players=2, seed=42)
        player_id, observation = wrapped.get_observation()
        assert wrapped.env.__class__ is LeTrucEnv
        assert player_id == 0
        assert "Your cards:" in observation
