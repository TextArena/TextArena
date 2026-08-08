import pytest
import os
from typing import Dict, Any, List, Optional
from unittest.mock import patch

import textarena as ta
from textarena.envs.WinAsMuchAsYouCan.env import WinAsMuchAsYouCanEnv


class TestWinAsMuchAsYouCanEnv:
    """Test suite for Win as Much as You Can environment."""
    
    @pytest.fixture
    def env(self):
        """Create a fresh environment for each test."""
        return WinAsMuchAsYouCanEnv()
    
    @pytest.fixture
    def reset_env(self, env):
        """Create and reset environment with 4 players."""
        env.reset(num_players=4)
        return env

    def test_init(self):
        """Test environment initialization with different parameters."""
        # Test default initialization
        env = WinAsMuchAsYouCanEnv()
        assert env.error_allowance == 3
        
        # Test custom initialization
        env = WinAsMuchAsYouCanEnv(error_allowance=5)
        assert env.error_allowance == 5

    def test_reset(self, env):
        """Test environment reset functionality."""
        # Test reset with correct number of players (4)
        env.reset(num_players=4)
        assert env.state.num_players == 4
        assert env.state.error_allowance == 3
        
        # Verify game state initialization
        game_state = env.state.game_state
        assert game_state["current_round"] == 1
        assert game_state["current_phase"] == "act"
        assert game_state["player_scores"] == {0: 0, 1: 0, 2: 0, 3: 0}
        assert game_state["talk_round"] == 0
        assert game_state["max_talk_rounds"] == 40
        assert len(game_state["players_passed"]) == 0
        assert len(game_state["talk_messages"]) == 0
        
        # Verify round multipliers
        expected_multipliers = {
            1: 1, 2: 1, 3: 1, 4: 1, 5: 3, 6: 1, 7: 1, 8: 5, 9: 1, 10: 10
        }
        assert game_state["round_multipliers"] == expected_multipliers
        
        # Verify communication rounds
        assert 5 in game_state["communication_rounds"]
        assert 8 in game_state["communication_rounds"]
        assert 10 in game_state["communication_rounds"]
        
        # Verify starting player is 0
        assert env.state.current_player_id == 0

    def test_reset_wrong_player_count(self, env):
        """Test reset with incorrect number of players."""
        # Game requires exactly 4 players
        with pytest.raises(ValueError, match="Win as Much as You Can requires exactly 4 players"):
            env.reset(num_players=3)
        
        with pytest.raises(ValueError, match="Win as Much as You Can requires exactly 4 players"):
            env.reset(num_players=5)

    def test_act_phase_valid_actions(self, reset_env):
        """Test valid actions during act phase."""
        env = reset_env
        
        # Test Choose X
        assert env._process_act_phase(0, "[Choose X]")
        assert env.state.game_state["player_choices"][0] == "X"
        
        # Test Choose Y
        assert env._process_act_phase(1, "[Choose Y]")
        assert env.state.game_state["player_choices"][1] == "Y"

    def test_act_phase_invalid_actions(self, reset_env):
        """Test invalid actions during act phase."""
        env = reset_env
        
        # Invalid action formats
        assert not env._process_act_phase(0, "Choose X")  # Missing brackets
        assert not env._process_act_phase(0, "[Choose Z]")  # Invalid choice
        assert not env._process_act_phase(0, "[Choose]")  # Incomplete
        assert not env._process_act_phase(0, "random text")  # Random text

    def test_act_phase_duplicate_choice(self, reset_env):
        """Test that players cannot make duplicate choices."""
        env = reset_env
        
        # First choice should succeed
        assert env._process_act_phase(0, "[Choose X]")
        
        # Second choice by same player should fail
        assert not env._process_act_phase(0, "[Choose Y]")

    def test_talk_phase_broadcast(self, reset_env):
        """Test broadcast messages in talk phase."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Valid broadcast
        assert env._process_talk_phase(0, "[Broadcast] Hello everyone!")
        
        # Check message was recorded
        messages = env.state.game_state["talk_messages"]
        assert len(messages) == 1
        assert messages[0]["type"] == "broadcast"
        assert messages[0]["from"] == 0
        assert messages[0]["to"] == "all"
        assert messages[0]["message"] == "Hello everyone!"

    def test_talk_phase_whisper(self, reset_env):
        """Test whisper messages in talk phase."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Valid whisper
        assert env._process_talk_phase(0, "[Whisper to 1] Secret message")
        
        # Check message was recorded
        messages = env.state.game_state["talk_messages"]
        assert len(messages) == 1
        assert messages[0]["type"] == "whisper"
        assert messages[0]["from"] == 0
        assert messages[0]["to"] == 1
        assert messages[0]["message"] == "Secret message"
        assert messages[0]["hidden"] == True

    def test_talk_phase_whisper_invalid_targets(self, reset_env):
        """Test whisper with invalid targets."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Whisper to self should fail
        assert not env._process_talk_phase(0, "[Whisper to 0] Self message")
        
        # Whisper to invalid player ID should fail
        assert not env._process_talk_phase(0, "[Whisper to 5] Invalid player")
        assert not env._process_talk_phase(0, "[Whisper to -1] Negative player")
        
        # Whisper with non-numeric target should fail
        assert not env._process_talk_phase(0, "[Whisper to abc] Non-numeric")

    def test_talk_phase_pass(self, reset_env):
        """Test pass action in talk phase."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Valid pass
        assert env._process_talk_phase(0, "[Pass]")
        
        # Check player is marked as passed
        assert 0 in env.state.game_state["players_passed"]
        
        # Player who passed cannot act again
        assert not env._process_talk_phase(0, "[Broadcast] I changed my mind")

    def test_talk_phase_empty_messages(self, reset_env):
        """Test empty messages in talk phase."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Empty broadcast should fail
        assert not env._process_talk_phase(0, "[Broadcast]")
        assert not env._process_talk_phase(0, "[Broadcast]   ")
        
        # Empty whisper should fail
        assert not env._process_talk_phase(0, "[Whisper to 1]")
        assert not env._process_talk_phase(0, "[Whisper to 1]   ")

    def test_scoring_rubric_4_ys(self, reset_env):
        """Test scoring when all 4 players choose Y."""
        env = reset_env
        
        # All players choose Y
        env.state.game_state["player_choices"] = {0: "Y", 1: "Y", 2: "Y", 3: "Y"}
        
        # Score the round
        env._score_round()
        
        # All players should get +1 point
        scores = env.state.game_state["player_scores"]
        assert scores[0] == 1
        assert scores[1] == 1
        assert scores[2] == 1
        assert scores[3] == 1

    def test_scoring_rubric_4_xs(self, reset_env):
        """Test scoring when all 4 players choose X."""
        env = reset_env
        
        # All players choose X
        env.state.game_state["player_choices"] = {0: "X", 1: "X", 2: "X", 3: "X"}
        
        # Score the round
        env._score_round()
        
        # All players should get -1 point
        scores = env.state.game_state["player_scores"]
        assert scores[0] == -1
        assert scores[1] == -1
        assert scores[2] == -1
        assert scores[3] == -1

    def test_scoring_rubric_1x_3y(self, reset_env):
        """Test scoring with 1 X and 3 Y's."""
        env = reset_env
        
        # 1 X, 3 Y's
        env.state.game_state["player_choices"] = {0: "X", 1: "Y", 2: "Y", 3: "Y"}
        
        # Score the round
        env._score_round()
        
        # X wins 3 points, Y's lose 1 point each
        scores = env.state.game_state["player_scores"]
        assert scores[0] == 3  # X player
        assert scores[1] == -1  # Y player
        assert scores[2] == -1  # Y player
        assert scores[3] == -1  # Y player

    def test_scoring_rubric_2x_2y(self, reset_env):
        """Test scoring with 2 X's and 2 Y's."""
        env = reset_env
        
        # 2 X's, 2 Y's
        env.state.game_state["player_choices"] = {0: "X", 1: "X", 2: "Y", 3: "Y"}
        
        # Score the round
        env._score_round()
        
        # X's win 2 points, Y's lose 2 points
        scores = env.state.game_state["player_scores"]
        assert scores[0] == 2  # X player
        assert scores[1] == 2  # X player
        assert scores[2] == -2  # Y player
        assert scores[3] == -2  # Y player

    def test_scoring_rubric_3x_1y(self, reset_env):
        """Test scoring with 3 X's and 1 Y."""
        env = reset_env
        
        # 3 X's, 1 Y
        env.state.game_state["player_choices"] = {0: "X", 1: "X", 2: "X", 3: "Y"}
        
        # Score the round
        env._score_round()
        
        # X's win 1 point, Y loses 3 points
        scores = env.state.game_state["player_scores"]
        assert scores[0] == 1  # X player
        assert scores[1] == 1  # X player
        assert scores[2] == 1  # X player
        assert scores[3] == -3  # Y player

    def test_scoring_multipliers(self, reset_env):
        """Test scoring multipliers for different rounds."""
        env = reset_env
        
        # Test round 1 (1x multiplier)
        env.state.game_state["current_round"] = 1
        env.state.game_state["player_choices"] = {0: "Y", 1: "Y", 2: "Y", 3: "Y"}
        env._score_round()
        assert env.state.game_state["player_scores"][0] == 1  # 1 * 1x
        
        # Reset scores and test round 5 (3x multiplier)
        env.state.game_state["player_scores"] = {0: 0, 1: 0, 2: 0, 3: 0}
        env.state.game_state["current_round"] = 5
        env.state.game_state["player_choices"] = {0: "Y", 1: "Y", 2: "Y", 3: "Y"}
        env._score_round()
        assert env.state.game_state["player_scores"][0] == 3  # 1 * 3x
        
        # Reset scores and test round 8 (5x multiplier)
        env.state.game_state["player_scores"] = {0: 0, 1: 0, 2: 0, 3: 0}
        env.state.game_state["current_round"] = 8
        env.state.game_state["player_choices"] = {0: "Y", 1: "Y", 2: "Y", 3: "Y"}
        env._score_round()
        assert env.state.game_state["player_scores"][0] == 5  # 1 * 5x
        
        # Reset scores and test round 10 (10x multiplier)
        env.state.game_state["player_scores"] = {0: 0, 1: 0, 2: 0, 3: 0}
        env.state.game_state["current_round"] = 10
        env.state.game_state["player_choices"] = {0: "Y", 1: "Y", 2: "Y", 3: "Y"}
        env._score_round()
        assert env.state.game_state["player_scores"][0] == 10  # 1 * 10x

    def test_phase_transition_act_to_talk(self, reset_env):
        """Test transition from act phase to talk phase."""
        env = reset_env
        
        # Set up round 4 (transition to round 5 which has talk phase)
        env.state.game_state["current_round"] = 4
        env.state.game_state["current_phase"] = "act"
        env.state.game_state["player_choices"] = {0: "X", 1: "Y", 2: "Y", 3: "Y"}
        
        # Trigger phase transition
        env._check_phase_transition()
        
        # Should move to round 5 with talk phase
        assert env.state.game_state["current_round"] == 5
        assert env.state.game_state["current_phase"] == "talk"
        assert env.state.game_state["talk_round"] == 0
        assert len(env.state.game_state["players_passed"]) == 0
        assert env.state.current_player_id == 0

    def test_phase_transition_talk_to_act(self, reset_env):
        """Test transition from talk phase to act phase."""
        env = reset_env
        
        # Set up talk phase
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["current_round"] = 2
        
        # Trigger phase transition
        env._check_phase_transition()
        
        # Should move to act phase of same round
        assert env.state.game_state["current_round"] == 2
        assert env.state.game_state["current_phase"] == "act"
        assert len(env.state.game_state["player_choices"]) == 0
        assert env.state.current_player_id == 0

    def test_talk_phase_max_rounds(self, reset_env):
        """Test talk phase ending when max rounds reached."""
        env = reset_env
        
        # Set up talk phase near max rounds
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["talk_round"] = 39
        env.state.game_state["max_talk_rounds"] = 40
        
        # One more action should end the phase
        result = env._check_if_phase_should_end(0, "[Broadcast] Final message")
        assert result == True

    def test_talk_phase_all_players_pass(self, reset_env):
        """Test talk phase ending when all players pass."""
        env = reset_env
        
        # Set up talk phase with 3 players passed
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["players_passed"] = {0, 1, 2}
        
        # Last player passes
        env.state.game_state["players_passed"].add(3)
        result = env._check_if_phase_should_end(3, "[Pass]")
        assert result == True

    def test_act_phase_ends_when_all_choose(self, reset_env):
        """Test act phase ending when all players choose."""
        env = reset_env
        
        # 3 players have chosen
        env.state.game_state["player_choices"] = {0: "X", 1: "Y", 2: "X"}
        
        # Last player chooses
        env.state.game_state["player_choices"][3] = "Y"
        result = env._check_if_phase_should_end(3, "[Choose Y]")
        assert result == True

    def test_turn_advancement_talk_phase(self, reset_env):
        """Test turn advancement in talk phase."""
        env = reset_env
        
        # Set up talk phase
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["talk_round"] = 1  # Not 0, so turn advancement should work
        env.state.current_player_id = 0
        
        # Get next talker
        next_talker = env._get_next_talk_player()
        assert next_talker == 1
        
        # Test with player 3
        env.state.current_player_id = 3
        next_talker = env._get_next_talk_player()
        assert next_talker == 0  # Should wrap around

    def test_turn_advancement_talk_phase_with_passed_players(self, reset_env):
        """Test turn advancement in talk phase with passed players."""
        env = reset_env
        
        # Set up talk phase with some players passed
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["talk_round"] = 1
        env.state.game_state["players_passed"] = {1, 2}
        env.state.current_player_id = 0
        
        # Should skip passed players
        next_talker = env._get_next_talk_player()
        assert next_talker == 3  # Skip 1 and 2

    def test_turn_advancement_act_phase(self, reset_env):
        """Test turn advancement in act phase."""
        env = reset_env
        
        # Set up act phase with some choices made
        env.state.game_state["player_choices"] = {0: "X", 2: "Y"}
        
        # Should return first player who hasn't chosen
        next_chooser = env._get_next_player_needing_choice()
        assert next_chooser == 1

    def test_game_end_after_round_10(self, reset_env):
        """Test game ending after round 10."""
        env = reset_env
        
        # Set up round 10 completion
        env.state.game_state["current_round"] = 10
        env.state.game_state["current_phase"] = "act"
        env.state.game_state["round_history"] = [{}] * 10  # 10 completed rounds
        
        # Check game end
        env._check_game_end()
        
        # Game should be done
        assert env.state.done

    def test_winner_determination_single_winner(self, reset_env):
        """Test winner determination with single winner."""
        env = reset_env
        
        # Set up final scores with clear winner
        env.state.game_state["player_scores"] = {0: 10, 1: 5, 2: 3, 3: 7}
        
        # End game
        env._end_game()
        
        # Check winner
        assert env.state.done
        assert env.state.rewards is not None
        assert env.state.rewards[0] == 100  # Winner gets 100

    def test_winner_determination_tie(self, reset_env):
        """Test winner determination with tie."""
        env = reset_env
        
        # Set up final scores with tie
        env.state.game_state["player_scores"] = {0: 10, 1: 10, 2: 5, 3: 7}
        
        # End game
        env._end_game()
        
        # Check tie
        assert env.state.done
        assert env.state.rewards is not None
        assert env.state.rewards[0] == 100  # Tied winners get 100
        assert env.state.rewards[1] == 100

    def test_step_function_act_phase(self, reset_env):
        """Test step function during act phase."""
        env = reset_env
        
        initial_player = env.state.current_player_id
        
        # Valid action
        done, info = env.step("[Choose X]")
        
        # Should not be done, choice should be recorded
        assert not done
        assert env.state.game_state["player_choices"][initial_player] == "X"

    def test_step_function_talk_phase(self, reset_env):
        """Test step function during talk phase."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Valid action
        done, info = env.step("[Broadcast] Hello!")
        
        # Should not be done, message should be recorded
        assert not done
        assert len(env.state.game_state["talk_messages"]) == 1

    def test_step_function_invalid_action(self, reset_env):
        """Test step function with invalid action."""
        env = reset_env
        
        initial_player = env.state.current_player_id
        
        # Invalid action
        done, info = env.step("invalid action")
        
        # Should not advance turn on invalid action
        assert not done
        assert env.state.current_player_id == initial_player

    def test_whisper_privacy_in_step(self, reset_env):
        """Test that whisper actions are logged privately."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        
        # Clear observations
        env.state.observations = {i: [] for i in range(4)}
        
        # Send whisper
        done, info = env.step("[Whisper to 1] Secret message")
        
        # Check that action was logged only to sender
        # (This tests the privacy fix in the step method)
        sender_obs = env.state.observations[0]
        other_obs = env.state.observations[2]  # Player 2 shouldn't see the raw action
        
        # Sender should see their own action
        action_logged_to_sender = any("[Whisper to 1]" in obs[1] for obs in sender_obs)
        assert action_logged_to_sender
        
        # Others should not see the raw whisper action
        action_logged_to_other = any("[Whisper to 1]" in obs[1] for obs in other_obs)
        assert not action_logged_to_other

    def test_complete_game_scenario(self, reset_env):
        """Test a complete game scenario."""
        env = reset_env
        
        # Play through round 1 (act only)
        for player in range(4):
            env.state.current_player_id = player
            done, info = env.step("[Choose Y]")
            if done:
                break
        
        # Should transition to round 2 (act only, no talk phase)
        assert env.state.game_state["current_round"] == 2
        assert env.state.game_state["current_phase"] == "act"
        
        # Play through round 2
        for player in range(4):
            if not done:
                env.state.current_player_id = player
                done, info = env.step("[Choose X]")
                if done:
                    break
        
        # Should transition to round 3
        assert env.state.game_state["current_round"] == 3
        assert env.state.game_state["current_phase"] == "act"

    def test_regex_patterns(self, reset_env):
        """Test regex pattern matching."""
        env = reset_env
        
        # Test broadcast pattern
        assert env.broadcast_pattern.search("[Broadcast] Hello")
        assert env.broadcast_pattern.search("[broadcast] Hello")  # Case insensitive
        assert not env.broadcast_pattern.search("Broadcast Hello")  # Missing brackets
        
        # Test whisper pattern
        match = env.whisper_pattern.search("[Whisper to 1] Secret")
        assert match
        assert match.group(1) == "1"
        assert match.group(2) == "Secret"
        
        # Test pass pattern
        assert env.pass_pattern.search("[Pass]")
        assert env.pass_pattern.search("[pass]")  # Case insensitive
        
        # Test choose patterns
        assert env.choose_x_pattern.search("[Choose X]")
        assert env.choose_x_pattern.search("[choose x]")  # Case insensitive
        assert env.choose_y_pattern.search("[Choose Y]")
        assert env.choose_y_pattern.search("[choose y]")  # Case insensitive

    def test_error_handling_invalid_moves(self, reset_env):
        """Test error handling for invalid moves."""
        env = reset_env
        
        current_player = env.state.current_player_id
        
        # Make invalid moves up to error allowance
        for i in range(env.error_allowance):
            done, info = env.step("invalid action")
            assert not done
            assert env.state.current_player_id == current_player  # Should not advance
        
        # Next invalid move should trigger elimination or default behavior
        done, info = env.step("invalid action")
        # Behavior depends on FFAMultiPlayerState implementation

    def test_observation_generation(self, reset_env):
        """Test observation generation."""
        env = reset_env
        
        player_id, observation = env.get_observation()
        
        # Should return current player and their observation
        assert player_id == env.state.current_player_id
        assert isinstance(observation, list)
        
        # Observation should contain game board
        obs_text = "\n".join([msg[1] for msg in observation])
        assert "Win as Much as You Can" in obs_text
        assert "OBJECTIVE" in obs_text
        assert "SCORING RUBRIC" in obs_text

    def test_round_history_tracking(self, reset_env):
        """Test round history tracking."""
        env = reset_env
        
        # Complete a round
        env.state.game_state["player_choices"] = {0: "X", 1: "Y", 2: "Y", 3: "Y"}
        env._score_round()
        
        # Check history
        history = env.state.game_state["round_history"]
        assert len(history) == 1
        
        round_data = history[0]
        assert round_data["round"] == 1
        assert round_data["x_count"] == 1
        assert round_data["y_count"] == 3
        assert round_data["multiplier"] == 1
        assert "results" in round_data

    def test_talk_message_recording(self, reset_env):
        """Test talk message recording."""
        env = reset_env
        
        # Switch to talk phase
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["current_round"] = 2
        env.state.game_state["talk_round"] = 1
        
        # Send messages
        env._process_talk_phase(0, "[Broadcast] Public message")
        env._process_talk_phase(1, "[Whisper to 2] Private message")
        
        # Check messages recorded
        messages = env.state.game_state["talk_messages"]
        assert len(messages) == 2
        
        # Check broadcast message
        broadcast_msg = messages[0]
        assert broadcast_msg["type"] == "broadcast"
        assert broadcast_msg["from"] == 0
        assert broadcast_msg["to"] == "all"
        assert broadcast_msg["message"] == "Public message"
        
        # Check whisper message
        whisper_msg = messages[1]
        assert whisper_msg["type"] == "whisper"
        assert whisper_msg["from"] == 1
        assert whisper_msg["to"] == 2
        assert whisper_msg["message"] == "Private message"
        assert whisper_msg["hidden"] == True

    def test_case_sensitivity_actions(self, reset_env):
        """Test case sensitivity in actions."""
        env = reset_env
        
        # These should work (case insensitive regex)
        assert env._process_act_phase(0, "[choose x]")
        env.state.game_state["player_choices"] = {}  # Reset
        assert env._process_act_phase(0, "[CHOOSE Y]")
        
        # Switch to talk phase for talk actions
        env.state.game_state["current_phase"] = "talk"
        assert env._process_talk_phase(1, "[broadcast] Hello")
        assert env._process_talk_phase(2, "[PASS]")

    def test_whitespace_handling(self, reset_env):
        """Test whitespace handling in actions."""
        env = reset_env
        
        # Extra whitespace should be handled
        assert env._process_act_phase(0, "  [Choose X]  ")
        
        env.state.game_state["player_choices"] = {}  # Reset
        env.state.game_state["current_phase"] = "talk"
        
        # Whitespace in messages should be trimmed
        env._process_talk_phase(1, "[Broadcast]   Hello world   ")
        messages = env.state.game_state["talk_messages"]
        assert messages[0]["message"] == "Hello world"

    def test_turn_advancement_edge_cases(self, reset_env):
        """Test edge cases in turn advancement."""
        env = reset_env
        
        # Test when all players have passed in talk phase
        env.state.game_state["current_phase"] = "talk"
        env.state.game_state["players_passed"] = {0, 1, 2, 3}
        
        next_talker = env._get_next_talk_player()
        assert next_talker is None
        
        # Test when all players have chosen in act phase
        env.state.game_state["player_choices"] = {0: "X", 1: "Y", 2: "X", 3: "Y"}
        
        next_chooser = env._get_next_player_needing_choice()
        assert next_chooser is None

    def test_talk_round_zero_no_advancement(self, reset_env):
        """Test that turn doesn't advance when talk_round is 0."""
        env = reset_env
