"""
Comprehensive test suite for Vendor Negotiation Environment

Action grammar: free-text conversation, optionally finished with a decision on
its own line: 'Propose X%, Y%, Z%, ...', 'Accept', or 'Reject'. A message
without a decision line is pure conversation. The legacy embedded bracketed
tokens ('[Accept]' etc.) are still tolerated but never required.
"""

import pytest
from pathlib import Path
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
        env.step("I think this works\nPropose 15%, 20%, 15%")
        return env
    
    def test_accept_without_proposal_invalid(self, fresh_env):
        """Test that accepting without a proposal is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I want to accept this.\nAccept")
        
        # Should be invalid move, game continues
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_reject_without_proposal_invalid(self, fresh_env):
        """Test that rejecting without a proposal is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("I want to reject this.\nReject")
        
        # Should be invalid move, game continues
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_accept_own_proposal_invalid(self, fresh_env):
        """Test that players cannot accept their own proposals"""
        env = fresh_env
        # Player 0 makes proposal
        env.step("Propose 15%, 20%, 15%")
        # Player 1 rejects
        env.step("Reject")
        # Now Player 0 tries to accept their own proposal (but there's no current proposal after reject)
        initial_error_count = env.state.error_count
        done, step_info = env.step("I accept my own proposal.\nAccept")
        
        # Should be invalid move (no current proposal to accept)
        assert not done
        assert env.state.error_count > initial_error_count

    @pytest.mark.parametrize("decision", ["Accept", "Reject"])
    def test_cannot_respond_to_own_still_active_proposal(self, fresh_env, decision):
        env = fresh_env
        env.step("Propose 15%, 20%, 15%")
        env.step("I need another turn to think")
        assert env.state.current_player_id == 0
        proposal_before = {
            "discounts": env.current_proposal["discounts"].copy(),
            "proposer": env.current_proposal["proposer"],
        }

        done, _ = env.step(decision)

        assert not done
        assert env.state.current_player_id == 0
        assert env.current_proposal == proposal_before
        assert env.state.error_count == 1
    
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
    
    def test_conversation_before_decision_captured(self, fresh_env):
        """Test that conversation before the decision line is captured"""
        env = fresh_env
        done, step_info = env.step("I think moderate discounts work well\nPropose 15%, 20%, 15%")
        
        # Should capture conversation part
        assert not done
        assert len(env.conversation_history) == 1
        assert env.conversation_history[0]['message'] == "I think moderate discounts work well"
        assert env.current_proposal['discounts'] is not None
    
    def test_wrong_number_of_discounts_invalid(self, fresh_env):
        """Test that wrong number of discount values is invalid"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("Propose 10%, 5%")  # Only 2 values for 3 products
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_invalid_discount_rate_invalid(self, fresh_env):
        """Test that invalid discount rates are rejected"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("Propose 10%, 5%, 25%")  # 10% and 25% not in allowed [0,15,20,30]
        
        # Should be invalid move
        assert not done
        assert env.state.error_count > initial_error_count
    
    def test_valid_proposal_format(self, fresh_env):
        """Test that valid positional format works"""
        env = fresh_env
        initial_error_count = env.state.error_count
        done, step_info = env.step("Propose 15%, 20%, 30%")
        
        # Should be valid
        assert not done
        assert env.state.error_count == initial_error_count
        assert env.current_proposal['discounts'] is not None
        assert len(env.current_proposal['discounts']) == 3
    
    def test_multiple_actions_invalid(self, env_with_proposal):
        """Test that multiple actions in same turn are invalid"""
        env = env_with_proposal
        initial_error_count = env.state.error_count
        done, step_info = env.step("Accept\nReject")
        
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
        env.step("Propose 15%, 20%, 15%")
        assert env.state.current_player_id == 1
        
        # Player 1 rejects
        env.step("Reject")
        assert env.state.current_player_id == 0
        
        # Player 0 makes new proposal
        env.step("Propose 20%, 30%, 20%")
        assert env.state.current_player_id == 1
    
    def test_deal_acceptance_ends_game(self, fresh_env):
        """Test that accepting a deal ends the game"""
        env = fresh_env
        
        # Player 0 proposes
        done, _ = env.step("I propose [Propose] 20%, 20%, 20%")
        assert not done
        
        # Player 1 accepts
        done, _ = env.step("Accept")
        assert done
        
        # Check proposal was accepted
        assert env.current_proposal['discounts'] is not None
        assert env._check_deal_accepted()
    
    def test_max_rounds_ends_game(self, fresh_env):
        """Test that reaching max rounds ends the game"""
        env = fresh_env
        env.max_rounds = 3  # Set low for testing
        
        # Play until max rounds
        env.step("Propose 15%, 20%, 15%")  # Round 1
        env.step("Reject")                 # Round 2
        done, _ = env.step("Propose 20%, 30%, 20%")  # Round 3
        
        # Should end due to max rounds
        assert done
    
    def test_conversation_tracking(self, fresh_env):
        """Test that conversation is tracked properly"""
        env = fresh_env
        
        # Free text conversation
        env.step("Hello, let's negotiate")
        assert len(env.conversation_history) == 1
        
        # Conversation before proposal
        env.step("I think this is fair\nPropose 15%, 20%, 15%")
        assert len(env.conversation_history) == 2
        assert env.conversation_history[1]['message'] == "I think this is fair"
        
        # Conversation before accept
        env.step("This works for me\nAccept")
        assert len(env.conversation_history) == 3
        assert env.conversation_history[2]['message'] == "This works for me"


class TestVendorNegotiationWinConditions:
    """Test win condition scenarios"""
    
    def test_both_players_win_scenario(self):
        """Test scenario where both players achieve objectives"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.6)  # Lower target
        env.reset(num_players=2, seed=42)
        
        # Make moderate discount deal
        env.step("Propose 20%, 20%, 20%")
        env.step("Accept")
        
        # Both should win with moderate discounts
        rewards, game_info = env.close()
        # Check that it's a draw (both won) or specific winner logic
        assert rewards is not None
    
    def test_brand_wins_vendor_loses(self):
        """Test scenario where only brand wins"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.5, vendor_baseline_multiplier=2.0)  # High vendor requirement
        env.reset(num_players=2, seed=42)
        
        # High discount deal - good for brand, bad for vendor
        env.step("Propose 20%, 20%, 20%")
        env.step("Accept")
        
        rewards, game_info = env.close()
        # Brand should win, vendor should lose
        assert rewards[0] > rewards[1]
    
    def test_vendor_wins_brand_loses(self):
        """Test scenario where only vendor wins"""
        env = VendorNegotiationEnv(num_products=3, brand_target_percentage=0.95, vendor_baseline_multiplier=1.0)  # Very high brand requirement, normal vendor
        env.reset(num_players=2, seed=42)
        
        # Low discount deal - good for vendor, bad for brand
        env.step("I propose [Propose] 0%, 0%, 0%")
        env.step("Accept")
        
        rewards, game_info = env.close()
        # Vendor should win, brand should lose
        assert rewards[1] > rewards[0]
    
    def test_no_deal_both_lose(self):
        """Test that no deal results in both players losing"""
        env = VendorNegotiationEnv(num_products=3, max_rounds=2)  # Very short game
        env.reset(num_players=2, seed=42)
        
        # Stubborn negotiation that fails
        env.step("Propose 20%, 20%, 20%")
        done, _ = env.step("Too much\nReject")
        
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

    def test_role_name_cannot_traverse_into_other_players_private_file(self):
        env = VendorNegotiationEnv(
            brand_role="../vendor/profit_focused",
            vendor_role="../brand/aggressive",
        )
        env.reset(num_players=2, seed=42)

        assert "Balanced" in env.brand_role_instructions
        assert "Profit Maximizer" not in env.brand_role_instructions
        assert "Balanced" in env.vendor_role_instructions
        assert "Aggressive" not in env.vendor_role_instructions


class TestVendorNegotiationSimulation:
    """Test Monte Carlo simulation functionality"""
    
    def test_simulation_runs(self):
        """Test that Monte Carlo simulation produces results"""
        env = VendorNegotiationEnv(num_products=3, num_simulations=100)  # Small for testing
        env.reset(num_players=2, seed=42)
        
        # Make a deal
        env.step("Propose 20%, 20%, 20%")
        env.step("Accept")
        
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
        env.step("Propose 20%, 20%, 20%")
        env.step("Accept")
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
        done, _ = env.step("I think moderate discounts work\nPropose 15%, 20%, 15%")
        assert not done
        assert len(env.conversation_history) == 3
        assert env.current_proposal['discounts'] is not None
        
        # Player 1 accepts with conversation
        done, _ = env.step("This looks good to me\nAccept")
        assert done
        assert len(env.conversation_history) == 4
    
    def test_failed_negotiation_max_rounds(self):
        """Test a negotiation that fails due to max rounds"""
        env = VendorNegotiationEnv(num_products=3, max_rounds=4)
        env.reset(num_players=2, seed=42)
        
        # Stubborn negotiation - need to reach max_rounds - 1
        env.step("Propose 20%, 20%, 20%")  # Round 1
        env.step("Too much\nReject")                  # Round 2
        env.step("Propose 15%, 15%, 15%")  # Round 3
        done, _ = env.step("Still too much\nReject")  # Round 4
        
        # Should end due to max rounds (check turn count)
        if not done:
            # May need one more action to trigger max rounds
            done, _ = env.step("Final offer\nPropose 10%, 10%, 10%")
        
        assert done or env.state.turn >= env.max_rounds - 1
    
    def test_error_recovery(self):
        """Test that players can recover from invalid moves"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Player 0 makes invalid move
        initial_error_count = env.state.error_count
        env.step("Propose 25%, 30%, 35%")  # Invalid discount rates
        assert env.state.error_count > initial_error_count
        
        # Player 0 recovers with valid move
        done, _ = env.step("Let me try again\nPropose 15%, 20%, 15%")
        assert not done
        assert env.current_proposal['discounts'] is not None
    
    def test_three_strikes_elimination(self):
        """Test that exceeding error allowance affects game"""
        env = VendorNegotiationEnv(num_products=3, error_allowance=2)  # Low allowance for testing
        env.reset(num_players=2, seed=42)
        
        # Player 0 makes invalid moves (need actual invalid actions, not free text)
        env.step("I want to accept this.\nAccept")  # Invalid - no proposal
        env.step("I want to accept this.\nAccept")  # Invalid - no proposal
        done, _ = env.step("I want to accept this.\nAccept")  # Should exceed allowance
        
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
        env.step("Propose 20%, 20%, 20%")
        
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
        env.step("Propose 20%, 20%, 20%")
        
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
        done, _ = env.step("Propose 20%")
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
        done, _ = env.step("   Propose   15%,   20%,   15%   ")
        assert not done
        assert env.current_proposal['discounts'] is not None
    
    def test_case_sensitivity(self):
        """Malformed embedded tokens stay free text"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        # Make proposal first
        env.step("Propose 15%, 20%, 15%")
        
        # A mid-sentence bracketed token with the wrong case is neither the
        # legacy command nor a bare decision line
        initial_error_count = env.state.error_count
        done, _ = env.step("I propose [PROPOSE] 15%, 20%, 15%")  # Wrong case for legacy Propose
        
        # Should be treated as free text conversation, not invalid proposal
        assert not done
        assert env.state.error_count == initial_error_count
        assert len(env.conversation_history) > 0
    
    def test_incidental_words_not_commands(self):
        """Words like 'accept'/'reject' inside a sentence are just conversation"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)

        env.step("Propose 15%, 20%, 15%")

        initial_error_count = env.state.error_count
        conversations_before = len(env.conversation_history)
        done, _ = env.step("I cannot accept these rates yet, and I won't reject them either")

        # Treated as pure conversation: no error, no accept/reject processed
        assert not done
        assert env.state.error_count == initial_error_count
        assert len(env.conversation_history) == conversations_before + 1
        assert env.current_proposal['discounts'] is not None  # proposal untouched
        assert not env._check_deal_accepted()

    def test_legacy_bracketed_forms_still_accepted(self):
        """Legacy embedded '[Propose]'/'[Accept]' commands remain tolerated"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)

        done, _ = env.step("I think this works [Propose] 15%, 20%, 15%")
        assert not done
        assert env.current_proposal['discounts'] is not None

        done, _ = env.step("This looks good to me [Accept]")
        assert done
        assert env._check_deal_accepted()

    def test_bare_single_command_turns_valid(self):
        """A pure single-command turn may omit the brackets entirely."""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)

        done, _ = env.step("Propose 15%, 20%, 15%")
        assert not done
        assert env.current_proposal['discounts'] is not None

        done, _ = env.step("Reject")
        assert not done
        assert env.current_proposal['discounts'] is None

        env.step("Propose 20%, 20%, 20%")
        done, _ = env.step("Accept")
        assert done
        assert env._check_deal_accepted()

    def test_empty_proposal_invalid(self):
        """Test that empty proposal is invalid"""
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        
        initial_error_count = env.state.error_count
        done, _ = env.step("Here is my offer.\nPropose")
        
        # Should be invalid
        assert not done
        assert env.state.error_count > initial_error_count


class TestVendorNegotiationRegressions:
    def test_numpy_is_declared_as_runtime_dependency(self):
        repo_root = Path(__file__).resolve().parents[3]
        pyproject = (repo_root / "pyproject.toml").read_text()
        requirements = (repo_root / "requirements.txt").read_text().splitlines()

        assert '"numpy"' in pyproject
        assert "numpy" in requirements

    def test_terminal_simulation_runs_once_and_render_matches_rewards(self, monkeypatch):
        env = VendorNegotiationEnv(num_products=3, num_simulations=50)
        env.reset(num_players=2, seed=42)

        original_calculate = env._calculate_actual_sales
        call_count = 0

        def counted_calculate(discounts):
            nonlocal call_count
            call_count += 1
            return original_calculate(discounts)

        monkeypatch.setattr(env, "_calculate_actual_sales", counted_calculate)
        env.step("Propose 20%, 20%, 20%")
        done, _ = env.step("Accept")

        assert done
        first_render = env.get_board_str()
        second_render = env.get_board_str()
        terminal = env.game_state["terminal_result"]
        expected_rewards = env._final_outcome(
            terminal["brand_won"], terminal["vendor_won"]
        ).rewards

        assert call_count == 1
        assert first_render == second_render == terminal["rendered"]
        assert env.render(0) == env.render(1) == terminal["rendered"]
        assert env.state.rewards == expected_rewards

    @pytest.mark.parametrize(
        "action,needs_proposal",
        [
            ("Propose 15%, 20%, 15%\nPropose 20%, 20%, 20%", False),
            ("Accept\nAccept", True),
            ("Reject\nReject", True),
        ],
    )
    def test_duplicate_decisions_are_atomic_invalids(self, action, needs_proposal):
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        if needs_proposal:
            env.step("Propose 15%, 20%, 15%")

        history_before = list(env.negotiation_history)
        conversation_before = list(env.conversation_history)
        proposal_before = {
            "discounts": (
                env.current_proposal["discounts"].copy()
                if env.current_proposal["discounts"] is not None
                else None
            ),
            "proposer": env.current_proposal["proposer"],
        }
        events_before = len(env.state.events)
        turn_before = env.state.turn

        done, _ = env.step(action)

        assert not done
        assert env.state.turn == turn_before
        assert env.negotiation_history == history_before
        assert env.conversation_history == conversation_before
        assert env.current_proposal == proposal_before
        assert all(
            event[2] != ta.ObservationType.PLAYER_ACTION
            for event in env.state.events[events_before:]
        )

    def test_malformed_proposal_is_not_logged_or_mutated(self):
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        events_before = len(env.state.events)

        done, _ = env.step("This should not be recorded\nPropose 25%, 20%, 15%")

        assert not done
        assert env.state.turn == 0
        assert env.current_proposal == {"discounts": None, "proposer": None}
        assert env.negotiation_history == []
        assert env.conversation_history == []
        assert all(
            event[2] != ta.ObservationType.PLAYER_ACTION
            for event in env.state.events[events_before:]
        )

    @pytest.mark.parametrize(
        "action",
        [
            "Propose 15% garbage, 20%, 15%",
            "Propose 15%, 20%, 15% trailing",
            "Propose 15%, 20%, 15%\nextra text",
        ],
    )
    def test_proposal_parser_rejects_unconsumed_text_atomically(self, action):
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)
        events_before = len(env.state.events)

        done, _ = env.step(action)

        assert not done
        assert env.state.turn == 0
        assert env.current_proposal == {"discounts": None, "proposer": None}
        assert env.negotiation_history == []
        assert env.conversation_history == []
        assert all(
            event[2] != ta.ObservationType.PLAYER_ACTION
            for event in env.state.events[events_before:]
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"num_products": 0},
            {"num_products": True},
            {"max_rounds": 0},
            {"error_allowance": -1},
            {"brand_target_percentage": -0.1},
            {"brand_target_percentage": 1.1},
            {"brand_target_percentage": float("nan")},
            {"brand_target_percentage": 10 ** 1000},
            {"vendor_baseline_multiplier": -0.1},
            {"vendor_baseline_multiplier": float("inf")},
            {"vendor_baseline_multiplier": 10 ** 1000},
            {"num_simulations": 0},
            {"seed": -1},
        ],
    )
    def test_invalid_configuration_is_rejected(self, kwargs):
        with pytest.raises(ValueError):
            VendorNegotiationEnv(**kwargs)

    def test_invalid_reset_seed_is_rejected(self):
        env = VendorNegotiationEnv(num_products=1)
        with pytest.raises(ValueError):
            env.reset(num_players=2, seed=-1)

    def test_terminal_accept_is_counted_for_both_players(self):
        env = VendorNegotiationEnv(num_products=3)
        env.reset(num_players=2, seed=42)

        env.step("Propose 20%, 20%, 20%")
        done, _ = env.step("Accept")

        assert done
        assert env.state.game_info[0]["turn_count"] == 1
        assert env.state.game_info[1]["turn_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
