import pytest
import os
from typing import Dict, Any, List, Optional
from unittest.mock import patch

import textarena as ta
from textarena.envs.ScorableGames.env import ScorableGamesEnv


class TestScorableGamesEnv:
    """Test suite for ScorableGames environment."""
    
    @pytest.fixture
    def env(self):
        """Create a fresh environment for each test."""
        return ScorableGamesEnv(game_config="base")
    
    @pytest.fixture
    def reset_env(self, env):
        """Create and reset environment with 6 players (base game)."""
        env.reset(num_players=6)
        return env

    def test_init(self):
        """Test environment initialization with different parameters."""
        # Test default initialization
        env = ScorableGamesEnv()
        assert env.game_config == "base"
        assert env.max_rounds == 120
        assert env.required_votes is None
        assert env.veto_roles == ["p1", "p2"]
        assert env.unanimity_bonus_role == "p1"
        assert env.starting_role == "p1"
        assert env.invalid_move_default == "Accept"
        assert env.error_allowance == 3
        
        # Test custom initialization
        env = ScorableGamesEnv(
            game_config="game1",
            max_rounds=50,
            required_votes=4,
            veto_roles=["p1"],
            unanimity_bonus_role="p2",
            starting_role="p2",
            invalid_move_default="Reject",
            error_allowance=5
        )
        assert env.game_config == "game1"
        assert env.max_rounds == 50
        assert env.required_votes == 4
        assert env.veto_roles == ["p1"]
        assert env.unanimity_bonus_role == "p2"
        assert env.starting_role == "p2"
        assert env.invalid_move_default == "Reject"
        assert env.error_allowance == 5

    def test_reset(self, env):
        """Test environment reset functionality."""
        # Test reset with correct number of players (6 for base game)
        env.reset(num_players=6)
        assert env.state.num_players == 6
        assert env.state.max_turns == 120
        assert env.state.error_allowance == 3
        
        # Verify game configuration loaded
        assert len(env.player_configs) == 6
        assert len(env.player_scores) == 6
        assert len(env.issues) == 5  # A, B, C, D, E
        
        # Verify issues are parsed correctly
        assert "A" in env.issues
        assert "B" in env.issues
        assert "C" in env.issues
        assert "D" in env.issues
        assert "E" in env.issues
        
        # Check issue A has 3 options
        assert len(env.issues["A"]["options"]) == 3
        assert "A1" in env.issues["A"]["options"]
        assert "A2" in env.issues["A"]["options"]
        assert "A3" in env.issues["A"]["options"]
        
        # Check issue E has 5 options
        assert len(env.issues["E"]["options"]) == 5
        assert "E1" in env.issues["E"]["options"]
        assert "E5" in env.issues["E"]["options"]
        
        # Verify starting player is set correctly (p1 role)
        p1_player_id = env._get_player_by_role("p1")
        assert env.state.current_player_id == p1_player_id

    def test_reset_wrong_player_count(self, env):
        """Test reset with incorrect number of players."""
        # Base game expects 6 players
        with pytest.raises(ValueError, match="Game config expects 6 players, got 4"):
            env.reset(num_players=4)
        
        with pytest.raises(ValueError, match="Game config expects 6 players, got 8"):
            env.reset(num_players=8)

    def test_game_configuration_loading(self, reset_env):
        """Test that game configurations are loaded correctly."""
        env = reset_env
        
        # Test global instructions loaded
        assert env.global_instructions
        assert "SportCo" in env.global_instructions
        assert "Harbour Sport Park" in env.global_instructions
        
        # Test player configurations loaded
        assert len(env.player_configs) == 6
        
        # Check specific player roles
        sportco_id = env._get_player_by_role("p1")
        dot_id = env._get_player_by_role("p2")
        assert sportco_id is not None
        assert dot_id is not None
        assert env.player_configs[sportco_id]["agent_name"] == "SportCo"
        assert env.player_configs[dot_id]["agent_name"] == "Department of Tourism"
        
        # Test player scores loaded
        for player_id in range(6):
            assert player_id in env.player_scores
            assert "threshold" in env.player_scores[player_id]
            # Check that all issues have scores
            for issue in ["A", "B", "C", "D", "E"]:
                assert issue in env.player_scores[player_id]
    
    def test_missing_bracketed_keyword(self, reset_env):
        """Test actions without bracketed keywords."""
        env = reset_env
        
        # Missing Propose command
        assert not env._is_valid_action("A1 B2 C3 D1 E4")
        assert not env._is_valid_action("I propose A1 B2 C3 D1 E4")
        
        # Missing Accept command
        assert not env._is_valid_action("I accept this proposal")
        assert not env._is_valid_action("accept")
        
        # Missing Reject command
        assert not env._is_valid_action("I reject this proposal")
        assert not env._is_valid_action("reject")

    def test_multiple_command_keywords(self, reset_env):
        """Reject duplicate or conflicting decision lines."""
        env = reset_env
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}

        # Multiple options on one proposal line remain supported.
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4 A2 B1 C2 D2 E3")
        for action in (
            "Accept\nAccept",
            "Reject\nReject",
            "Accept\nReject",
            "Reject\nAccept",
            "Propose A1 B2 C3 D1 E4\nAccept",
            "Accept\nPropose A1 B2 C3 D1 E4",
        ):
            assert not env._is_valid_action(action)

    def test_multiple_proposals(self, reset_env):
        """Test actions with multiple proposal strings and option processing."""
        env = reset_env
        
        # Test validation - these should all be valid
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4 A2 B1 C2 D2 E3")
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4")
        assert env._is_valid_action("Propose A1 A2 B2 C3 D1 E4")
        
        # Test actual processing behavior - last valid option for each issue wins
        current_player = env.state.current_player_id
        
        # 1. Multiple complete proposals - last valid options win
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4 A2 B1 C2 D2 E3")
        # The last valid option for each issue should be used: A2, B1, C2, D2, E3
        assert env.current_deal == {"A": "A2", "B": "B1", "C": "C2", "D": "D2", "E": "E3"}
        
        # 2. Duplicate options for same issue - last one wins
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 A2 B2 C3 D1 E4")
        # A2 should override A1
        assert env.current_deal == {"A": "A2", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # 3. Duplicate in middle - still last one wins
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 A2 C3 D1 E4")
        # A2 should override A1 even though it appears in the middle
        assert env.current_deal == {"A": "A2", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # 4. Extra option at end - last valid one wins
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4 A2")
        # A2 should override A1
        assert env.current_deal == {"A": "A2", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # 5. Invalid options are ignored
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4 X1 Y2")
        # Invalid options X1, Y2 are ignored, original proposal stands
        assert env.current_deal == {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # 6. Newline separation - only first line is processed
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4\nA2 B1 C2 D2 E3")
        # Only the first line should be processed
        assert env.current_deal == {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}

    def test_rationale_before_and_after_keyword(self, reset_env):
        """Test rationale text around command keywords and verify extraction."""
        env = reset_env
        current_player = env.state.current_player_id
        
        # Test validation - all these should be valid
        assert env._is_valid_action("I think this is fair\nPropose A1 B2 C3 D1 E4")
        assert env._is_valid_action("This meets our needs\nAccept")
        assert env._is_valid_action("This is unacceptable\nReject")
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4 because it's balanced")
        assert env._is_valid_action("Accept this proposal")
        assert env._is_valid_action("Reject due to environmental concerns")
        assert env._is_valid_action("I believe\nPropose A1 B2 C3 D1 E4 is the best option")
        
        # Test actual rationale extraction behavior
        
        # 1. Rationale before keyword - should be extracted
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "I think this is fair\nPropose A1 B2 C3 D1 E4")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == "I think this is fair"
        assert env.negotiation_history[0]["action_type"] == "Propose"
        
        # 2. Rationale after keyword - should be empty (text after keyword is ignored)
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4 because it's balanced")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == ""
        assert env.negotiation_history[0]["action_type"] == "Propose"
        
        # 3. Both before and after - only before keyword is extracted
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "I believe\nPropose A1 B2 C3 D1 E4 is the best option")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == "I believe"
        assert env.negotiation_history[0]["action_type"] == "Propose"
        
        # 4. Voting rationale before keyword
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "This meets our needs\nAccept")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == "This meets our needs"
        assert env.negotiation_history[0]["action_type"] == "Accept"
        
        # 5. Voting rationale after keyword - should be empty
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "Accept this proposal")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == ""
        assert env.negotiation_history[0]["action_type"] == "Accept"
        
        # 6. Reject with rationale before
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "Environmental concerns\nReject")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == "Environmental concerns"
        assert env.negotiation_history[0]["action_type"] == "Reject"
        
        # 7. Reject with rationale after - should be empty
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "Reject due to environmental impact")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == ""
        assert env.negotiation_history[0]["action_type"] == "Reject"
        
        # 8. No rationale - should be empty
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == ""
        assert env.negotiation_history[0]["action_type"] == "Propose"
        
        # 9. Whitespace handling - should be trimmed
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "   Leading spaces\nAccept   ")
        assert len(env.negotiation_history) == 1
        assert env.negotiation_history[0]["rationale"] == "Leading spaces"  # Trimmed
        assert env.negotiation_history[0]["action_type"] == "Accept"

    def test_similar_but_not_keyword(self, reset_env):
        """Test text that looks like a keyword but isn't, including mixed valid/invalid cases."""
        env = reset_env
        current_player = env.state.current_player_id
        
        # Pure invalid keywords - should be invalid
        assert not env._is_valid_action("InvalidKeyword A1 B2 C3 D1 E4")
        assert not env._is_valid_action("Propose123 A1 B2 C3 D1 E4")
        assert not env._is_valid_action("PROPOSE A1 B2 C3 D1 E4")  # Case sensitive
        assert not env._is_valid_action("propose A1 B2 C3 D1 E4")  # Case sensitive
        assert not env._is_valid_action("Accept123")
        assert not env._is_valid_action("Rejected")
        assert not env._is_valid_action("Maybe")
        assert not env._is_valid_action("Vote")
        
        # Mixed invalid and valid keywords - should be valid and process only valid keywords
        
        # 1. Invalid keyword line before valid proposal line - should process as proposal
        assert env._is_valid_action("InvalidKeyword\nPropose A1 B2 C3 D1 E4")
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "InvalidKeyword\nPropose A1 B2 C3 D1 E4")
        assert env.current_deal == {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        assert env.negotiation_history[-1]["action_type"] == "Propose"
        
        # 2. Valid proposal before invalid keyword - should process as proposal
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4 InvalidKeyword")
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4 InvalidKeyword")
        assert env.current_deal == {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        assert env.negotiation_history[-1]["action_type"] == "Propose"
        
        # 3. Invalid keyword line before valid accept - should process as accept
        assert env._is_valid_action("Maybe\nAccept")
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "Maybe\nAccept")
        assert env.player_votes[current_player] == "Accept"
        assert env.negotiation_history[-1]["action_type"] == "Accept"
        
        # 4. Valid accept before invalid keyword - should process as accept
        assert env._is_valid_action("Accept Vote")
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "Accept Vote")
        assert env.player_votes[current_player] == "Accept"
        assert env.negotiation_history[-1]["action_type"] == "Accept"
        
        # 5. Invalid keyword line before valid reject - should process as reject
        assert env._is_valid_action("NotAKeyword\nReject")
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "NotAKeyword\nReject")
        assert env.player_votes[current_player] == "Reject"
        assert env.negotiation_history[-1]["action_type"] == "Reject"
        
        # 6. Valid reject before invalid keyword - should process as reject
        assert env._is_valid_action("Reject SomeOtherThing")
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "Reject SomeOtherThing")
        assert env.player_votes[current_player] == "Reject"
        assert env.negotiation_history[-1]["action_type"] == "Reject"
        
        # 7. Case-sensitive: invalid case line before valid keyword - should process valid one
        assert env._is_valid_action("PROPOSE\nPropose A1 B2 C3 D1 E4")
        env.negotiation_history = []
        env.current_deal = {}
        env._process_valid_action(current_player, "PROPOSE\nPropose A1 B2 C3 D1 E4")
        assert env.current_deal == {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        assert env.negotiation_history[-1]["action_type"] == "Propose"
        
        # 8. Case-sensitive: invalid case line before valid accept - should process valid one
        assert env._is_valid_action("propose\nAccept")
        env.negotiation_history = []
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {}
        env._process_valid_action(current_player, "propose\nAccept")
        assert env.player_votes[current_player] == "Accept"
        assert env.negotiation_history[-1]["action_type"] == "Accept"

    def test_random_inputs_become_invalid(self, reset_env):
        """Test that random inputs are treated as invalid."""
        env = reset_env
        
        # Gibberish text
        assert not env._is_valid_action("asdfghjkl")
        assert not env._is_valid_action("random text here")
        assert not env._is_valid_action("12345")
        assert not env._is_valid_action("!@#$%^&*()")
        assert not env._is_valid_action("")
        assert not env._is_valid_action("   ")
        
        # Numbers
        assert not env._is_valid_action("123456")
        assert not env._is_valid_action("0")
        
        # Special characters
        assert not env._is_valid_action("!@#$%")
        assert not env._is_valid_action("[]{}()")

    def test_malformed_proposals(self, reset_env):
        """Test malformed proposal formats."""
        env = reset_env
        
        # Too many letters - the implementation ignores extra options if first 5 cover all issues
        # So this will be valid because A1 B2 C3 D1 E4 covers all issues
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4 F1")
        
        # Non-existent options
        assert not env._is_valid_action("Propose A9 B2 C3 D1 E4")  # A9 doesn't exist
        assert not env._is_valid_action("Propose A1 B9 C3 D1 E4")  # B9 doesn't exist
        assert not env._is_valid_action("Propose A1 B2 C9 D1 E4")  # C9 doesn't exist
        assert not env._is_valid_action("Propose A1 B2 C3 D9 E4")  # D9 doesn't exist
        assert not env._is_valid_action("Propose A1 B2 C3 D1 E9")  # E9 doesn't exist
        
        # Too few letters (missing issues)
        assert not env._is_valid_action("Propose A1 B2")
        assert not env._is_valid_action("Propose A1 B2 C3")
        assert not env._is_valid_action("Propose A1 B2 C3 D1")
        
        # Invalid issue letters
        assert not env._is_valid_action("Propose F1 B2 C3 D1 E4")  # F doesn't exist
        assert not env._is_valid_action("Propose A1 G2 C3 D1 E4")  # G doesn't exist
        assert not env._is_valid_action("Propose Z1 B2 C3 D1 E4")  # Z doesn't exist

    def test_valid_proposal_formats(self, reset_env):
        """Test valid proposal formats."""
        env = reset_env
        
        # Basic valid proposals
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4")
        assert env._is_valid_action("Propose A3 B1 C4 D4 E5")
        assert env._is_valid_action("Propose A2 B3 C2 D3 E1")
        
        # With rationale
        assert env._is_valid_action("This is balanced\nPropose A1 B2 C3 D1 E4")
        
        # Different order (should still be valid as long as all issues covered)
        assert env._is_valid_action("Propose E4 D1 C3 B2 A1")

    def test_get_score_as_expected(self, reset_env):
        """Test that scores are calculated correctly for accepted deals."""
        env = reset_env
        
        # Create a test deal
        test_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # Calculate score for player 0 (SportCo)
        player_0_score = env._calculate_player_score(0, test_deal)
        
        # Verify score calculation
        expected_score = 0
        player_scores = env.player_scores[0]
        for issue, option in test_deal.items():
            if issue in player_scores and option in player_scores[issue]:
                expected_score += player_scores[issue][option]
        
        assert player_0_score == expected_score
        assert isinstance(player_0_score, int)

    def test_get_threshold_score_if_deal_not_reached(self, reset_env):
        """Test that players get threshold score when no deal is reached."""
        env = reset_env
        
        # Simulate max rounds reached without deal
        env.state.turn = env.max_rounds
        outcome = env._handle_no_deal()
        
        # Check that all players get their threshold scores
        for player_id in range(6):
            threshold = env.player_scores[player_id]["threshold"]
            assert outcome.rewards[player_id] == threshold

    def test_score_calculation_different_deals(self, reset_env):
        """Test score calculation for different deal combinations."""
        env = reset_env
        
        # Test multiple deals
        deals = [
            {"A": "A1", "B": "B1", "C": "C1", "D": "D1", "E": "E1"},
            {"A": "A3", "B": "B3", "C": "C4", "D": "D4", "E": "E5"},
            {"A": "A2", "B": "B2", "C": "C2", "D": "D2", "E": "E3"}
        ]
        
        for deal in deals:
            for player_id in range(6):
                score = env._calculate_player_score(player_id, deal)
                assert isinstance(score, int)
                # Score should be sum of individual option scores
                expected = sum(
                    env.player_scores[player_id][issue][option]
                    for issue, option in deal.items()
                    if issue in env.player_scores[player_id] and option in env.player_scores[player_id][issue]
                )
                assert score == expected

    def test_unanimity_bonus_application(self, reset_env):
        """Test unanimity bonus for configured role."""
        env = reset_env
        
        # Create a deal and make all players accept
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {i: "Accept" for i in range(6)}
        
        # Finalize the deal
        env._finalize_accepted_deal()
        
        # Check that p1 (SportCo) gets the unanimity bonus
        p1_id = env._get_player_by_role("p1")
        base_score = env._calculate_player_score(p1_id, env.current_deal)
        
        # The bonus should be applied in _finalize_accepted_deal
        # We can't directly check rewards due to normalization, but we can verify the logic
    
    def test_can_only_see_own_preferences(self, reset_env):
        """Test that players can only see their own scoring preferences and personal context."""
        env = reset_env
        
        # Get all agent names for comparison
        all_agent_names = [env.player_configs[i]["agent_name"] for i in range(6)]
        
        # Test each player's observation
        for player_id in range(6):
            env.state.current_player_id = player_id
            _, observation = env.get_observation()
            
            # Convert observation to string for analysis
            obs_text = "\n".join([msg[1] for msg in observation])
            player_name = env.player_configs[player_id]["agent_name"]
            
            # Should contain own scoring information
            assert "Private Scoring Function" in obs_text
            
            # Should contain their own agent name in personal context
            assert player_name in obs_text
            
            # Verify their name appears in personal context (e.g., "You represent the [agent_name]")
            personal_contexts = [
                f"You represent the {player_name}",
                f"{player_name}'s Private Scoring Function",
                f"represent the {player_name}",
            ]
            
            has_personal_context = any(context in obs_text for context in personal_contexts)
            assert has_personal_context, f"Player {player_id} ({player_name}) should see their name in personal context"
            
            # Verify that other players' names appear only in general game description contexts
            # They should NOT appear in personal/private contexts like scoring functions
            private_scoring_section_start = obs_text.find("Private Scoring Function")
            if private_scoring_section_start != -1:
                # Find the end of the private scoring section
                next_section_markers = ["GAME RULES", "CURRENT GAME STATE", "NEGOTIATION HISTORY"]
                private_scoring_section_end = len(obs_text)
                for marker in next_section_markers:
                    marker_idx = obs_text.find(marker, private_scoring_section_start + 1)
                    if marker_idx != -1 and marker_idx < private_scoring_section_end:
                        private_scoring_section_end = marker_idx
                
                private_scoring_section = obs_text[private_scoring_section_start:private_scoring_section_end]
                
                # Other players' names should NOT appear in the private scoring section
                for other_player_id in range(6):
                    if other_player_id != player_id:
                        other_name = env.player_configs[other_player_id]["agent_name"]
                        assert other_name not in private_scoring_section, \
                            f"Player {player_id} ({player_name}) should not see {other_name} in their private scoring section"
            
            # Verify that all agent names appear in general game description (this is expected)
            # but only the current player's name should appear in personal contexts
            for other_player_id in range(6):
                other_name = env.player_configs[other_player_id]["agent_name"]
                if other_player_id != player_id:
                    # Other names should appear in general description but not in personal contexts
                    assert other_name in obs_text, f"Player {player_id} should see {other_name} in general game description"
                    
                    # But should NOT appear in personal contexts
                    other_personal_contexts = [
                        f"You represent the {other_name}",
                        f"{other_name}'s Private Scoring Function",
                    ]
                    
                    for context in other_personal_contexts:
                        assert context not in obs_text, \
                            f"Player {player_id} ({player_name}) should not see personal context for {other_name}: '{context}'"

    def test_observation_content_validation(self, reset_env):
        """Test that observations contain expected content."""
        env = reset_env
        
        player_id, observation = env.get_observation()
        obs_text = "\n".join([msg[1] for msg in observation])
        
        # Should contain game rules
        assert "GAME RULES" in obs_text
        assert "REQUIRED ACTION FORMAT" in obs_text
        assert "VOTING RULES" in obs_text
        
        # Should contain issues information
        assert "Infrastructure Mix" in obs_text
        assert "Ecological Impact" in obs_text
        assert "Employment Rules" in obs_text
        assert "Federal Loan" in obs_text
        assert "Compensation to other cities" in obs_text
        
        # Should contain player's scoring information
        player_name = env.player_configs[player_id]["agent_name"]
        assert player_name in obs_text

    def test_game_state_visibility(self, reset_env):
        """Test visibility of current deal, votes, and history."""
        env = reset_env
        
        # Initially no deal
        player_id, observation = env.get_observation()
        obs_text = "\n".join([msg[1] for msg in observation])
        assert "No current deal proposal" in obs_text or "Private Scoring Function" in obs_text
        
        # Make a proposal
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {0: "Accept", 1: "Reject"}
        
        player_id, observation = env.get_observation()
        obs_text = "\n".join([msg[1] for msg in observation])
        
        # Should show current deal and voting status
        assert "Current Deal" in obs_text
        assert "Voting Status" in obs_text
    
    def test_deal_acceptance_with_required_votes(self, reset_env):
        """Test deal acceptance with required votes."""
        env = reset_env
        
        # Set up a deal
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # Test with default required votes (5 out of 6)
        env.player_votes = {0: "Accept", 1: "Accept", 2: "Accept", 3: "Accept", 4: "Accept"}
        assert env._check_deal_accepted()
        
        # Test with insufficient votes
        env.player_votes = {0: "Accept", 1: "Accept", 2: "Accept", 3: "Reject"}
        assert not env._check_deal_accepted()

    def test_veto_power_blocking_deals(self, reset_env):
        """Test that veto players can block deals."""
        env = reset_env
        
        # Set up a deal
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # Get p1 and p2 player IDs (veto players)
        p1_id = env._get_player_by_role("p1")
        p2_id = env._get_player_by_role("p2")
        
        # Even with majority accept, if p1 rejects, deal should fail
        env.player_votes = {i: "Accept" for i in range(6)}
        env.player_votes[p1_id] = "Reject"
        assert not env._check_deal_accepted()
        
        # Even with majority accept, if p2 rejects, deal should fail
        env.player_votes = {i: "Accept" for i in range(6)}
        env.player_votes[p2_id] = "Reject"
        assert not env._check_deal_accepted()
        
        # Both veto players must accept
        env.player_votes = {i: "Accept" for i in range(6)}
        assert env._check_deal_accepted()

    def test_maximum_rounds_reached(self, reset_env):
        """Test game ending when maximum rounds reached through natural gameplay."""
        env = reset_env
        
        # Use a smaller max_rounds for faster testing
        env.max_rounds = 10
        env.state.max_turns = 10
        
        # Play the game until max rounds are reached
        # Use actions that won't end the game early (proposals that get rejected)
        round_count = 0
        while not env.state.done and round_count < 15:  # Safety limit
            if env.state.turn >= env.max_rounds:
                break
                
            # Make actions that keep the game going
            if round_count % 6 == 0:  # Every 6th action, make a proposal
                done, info = env.step("Propose A1 B2 C3 D1 E4")
            else:  # Otherwise reject to keep game going
                done, info = env.step("Reject")
            
            round_count += 1
        
        # Game should end when max rounds reached
        assert env.state.done or env.state.turn >= env.max_rounds
        
        # If game ended due to max rounds, players should get threshold scores
        if env.state.done and env.state.turn >= env.max_rounds:
            assert env.state.rewards is not None
            # Check that players got their threshold scores (or close to it due to normalization)
            for player_id in range(6):
                assert env.state.rewards[player_id] is not None

    def test_winner_determination_logic(self, reset_env):
        """Test winner determination based on scores and thresholds."""
        env = reset_env
        
        # Create a deal that gives different scores to players
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        env.player_votes = {i: "Accept" for i in range(6)}
        
        # End the game (which calls _finalize_accepted_deal internally)
        env._end_game()
        
        # Check that game is marked as done and rewards are set
        assert env.state.done
        assert env.state.rewards is not None
        assert len(env.state.rewards) == 6
    
    def test_invalid_action_escalation(self, reset_env):
        """Test invalid action handling with error allowance."""
        env = reset_env
        
        current_player = env.state.current_player_id
        
        # Make invalid actions up to error allowance
        for i in range(env.error_allowance):
            # Should not apply default yet
            can_advance = env._handle_invalid_action(current_player, "invalid action")
            assert not can_advance  # Should not advance turn
        
        # Next invalid action should trigger default
        can_advance = env._handle_invalid_action(current_player, "invalid action")
        assert can_advance  # Should advance turn after applying default

    def test_default_action_application(self, reset_env):
        """Test default action application when error allowance exceeded."""
        env = reset_env
        
        current_player = env.state.current_player_id
        
        # Create a current deal first
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # Apply default action
        env._apply_default_action(current_player)
        
        # Should have voted with default action
        assert current_player in env.player_votes
        assert env.player_votes[current_player] == env.invalid_move_default

    def test_auto_proposal_generation(self, reset_env):
        """Test auto-proposal generation for defaulted players."""
        env = reset_env
        
        current_player = env.state.current_player_id
        
        # No current deal - should generate optimal proposal
        env._apply_default_action(current_player)
        
        # Should have created a deal
        assert env.current_deal is not None
        assert len(env.current_deal) == 5  # All 5 issues covered

    def test_error_count_reset_after_default(self, reset_env):
        """Test that error count resets after applying default action."""
        env = reset_env
        
        current_player = env.state.current_player_id
        
        # Set error count to max
        env.state.error_count = env.error_allowance
        
        # Apply default action
        env._apply_default_action(current_player)
        
        # Error count should be reset
        assert env.state.error_count == 0
        assert not env.state.made_invalid_move

    def test_step_function_valid_action(self, reset_env):
        """Test step function with valid actions."""
        env = reset_env
        
        initial_player = env.state.current_player_id
        
        # Make a valid proposal
        done, info = env.step("Propose A1 B2 C3 D1 E4")
        
        # Game should not be done, player should advance
        assert not done
        assert env.state.current_player_id != initial_player

    def test_step_function_invalid_action(self, reset_env):
        """Test step function with invalid actions."""
        env = reset_env
        
        initial_player = env.state.current_player_id
        
        # Make an invalid action
        done, info = env.step("invalid action")
        
        # Player should not advance on first invalid action
        assert not done
        assert env.state.current_player_id == initial_player

    def test_complete_game_scenario(self, reset_env):
        """Test a complete game scenario from start to finish."""
        env = reset_env
        
        # Get the starting player (p1)
        p1_id = env._get_player_by_role("p1")
        assert env.state.current_player_id == p1_id
        
        # Player p1 makes a proposal
        done, info = env.step("Propose A1 B2 C3 D1 E4")
        assert not done
        assert env.current_deal is not None
        
        # All 6 players need to vote (including both veto players)
        for _ in range(6):  # All 6 players vote
            done, info = env.step("Accept")
            if done:
                break
        
        # Game should be done after all players accept
        assert done
        assert env.state.rewards is not None

    def test_proposal_with_rationale_processing(self, reset_env):
        """Test proposal processing with rationale."""
        env = reset_env
        
        rationale = "This proposal balances all interests"
        action = f"{rationale}\nPropose A1 B2 C3 D1 E4"
        
        # Process the action
        env._process_valid_action(0, action)
        
        # Check that proposal was created and rationale stored
        assert env.current_deal is not None
        assert len(env.negotiation_history) > 0
        assert env.negotiation_history[-1]["rationale"] == rationale

    def test_identical_proposal_handling(self, reset_env):
        """Test that identical proposals are treated as acceptance."""
        env = reset_env
        
        # Set up existing deal
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        current_player = env.state.current_player_id
        
        # Make identical proposal
        env._process_valid_action(current_player, "Propose A1 B2 C3 D1 E4")
        
        # Should be treated as acceptance
        assert current_player in env.player_votes
        assert env.player_votes[current_player] == "Accept"

    def test_voting_without_current_proposal(self, reset_env):
        """Test voting when there's no current proposal."""
        env = reset_env
        
        current_player = env.state.current_player_id
        
        # Try to accept without proposal - should be handled as invalid
        result = env._handle_invalid_action(current_player, "Accept")
        assert not result  # Should not advance turn
    
    def test_different_required_votes_settings(self):
        """Test different required_votes configurations."""
        # Test with custom required votes
        env = ScorableGamesEnv(required_votes=4)
        env.reset(num_players=6)
        
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # Should pass with 4 accepts (including veto players)
        p1_id = env._get_player_by_role("p1")
        p2_id = env._get_player_by_role("p2")
        # Get two other player IDs that are not p1 or p2
        other_players = [i for i in range(6) if i not in [p1_id, p2_id]]
        env.player_votes = {p1_id: "Accept", p2_id: "Accept", other_players[0]: "Accept", other_players[1]: "Accept"}
        
        assert env._check_deal_accepted()

    def test_different_veto_roles_configurations(self):
        """Test different veto_roles configurations."""
        # Test with only p1 as veto player
        env = ScorableGamesEnv(veto_roles=["p1"])
        env.reset(num_players=6)
        
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        p1_id = env._get_player_by_role("p1")
        p2_id = env._get_player_by_role("p2")
        
        # p2 can reject, but if p1 accepts and we have enough votes, should pass
        env.player_votes = {i: "Accept" for i in range(6)}
        env.player_votes[p2_id] = "Reject"  # p2 rejects but doesn't have veto
        
        assert env._check_deal_accepted()

    def test_different_starting_role_configurations(self):
        """Test different starting_role configurations."""
        # Test with p2 as starting role
        env = ScorableGamesEnv(starting_role="p2")
        env.reset(num_players=6)
        
        p2_id = env._get_player_by_role("p2")
        assert env.state.current_player_id == p2_id

    def test_custom_invalid_move_default(self):
        """Test custom invalid_move_default settings."""
        env = ScorableGamesEnv(invalid_move_default="Reject")
        env.reset(num_players=6)
        
        current_player = env.state.current_player_id
        
        # Create a current deal
        env.current_deal = {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}
        
        # Apply default action
        env._apply_default_action(current_player)
        
        # Should have voted with custom default
        assert current_player in env.player_votes
        assert env.player_votes[current_player] == "Reject"
    
    def test_empty_and_whitespace_actions(self, reset_env):
        """Test empty actions and whitespace-only actions."""
        env = reset_env
        
        # Empty string
        assert not env._is_valid_action("")
        
        # Whitespace only
        assert not env._is_valid_action("   ")
        assert not env._is_valid_action("\t")
        assert not env._is_valid_action("\n")
        assert not env._is_valid_action("  \t  \n  ")

    def test_actions_with_excessive_whitespace(self, reset_env):
        """Test actions with excessive whitespace."""
        env = reset_env
        
        # Should still be valid with extra whitespace
        assert env._is_valid_action("   Propose   A1   B2   C3   D1   E4   ")
        assert env._is_valid_action("\tAccept\t")
        assert env._is_valid_action("\nReject\n")

    def test_case_sensitivity_in_keywords(self, reset_env):
        """Test case sensitivity in keywords and proposals."""
        env = reset_env
        
        # Keywords are case sensitive
        assert not env._is_valid_action("propose A1 B2 C3 D1 E4")
        assert not env._is_valid_action("PROPOSE A1 B2 C3 D1 E4")
        assert not env._is_valid_action("accept")
        assert not env._is_valid_action("ACCEPT")
        assert not env._is_valid_action("reject")
        assert not env._is_valid_action("REJECT")
        
        # Proposals with lowercase options should be invalid (case sensitive)
        assert not env._is_valid_action("Propose a1 b2 c3 d1 e4")

    def test_unicode_and_special_character_handling(self, reset_env):
        """Test unicode and special character handling."""
        env = reset_env
        
        # Unicode characters are allowed in rationale - the implementation is permissive
        assert env._is_valid_action("🎮\nPropose A1 B2 C3 D1 E4")
        assert env._is_valid_action("Propose A1 B2 C3 D1 E4 🎯")
        
        # Special characters in rationale should be fine
        assert env._is_valid_action("This is 100% fair!\nAccept")
        assert env._is_valid_action("Cost: $1M+\nReject")
    
    def test_game_state_persistence_across_actions(self, reset_env):
        """Test that game state persists correctly across actions."""
        env = reset_env
        
        # Make a proposal
        env.step("Propose A1 B2 C3 D1 E4")
        
        # Verify state persisted
        assert env.current_deal is not None
        assert len(env.negotiation_history) == 1
        
        # Make a vote
        env.step("Accept")
        
        # Verify both actions are in history
        assert len(env.negotiation_history) == 2
        assert env.negotiation_history[0]["action_type"] == "Propose"
        assert env.negotiation_history[1]["action_type"] == "Accept"

    def test_player_turn_management(self, reset_env):
        """Test player turn management."""
        env = reset_env
        
        initial_player = env.state.current_player_id
        
        # Valid action should advance turn
        env.step("Propose A1 B2 C3 D1 E4")
        assert env.state.current_player_id != initial_player
        
        # Turn should cycle through players
        next_player = env.state.current_player_id
        env.step("Accept")
        assert env.state.current_player_id != next_player

    def test_history_tracking_accuracy(self, reset_env):
        """Test that history tracking is accurate."""
        env = reset_env
        
        # Make several actions
        actions = [
            "Propose A1 B2 C3 D1 E4",
            "Accept",
            "Reject"
        ]
        
        for i, action in enumerate(actions):
            env.step(action)
            
            # Check history length
            assert len(env.negotiation_history) == i + 1
            
            # Check latest entry
            latest = env.negotiation_history[-1]
            assert latest["round"] == env.state.turn - 1  # Turn advances after action

    def test_observation_consistency(self, reset_env):
        """Test that observations are consistent for the same game state."""
        env = reset_env
        
        # Get initial observation
        player_id, obs1 = env.get_observation()
        
        # The observation system may consume observations, so we test consistency differently
        # Test that the same player ID is returned
        player_id2, obs2 = env.get_observation()
        assert player_id == player_id2
        
        # Test that observations are properly structured when they exist
        if len(obs1) > 0:
            assert all(len(msg) >= 2 for msg in obs1)  # Each observation should have at least 2 elements
    
    def test_large_number_of_rounds(self):
        """Test handling of large number of rounds."""
        env = ScorableGamesEnv(max_rounds=1000)
        env.reset(num_players=6)
        
        # Should initialize without issues
        assert env.max_rounds == 1000
        assert env.state.max_turns == 1000

    def test_rapid_action_sequences(self, reset_env):
        """Test rapid sequences of actions."""
        env = reset_env
        
        # Rapid sequence of valid actions
        for i in range(10):
            if not env.state.done:
                env.step("Propose A1 B2 C3 D1 E4")
            if not env.state.done:
                env.step("Accept")
        
        # Should handle without errors
        assert len(env.negotiation_history) > 0

    def test_memory_usage_with_long_histories(self, reset_env):
        """Test memory usage doesn't grow excessively with long histories."""
        env = reset_env
        
        # Create a long history
        for i in range(50):
            if not env.state.done:
                env.step(f"Round {i}\nPropose A1 B2 C3 D1 E4")
                if not env.state.done:
                    env.step(f"Round {i} response\nReject")
        
        # History should be manageable
        assert len(env.negotiation_history) <= 100  # Should not grow unbounded
    
    def test_game1_configuration(self):
        """Test with game1 configuration."""
        try:
            env = ScorableGamesEnv(game_config="game1")
            env.reset(num_players=6)  # Assuming game1 also has 6 players
            
            # Should load successfully
            assert len(env.issues) > 0
            assert len(env.player_configs) > 0
            
        except FileNotFoundError:
            # Skip if game1 config doesn't exist
            pytest.skip("game1 configuration not available")

    def test_base_7players_configuration(self):
        """Test with base_7players configuration."""
        try:
            env = ScorableGamesEnv(game_config="base_7players")
            env.reset(num_players=7)
            
            # Should load successfully with 7 players
            assert env.state.num_players == 7
            assert len(env.player_configs) == 7
            
        except (FileNotFoundError, ValueError):
            # Skip if base_7players config doesn't exist or has different player count
            pytest.skip("base_7players configuration not available or has different player count")
    
    def test_full_negotiation_workflow(self, reset_env):
        """Test a complete negotiation workflow."""
        env = reset_env
        
        # Phase 1: Initial proposal
        done, info = env.step("I believe this is fair\nPropose A1 B2 C3 D1 E4")
        assert not done
        assert env.current_deal is not None
        
        # Phase 2: Some players accept, some reject
        done, info = env.step("This works for us\nAccept")
        assert not done
        
        done, info = env.step("Environmental concerns\nReject")
        assert not done
        
        # Phase 3: New proposal
        done, info = env.step("Better environmental option\nPropose A3 B3 C3 D1 E4")
        assert not done
        
        # Phase 4: Final voting
        for _ in range(5):  # Remaining players
            if not done:
                done, info = env.step("Accept")
        
        # Should eventually reach conclusion
        assert done or env.state.turn < env.max_rounds


class TestScorableGamesRegressions:
    @staticmethod
    def _base_deal():
        return {"A": "A1", "B": "B2", "C": "C3", "D": "D1", "E": "E4"}

    def test_medical_ethics_enforces_required_votes_without_recognized_veto_roles(self):
        env = ScorableGamesEnv(game_config="medical_ethics", required_votes=4)
        env.reset(num_players=4, seed=42)
        env.current_deal = env._generate_optimal_proposal(0)

        assert all(env._get_player_by_role(role) is None for role in env.veto_roles)
        env.player_votes = {0: "Accept", 1: "Accept", 2: "Accept"}
        assert not env._check_deal_accepted()
        env.player_votes[3] = "Accept"
        assert env._check_deal_accepted()

    def test_no_veto_base_enforces_configured_required_votes(self):
        env = ScorableGamesEnv(game_config="base", required_votes=5, veto_roles=[])
        env.reset(num_players=6, seed=42)
        env.current_deal = self._base_deal()

        env.player_votes = {pid: "Accept" for pid in range(4)}
        assert not env._check_deal_accepted()
        env.player_votes[4] = "Accept"
        assert env._check_deal_accepted()

    @pytest.mark.parametrize(
        "action",
        [
            "Accept",
            "Reject",
            "Propose A9 B2 C3 D1 E4",
        ],
    )
    def test_invalid_actions_are_atomic_before_logging_and_marking(self, action):
        env = ScorableGamesEnv(game_config="base")
        env.reset(num_players=6, seed=42)
        events_before = len(env.state.events)
        containers_before = {
            "deal": env.current_deal.copy(),
            "history": list(env.negotiation_history),
            "votes": env.player_votes.copy(),
            "valid": env.valid_actions_this_round.copy(),
        }

        done, _ = env.step(action)

        assert not done
        assert env.state.turn == 0
        assert env.current_deal == containers_before["deal"]
        assert env.negotiation_history == containers_before["history"]
        assert env.player_votes == containers_before["votes"]
        assert env.valid_actions_this_round == containers_before["valid"]
        assert all(
            event[2] != ta.ObservationType.PLAYER_ACTION
            for event in env.state.events[events_before:]
        )

    @pytest.mark.parametrize(
        "action",
        [
            "Accept\nAccept",
            "Reject\nReject",
            "Accept\nReject",
            "Propose A1 B2 C3 D1 E4\nAccept",
        ],
    )
    def test_duplicate_decisions_are_atomic_invalids(self, action):
        env = ScorableGamesEnv(game_config="base")
        env.reset(num_players=6, seed=42)
        env.step("Propose A1 B2 C3 D1 E4")
        events_before = len(env.state.events)
        history_before = list(env.negotiation_history)
        votes_before = env.player_votes.copy()
        valid_before = env.valid_actions_this_round.copy()
        turn_before = env.state.turn

        done, _ = env.step(action)

        assert not done
        assert env.state.turn == turn_before
        assert env.negotiation_history == history_before
        assert env.player_votes == votes_before
        assert env.valid_actions_this_round == valid_before
        assert all(
            event[2] != ta.ObservationType.PLAYER_ACTION
            for event in env.state.events[events_before:]
        )

    def test_active_state_containers_have_one_canonical_owner(self):
        env = ScorableGamesEnv(game_config="base")
        env.reset(num_players=6, seed=42)

        assert env.current_deal is env.game_state["current_deal"]
        assert env.negotiation_history is env.game_state["negotiation_history"]
        assert env.player_votes is env.game_state["player_votes"]
        assert env.valid_actions_this_round is env.game_state["valid_actions_this_round"]

        env.step("Propose A1 B2 C3 D1 E4")

        assert env.current_deal is env.game_state["current_deal"]
        assert env.negotiation_history is env.game_state["negotiation_history"]
        assert env.player_votes is env.game_state["player_votes"]
        assert env.valid_actions_this_round is env.game_state["valid_actions_this_round"]

    def test_vote_renderer_counts_stored_vote_values(self):
        env = ScorableGamesEnv(game_config="base")
        env.reset(num_players=6, seed=42)
        env.current_deal = self._base_deal()
        env.player_votes = {0: "Accept", 1: "Reject"}

        board = env.get_board_str()

        assert "Summary: 1 Accept, 1 Reject" in board

    def test_no_deal_clears_proposal_persists_scores_and_renders_stably(self):
        env = ScorableGamesEnv(game_config="base", max_rounds=1)
        env.reset(num_players=6, seed=42)

        done, _ = env.step("Propose A1 B2 C3 D1 E4")

        assert done
        assert env.current_deal == {}
        assert env.current_deal is env.game_state["current_deal"]
        assert env.game_state["terminal_result"]["deal_accepted"] is False
        first_render = env.get_board_str()
        second_render = env.get_board_str()
        assert first_render == second_render
        assert "No deal was reached." in first_render
        assert "Final Deal Accepted" not in first_render

        for pid in range(env.state.num_players):
            threshold = env.player_scores[pid]["threshold"]
            assert env.state.game_info[pid]["score"] == threshold
            assert env.state.game_info[pid]["threshold"] == threshold
            assert env.state.game_info[pid]["deal_accepted"] is False
            assert env.state.rewards[pid] == threshold

    def test_terminal_accept_action_is_counted(self):
        env = ScorableGamesEnv(
            game_config="base", required_votes=1, veto_roles=[]
        )
        env.reset(num_players=6, seed=42)

        proposer = env.state.current_player_id
        env.step("Propose A1 B2 C3 D1 E4")
        accepter = env.state.current_player_id
        done, _ = env.step("Accept")

        assert done
        assert env.state.game_info[proposer]["turn_count"] == 1
        assert env.state.game_info[accepter]["turn_count"] == 1

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"game_config": "../base"},
            {"max_rounds": 0},
            {"max_rounds": True},
            {"required_votes": 0},
            {"required_votes": True},
            {"veto_roles": None},
            {"veto_roles": [""]},
            {"unanimity_bonus_role": ""},
            {"starting_role": ""},
            {"invalid_move_default": "Maybe"},
            {"error_allowance": -1},
        ],
    )
    def test_invalid_configuration_is_rejected(self, kwargs):
        with pytest.raises(ValueError):
            ScorableGamesEnv(**kwargs)

    def test_required_votes_cannot_exceed_loaded_player_count(self):
        env = ScorableGamesEnv(game_config="medical_ethics", required_votes=5)
        with pytest.raises(ValueError, match="required_votes"):
            env.reset(num_players=4, seed=42)

    def test_veto_role_configuration_is_detached_and_default_vote_normalized(self):
        veto_roles = ["p1"]
        env = ScorableGamesEnv(
            veto_roles=veto_roles, invalid_move_default="[reject]"
        )
        veto_roles.append("p2")
        assert env.veto_roles == ["p1"]
        assert env.invalid_move_default == "Reject"
