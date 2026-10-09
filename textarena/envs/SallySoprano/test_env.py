import pytest
import sys
import os

# Add the TextArena root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

import textarena as ta
from textarena.envs.SallySoprano.env import SallySopranoEnv


class TestSallySopranoEnv:
    """Test suite for Sally Soprano negotiation environment."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        self.env = SallySopranoEnv(max_rounds=10)
    
    def test_initialization(self):
        """Test environment initialization."""
        assert self.env.max_rounds == 10
        assert self.env.error_allowance == 3
        assert self.env.propose_pattern is not None
        assert self.env.accept_pattern is not None
    
    def test_reset_with_correct_players(self):
        """Test reset with correct number of players."""
        self.env.reset(num_players=3, seed=42)
        
        assert self.env.state.num_players == 3
        assert self.env.state.current_player_id == 0
        assert len(self.env.state.role_mapping) == 4  # 3 players + GAME
        assert self.env.state.role_mapping[0] == "Sally's Agent"
        assert self.env.state.role_mapping[1] == "Business Manager"
        assert self.env.state.role_mapping[2] == "Judge"
    
    def test_reset_with_wrong_players(self):
        """Test reset fails with wrong number of players."""
        with pytest.raises(ValueError, match="SallySoprano requires exactly 3 players"):
            self.env.reset(num_players=2)
    
    def test_initial_game_state(self):
        """Test initial game state after reset."""
        self.env.reset(num_players=3, seed=42)
        
        game_state = self.env.state.game_state
        assert game_state["current_proposal"] is None
        assert game_state["proposal_history"] == []
        assert game_state["deal_reached"] is False
        assert game_state["final_deal"] is None
        assert game_state["negotiation_complete"] is False
    
    def test_get_initial_observation(self):
        """Test getting initial observation."""
        self.env.reset(num_players=3, seed=42)
        
        player_id, obs = self.env.get_observation()
        assert player_id == 0  # Sally's Agent starts
        assert len(obs) > 0
        
        # Check that the observation contains the prompt
        prompt_obs = [msg for sender, msg, obs_type in obs if obs_type == ta.ObservationType.PROMPT]
        assert len(prompt_obs) == 1
        assert "Sally's Agent" in prompt_obs[0]
    
    def test_proposal_action(self):
        """Test making a salary proposal."""
        self.env.reset(num_players=3, seed=42)
        
        # Sally's Agent makes proposal
        action = "I believe Sally deserves fair compensation. [Propose] 30000"
        done, info = self.env.step(action)
        
        assert not done
        assert self.env.state.current_player_id == 1  # Should switch to Business Manager
        assert self.env.state.game_state["current_proposal"] is not None
        assert self.env.state.game_state["current_proposal"]["amount"] == 30000
        assert self.env.state.game_state["current_proposal"]["proposer"] == 0
    
    def test_accept_proposal(self):
        """Test accepting a proposal."""
        self.env.reset(num_players=3, seed=42)
        
        # Sally's Agent makes proposal
        self.env.step("I believe Sally deserves fair compensation. [Propose] 30000")
        
        # Business Manager accepts
        action = "This seems reasonable. [Accept]"
        done, info = self.env.step(action)
        
        assert not done  # Game continues to judge evaluation
        assert self.env.state.game_state["deal_reached"] is True
        assert self.env.state.game_state["final_deal"]["amount"] == 30000
        assert self.env.state.game_state["negotiation_complete"] is True
    
    def test_reject_own_proposal(self):
        """Test that players cannot accept their own proposals."""
        self.env.reset(num_players=3, seed=42)
        
        # Sally's Agent makes proposal
        self.env.step("I believe Sally deserves fair compensation. [Propose] 30000")
        
        # Switch back to Sally's Agent (simulate invalid state)
        self.env.state.current_player_id = 0
        
        # Try to accept own proposal
        action = "[Accept]"
        done, info = self.env.step(action)
        
        # Invalid move - should stay on same player and no deal reached
        assert self.env.state.current_player_id == 0
        assert not self.env.state.game_state["deal_reached"]
    
    def test_accept_without_proposal(self):
        """Test accepting when no proposal exists."""
        self.env.reset(num_players=3, seed=42)
        
        # Try to accept without any proposal
        action = "[Accept]"
        done, info = self.env.step(action)
        
        # Invalid move - should stay on same player
        assert self.env.state.current_player_id == 0
        assert not self.env.state.game_state["deal_reached"]
        assert self.env.state.game_state["current_proposal"] is None
    
    def test_free_text_discussion(self):
        """Test free text discussion without bracketed actions."""
        self.env.reset(num_players=3, seed=42)
        
        # Sally's Agent makes free text comment
        action = "Sally has extensive experience and would be perfect for this role."
        done, info = self.env.step(action)
        
        assert not done
        assert self.env.state.current_player_id == 1  # Should switch to Business Manager
    
    def test_judge_observing(self):
        """Test that judge observes during negotiation."""
        self.env.reset(num_players=3, seed=42)
        
        # Sally's Agent makes comment
        self.env.step("Sally has extensive experience.")
        # Business Manager responds  
        self.env.step("We need to consider our budget.")
        
        # In our new implementation, judge doesn't get explicit turns during negotiation
        # The game alternates between players 0 and 1 only
        assert self.env.state.current_player_id in [0, 1]  # Should be one of the negotiating players
        assert not self.env.state.game_state["negotiation_complete"]
    
    def test_judge_decision_business_manager_wins(self):
        """Test judge decision parsing when Business Manager wins."""
        self.env.reset(num_players=3, seed=42)
        
        # Complete negotiation
        self.env.step("[Propose] 15000")
        self.env.step("[Accept]")
        
        # Judge makes decision
        judge_decision = "[winner] Business Manager\n[reason] The Business Manager got a better deal."
        done, info = self.env.step(judge_decision)
        
        assert done
        rewards, game_info = self.env.close()
        assert rewards[1] == 1  # Business Manager wins
        assert rewards[0] == -1  # Sally's Agent loses
    
    def test_judge_decision_sally_agent_wins(self):
        """Test judge decision parsing when Sally's Agent wins."""
        self.env.reset(num_players=3, seed=42)
        
        # Complete negotiation
        self.env.step("[Propose] 42000")
        self.env.step("[Accept]")
        
        # Judge makes decision
        judge_decision = "[winner] Sally's Agent\n[reason] Sally's Agent negotiated a great deal."
        done, info = self.env.step(judge_decision)
        
        assert done
        rewards, game_info = self.env.close()
        assert rewards[0] == 1  # Sally's Agent wins
        assert rewards[1] == -1  # Business Manager loses
    
    def test_judge_decision_draw(self):
        """Test judge decision parsing for draw."""
        self.env.reset(num_players=3, seed=42)
        
        # Complete negotiation
        self.env.step("[Propose] 30000")
        self.env.step("[Accept]")
        
        # Judge makes decision
        judge_decision = "[winner] Draw\n[reason] Both parties achieved reasonable outcomes."
        done, info = self.env.step(judge_decision)
        
        assert done
        rewards, game_info = self.env.close()
        assert rewards[0] == 0  # Draw
        assert rewards[1] == 0  # Draw
        assert rewards[2] == 0  # Judge also gets 0 in draw
    
    def test_max_rounds_reached(self):
        """Test game ending when max rounds reached."""
        env = SallySopranoEnv(max_rounds=2)  # Very short game - 2 negotiation rounds
        env.reset(num_players=3, seed=42)
        
        # Make moves until max rounds
        env.step("Let's negotiate.")  # Player 0 - Round 1
        done, info = env.step("I agree.")  # Player 1 - Round 2, should end with automatic draw
        
        # Should end game with automatic draw (no deal reached)
        assert done
        assert env.state.game_state["negotiation_complete"] is True
    
    def test_proposal_history_tracking(self):
        """Test that proposal history is tracked correctly."""
        self.env.reset(num_players=3, seed=42)
        
        # Make multiple proposals
        self.env.step("[Propose] 25000")
        self.env.step("[Propose] 35000")
        
        history = self.env.state.game_state["proposal_history"]
        assert len(history) == 2
        assert history[0]["amount"] == 25000
        assert history[0]["proposer"] == 0
        assert history[1]["amount"] == 35000
        assert history[1]["proposer"] == 1
    
    def test_pattern_matching(self):
        """Test regex pattern matching for actions."""
        self.env.reset(num_players=3, seed=42)
        
        # Test various proposal formats
        test_cases = [
            "[Propose] 30000",
            "[propose] 25000",
            "[PROPOSE] 40000",
            "Some text [Propose] 35000 more text"
        ]
        
        for action in test_cases:
            match = self.env.propose_pattern.search(action)
            assert match is not None
            assert match.group(1).isdigit()
        
        # Test accept pattern
        accept_cases = ["[Accept]", "[accept]", "[ACCEPT]", "Text [Accept] more text"]
        for action in accept_cases:
            match = self.env.accept_pattern.search(action)
            assert match is not None
    
    def test_round_counter_in_actions(self):
        """Test that round counter appears in player actions."""
        self.env.reset(num_players=3, seed=42)
        
        # Make some actions and check observations
        self.env.step("Hello there")
        
        # Get the latest observation to check for round counter
        player_id, obs = self.env.get_observation()
        
        # Check that some observation contains round counter format
        found_round_counter = False
        for sender, message, obs_type in obs:
            if "[Round 1/10]" in message:
                found_round_counter = True
                break
        
        assert found_round_counter, "Round counter not found in observations"