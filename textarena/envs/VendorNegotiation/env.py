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
import csv
import math
import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict

import textarena as ta
from textarena.envs.VendorNegotiation.renderer import (
    render_product_data_for_brand,
    render_product_data_for_vendor,
    render_current_state,
    render_final_results,
    render_no_deal
)


class VendorNegotiationEnv(ta.GameEnv):
    """
    Two-player vendor negotiation environment.

    Player 0: Brand Specialist (wants high sales)
    Player 1: Vendor (wants high profit)
    """

    min_players = 2
    max_players = 2

    # Command grammar: the decision is a bare command phrase on its own line
    # (this is what the prompts teach); messages without a decision line are
    # free-text conversation. Optional surrounding brackets and the legacy
    # embedded "[Command]" tokens are still recognized for backwards
    # compatibility, but brackets are never required.
    _BARE_ACCEPT_RE = re.compile(r"^[ \t]*\[?[ \t]*(?P<command>accept)[ \t]*\]?[ \t]*[.!]?[ \t]*$", re.IGNORECASE | re.MULTILINE)
    _BARE_REJECT_RE = re.compile(r"^[ \t]*\[?[ \t]*(?P<command>reject)[ \t]*\]?[ \t]*[.!]?[ \t]*$", re.IGNORECASE | re.MULTILINE)
    _BARE_PROPOSE_RE = re.compile(r"^[ \t]*\[?[ \t]*(?P<command>propose)[ \t]*\]?[ \t]*:?(?P<rest>[^\n]*)$", re.IGNORECASE | re.MULTILINE)
    _LEGACY_DECISION_RE = re.compile(r"\[(Propose|Accept|Reject)\]")

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
        if not isinstance(num_products, int) or isinstance(num_products, bool) or num_products <= 0:
            raise ValueError("num_products must be a positive integer")
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds <= 0:
            raise ValueError("max_rounds must be a positive integer")
        if not isinstance(error_allowance, int) or isinstance(error_allowance, bool) or error_allowance < 0:
            raise ValueError("error_allowance must be a non-negative integer")
        try:
            normalized_brand_target = float(brand_target_percentage)
        except (TypeError, ValueError, OverflowError):
            normalized_brand_target = math.nan
        if (
            not isinstance(brand_target_percentage, (int, float))
            or isinstance(brand_target_percentage, bool)
            or not math.isfinite(normalized_brand_target)
            or not 0 <= normalized_brand_target <= 1
        ):
            raise ValueError("brand_target_percentage must be a finite number between 0 and 1")
        try:
            normalized_vendor_multiplier = float(vendor_baseline_multiplier)
        except (TypeError, ValueError, OverflowError):
            normalized_vendor_multiplier = math.nan
        if (
            not isinstance(vendor_baseline_multiplier, (int, float))
            or isinstance(vendor_baseline_multiplier, bool)
            or not math.isfinite(normalized_vendor_multiplier)
            or normalized_vendor_multiplier < 0
        ):
            raise ValueError("vendor_baseline_multiplier must be a finite non-negative number")
        if not isinstance(num_simulations, int) or isinstance(num_simulations, bool) or num_simulations <= 0:
            raise ValueError("num_simulations must be a positive integer")
        self._validate_seed(seed)
        self.num_products = num_products
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance
        self.brand_target_percentage = normalized_brand_target
        self.vendor_baseline_multiplier = normalized_vendor_multiplier
        self.num_simulations = num_simulations
        self.brand_role_name = brand_role or "default"
        self.vendor_role_name = vendor_role or "default"
        self.product_list_path = product_list_path or "data/product_list.csv"
        self.seed = seed

        # Load product data and roles
        self.all_products = self._load_product_data()
        if not self.all_products:
            raise ValueError("product data must contain at least one product")

        # Always infer allowed discounts from product data
        self.allowed_discounts = self._infer_allowed_discounts()
        self.brand_role_instructions = self._load_role_instructions("brand", self.brand_role_name)
        self.vendor_role_instructions = self._load_role_instructions("vendor", self.vendor_role_name)

        # Per-game data (initialized in setup)
        self.selected_products = []
        self.products = {}
        self.brand_target = 0.0
        self.vendor_baseline = 0.0

    # -- game_state-backed views (kept as attributes for renderers/analysis) --
    @property
    def current_proposal(self) -> Dict[str, Any]:
        return self.game_state["current_proposal"]

    @property
    def negotiation_history(self) -> List[Dict[str, Any]]:
        return self.game_state["negotiation_history"]

    @property
    def conversation_history(self) -> List[Dict[str, Any]]:
        return self.game_state["conversation_history"]

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
        """Infer rates available for every product so any proposal is executable."""
        discount_sets = [
            set(product_data["data"])
            for product_data in self.all_products.values()
        ]
        common_discounts = set.intersection(*discount_sets)
        if not common_discounts or 0 not in common_discounts:
            raise ValueError("every product must provide a shared 0% discount option")
        return sorted(common_discounts)

    def _get_max_discount_rate(self) -> int:
        """Get the maximum discount rate from allowed discounts."""
        return max(self.allowed_discounts) if self.allowed_discounts else 30

    def _load_role_instructions(self, player_type: str, role_name: str) -> str:
        """Load role instructions from text file."""
        if (
            not isinstance(role_name, str)
            or not role_name
            or os.path.basename(role_name) != role_name
            or role_name in {".", ".."}
        ):
            role_name = "default"
        role_path = os.path.join(os.path.dirname(__file__), "data", "roles", player_type, f"{role_name}.txt")

        try:
            with open(role_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback to default if role not found
            default_path = os.path.join(os.path.dirname(__file__), "data", "roles", player_type, "default.txt")
            with open(default_path, 'r') as f:
                return f.read().strip()

    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the environment with an isolated NumPy generator for simulation."""
        if seed is None:
            seed = self.seed
        self._validate_seed(seed)
        self.np_rng = np.random.default_rng(seed)
        super().reset(num_players=num_players, seed=seed)

    @staticmethod
    def _validate_seed(seed: Optional[int]) -> None:
        if seed is not None and (
            not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
        ):
            raise ValueError("seed must be a non-negative integer or None")

    def roles(self) -> Dict[int, str]:
        return {0: "Brand Specialist", 1: "Vendor"}

    def setup(self) -> Dict[str, Any]:
        # Select random products
        all_product_names = list(self.all_products.keys())
        self.selected_products = self.rng.sample(all_product_names, min(self.num_products, len(all_product_names)))
        self.products = {name: self.all_products[name] for name in self.selected_products}

        # Calculate targets using maximum discount rate
        max_discount = self._get_max_discount_rate()
        self.brand_target = self.brand_target_percentage * sum(
            self.products[p]['data'][max_discount]['mean_sales'] for p in self.selected_products
        )
        self.vendor_baseline = self.vendor_baseline_multiplier * sum(
            self.products[p]['data'][0]['mean_profit'] for p in self.selected_products
        )

        return {
            'current_proposal': {'discounts': None, 'proposer': None},
            'negotiation_history': [],
            'conversation_history': [],
            'terminal_result': None,
        }

    def prompt(self, player_id: int) -> str:
        """Generate initial prompt for a player."""
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
2. To take a structured action, finish your message with the decision on its own line:
- Propose X%, Y%, Z%, ... (follow product order above)
- Accept
- Reject
A message without a decision line is treated as pure conversation.

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
2. To take a structured action, finish your message with the decision on its own line:
- Propose X%, Y%, Z%, ... (follow product order above)
- Accept
- Reject
A message without a decision line is treated as pure conversation.

ROUNDS: {self.max_rounds} maximum
"""

        return initial_prompt + prompt

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # the env emits its own "Your action: ..." echo in apply

    def render(self, player_id: int) -> str:
        """Current state (with per-player proposal analysis) for the player about to act."""
        terminal_result = self.game_state.get("terminal_result")
        if terminal_result is not None:
            return terminal_result["rendered"]

        return render_current_state(
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

    # -- command detection: bare own-line phrase or legacy bracketed token --
    def _decision_occurrences(self, action: str) -> List[Tuple[str, Tuple[int, int]]]:
        """Return every recognized decision, de-duplicating bracketed own-line commands."""
        occurrences = []
        for kind, pattern in (
            ("Propose", self._BARE_PROPOSE_RE),
            ("Accept", self._BARE_ACCEPT_RE),
            ("Reject", self._BARE_REJECT_RE),
        ):
            occurrences.extend(
                (kind, match.span("command")) for match in pattern.finditer(action)
            )

        for match in self._LEGACY_DECISION_RE.finditer(action):
            kind = match.group(1)
            start, end = match.span()
            overlaps_bare_command = any(
                existing_kind == kind
                and max(start, existing_start) < min(end, existing_end)
                for existing_kind, (existing_start, existing_end) in occurrences
            )
            if not overlaps_bare_command:
                occurrences.append((kind, (start, end)))

        return sorted(occurrences, key=lambda occurrence: occurrence[1][0])

    def _has_accept(self, action: str) -> bool:
        return any(kind == "Accept" for kind, _ in self._decision_occurrences(action))

    def _has_reject(self, action: str) -> bool:
        return any(kind == "Reject" for kind, _ in self._decision_occurrences(action))

    def _has_propose(self, action: str) -> bool:
        return any(kind == "Propose" for kind, _ in self._decision_occurrences(action))

    def _text_before_command(self, action: str, legacy_token: str, bare_re: re.Pattern) -> str:
        """Free-text conversation part: everything before the command token/line."""
        starts = []
        idx = action.find(legacy_token)
        if idx >= 0:
            starts.append(idx)
        bare_match = bare_re.search(action)
        if bare_match:
            starts.append(bare_match.start())
        return action[:min(starts)].strip() if starts else action.strip()

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Process a player's action."""
        valid, reason = self._validate_action(player_id, action)
        if not valid:
            return self.invalid(reason)

        # Log only after validation; invalid actions must be atomic.
        self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        self._process_valid_action(player_id, action)

        # Check for game end conditions
        deal_accepted = self._check_deal_accepted()
        if deal_accepted or self.state.turn >= self.max_rounds - 1:
            return self._end_game(deal_accepted)
        return None

    def _validate_action(self, player_id: int, action: str) -> Tuple[bool, Optional[str]]:
        """Check if an action is valid; return (valid, reason)."""
        action = action.strip()

        decisions = self._decision_occurrences(action)
        if len(decisions) > 1:
            return False, "Multiple decision lines detected. Use only one action per turn"

        # Allow free-text conversation (no decision line)
        if not decisions:
            return True, None

        decision = decisions[0][0]
        has_propose = decision == "Propose"
        has_accept = decision == "Accept"
        has_reject = decision == "Reject"

        # Validate proposal
        if has_propose:
            valid, reason = self._validate_proposal(action)
            if not valid:
                return False, reason

        # Validate accept/reject
        if has_accept or has_reject:
            if self.current_proposal['discounts'] is None:
                action_type = "accept" if has_accept else "reject"
                return False, f"No current proposal to {action_type}"

            if self.current_proposal['proposer'] == player_id:
                action_type = "accept" if has_accept else "reject"
                return False, f"You cannot {action_type} your own proposal"

        return True, None

    def _validate_proposal(self, action: str) -> Tuple[bool, Optional[str]]:
        """Check if a proposal is valid; return (valid, reason)."""
        try:
            discounts = self._extract_proposal_discounts(action)
            if discounts is None:
                product_order = ", ".join(self.selected_products)
                return False, f"Invalid proposal format. Use: 'Propose X%, Y%, Z%, ...' on its own line, following order: {product_order}"

            # Check all products are included
            if set(discounts.keys()) != set(self.selected_products):
                missing = set(self.selected_products) - set(discounts.keys())
                extra = set(discounts.keys()) - set(self.selected_products)
                msg = "Proposal must include all products. "
                if missing:
                    msg += f"Missing: {', '.join(missing)}. "
                if extra:
                    msg += f"Extra: {', '.join(extra)}."
                return False, msg

            # Check all discounts are allowed
            for product, discount in discounts.items():
                if discount not in self.allowed_discounts:
                    return False, (
                        f"Invalid discount {discount}% for {product}. "
                        f"Allowed: {', '.join(str(d) + '%' for d in self.allowed_discounts)}"
                    )

            return True, None
        except Exception as e:
            return False, f"Error parsing proposal: {str(e)}"

    def _extract_proposal_discounts(self, action: str) -> Optional[Dict[str, int]]:
        """
        Extract discount rates from proposal action.
        Only supports positional format: 'Propose 10%, 5%, 10%, 20%, 0%'
        (legacy '[Propose] ...' is also tolerated).
        """
        try:
            if "[Propose]" in action:
                proposal_text = action.split("[Propose]")[1].strip()
            else:
                bare_match = self._BARE_PROPOSE_RE.search(action)
                if bare_match is None:
                    return None
                proposal_text = bare_match.group("rest")
                if action[bare_match.end():].strip():
                    return None

            # Parse exactly the taught positional format. Do not silently ignore
            # junk, extra commands, or a second line after the proposal.
            if re.fullmatch(r"\s*\d+%\s*(?:,\s*\d+%\s*)*", proposal_text) is None:
                return None
            positional_matches = re.findall(r'(\d+)%', proposal_text)

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

        if self._has_propose(action):
            self._process_proposal(player_id, action)
        elif self._has_accept(action):
            self._process_accept(player_id, action)
        elif self._has_reject(action):
            self._process_reject(player_id, action)
        else:
            # Free-text conversation - just broadcast it
            self._process_conversation(player_id, action)

    def _record_conversation(self, player_id: int, message: str):
        self.conversation_history.append({
            'player': player_id,
            'message': message,
            'round': self.state.turn + 1
        })

    def _process_conversation(self, player_id: int, action: str):
        """Process free-text conversation."""
        self._record_conversation(player_id, action)
        self._record_action(player_id, 'conversation', None)
        self.broadcast(f"Player {player_id}: {action}", ta.ObservationType.GAME_MESSAGE)

    def _process_proposal(self, player_id: int, action: str):
        """Process a proposal."""
        discounts = self._extract_proposal_discounts(action)

        # Extract conversation part (text before the propose command)
        conversation_part = self._text_before_command(action, "[Propose]", self._BARE_PROPOSE_RE)
        if conversation_part:
            self._record_conversation(player_id, conversation_part)

        # Update current proposal
        self.game_state['current_proposal'] = {'discounts': discounts, 'proposer': player_id}

        self._record_action(player_id, 'propose', discounts)

        proposal_str = ", ".join(f"{p}:{d}%" for p, d in discounts.items())
        self.broadcast(f"Player {player_id} proposed: {proposal_str}", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_accept(self, player_id: int, action: str):
        """Process an accept action."""
        conversation_part = self._text_before_command(action, "[Accept]", self._BARE_ACCEPT_RE)
        if conversation_part:
            self._record_conversation(player_id, conversation_part)

        self._record_action(player_id, 'accept', None)
        self.broadcast(f"Player {player_id} accepted the proposal", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_reject(self, player_id: int, action: str):
        """Process a reject action."""
        conversation_part = self._text_before_command(action, "[Reject]", self._BARE_REJECT_RE)
        if conversation_part:
            self._record_conversation(player_id, conversation_part)

        self._record_action(player_id, 'reject', None)

        # Reset proposal
        self.game_state['current_proposal'] = {'discounts': None, 'proposer': None}
        self.broadcast(f"Player {player_id} rejected the proposal", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _record_action(self, player_id: int, action_type: str, discounts: Optional[Dict]):
        """Record action in history."""
        self.negotiation_history.append({
            'player': player_id,
            'type': action_type,
            'discounts': discounts,
            'round': self.state.turn + 1
        })

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

    def _end_game(self, deal_accepted: bool) -> ta.Outcome:
        """End the game and determine outcomes."""
        if deal_accepted:
            return self._finalize_accepted_deal()
        return self._handle_no_deal()

    def _finalize_accepted_deal(self) -> ta.Outcome:
        """Finalize an accepted deal with Monte Carlo simulation."""
        cached = self.game_state.get("terminal_result")
        if cached is not None:
            return self._final_outcome(cached["brand_won"], cached["vendor_won"])

        agreed_discounts = self.current_proposal['discounts']

        # Run Monte Carlo simulation
        simulation_results = self._calculate_actual_sales(agreed_discounts)

        total_sales = sum(r['avg_sales'] for r in simulation_results.values())
        total_profit = sum(r['avg_profit'] for r in simulation_results.values())

        # Check win conditions
        brand_won = total_sales >= self.brand_target
        vendor_won = total_profit > self.vendor_baseline

        results_str = render_final_results(
            simulation_results,
            agreed_discounts,
            brand_won,
            vendor_won,
            self.brand_target,
            self.vendor_baseline,
            self.num_simulations
        )
        self.game_state["terminal_result"] = {
            "deal_accepted": True,
            "agreed_discounts": agreed_discounts.copy(),
            "simulation_results": simulation_results,
            "brand_won": brand_won,
            "vendor_won": vendor_won,
            "rendered": results_str,
        }
        self.broadcast(results_str, ta.ObservationType.GAME_ADMIN)

        return self._final_outcome(brand_won, vendor_won)

    def _calculate_actual_sales(self, agreed_discounts: Dict[str, int]) -> Dict[str, Dict[str, float]]:
        """Run Monte Carlo simulation to calculate expected sales and profit."""
        all_simulations = {
            product: {'units': [], 'sales': [], 'profit': []} for product in agreed_discounts.keys()
        }

        # Run simulations (vectorized for speed)
        for product_name, discount in agreed_discounts.items():
            product_data = self.products[product_name]['data'][discount]

            units_samples = np.maximum(0, self.np_rng.normal(
                product_data['mean_units'],
                product_data['std_units'],
                size=self.num_simulations
            ))

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
            results[product_name] = {
                'discount': agreed_discounts[product_name],
                'avg_units': float(np.mean(all_simulations[product_name]['units'])),
                'avg_sales': float(np.mean(all_simulations[product_name]['sales'])),
                'avg_profit': float(np.mean(all_simulations[product_name]['profit']))
            }

        return results

    def _handle_no_deal(self) -> ta.Outcome:
        """Handle case where no deal was reached."""
        cached = self.game_state.get("terminal_result")
        if cached is not None:
            return self._final_outcome(cached["brand_won"], cached["vendor_won"])

        results_str = render_no_deal(self.brand_target, self.vendor_baseline)
        self.game_state["terminal_result"] = {
            "deal_accepted": False,
            "brand_won": False,
            "vendor_won": False,
            "rendered": results_str,
        }
        self.broadcast(results_str, ta.ObservationType.GAME_ADMIN)

        # Both players lose
        return self._final_outcome(False, False)

    def _final_outcome(self, brand_won: bool, vendor_won: bool) -> ta.Outcome:
        """Build the final Outcome based on win conditions."""
        if brand_won and vendor_won:
            return self.draw(reason="Both players achieved their objectives")
        elif brand_won and not vendor_won:
            return self.winner(0, reason="Brand Specialist achieved sales target")
        elif vendor_won and not brand_won:
            return self.winner(1, reason="Vendor achieved profit target")
        else:
            return self.draw(reason="Neither player achieved their objective")

    def get_board_str(self) -> str:
        """Return the main board string for rendering."""
        terminal_result = self.game_state.get("terminal_result")
        if terminal_result is not None:
            return terminal_result["rendered"]

        # Ongoing game
        return render_current_state(
            self.current_proposal,
            self.negotiation_history,
            self.state.turn + 1,
            self.max_rounds,
            self.conversation_history
        )
