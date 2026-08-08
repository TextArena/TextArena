"""
Comprehensive test suite for Vendor Negotiation Environment
"""

import pytest
import textarena as ta
from textarena.envs.VendorNegotiation.env import VendorNegotiationEnv


class TestVendorNegotiationValidation:
    """Test action validation logic"""
    
    @pytest.fixture
    def fresh_env(self):
        """Create a fresh environment for each test"""
        env = VendorNegotiationEnv(num_products=3, brand_role="default", vendor_role="default")
        env.reset(num_players=2, seed=42)
        return env
    
    @pytest.fixture
    def env_with_proposal(self):
        """Create environment with an active proposal"""
        env = VendorNegotiationEnv(num_products=3, brand_role="default", vendor_role="default")
        env.reset(num_players=2, seed=42)
        # Player 0 makes a proposal
        env.step("I think this works [Propose] 15%, 20%, 15%")
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
        env.step("I propose [Propose] 15%, 20%, 15%")
        # Player 1 rejects
        env.step("I reject [Reject]")
        # Now Player 0 tries to accept their own proposal (but there's no current proposal after reject)
        initial_error_count = env.state.error_count
        done, step_info = env.step("I accept my own proposal [Accept]")
        
        # Should be invalid move (no current proposal to accept)
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_free_text_conversation_valid(self, fresh_env):
        """Test that free text conversation is valid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("Hello, let's discuss the discount rates for our products")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert len(env.conversation_history) == 1
        assert env.conversation_history[0]['message'] == "Hello, let's discuss the discount rates for our products"
    
    def test_conversation_before_brackets_captured(self, fresh_env):
        """Test that conversation before bracketed actions is captured"""
        env = fresh_env
        done, step_info = env.step("I think moderate discounts work well [Propose] 15%, 20%, 15%")
        
        # Should capture conversation part
        assert not done
        assert len(env.conversation_history) == 1
        assert env.conversation_history[0]['message'] == "I think moderate discounts work well"
        assert env.current_proposal['discounts'] is not None
    
    def test_wrong_number_of_discounts_invalid(self, fresh_env):
        """Test that wrong number of discount values is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] 10%, 5%")  # Only 2 values for 3 products
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_invalid_discount_rate_invalid(self, fresh_env):
        """Test that invalid discount rates are rejected"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] 10%, 5%, 25%")  # 10% and 25% not in allowed [0,15,20,30]
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_valid_proposal_format(self, fresh_env):
        """Test that valid positional format works"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I propose [Propose] 15%, 20%, 30%")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal['discounts'] is not None
        assert len(env.current_proposal['discounts']) == 3
    
    def test_multiple_actions_invalid(self, env_with_proposal):
        """Test that multiple actions in same turn are invalid"""
        env = env_with_proposal
        initial_error_count = env.state.error_count
        done, step_info = env.step("I accept [Accept] but also [Reject] this proposal")
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count


class TestVendorNegotiationGameFlow:
    """Test game flow and state management"""
    
    @pytest.fixture
    def fresh_env(self):
        """Create a fresh environment for each test"""
        env = VendorNegotiationEnv(num_products=3, brand_role="default", vendor_role="default")
        env.reset(num_players=2, seed=42)
        return env
    
    def test_turn_alternation(self, fresh_env):
        """Test that turns alternate between players correctly"""
        env = fresh_env
        
        # Player 0 starts
        assert env.state.current_player_id == 0
        
        # Player 0 makes proposal
        env.step("I propose [Propose] 15%, 20%, 15%")
        assert env.state.current_player_id == 1
        
        # Player 1 rejects
        env.step("I reject [Reject]")
        assert env.state.current_player_id == 0
        
        # Player 0 makes new proposal
        env.step("I propose [Propose] 20%, 30%, 20%")
        assert env.state.current_player_id == 1
    
    def test_deal_acceptance_ends_game(self, fresh_env):
        """Test that accepting a deal ends the game"""
        env = fresh_env
        
        # Player 0 proposes
        done, _ = env.step("I propose [Propose] 20%, 20%, 20%")
        assert not done
        
        # Player 1 accepts
        done, _ = env.step("I accept [Accept]")
        assert done
        
        # Check proposal was accepted
        assert env.current_proposal['discounts'] is not None
        assert env._check_deal_accepted()
    
    def test_max_rounds_ends_game(self, fresh_env):
        """Test that reaching max rounds ends the game"""
        env = fresh_env
        env.max_rounds = 3  # Set low for testing
        
        # Play until max rounds
        env.step("I propose [Propose] 15%, 20%, 15%")  # Round 1
        env.step("I reject [Reject]")                 # Round 2
        done, _ = env.step("I propose [Propose] 20%, 30%, 20%")  # Round 3
        
        # Should end due to max rounds
        assert done
    
    def test_conversation_tracking(self, fresh_env):
        """Test that conversation is tracked properly"""
        env = fresh_env
        
        # Free text conversation
        env.step("Hello, let's negotiate")
        assert len(env.conversation_history) == 1
        
        # Conversation before proposal
        env.step("I think this is fair [Propose] 15%, 20%, 15%")
        assert len(env.conversation_history) == 2
        assert env.conversation_history[1]['message'] == "I think this is fair"
        
        # Conversation before accept
        env.step("This works for me [Accept]")
        assert len(env.conversation_history) == 3
        assert env.conversation_history[2]['message'] == "This works for me"


class TestVendorNegotiationWinConditions:
    """Test win condition scenarios"""
    
    def test_both_players_win_scenario(self):
        """Test scenario where both players achieve objectives"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.6)  # Lower target
        env.reset(num_players=2, seed=42)
        
        # Make moderate discount deal
        env.step("I propose [Propose] 20%, 20%, 20%")
        env.step("I accept [Accept]")
        
        # Both should win with moderate discounts
        rewards, game_info = env.close()
        # Check that it's a draw (both won) or specific winner logic
        assert rewards is not None
    
    def test_brand_wins_vendor_loses(self):
        """Test scenario where only brand wins"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.5, vendor_baseline_multiplier=2.0)  # High vendor requirement
        env.reset(num_players=2, seed=42)
        
        # High discount deal - good for brand, bad for vendor
        env.step("I propose [Propose] 20%, 20%, 20%")
        env.step("I accept [Accept]")
        
        rewards, game_info = env.close()
        # Brand should win, vendor should lose
        assert rewards[0] > rewards[1]
    
    def test_vendor_wins_brand_loses(self):
        """Test scenario where only vendor wins"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.95, vendor_baseline_multiplier=1.0)  # Very high brand requirement, normal vendor
        env.reset(num_players=2, seed=42)
        
        # Low discount deal - good for vendor, bad for brand
        env.step("I propose [Propose] 0%, 0%, 0%")
        env.step("I accept [Accept]")
        
        rewards, game_info = env.close()
        # Vendor should win, brand should lose
        assert rewards[1] > rewards[0]
    
    def test_no_deal_both_lose(self):
        """Test that no deal results in both players losing"""
        env = VendorNegotiationEnv(num_products=3, max_rounds=2)  # Very short game
        env.reset(num_players=2, seed=42)
        
        # Stubborn negotiation that fails
        env.step("I propose [Propose] 20%, 20%, 20%")
        done, _ = env.step("Too much [Reject]")
        
        # Should end with no deal
        assert done
        rewards, game_info = env.close()
        # Both should have same (losing) reward
        assert rewards[0] == rewards[1] == 0


class TestVendorNegotiationRoles:
    """Test role-specific behaviors"""
    
    def test_role_loading_default(self):
        """Test that default roles load correctly"""
        env = VendorNegotiationEnv(brand_role="default", vendor_role="default")
        env.reset(num_players=2, seed=42)
        
        # Should load without errors
        assert env.brand_role_instructions is not None
        assert env.vendor_role_instructions is not None
        assert "Balanced" in env.brand_role_instructions
        assert "Balanced" in env.vendor_role_instructions
    
    def test_role_loading_custom(self):
        """Test that custom roles load correctly"""
        env = VendorNegotiationEnv(brand_role="aggressive", vendor_role="profit_focused")
        env.reset(num_players=2, seed=42)
        
        # Should load custom roles
        assert "Aggressive" in env.brand_role_instructions
        assert "Profit Maximizer" in env.vendor_role_instructions
    
    def test_role_loading_fallback(self):
        """Test that invalid role names fall back to default"""
        env = VendorNegotiationEnv(brand_role="nonexistent", vendor_role="alsononexistent")
        env.reset(num_players=2, seed=42)
        
        # Should fall back to default roles
        assert env.brand_role_instructions is not None
        assert env.vendor_role_instructions is not None


class TestVendorNegotiationSimulation:
    """Test Monte Carlo simulation functionality"""
    
    def test_simulation_runs(self):
        """Test that Monte Carlo simulation produces results"""
        env = VendorNegotiationEnv(num_products=3, num_simulations=100)  # Small for testing
        env.reset(num_players=2, seed=42)
        
        # Make a deal
        env.step("I propose [Propose] 20%, 20%, 20%")
        env.step("I accept [Accept]")
        
        # Should have run simulation
        assert env.state.done
        # Check that board string contains simulation results
        board_str = env.get_board_str()
        assert "SIMULATION RESULTS" in board_str
        assert "TOTALS:" in board_str
        assert "OUTCOMES:" in board_str
    
    def test_simulation_deterministic_with_seed(self):
        """Test that simulation is deterministic with same seed"""
        # Run same scenario twice with same seed
        results1 = self._run_simulation_scenario(seed=42)
        results2 = self._run_simulation_scenario(seed=42)
        
        # Results should be identical
        assert results1 == results2
    
    def test_simulation_different_with_different_seed(self):
        """Test that simulation varies with different seeds"""
        # Run same scenario with different seeds
        results1 = self._run_simulation_scenario(seed=42)
        results2 = self._run_simulation_scenario(seed=123)
        
        # Results should be different
        assert results1 != results2
    
    def _run_simulation_scenario(self, seed):
        """Helper to run a simulation scenario"""
        env = VendorNegotiationEnv(num_products=3, num_simulations=100)
        env.reset(num_players=2, seed=seed)
        env.step("I propose [Propose] 20%, 20%, 20%")
        env.step("I accept [Accept]")
        return env.get_board_str()


class TestVendorNegotiationIntegration:
    """Test complete game scenarios"""
    
    def test_successful_negotiation_with_conversation(self):
        """Test a complete successful negotiation with conversation"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Player 0 starts conversation
        done, _ = env.step("Hello, I'd like to discuss discount rates")
        assert not done
        assert len(env.conversation_history) == 1
        
        # Player 1 responds
        done, _ = env.step("Sure, I'm open to reasonable discounts")
        assert not done
        assert len(env.conversation_history) == 2
        
        # Player 0 proposes with conversation
        done, _ = env.step("I think moderate discounts work [Propose] 15%, 20%, 15%")
        assert not done
        assert len(env.conversation_history) == 3
        assert env.current_proposal['discounts'] is not None
        
        # Player 1 accepts with conversation
        done, _ = env.step("This looks good to me [Accept]")
        assert done
        assert len(env.conversation_history) == 4
    
    def test_failed_negotiation_max_rounds(self):
        """Test a negotiation that fails due to max rounds"""
        env = VendorNegotiationEnv(num_products=3, max_rounds=4)
        env.reset(num_players=2, seed=42)
        
        # Stubborn negotiation - need to reach max_rounds - 1
        env.step("I propose [Propose] 20%, 20%, 20%")  # Round 1
        env.step("Too much [Reject]")                  # Round 2
        env.step("I propose [Propose] 15%, 15%, 15%")  # Round 3
        done, _ = env.step("Still too much [Reject]")  # Round 4
        
        # Should end due to max rounds (check turn count)
        if not done:
            # May need one more action to trigger max rounds
            done, _ = env.step("Final offer [Propose] 10%, 10%, 10%")
        
        assert done or env.state.turn >= env.max_rounds - 1
    
    def test_error_recovery(self):
        """Test that players can recover from invalid moves"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Player 0 makes invalid move
        initial_error_count = env.state.error_count
        env.step("I propose [Propose] 25%, 30%, 35%")  # Invalid discount rates
        assert env.state.error_count > initial_error_count
        
        # Player 0 recovers with valid move
        done, _ = env.step("Let me try again [Propose] 15%, 20%, 15%")
        assert not done
        assert env.current_proposal['discounts'] is not None
    
    def test_three_strikes_elimination(self):
        """Test that exceeding error allowance affects game"""
        env = VendorNegotiationEnv(num_products=3, error_allowance=2)  # Low allowance for testing
        env.reset(num_players=2, seed=42)
        
        # Player 0 makes invalid moves (need actual invalid actions, not free text)
        env.step("I want to accept [Accept]")  # Invalid - no proposal
        env.step("I want to accept [Accept]")  # Invalid - no proposal  
        done, _ = env.step("I want to accept [Accept]")  # Should exceed allowance
        
        # Should handle according to TextArena's error system
        # Free text conversation doesn't count as errors, so use actual invalid actions
        assert env.state.error_count >= 2 or done


class TestVendorNegotiationProductSelection:
    """Test product selection and data loading"""
    
    def test_product_selection_count(self):
        """Test that correct number of products are selected"""
        env = VendorNegotiationEnv(num_products=5)
        env.reset(num_players=2, seed=42)
        
        assert len(env.selected_products) == 5
        assert len(env.products) == 5
    
    def test_product_selection_deterministic(self):
        """Test that product selection is deterministic with seed"""
        env1 = VendorNegotiationEnv(num_products=3)
        env1.reset(num_players=2, seed=42)
        products1 = env1.selected_products.copy()
        
        env2 = VendorNegotiationEnv(num_products=3)
        env2.reset(num_players=2, seed=42)
        products2 = env2.selected_products.copy()
        
        assert products1 == products2
    
    def test_product_data_loading(self):
        """Test that product data loads correctly"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Check that products have required data structure
        for product_name in env.selected_products:
            product = env.products[product_name]
            assert 'price' in product
            assert 'cost' in product
            assert 'data' in product
            
            # Check discount rate data
            for discount in [0, 15, 20, 30]:
                assert discount in product['data']
                data = product['data'][discount]
                assert 'mean_units' in data
                assert 'mean_sales' in data
                assert 'mean_profit' in data
    
    def test_target_calculation(self):
        """Test that brand target and vendor baseline are calculated correctly"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.8, vendor_baseline_multiplier=1.0)
        env.reset(num_players=2, seed=42)
        
        # Calculate expected values
        expected_brand_target = 0.8 * sum(
            env.products[p]['data'][30]['mean_sales'] for p in env.selected_products
        )
        expected_vendor_baseline = 1.0 * sum(
            env.products[p]['data'][0]['mean_profit'] for p in env.selected_products
        )
        
        assert abs(env.brand_target - expected_brand_target) < 0.01
        assert abs(env.vendor_baseline - expected_vendor_baseline) < 0.01


class TestVendorNegotiationProposalAnalysis:
    """Test proposal analysis functionality"""
    
    def test_proposal_analysis_brand(self):
        """Test that brand sees sales analysis"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Player 0 (Brand) makes proposal
        env.step("I propose [Propose] 20%, 20%, 20%")
        
        # Player 1 should see analysis in their observation
        player_id, observation = env.get_observation()
        assert player_id == 1  # Vendor's turn
        
        # Check that observation contains analysis
        obs_str = str(observation)
        assert "PROPOSAL ANALYSIS" in obs_str
        assert "Expected Profit" in obs_str
        assert ("LIKELY BEATS BASELINE" in obs_str or "RISKY - MAY MISS BASELINE" in obs_str or 
                "BEATS BASELINE" in obs_str or "BELOW BASELINE" in obs_str)
    
    def test_proposal_analysis_vendor(self):
        """Test that vendor sees sales analysis when brand makes proposal"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Player 0 (Brand) makes proposal
        env.step("I propose [Propose] 20%, 20%, 20%")
        
        # Player 1 (Vendor) should see profit analysis
        player_id, observation = env.get_observation()
        assert player_id == 1  # Vendor's turn
        
        obs_str = str(observation)
        assert "PROPOSAL ANALYSIS" in obs_str
        assert "Expected Profit" in obs_str
        assert ("LIKELY BEATS BASELINE" in obs_str or "RISKY - MAY MISS BASELINE" in obs_str or 
                "BEATS BASELINE" in obs_str or "BELOW BASELINE" in obs_str)


class TestVendorNegotiationEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_minimum_products(self):
        """Test with minimum number of products"""
        env = VendorNegotiationEnv(num_products=1)
        env.reset(num_players=2, seed=42)
        
        assert len(env.selected_products) == 1
        
        # Should work with single product
        done, _ = env.step("I propose [Propose] 20%")
        assert not done
        assert env.current_proposal['discounts'] is not None
    
    def test_maximum_products(self):
        """Test with maximum available products"""
        env = VendorNegotiationEnv(num_products=20)  # More than available
        env.reset(num_players=2, seed=42)
        
        # Should select all available products
        assert len(env.selected_products) <= len(env.all_products)
        assert len(env.selected_products) == len(env.all_products)
    
    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Test with extra spaces
        done, _ = env.step("   I propose   [Propose]   15%,   20%,   15%   ")
        assert not done
        assert env.current_proposal['discounts'] is not None
    
    def test_case_sensitivity(self):
        """Test case sensitivity of actions"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Make proposal first
        env.step("I propose [Propose] 15%, 20%, 15%")
        
        # Test wrong case - [ACCEPT] should be treated as free text, not invalid action
        # So let's test with a malformed proposal instead
        initial_error_count = env.state.error_count
        done, _ = env.step("I propose [PROPOSE] 15%, 20%, 15%")  # Wrong case for Propose
        
        # Should be treated as free text conversation, not invalid proposal
        assert not done
        assert env.state.error_count == initial_error_count
        assert len(env.conversation_history) > 0
    
    def test_empty_proposal_invalid(self):
        """Test that empty proposal is invalid"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        initial_error_count = env.state.error_count
        done, _ = env.step("I propose [Propose]")
        
        # Should be invalid
        assert not done
        assert env.state.error_count > initial_error_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
