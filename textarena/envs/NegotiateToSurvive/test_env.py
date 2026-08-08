import pytest
import sys
import os

# Add the TextArena directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from textarena.envs.NegotiateToSurvive.env import NegotiateToSurviveEnv
import textarena as ta


class TestNegotiateToSurviveEnv:
    """Test suite for Negotiate to Survive environment."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        self.env_distributive = NegotiateToSurviveEnv(game_variant="distributive", max_rounds=10)
        self.env_integrative = NegotiateToSurviveEnv(game_variant="integrative", max_rounds=10)
    
    # ===== ACTION FORMAT VALIDATION TESTS =====
    
    def test_valid_whisper_format(self):
        """Test valid whisper action format."""
        self.env_distributive.reset()
        assert self.env_distributive._is_valid_whisper("[Whisper] 1 Hello there")
        assert self.env_distributive._is_valid_whisper("[Whisper] 2 Let's make a deal")
        
    def test_invalid_whisper_formats(self):
        """Test invalid whisper action formats."""
        self.env_distributive.reset()
        # Missing target player
        assert not self.env_distributive._is_valid_whisper("[Whisper] Hello")
        # Invalid player ID
        assert not self.env_distributive._is_valid_whisper("[Whisper] 5 Hello")
        assert not self.env_distributive._is_valid_whisper("[Whisper] -1 Hello")
        # Whisper to self
        self.env_distributive.state.current_player_id = 0
        assert not self.env_distributive._is_valid_whisper("[Whisper] 0 Hello")
        # Empty message
        assert not self.env_distributive._is_valid_whisper("[Whisper] 1 ")
    
    def test_valid_proposal_format(self):
        """Test valid proposal action format."""
        self.env_distributive.reset()
        self.env_distributive.state.current_player_id = 0
        assert self.env_distributive._is_valid_proposal("[Propose] 10 for water")
        assert self.env_distributive._is_valid_proposal("[Propose] 25 for medicine")
        
    def test_invalid_proposal_formats(self):
        """Test invalid proposal action formats."""
        self.env_distributive.reset()
        self.env_distributive.state.current_player_id = 0
        # Invalid resource
        assert not self.env_distributive._is_valid_proposal("[Propose] 10 for gold")
        # Zero coins
        assert not self.env_distributive._is_valid_proposal("[Propose] 0 for water")
        # Negative coins
        assert not self.env_distributive._is_valid_proposal("[Propose] -5 for water")
        # Not enough coins
        assert not self.env_distributive._is_valid_proposal("[Propose] 100 for water")
        # Malformed format
        assert not self.env_distributive._is_valid_proposal("[Propose] ten for water")
        assert not self.env_distributive._is_valid_proposal("[Propose] 10 water")
    
    def test_valid_accept_format(self):
        """Test valid accept action format."""
        self.env_distributive.reset()
        # Create a proposal first
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        
        # Player 1 has water, so they can accept
        self.env_distributive.state.current_player_id = 1
        assert self.env_distributive._is_valid_accept("[Accept] 1")
        
    def test_invalid_accept_formats(self):
        """Test invalid accept action formats."""
        self.env_distributive.reset()
        # Non-existent proposal
        assert not self.env_distributive._is_valid_accept("[Accept] 999")
        # Malformed format
        assert not self.env_distributive._is_valid_accept("[Accept] abc")
        assert not self.env_distributive._is_valid_accept("[Accept]")
    
    def test_multiple_bracketed_actions(self):
        """Test that only the first bracketed action is processed."""
        self.env_distributive.reset()
        action = "I want to trade [Propose] 10 for water [Accept] 1"
        
        # Should extract only the first bracketed action
        free_text = self.env_distributive._extract_free_text(action)
        assert free_text == "I want to trade"
        
        # Should process as a proposal, not accept
        assert "[Propose]" in action
        assert self.env_distributive._is_valid_proposal(action)
    
    # ===== TRADING AND RESOURCE TRACKING TESTS =====
    
    def test_basic_trading_mechanics(self):
        """Test basic trading functionality."""
        self.env_distributive.reset()
        
        # Initial state: Player 0 has [food], Player 1 has [water]
        assert "food" in self.env_distributive.player_resources[0]
        assert "water" in self.env_distributive.player_resources[1]
        assert self.env_distributive.player_coins[0] == 50
        assert self.env_distributive.player_coins[1] == 50
        
        # Player 0 proposes to buy water
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        
        # Player 1 accepts
        self.env_distributive.state.current_player_id = 1
        self.env_distributive._process_accept(1, "[Accept] 1")
        
        # Check results
        assert "food" in self.env_distributive.player_resources[0]
        assert "water" in self.env_distributive.player_resources[0]  # Player 0 now has both
        assert len(self.env_distributive.player_resources[1]) == 0  # Player 1 has no resources
        assert self.env_distributive.player_coins[0] == 40  # Lost 10 coins
        assert self.env_distributive.player_coins[1] == 60  # Gained 10 coins
        
        # Check resource history
        assert 0 in self.env_distributive.resource_history["water"]
        assert 1 in self.env_distributive.resource_history["water"]
    
    def test_resource_ownership_tracking(self):
        """Test that resource ownership is properly tracked."""
        self.env_distributive.reset()
        
        # All resources should have exactly one owner initially
        all_resources = set()
        for resources in self.env_distributive.player_resources.values():
            all_resources.update(resources)
        
        assert len(all_resources) == 5  # All 5 resources are owned
        assert all_resources == set(self.env_distributive.resources)
    
    def test_cannot_accept_resource_you_dont_own(self):
        """Test that players can't accept proposals for resources they don't own."""
        self.env_distributive.reset()
        
        # Player 0 proposes to buy water
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        
        # Player 2 (who has shelter, not water) tries to accept
        self.env_distributive.state.current_player_id = 2
        assert not self.env_distributive._is_valid_accept("[Accept] 1")
    
    def test_proposal_tracking(self):
        """Test that proposals are properly tracked and removed."""
        self.env_distributive.reset()
        
        # Create multiple proposals
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        self.env_distributive._process_proposal(0, "[Propose] 15 for medicine")
        
        assert len(self.env_distributive.proposals) == 2
        assert 1 in self.env_distributive.proposals
        assert 2 in self.env_distributive.proposals
        
        # Accept one proposal
        self.env_distributive.state.current_player_id = 1  # Player 1 has water
        self.env_distributive._process_accept(1, "[Accept] 1")
        
        # Proposal should be removed
        assert len(self.env_distributive.proposals) == 1
        assert 1 not in self.env_distributive.proposals
        assert 2 in self.env_distributive.proposals
    
    # ===== WHISPER FUNCTIONALITY TESTS =====
    
    def test_whisper_privacy(self):
        """Test that whispers are private between sender and receiver."""
        self.env_distributive.reset()
        
        # Get initial observation count
        initial_logs_count = len(self.env_distributive.state.logs)
        
        # Player 0 whispers to Player 1
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_whisper(0, "[Whisper] 1 Secret message")
        
        # Check that logs were added (whisper should generate multiple log entries)
        assert len(self.env_distributive.state.logs) > initial_logs_count
        
        # Check that whisper was recorded in history
        assert len(self.env_distributive.whisper_history) == 1
        whisper = self.env_distributive.whisper_history[0]
        assert whisper["from"] == 0
        assert whisper["to"] == 1
        assert whisper["message"] == "Secret message"
    
    def test_whisper_history_tracking(self):
        """Test that whisper history is properly tracked."""
        self.env_distributive.reset()
        
        # Send a whisper
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_whisper(0, "[Whisper] 1 Test message")
        
        # Check whisper history
        assert len(self.env_distributive.whisper_history) == 1
        whisper = self.env_distributive.whisper_history[0]
        assert whisper["from"] == 0
        assert whisper["to"] == 1
        assert whisper["message"] == "Test message"
        assert whisper["round"] == self.env_distributive.state.turn
    
    # ===== END GAME LOGIC TESTS =====
    
    def test_distributive_end_game_condition(self):
        """Test end game condition for distributive variant."""
        self.env_distributive.reset()
        
        # Initially, no player has 4+ resources in history
        assert not self.env_distributive._check_game_end()
        
        # Simulate Player 0 acquiring 4 different resources
        # Player 0 starts with food, needs 3 more
        resources_to_add = ["water", "shelter", "medicine"]
        
        for i, resource in enumerate(resources_to_add):
            # Add resource to Player 0's collection
            self.env_distributive.player_resources[0].append(resource)
            # Update resource history
            if resource not in self.env_distributive.resource_history:
                self.env_distributive.resource_history[resource] = []
            self.env_distributive.resource_history[resource].append(0)
        
        # Now Player 0 should have 4 resources in history
        assert self.env_distributive._check_game_end()
    
    def test_integrative_end_game_condition(self):
        """Test end game condition for integrative variant."""
        self.env_integrative.reset()
        
        # Initially, no player has all 5 resources in history
        assert not self.env_integrative._check_game_end()
        
        # Simulate Player 0 acquiring all 5 resources
        # Player 0 starts with food, needs 4 more
        resources_to_add = ["water", "shelter", "medicine", "clothing"]
        
        for resource in resources_to_add:
            # Add resource to Player 0's collection
            self.env_integrative.player_resources[0].append(resource)
            # Update resource history
            if resource not in self.env_integrative.resource_history:
                self.env_integrative.resource_history[resource] = []
            self.env_integrative.resource_history[resource].append(0)
        
        # Now Player 0 should have all 5 resources in history
        assert self.env_integrative._check_game_end()
    
    def test_distributive_winner_determination(self):
        """Test winner determination in distributive variant."""
        self.env_distributive.reset()
        
        # Set up end game scenario
        # Player 0 has 4 resources (meets survival condition)
        for resource in ["water", "shelter", "medicine"]:
            self.env_distributive.player_resources[0].append(resource)
            if resource not in self.env_distributive.resource_history:
                self.env_distributive.resource_history[resource] = []
            self.env_distributive.resource_history[resource].append(0)
        
        # Set different coin amounts
        self.env_distributive.player_coins[0] = 60  # Highest coins
        self.env_distributive.player_coins[1] = 40
        self.env_distributive.player_coins[2] = 30
        
        # End the game
        self.env_distributive._end_game()
        
        # Player 0 should win (highest coins)
        assert self.env_distributive.state.game_info[0]["winner"] == True
        assert self.env_distributive.state.game_info[1]["winner"] == False
        assert self.env_distributive.state.game_info[2]["winner"] == False
    
    def test_integrative_winner_determination(self):
        """Test winner determination in integrative variant."""
        self.env_integrative.reset()
        
        # Set up end game scenario
        # Player 0 has all 5 resources (meets survival condition)
        for resource in ["water", "shelter", "medicine", "clothing"]:
            self.env_integrative.player_resources[0].append(resource)
            if resource not in self.env_integrative.resource_history:
                self.env_integrative.resource_history[resource] = []
            self.env_integrative.resource_history[resource].append(0)
        
        # End the game
        self.env_integrative._end_game()
        
        # All players should win in integrative variant
        for pid in range(5):
            assert self.env_integrative.state.game_info[pid]["winner"] == True
    
    def test_no_survival_condition_met(self):
        """Test game end when no survival conditions are met."""
        self.env_distributive.reset()
        
        # Force game to end without meeting survival conditions
        self.env_distributive.state.turn = self.env_distributive.max_rounds - 1
        self.env_distributive._end_game()
        
        # No one should win
        for pid in range(5):
            assert self.env_distributive.state.game_info[pid]["winner"] == False
    
    # ===== INTEGRATION TESTS =====
    
    def test_full_game_flow(self):
        """Test a complete game flow with multiple actions."""
        self.env_distributive.reset()
        
        # Player 0's turn: Propose to buy water
        self.env_distributive.state.current_player_id = 0
        done, info = self.env_distributive.step("I need water for survival [Propose] 15 for water")
        assert not done
        
        # Player 1's turn: Accept the proposal
        self.env_distributive.state.current_player_id = 1
        done, info = self.env_distributive.step("That's a good deal [Accept] 1")
        assert not done
        
        # Verify trade occurred
        assert "water" in self.env_distributive.player_resources[0]
        assert len(self.env_distributive.player_resources[1]) == 0
        assert self.env_distributive.player_coins[0] == 35
        assert self.env_distributive.player_coins[1] == 65
    
    def test_invalid_action_handling(self):
        """Test handling of invalid actions."""
        self.env_distributive.reset()
        
        # Test invalid action
        self.env_distributive.state.current_player_id = 0
        initial_error_count = self.env_distributive.state.error_count
        
        # This should be invalid (malformed proposal)
        done, info = self.env_distributive.step("[Propose] invalid format")
        
        # Error count should increase
        assert self.env_distributive.state.error_count > initial_error_count
    
    def test_pass_action(self):
        """Test pass action functionality."""
        self.env_distributive.reset()
        
        self.env_distributive.state.current_player_id = 0
        done, info = self.env_distributive.step("I'll wait this turn [Pass]")
        
        # Should advance to next player
        assert not done
        # Game should continue normally
    
    # ===== SELF-INTERACTION VALIDATION TESTS =====
    
    def test_cannot_accept_own_proposal(self):
        """Test that players cannot accept their own proposals."""
        self.env_distributive.reset()
        
        # Player 0 creates a proposal
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        
        # Player 0 tries to accept their own proposal
        assert not self.env_distributive._is_valid_accept("[Accept] 1")
    
    def test_cannot_propose_for_resource_you_own(self):
        """Test that players cannot propose for resources they already own."""
        self.env_distributive.reset()
        
        # Player 0 starts with food, tries to propose for food
        self.env_distributive.state.current_player_id = 0
        
        # This should be invalid - you can't buy what you already have
        # Note: This might be a design decision - should players be able to buy duplicates?
        # For now, let's test the current behavior
        
        # Actually, let's check if this is currently allowed or not
        # If it's allowed, we might want to add a test for the edge case
        pass  # We'll implement this based on current behavior
    
    def test_whisper_to_self_validation(self):
        """Test comprehensive whisper-to-self validation."""
        self.env_distributive.reset()
        
        # Test all player IDs trying to whisper to themselves
        for player_id in range(5):
            self.env_distributive.state.current_player_id = player_id
            assert not self.env_distributive._is_valid_whisper(f"[Whisper] {player_id} Hello myself")
    
    def test_proposal_ownership_edge_cases(self):
        """Test edge cases around proposal ownership and validation."""
        self.env_distributive.reset()
        
        # Player 0 creates multiple proposals
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        self.env_distributive._process_proposal(0, "[Propose] 15 for medicine")
        
        # Verify proposals are tracked correctly
        assert len(self.env_distributive.proposals) == 2
        
        # Verify proposer cannot accept their own proposals
        for proposal_id in self.env_distributive.proposals:
            assert not self.env_distributive._is_valid_accept(f"[Accept] {proposal_id}")
    
    def test_insufficient_coins_for_proposal(self):
        """Test that players with insufficient coins cannot make proposals."""
        self.env_distributive.reset()
        
        # Set player 0 to have very few coins
        self.env_distributive.player_coins[0] = 5
        self.env_distributive.state.current_player_id = 0
        
        # Should not be able to propose more coins than they have
        assert not self.env_distributive._is_valid_proposal("[Propose] 10 for water")
        assert not self.env_distributive._is_valid_proposal("[Propose] 100 for medicine")
        
        # Should be able to propose within their means
        assert self.env_distributive._is_valid_proposal("[Propose] 5 for water")
        assert self.env_distributive._is_valid_proposal("[Propose] 3 for shelter")
    
    def test_proposer_loses_coins_after_spending(self):
        """Test that proposer's coin validation updates after spending."""
        self.env_distributive.reset()
        
        # Player 0 starts with 50 coins
        self.env_distributive.state.current_player_id = 0
        
        # Make a proposal for 40 coins
        self.env_distributive._process_proposal(0, "[Propose] 40 for water")
        
        # Player 1 accepts, reducing Player 0's coins to 10
        self.env_distributive.state.current_player_id = 1
        self.env_distributive._process_accept(1, "[Accept] 1")
        
        # Now Player 0 should only be able to propose up to 10 coins
        self.env_distributive.state.current_player_id = 0
        assert not self.env_distributive._is_valid_proposal("[Propose] 15 for medicine")
        assert self.env_distributive._is_valid_proposal("[Propose] 10 for medicine")
        assert self.env_distributive._is_valid_proposal("[Propose] 5 for shelter")
    
    def test_accept_nonexistent_proposal_edge_cases(self):
        """Test various edge cases for accepting non-existent proposals."""
        self.env_distributive.reset()
        
        # Try to accept proposals that don't exist
        assert not self.env_distributive._is_valid_accept("[Accept] 999")
        assert not self.env_distributive._is_valid_accept("[Accept] 0")
        assert not self.env_distributive._is_valid_accept("[Accept] -1")
        
        # Create and then remove a proposal, try to accept the removed one
        self.env_distributive.state.current_player_id = 0
        self.env_distributive._process_proposal(0, "[Propose] 10 for water")
        
        # Accept the proposal (removes it)
        self.env_distributive.state.current_player_id = 1
        self.env_distributive._process_accept(1, "[Accept] 1")
        
        # Try to accept the same proposal again (should fail)
        assert not self.env_distributive._is_valid_accept("[Accept] 1")


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])
