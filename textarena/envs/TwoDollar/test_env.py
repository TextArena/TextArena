"""
Comprehensive test suite for Two Dollar Negotiation Game Environment
"""

import pytest
import textarena as ta
from textarena.envs.TwoDollar.env import TwoDollarEnv


class TestTwoDollarValidation:
    """Test action validation logic"""
    
    @pytest.fixture
    def fresh_env(self):
        """Create a fresh environment for each test"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        return env
    
    @pytest.fixture
    def env_with_proposal(self):
        """Create environment with an active proposal"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        # Player 0 makes a proposal
        env.step("I think this is fair [Propose] $1.00")
        return env
    
    def test_accept_without_proposal_invalid(self, fresh_env):
        """Test that accepting without a proposal is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I want to accept [Accept]")
        
        # Should be invalid move, game continues
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_reject_without_proposal_invalid(self, fresh_env):
        """Test that rejecting without a proposal is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I want to reject [Reject]")
        
        # Should be invalid move, game continues
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_accept_own_proposal_invalid(self, fresh_env):
        """Test that players cannot accept their own proposals"""
        env = fresh_env
        # Player 0 makes proposal
        env.step("I propose [Propose] $1.50")
        # Player 1 rejects
        env.step("I reject [Reject]")
        # Now Player 0 tries to accept their own (still active) proposal
        initial_error_count = env.state.error_count
        done, step_info = env.step("I accept my own proposal [Accept]")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_reject_own_proposal_invalid(self, fresh_env):
        """Test that players cannot reject their own proposals"""
        env = fresh_env
        # Player 0 makes proposal
        env.step("I propose [Propose] $1.50")
        # Player 1 rejects
        env.step("I reject [Reject]")
        # Now Player 0 tries to reject their own (still active) proposal
        initial_error_count = env.state.error_count
        done, step_info = env.step("I reject my own proposal [Reject]")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_no_bracketed_action_invalid(self, fresh_env):
        """Test that actions without brackets are invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I want to propose one dollar")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_free_text_before_action_valid(self, fresh_env):
        """Test that free text before bracketed actions is allowed"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I think this is a fair split because we both contributed equally to this negotiation [Propose] $1.00")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal["amount"] == 1.00
    
    def test_other_brackets_ignored(self, fresh_env):
        """Test that other brackets like [Kill], [Steal] are ignored but our actions work"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I will [Kill] you if you don't accept this [Propose] $1.75")
        
        # Should be valid - other brackets ignored, our action processed
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal["amount"] == 1.75
    
    def test_multiple_actions_invalid(self, env_with_proposal):
        """Test that multiple actions in same turn are invalid"""
        env = env_with_proposal
        initial_error_count = env.state.error_count
        done, step_info = env.step("I accept [Accept] but also [Reject] this proposal")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_multiple_actions_propose_accept_invalid(self, fresh_env):
        """Test that proposing and accepting in same turn is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $1.00 and [Accept] it")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_negative_amount_invalid(self, fresh_env):
        """Test that negative amounts are invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $-0.50")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_amount_over_limit_invalid(self, fresh_env):
        """Test that amounts over $2.00 are invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $3.00")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_propose_zero_valid(self, fresh_env):
        """Test that proposing $0.00 is valid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $0.00")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal["amount"] == 0.00
    
    def test_propose_exact_limit_valid(self, fresh_env):
        """Test that proposing exactly $2.00 is valid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $2.00")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal["amount"] == 2.00
    
    def test_decimal_amounts_valid(self, fresh_env):
        """Test that decimal amounts work correctly"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $1.25")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal["amount"] == 1.25
    
    def test_non_decimal_amounts_valid(self, fresh_env):
        """Test that whole dollar amounts work correctly"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] $1")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal["amount"] == 1.00
    
    def test_missing_dollar_sign_invalid(self, fresh_env):
        """Test that missing dollar sign is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] 1.50")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_dollar_sign_after_number_invalid(self, fresh_env):
        """Test that dollar sign after number is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] 1.50$")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count


class TestTwoDollarGameFlow:
    """Test game flow and state management"""
    
    @pytest.fixture
    def fresh_env(self):
        """Create a fresh environment for each test"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        return env
    
    def test_turn_alternation(self, fresh_env):
        """Test that turns alternate between players correctly"""
        env = fresh_env
        
        # Player 0 starts
        assert env.state.current_player_id == 0
        
        # Player 0 makes proposal
        env.step("I propose [Propose] $1.00")
        assert env.state.current_player_id == 1
        
        # Player 1 rejects
        env.step("I reject [Reject]")
        assert env.state.current_player_id == 0
        
        # Player 0 makes new proposal
        env.step("I propose [Propose] $1.25")
        assert env.state.current_player_id == 1
    
    def test_round_counter_increments(self, fresh_env):
        """Test that round counter increments properly"""
        env = fresh_env
        
        initial_turn = env.state.turn
        
        # Player 0 acts
        env.step("I propose [Propose] $1.00")
        assert env.state.turn == initial_turn + 1
        
        # Player 1 acts
        env.step("I reject [Reject]")
        assert env.state.turn == initial_turn + 2
    
    def test_deal_acceptance_ends_game(self, fresh_env):
        """Test that accepting a deal ends the game"""
        env = fresh_env
        
        # Player 0 proposes
        done, _ = env.step("I propose [Propose] $1.00")
        assert not done
        
        # Player 1 accepts
        done, _ = env.step("I accept [Accept]")
        assert done
        
        # Check final amounts
        assert env.final_amounts[0] == 1.00
        assert env.final_amounts[1] == 1.00
    
    def test_max_rounds_ends_game(self, fresh_env):
        """Test that reaching max rounds ends the game"""
        env = fresh_env
        env.max_rounds = 3  # Set low for testing
        
        # Play until max rounds
        env.step("I propose [Propose] $1.00")  # Round 1
        env.step("I reject [Reject]")          # Round 2
        done, _ = env.step("I propose [Propose] $1.50")  # Round 3
        
        # Should end due to max rounds
        assert done
        assert env.final_amounts[0] == 0.0
        assert env.final_amounts[1] == 0.0
    
    def test_final_rewards_scaling(self, fresh_env):
        """Test that final rewards are scaled correctly (0-100)"""
        env = fresh_env
        
        # Make a deal
        env.step("I propose [Propose] $1.50")
        env.step("I accept [Accept]")
        
        # Check rewards are scaled to 0-100
        assert env.state.rewards[0] == 75  # $1.50 / $2.00 * 100
        assert env.state.rewards[1] == 25  # $0.50 / $2.00 * 100


class TestTwoDollarRoles:
    """Test role-specific behaviors"""
    
    def test_say_little_role_word_limit(self):
        """Test that say_little role enforces word limit"""
        env = TwoDollarEnv(player_roles=["say_little", "dependent"])
        env.reset(num_players=2, seed=42)
        
        # Try to exceed word limit (say_little allows max 15 words)
        long_message = "I really think that this proposal is very fair and reasonable and should be accepted by you immediately"
        initial_error_count = env.state.error_count
        done, _ = env.step(f"{long_message} [Propose] $1.00")
        
        # Should be invalid due to word limit
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_say_little_role_within_limit(self):
        """Test that say_little role allows messages within word limit"""
        env = TwoDollarEnv(player_roles=["say_little", "dependent"])
        env.reset(num_players=2, seed=42)
        
        # Short message within limit
        initial_error_count = env.state.error_count
        done, _ = env.step("Fair split [Propose] $1.00")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
    
    def test_high_tension_role_concession_limit(self):
        """Test that high_tension role enforces concession limits"""
        env = TwoDollarEnv(player_roles=["high_tension", "dependent"])
        env.reset(num_players=2, seed=42)
        
        # First proposal
        env.step("I propose [Propose] $1.50")
        env.step("I reject [Reject]")
        
        # Try to make large concession (high_tension allows max $0.01)
        initial_error_count = env.state.error_count
        done, _ = env.step("I propose [Propose] $1.00")  # $0.50 concession
        
        # Should be invalid due to concession limit
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_threshold_role_enforcement(self):
        """Test that threshold roles are enforced at game end"""
        env = TwoDollarEnv(player_roles=["50_cents", "dependent"])
        env.reset(num_players=2, seed=42)
        
        # Make deal that violates 50_cents threshold
        env.step("I propose [Propose] $0.25")  # Player 0 gets $0.25 (below $0.50 threshold)
        env.step("I accept [Accept]")
        
        # Player 0 should get $0 due to threshold violation
        assert env.final_amounts[0] == 0.0
        assert env.final_amounts[1] == 1.75  # Player 1 gets $2.00 - $0.25 = $1.75


class TestTwoDollarIntegration:
    """Test complete game scenarios"""
    
    def test_successful_negotiation(self):
        """Test a complete successful negotiation"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        
        # Player 0 proposes
        done, _ = env.step("I think we should split evenly [Propose] $1.00")
        assert not done
        assert env.current_proposal["amount"] == 1.00
        
        # Player 1 accepts
        done, _ = env.step("That sounds fair to me [Accept]")
        assert done
        
        # Check final state
        assert env.final_amounts[0] == 1.00
        assert env.final_amounts[1] == 1.00
        assert env.state.rewards[0] == 50
        assert env.state.rewards[1] == 50
    
    def test_failed_negotiation(self):
        """Test a negotiation that fails due to max rounds"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        env.max_rounds = 4  # Set low for testing
        
        # Stubborn negotiation
        env.step("I propose [Propose] $1.75")  # Round 1
        env.step("Too greedy [Reject]")        # Round 2
        env.step("I propose [Propose] $1.70")  # Round 3
        done, _ = env.step("Still too much [Reject]")  # Round 4
        
        # Should end with no deal
        assert done
        assert env.final_amounts[0] == 0.0
        assert env.final_amounts[1] == 0.0
    
    def test_error_recovery(self):
        """Test that players can recover from invalid moves"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        
        # Player 0 makes invalid move
        initial_error_count = env.state.error_count
        env.step("Invalid action without brackets")
        assert env.state.error_count > initial_error_count
        
        # Player 0 recovers with valid move
        done, _ = env.step("Let me try again [Propose] $1.00")
        assert not done
        # After valid move, player should be able to continue playing
        assert env.current_proposal["amount"] == 1.00
    
    def test_three_strikes_elimination(self):
        """Test that exceeding error allowance eliminates a player"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        
        # Player 0 makes invalid moves up to the error allowance (3) + 1
        env.step("Invalid move 1")
        env.step("Invalid move 2")
        env.step("Invalid move 3")
        done, _ = env.step("Invalid move 4")  # This should exceed the allowance
        
        # Should end game with player 0 losing
        assert done
        assert env.state.rewards[0] < env.state.rewards[1]


class TestTwoDollarEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_boundary_values(self):
        """Test exact boundary values"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        
        # Test $0.00
        done, _ = env.step("I propose [Propose] $0.00")
        assert not done
        assert env.current_proposal["amount"] == 0.00
        
        env.step("I reject [Reject]")
        
        # Test $2.00
        done, _ = env.step("I propose [Propose] $2.00")
        assert not done
        assert env.current_proposal["amount"] == 2.00
        
        env.step("I reject [Reject]")
        
        # Test $0.01
        done, _ = env.step("I propose [Propose] $0.01")
        assert not done
        assert env.current_proposal["amount"] == 0.01
    
    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        
        # Test with extra spaces
        done, _ = env.step("   I propose   [Propose]   $1.50   ")
        assert not done
        assert env.current_proposal["amount"] == 1.50
    
    def test_case_sensitivity(self):
        """Test case sensitivity of actions"""
        env = TwoDollarEnv(player_roles=["dependent", "public_figure"])
        env.reset(num_players=2, seed=42)
        
        # Make proposal first
        env.step("I propose [Propose] $1.00")
        
        # Test different cases - should all be invalid (case sensitive)
        initial_error_count = env.state.error_count
        done, _ = env.step("I accept [ACCEPT]")
        assert env.state.error_count > initial_error_count
        
        # Test another case
        initial_error_count = env.state.error_count
        done, _ = env.step("I accept [accept]")
        assert env.state.error_count > initial_error_count
    
    def test_role_assignment_random(self):
        """Test random role assignment"""
        env = TwoDollarEnv()  # No specific roles
        env.reset(num_players=2, seed=42)
        
        # Should have assigned two different roles
        assert len(env.player_roles) == 2
        assert 0 in env.player_roles
        assert 1 in env.player_roles
        assert env.player_roles[0] != env.player_roles[1]
    
    def test_role_assignment_specific(self):
        """Test specific role assignment"""
        env = TwoDollarEnv(player_roles=["dependent", "50_cents"])
        env.reset(num_players=2, seed=42)
        
        # Should have assigned specific roles
        assert env.player_roles[0]["name"] == "dependent"
        assert env.player_roles[1]["name"] == "50_cents"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
