"""
Vendor Negotiation Environment

A two-player negotiation game where a Brand Specialist (Player 0) negotiates
with a Vendor (Player 1) over discount rates for products in an upcoming sales event.

Both players can win by achieving their respective objectives:
- Brand Specialist: Achieve target sales (% of maximum possible)
- Vendor: Achieve profit above baseline (X times 0% discount scenario)
"""

import os
import re
import random
import csv
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

import textarena as ta
from textarena.envs.VendorNegotiation.renderer import (
    render_product_data_for_brand,
    render_product_data_for_vendor,
    render_current_state,
    render_final_results,
    render_no_deal
)


class VendorNegotiationEnv(ta.Env):
    """
    Two-player vendor negotiation environment.
    
    Player 0: Brand Specialist (wants high sales)
    Player 1: Vendor (wants high profit)
    """
    
    def __init__(self,
                 num_products: int = 5,
                 max_rounds: int = 20,
                 error_allowance: int = 3,
                 brand_target_percentage: float = 0.8,
                 vendor_baseline_multiplier: float = 1.2,
                 num_simulations: int = 1000,
                 brand_role: Optional[str] = None,
                 vendor_role: Optional[str] = None,
                 product_list_path: Optional[str] = None,
                 seed: Optional[int] = None):
        """
        Initialize the Vendor Negotiation environment.
        
        Args:
            num_products: Number of products to negotiate (default: 5)
            max_rounds: Maximum negotiation rounds (default: 20)
            error_allowance: Invalid moves allowed before penalty (default: 3)
            brand_target_percentage: Brand's target as % of max sales (default: 0.95)
            vendor_baseline_multiplier: Vendor must beat this × baseline (default: 1.5)
            num_simulations: Monte Carlo simulation runs (default: 1000)
            brand_role: Role file name for Player 0 (default: "default")
            vendor_role: Role file name for Player 1 (default: "default")
            product_list_path: Path to product CSV file (default: "data/product_list.csv")
            seed: Random seed for reproducibility
        """
        super().__init__()
        
        self.num_products = num_products
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance
        self.brand_target_percentage = brand_target_percentage
        self.vendor_baseline_multiplier = vendor_baseline_multiplier
        self.num_simulations = num_simulations
        self.brand_role_name = brand_role or "default"
        self.vendor_role_name = vendor_role or "default"
        self.product_list_path = product_list_path or "data/product_list.csv"
        self.seed = seed
        
        # Load product data and roles
        self.all_products = self._load_product_data()
        
        # Always infer allowed discounts from product data
        self.allowed_discounts = self._infer_allowed_discounts()
        self.brand_role_instructions = self._load_role_instructions("brand", self.brand_role_name)
        self.vendor_role_instructions = self._load_role_instructions("vendor", self.vendor_role_name)
        
        # Game state (initialized in reset)
        self.selected_products = []
        self.products = {}
        self.current_proposal = {}
        self.negotiation_history = []
        self.brand_target = 0.0
        self.vendor_baseline = 0.0

    def _load_product_data(self) -> Dict:
        """Load product data from CSV in long format (no pandas)."""
        if os.path.isabs(self.product_list_path):
            csv_path = self.product_list_path
        else:
            csv_path = os.path.join(os.path.dirname(__file__), self.product_list_path)

        products = defaultdict(lambda: {"data": {}})

        with open(csv_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                product_name = row["product"]

                # Convert discount rate, keeping whole numbers as ints
                discount_rate_raw = float(row["discount_rate"])
                discount_rate = int(discount_rate_raw) if discount_rate_raw.is_integer() else discount_rate_raw

                price_per_unit = int(row["price_per_unit"])
                cost_per_unit = int(row["cost_per_unit"])

                if "price" not in products[product_name]:
                    products[product_name]["price"] = price_per_unit
                    products[product_name]["cost"] = cost_per_unit

                # Store all other data fields
                data_entry = {}
                for key, val in row.items():
                    if key == "product":
                        continue
                    # Try numeric conversion
                    try:
                        num_val = float(val)
                        val = int(num_val) if num_val.is_integer() else num_val
                    except ValueError:
                        pass
                    data_entry[key] = val

                products[product_name]["data"][discount_rate] = data_entry

        return dict(products)

    def _infer_allowed_discounts(self) -> List[int]:
        """Infer allowed discount rates from product data."""
        if not self.all_products:
            return [0, 15, 20, 30]  # Fallback default
        
        # Get all unique discount rates from any product
        all_discount_rates = set()
        for product_name, product_data in self.all_products.items():
            all_discount_rates.update(product_data['data'].keys())
        
        # Return sorted list
        return sorted(list(all_discount_rates))
    
    def _get_max_discount_rate(self) -> int:
        """Get the maximum discount rate from allowed discounts."""
        return max(self.allowed_discounts) if self.allowed_discounts else 30
    
    def _load_role_instructions(self, player_type: str, role_name: str) -> str:
        """Load role instructions from text file."""
        role_path = os.path.join(
            os.path.dirname(__file__),
            "data",
            "roles",
            player_type,
            f"{role_name}.txt"
        )
        
        try:
            with open(role_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback to default if role not found
            default_path = os.path.join(
                os.path.dirname(__file__),
                "data",
                "roles",
                player_type,
                "default.txt"
            )
            with open(default_path, 'r') as f:
                return f.read().strip()
    
    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the environment to initial state."""
        if num_players != 2:
            raise ValueError("VendorNegotiation requires exactly 2 players")
        
        # Set random seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        elif self.seed is not None:
            random.seed(self.seed)
            np.random.seed(self.seed)
        
        # Select random products
        all_product_names = list(self.all_products.keys())
        self.selected_products = random.sample(all_product_names, min(self.num_products, len(all_product_names)))
        self.products = {name: self.all_products[name] for name in self.selected_products}
        
        # Calculate targets using maximum discount rate
        max_discount = self._get_max_discount_rate()
        self.brand_target = self.brand_target_percentage * sum(
            self.products[p]['data'][max_discount]['mean_sales'] for p in self.selected_products
        )
        self.vendor_baseline = self.vendor_baseline_multiplier * sum(
            self.products[p]['data'][0]['mean_profit'] for p in self.selected_products
        )
        
        # Initialize TextArena state
        self.state = ta.TwoPlayerState(
            num_players=num_players,
            max_turns=self.max_rounds,
            seed=seed,
            error_allowance=self.error_allowance
        )
        
        # Reset game state
        self.current_proposal = {'discounts': None, 'proposer': None}
        self.negotiation_history = []
        self.conversation_history = []
        
        game_state = {
            'current_proposal': self.current_proposal,
            'negotiation_history': self.negotiation_history,
            'conversation_history': self.conversation_history
        }
        
        # Call state's reset method
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt,
            role_mapping={0: "Brand Specialist", 1: "Vendor"}
        )
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Generate initial prompt for a player."""
        # Create product order string
        product_order = ", ".join(self.selected_products)
        initial_prompt = f"You are Player {player_id}.\n"
        
        if player_id == 0:  # Brand Specialist
            prompt = f"""ROLE: Brand Specialist at E-commerce Platform
OBJECTIVE: Achieve total sales ≥ ${self.brand_target:.0f} ({self.brand_target_percentage*100:.0f}% of maximum possible)

{self.brand_role_instructions}

NEGOTIATION: Agree on discount rates for {self.num_products} products with Vendor

{render_product_data_for_brand(self.products, self.selected_products, self.allowed_discounts)}

PRODUCT ORDER: {product_order}

ACTIONS: There are two parts of an action, STRICTLY in this order.
1. Free-text communication to the other party to persuade them to agree to a deal favorable to you.
2. ALWAYS end with one of these bracketed actions:
- [Propose] X%, Y%, Z%, ... (follow product order above)
- [Accept]
- [Reject]

ROUNDS: {self.max_rounds} maximum
"""
        else:  # Vendor
            prompt = f"""ROLE: Vendor
OBJECTIVE: Achieve total profit > ${self.vendor_baseline:.0f} (baseline at {self.vendor_baseline_multiplier} times profit at 0% discount)

You must NEVER reveal information about your profit and cost.
{self.vendor_role_instructions}

NEGOTIATION: Agree on discount rates for {self.num_products} products with Brand Specialist

{render_product_data_for_vendor(self.products, self.selected_products, self.allowed_discounts)}

PRODUCT ORDER: {product_order}

ACTIONS: There are two parts of an action, STRICTLY in this order.
1. Free-text communication to the other party to persuade them to agree to a deal favorable to you.
2. ALWAYS end with one of these bracketed actions:
- [Propose] X%, Y%, Z%, ... (follow product order above)
- [Accept]
- [Reject]

ROUNDS: {self.max_rounds} maximum
"""
        
        return initial_prompt + prompt
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process a player's action."""
        current_pid = self.state.current_player_id
        
        # Log the action
        self.state.add_observation(
            from_id=current_pid,
            to_id=current_pid,
            message=f"Your action: {action}",
            observation_type=ta.ObservationType.PLAYER_ACTION
        )
        
        # Process the action
        if self._is_valid_action(action):
            self._process_valid_action(current_pid, action)
        
        # Check for game end conditions
        deal_accepted = self._check_deal_accepted()
        max_turns_reached = self.state.turn >= self.max_rounds - 1
        
        if deal_accepted or max_turns_reached:
            self._end_game(deal_accepted)
        
        # Let TextArena handle turn advancement
        return self.state.step()
    
    def _is_valid_action(self, action: str) -> bool:
        """Check if an action is valid."""
        action = action.strip()
        
        # Check for action types
        has_propose = "[Propose]" in action
        has_accept = "[Accept]" in action
        has_reject = "[Reject]" in action
        
        action_count = sum([has_propose, has_accept, has_reject])
        
        # Allow free-text conversation (no bracketed action)
        if action_count == 0:
            # This is just conversation - always valid
            return True
        elif action_count > 1:
            self.state.set_invalid_move("Multiple actions detected. Use only one action per turn")
            return False
        
        # Validate proposal
        if has_propose:
            if not self._is_valid_proposal(action):
                return False
        
        # Validate accept/reject
        if has_accept or has_reject:
            if self.current_proposal['discounts'] is None:
                action_type = "accept" if has_accept else "reject"
                self.state.set_invalid_move(f"No current proposal to {action_type}")
                return False
            
            if self.current_proposal['proposer'] == self.state.current_player_id:
                action_type = "accept" if has_accept else "reject"
                self.state.set_invalid_move(f"You cannot {action_type} your own proposal")
                return False
        
        return True
    
    def _is_valid_proposal(self, action: str) -> bool:
        """Check if a proposal is valid."""
        try:
            discounts = self._extract_proposal_discounts(action)
            if discounts is None:
                product_order = ", ".join(self.selected_products)
                self.state.set_invalid_move(f"Invalid proposal format. Use: [Propose] X%, Y%, Z%, ... following order: {product_order}")
                return False
            
            # Check all products are included
            if set(discounts.keys()) != set(self.selected_products):
                missing = set(self.selected_products) - set(discounts.keys())
                extra = set(discounts.keys()) - set(self.selected_products)
                msg = "Proposal must include all products. "
                if missing:
                    msg += f"Missing: {', '.join(missing)}. "
                if extra:
                    msg += f"Extra: {', '.join(extra)}."
                self.state.set_invalid_move(msg)
                return False
            
            # Check all discounts are allowed
            for product, discount in discounts.items():
                if discount not in self.allowed_discounts:
                    self.state.set_invalid_move(
                        f"Invalid discount {discount}% for {product}. "
                        f"Allowed: {', '.join(str(d) + '%' for d in self.allowed_discounts)}"
                    )
                    return False
            
            return True
        except Exception as e:
            self.state.set_invalid_move(f"Error parsing proposal: {str(e)}")
            return False
    
    def _extract_proposal_discounts(self, action: str) -> Optional[Dict[str, int]]:
        """
        Extract discount rates from proposal action.
        Only supports positional format: [Propose] 10%, 5%, 10%, 20%, 0%
        """
        try:
            # Find the part after [Propose]
            if "[Propose]" not in action:
                return None
            
            proposal_text = action.split("[Propose]")[1].strip()
            
            # Parse positional format: [Propose] 10%, 5%, 10%, 20%, 0%
            positional_pattern = r'(\d+)%'
            positional_matches = re.findall(positional_pattern, proposal_text)
            
            if not positional_matches:
                return None
            
            # Check correct number of discounts
            if len(positional_matches) != len(self.selected_products):
                return None
            
            # Map to products in order
            discounts = {}
            for i, discount_str in enumerate(positional_matches):
                discounts[self.selected_products[i]] = int(discount_str)
            
            return discounts
        except Exception:
            return None
    
    def _process_valid_action(self, player_id: int, action: str):
        """Process a valid action."""
        action = action.strip()
        
        if "[Propose]" in action:
            self._process_proposal(player_id, action)
        elif "[Accept]" in action:
            self._process_accept(player_id, action)
        elif "[Reject]" in action:
            self._process_reject(player_id, action)
        else:
            # Free-text conversation - just broadcast it
            self._process_conversation(player_id, action)
    
    def _process_conversation(self, player_id: int, action: str):
        """Process free-text conversation."""
        # Record in conversation history
        self.conversation_history.append({
            'player': player_id,
            'message': action,
            'round': self.state.turn + 1
        })
        self.state.game_state['conversation_history'] = self.conversation_history
        
        # Record in general history
        self._record_action(player_id, 'conversation', None)
        
        # Broadcast the message
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"Player {player_id}: {action}",
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
    
    def _process_proposal(self, player_id: int, action: str):
        """Process a proposal."""
        discounts = self._extract_proposal_discounts(action)
        
        # Extract conversation part (text before [Propose])
        conversation_part = action.split("[Propose]")[0].strip()
        if conversation_part:
            # Record the conversation part
            self.conversation_history.append({
                'player': player_id,
                'message': conversation_part,
                'round': self.state.turn + 1
            })
            self.state.game_state['conversation_history'] = self.conversation_history
        
        # Update current proposal
        self.current_proposal = {'discounts': discounts, 'proposer': player_id}
        self.state.game_state['current_proposal'] = self.current_proposal
        
        # Record in history
        self._record_action(player_id, 'propose', discounts)
        
        # Announce the proposal
        proposal_str = ", ".join(f"{p}:{d}%" for p, d in discounts.items())
        message = f"Player {player_id} proposed: {proposal_str}"
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _process_accept(self, player_id: int, action: str):
        """Process an accept action."""
        # Extract conversation part (text before [Accept])
        conversation_part = action.split("[Accept]")[0].strip()
        if conversation_part:
            # Record the conversation part
            self.conversation_history.append({
                'player': player_id,
                'message': conversation_part,
                'round': self.state.turn + 1
            })
            self.state.game_state['conversation_history'] = self.conversation_history
        
        self._record_action(player_id, 'accept', None)
        
        message = f"Player {player_id} accepted the proposal"
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _process_reject(self, player_id: int, action: str):
        """Process a reject action."""
        # Extract conversation part (text before [Reject])
        conversation_part = action.split("[Reject]")[0].strip()
        if conversation_part:
            # Record the conversation part
            self.conversation_history.append({
                'player': player_id,
                'message': conversation_part,
                'round': self.state.turn + 1
            })
            self.state.game_state['conversation_history'] = self.conversation_history
        
        self._record_action(player_id, 'reject', None)
        
        message = f"Player {player_id} rejected the proposal"
        
        # Reset proposal
        self.current_proposal = {'discounts': None, 'proposer': None}
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _record_action(self, player_id: int, action_type: str, discounts: Optional[Dict]):
        """Record action in history."""
        self.negotiation_history.append({
            'player': player_id,
            'type': action_type,
            'discounts': discounts,
            'round': self.state.turn + 1
        })
        
        self.state.game_state['negotiation_history'] = self.negotiation_history
    
    def _check_deal_accepted(self) -> bool:
        """Check if the current deal has been accepted."""
        if self.current_proposal['discounts'] is None:
            return False
        
        if self.negotiation_history:
            last_action = self.negotiation_history[-1]
            if (last_action['type'] == 'accept' and 
                last_action['player'] != self.current_proposal['proposer']):
                return True
        
        return False
    
    def _end_game(self, deal_accepted: bool):
        """End the game and determine outcomes."""
        if deal_accepted:
            self._finalize_accepted_deal()
        else:
            self._handle_no_deal()
        
        self.state.done = True
    
    def _finalize_accepted_deal(self):
        """Finalize an accepted deal with Monte Carlo simulation."""
        agreed_discounts = self.current_proposal['discounts']
        
        # Run Monte Carlo simulation
        simulation_results = self._calculate_actual_sales(agreed_discounts)
        
        # Calculate totals
        total_sales = sum(r['avg_sales'] for r in simulation_results.values())
        total_profit = sum(r['avg_profit'] for r in simulation_results.values())
        
        # Check win conditions
        brand_won = total_sales >= self.brand_target
        vendor_won = total_profit > self.vendor_baseline
        
        # Announce results
        results_str = render_final_results(
            simulation_results,
            agreed_discounts,
            brand_won,
            vendor_won,
            self.brand_target,
            self.vendor_baseline,
            self.num_simulations
        )
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=results_str,
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Set rewards
        self._set_final_rewards(brand_won, vendor_won)
    
    def _calculate_actual_sales(self, agreed_discounts: Dict[str, int]) -> Dict[str, Dict[str, float]]:
        """Run Monte Carlo simulation to calculate expected sales and profit."""
        # Store all simulation results
        all_simulations = {
            product: {
                'units': [],
                'sales': [],
                'profit': []
            } for product in agreed_discounts.keys()
        }
        
        # Run simulations (vectorized for speed)
        for product_name, discount in agreed_discounts.items():
            product_data = self.products[product_name]['data'][discount]
            
            # Generate all samples at once
            units_samples = np.maximum(0, np.random.normal(
                product_data['mean_units'],
                product_data['std_units'],
                size=self.num_simulations
            ))
            
            # Vectorized calculations
            price = self.products[product_name]['price']
            cost = self.products[product_name]['cost']
            discount_multiplier = 1 - (discount / 100)
            
            sales_samples = units_samples * price * discount_multiplier
            profit_samples = units_samples * (price * discount_multiplier - cost)
            
            all_simulations[product_name]['units'] = units_samples
            all_simulations[product_name]['sales'] = sales_samples
            all_simulations[product_name]['profit'] = profit_samples
        
        # Calculate statistics
        results = {}
        for product_name in agreed_discounts.keys():
            units_array = all_simulations[product_name]['units']
            sales_array = all_simulations[product_name]['sales']
            profit_array = all_simulations[product_name]['profit']
            
            results[product_name] = {
                'discount': agreed_discounts[product_name],
                'avg_units': float(np.mean(units_array)),
                'avg_sales': float(np.mean(sales_array)),
                'avg_profit': float(np.mean(profit_array))
            }
        
        return results
    
    def _handle_no_deal(self):
        """Handle case where no deal was reached."""
        results_str = render_no_deal(self.brand_target, self.vendor_baseline)
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=results_str,
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Both players lose
        self._set_final_rewards(False, False)
    
    def _set_final_rewards(self, brand_won: bool, vendor_won: bool):
        """Set final rewards based on win conditions."""
        if brand_won and vendor_won:
            # Both won - draw
            self.state.set_draw(reason="Both players achieved their objectives")
        elif brand_won and not vendor_won:
            # Brand won
            self.state.set_winner(player_id=0, reason="Brand Specialist achieved sales target")
        elif vendor_won and not brand_won:
            # Vendor won
            self.state.set_winner(player_id=1, reason="Vendor achieved profit target")
        else:
            # Both lost - draw
            self.state.set_draw(reason="Neither player achieved their objective")
    
    def get_observation(self):
        """Get observation for current player."""
        player_id = self.state.current_player_id
        observation = self.state.get_current_player_observation()
        
        # Add current state information
        state_info = render_current_state(
            self.current_proposal,
            self.negotiation_history,
            self.state.turn + 1,
            self.max_rounds,
            self.conversation_history,
            self.products,
            self.brand_target,
            self.vendor_baseline,
            player_id
        )
        
        observation.append((ta.GAME_ID, state_info, ta.ObservationType.GAME_BOARD))
        
        return player_id, observation
    
    def get_board_str(self) -> str:
        """Return the main board string for rendering."""
        if getattr(self.state, "done", False):
            # Game is over - show final results
            if self.current_proposal['discounts'] is not None and self._check_deal_accepted():
                # Deal was accepted - show the actual simulation results
                agreed_discounts = self.current_proposal['discounts']
                simulation_results = self._calculate_actual_sales(agreed_discounts)
                
                # Calculate totals
                total_sales = sum(r['avg_sales'] for r in simulation_results.values())
                total_profit = sum(r['avg_profit'] for r in simulation_results.values())
                
                # Check win conditions
                brand_won = total_sales >= self.brand_target
                vendor_won = total_profit > self.vendor_baseline
                
                return render_final_results(
                    simulation_results,
                    agreed_discounts,
                    brand_won,
                    vendor_won,
                    self.brand_target,
                    self.vendor_baseline,
                    self.num_simulations
                )
            else:
                # No deal
                return render_no_deal(self.brand_target, self.vendor_baseline)
        
        # Ongoing game
        return render_current_state(
            self.current_proposal,
            self.negotiation_history,
            self.state.turn + 1,
            self.max_rounds,
            self.conversation_history
        )
