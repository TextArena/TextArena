"""
Vendor Negotiation Environment

A two-player negotiation game where a Brand Specialist (Player 0) negotiates
with a Vendor (Player 1) over discount rates for products in an upcoming sales event.

Each player has a private target placed inside the range of totals the drawn
products can actually reach, from the worst to the best allowed discount for
every product:
- Brand Specialist: total sales at least `brand_target_fraction` of the way up the sales range
- Vendor: total profit at least `vendor_target_fraction` of the way up the profit range
"""

import os
import re
import csv
import math
import statistics
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

    # Decision grammar (what the prompts teach): a decision is a line whose
    # first token is exactly the command keyword, case-insensitive, followed
    # by its arguments; trailing "." or "!" is tolerated. A "propose" line
    # whose remainder is empty or starts with a digit is a proposal attempt
    # and must be well-formed. Every other line, such as "Proposed changes ..."
    # or "Accept this?", is conversation.
    _ACCEPT_LINE_RE = re.compile(r"accept[.!]*", re.IGNORECASE)
    _REJECT_LINE_RE = re.compile(r"reject[.!]*", re.IGNORECASE)
    _PROPOSE_LINE_RE = re.compile(r"propose(?![^\s:.!])\s*:?\s*(?P<args>.*)", re.IGNORECASE)
    _DISCOUNT_LIST_RE = re.compile(r"[0-9]+%(?:\s*,\s*[0-9]+%)*")

    def __init__(self,
                 num_products: int = 5,
                 max_rounds: int = 20,
                 error_allowance: int = 3,
                 brand_target_fraction: float = 0.5,
                 vendor_target_fraction: float = 0.5,
                 num_simulations: int = 1000,
                 brand_role: Optional[str] = None,
                 vendor_role: Optional[str] = None,
                 product_list_path: Optional[str] = None):
        """
        Initialize the Vendor Negotiation environment.

        Args:
            num_products: Number of products to negotiate (default: 5)
            max_rounds: Maximum negotiation rounds (default: 20)
            error_allowance: Invalid moves allowed before penalty (default: 3)
            brand_target_fraction: Brand's sales target as a position (0-1) between the lowest
                and highest total sales the drawn products can reach (default: 0.5)
            vendor_target_fraction: Vendor's profit target as a position (0-1) between the lowest
                and highest total profit the drawn products can reach (default: 0.5)
            num_simulations: Monte Carlo simulation runs (default: 1000)
            brand_role: Role file name for Player 0 (default: "default")
            vendor_role: Role file name for Player 1 (default: "default")
            product_list_path: Path to product CSV file (default: "data/product_list.csv")
        """
        if not isinstance(num_products, int) or isinstance(num_products, bool) or num_products <= 0:
            raise ValueError("num_products must be a positive integer")
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds <= 0:
            raise ValueError("max_rounds must be a positive integer")
        if not isinstance(error_allowance, int) or isinstance(error_allowance, bool) or error_allowance < 0:
            raise ValueError("error_allowance must be a non-negative integer")
        if not isinstance(num_simulations, int) or isinstance(num_simulations, bool) or num_simulations <= 0:
            raise ValueError("num_simulations must be a positive integer")
        self.num_products = num_products
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance
        self.brand_target_fraction = self._validate_fraction(brand_target_fraction, "brand_target_fraction")
        self.vendor_target_fraction = self._validate_fraction(vendor_target_fraction, "vendor_target_fraction")
        self.num_simulations = num_simulations
        self.brand_role_name = brand_role or "default"
        self.vendor_role_name = vendor_role or "default"
        self.product_list_path = product_list_path or "data/product_list.csv"

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
        self.sales_range = (0.0, 0.0)
        self.profit_range = (0.0, 0.0)
        self.brand_target = 0.0
        self.vendor_target = 0.0

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

    def _attainable_range(self, metric: str) -> Tuple[float, float]:
        """Lowest and highest forecast total of `metric` over all allowed proposals."""
        low = high = 0.0
        for product in self.selected_products:
            values = [self.products[product]['data'][d][metric] for d in self.allowed_discounts]
            low += min(values)
            high += max(values)
        return low, high

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

    @staticmethod
    def _validate_fraction(value: float, name: str) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError, OverflowError):
            normalized = math.nan
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(normalized)
            or not 0 <= normalized <= 1
        ):
            raise ValueError(f"{name} must be a finite number between 0 and 1")
        return normalized

    def roles(self) -> Dict[int, str]:
        return {0: "Brand Specialist", 1: "Vendor"}

    def setup(self) -> Dict[str, Any]:
        # Select random products
        all_product_names = list(self.all_products.keys())
        self.selected_products = self.rng.sample(all_product_names, min(self.num_products, len(all_product_names)))
        self.products = {name: self.all_products[name] for name in self.selected_products}

        # Each target sits a fixed fraction of the way up the range the drawn
        # products can reach, so every draw leaves both sides able to win or lose.
        self.sales_range = self._attainable_range('mean_sales')
        self.profit_range = self._attainable_range('mean_profit')
        sales_low, sales_high = self.sales_range
        profit_low, profit_high = self.profit_range
        self.brand_target = sales_low + self.brand_target_fraction * (sales_high - sales_low)
        self.vendor_target = profit_low + self.vendor_target_fraction * (profit_high - profit_low)

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
            sales_low, sales_high = self.sales_range
            prompt = f"""ROLE: Brand Specialist at E-commerce Platform
OBJECTIVE: Achieve total sales ≥ ${self.brand_target:.0f}
(Depending on the discounts, total sales for these products range from ${sales_low:.0f} to ${sales_high:.0f}; your target is {self.brand_target_fraction:.0%} of the way up that range.)

{self.brand_role_instructions}

NEGOTIATION: Agree on discount rates for {len(self.selected_products)} products with Vendor

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
            profit_low, profit_high = self.profit_range
            prompt = f"""ROLE: Vendor
OBJECTIVE: Achieve total profit ≥ ${self.vendor_target:.0f}
(Depending on the discounts, total profit for these products ranges from ${profit_low:.0f} to ${profit_high:.0f}; your target is {self.vendor_target_fraction:.0%} of the way up that range.)

You must NEVER reveal information about your profit and cost.
{self.vendor_role_instructions}

NEGOTIATION: Agree on discount rates for {len(self.selected_products)} products with Brand Specialist

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
            self.vendor_target,
            player_id,
            self.num_simulations,
        )

    # -- command detection: a decision is a line of its own --
    def _classify_line(self, line: str) -> Optional[Tuple[str, str]]:
        """('accept'|'reject', '') or ('propose', arguments) if a stripped line is a decision."""
        if self._ACCEPT_LINE_RE.fullmatch(line):
            return "accept", ""
        if self._REJECT_LINE_RE.fullmatch(line):
            return "reject", ""
        match = self._PROPOSE_LINE_RE.fullmatch(line)
        if match is not None:
            args = match.group("args").rstrip(" \t.!")
            if not args or args[0] in "0123456789":
                return "propose", args
        return None

    def _find_decisions(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Every decision line in the message: kind, arguments, and line index."""
        decisions = []
        for index, line in enumerate(lines):
            classified = self._classify_line(line.strip())
            if classified is not None:
                kind, args = classified
                decisions.append({"kind": kind, "args": args, "line": index})
        return decisions

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Process a player's action."""
        action = self.strip_role_tags(action).strip()
        decision, reason = self._parse_action(player_id, action)
        if reason is not None:
            return self.invalid(reason)

        # Log only after validation; invalid actions must be atomic.
        self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        if decision is None:
            self._process_conversation(player_id, action)
        else:
            if decision["before"]:
                self._record_conversation(player_id, decision["before"])
            if decision["kind"] == "propose":
                self._process_proposal(player_id, decision["discounts"])
            elif decision["kind"] == "accept":
                self._process_accept(player_id)
            else:
                self._process_reject(player_id)

        # Check for game end conditions
        deal_accepted = self._check_deal_accepted()
        if deal_accepted or self.state.turn >= self.max_rounds - 1:
            return self._end_game(deal_accepted)
        return None

    def _parse_action(self, player_id: int, action: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Return (decision, None) for a valid action (decision is None for pure
        conversation) or (None, reason) for an invalid one."""
        lines = action.split("\n")
        decisions = self._find_decisions(lines)
        if not decisions:
            return None, None
        if len(decisions) > 1:
            return None, "Multiple decisions detected. Use only one decision per turn."
        decision = decisions[0]
        if any(rest.strip() for rest in lines[decision["line"] + 1:]):
            return None, "The decision must be the last line of your message."
        decision["before"] = "\n".join(lines[:decision["line"]]).strip()

        if decision["kind"] == "propose":
            discounts, reason = self._parse_discounts(decision["args"])
            if reason is not None:
                return None, reason
            decision["discounts"] = discounts
        elif self.current_proposal['discounts'] is None:
            return None, f"No current proposal to {decision['kind']}"
        elif self.current_proposal['proposer'] == player_id:
            return None, f"You cannot {decision['kind']} your own proposal"
        return decision, None

    def _parse_discounts(self, args: str) -> Tuple[Optional[Dict[str, int]], Optional[str]]:
        """Map 'X%, Y%, Z%' onto the product order; return (discounts, None) or (None, reason)."""
        product_order = ", ".join(self.selected_products)
        if self._DISCOUNT_LIST_RE.fullmatch(args) is None:
            return None, f"Invalid proposal format. Use: 'Propose X%, Y%, Z%, ...' on its own line, following order: {product_order}"
        values = re.findall(r"[0-9]+", args)
        if len(values) != len(self.selected_products):
            return None, (
                f"Proposal must list exactly {len(self.selected_products)} discounts, "
                f"one per product in this order: {product_order}"
            )
        allowed = ", ".join(f"{d}%" for d in self.allowed_discounts)
        discounts = {}
        for product, value in zip(self.selected_products, values):
            discount = int(value) if len(value) <= 9 else None
            if discount not in self.allowed_discounts:
                return None, f"Invalid discount {value}% for {product}. Allowed: {allowed}"
            discounts[product] = discount
        return discounts, None

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

    def _process_proposal(self, player_id: int, discounts: Dict[str, int]):
        """Process a proposal."""
        self.game_state['current_proposal'] = {'discounts': discounts, 'proposer': player_id}

        self._record_action(player_id, 'propose', discounts)

        proposal_str = ", ".join(f"{p}:{d}%" for p, d in discounts.items())
        self.broadcast(f"Player {player_id} proposed: {proposal_str}", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_accept(self, player_id: int):
        """Process an accept action."""
        self._record_action(player_id, 'accept', None)
        self.broadcast(f"Player {player_id} accepted the proposal", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_reject(self, player_id: int):
        """Process a reject action."""
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
        vendor_won = total_profit >= self.vendor_target

        results_str = render_final_results(
            simulation_results,
            agreed_discounts,
            brand_won,
            vendor_won,
            self.brand_target,
            self.vendor_target,
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
        results = {}
        for product_name, discount in agreed_discounts.items():
            product_data = self.products[product_name]['data'][discount]

            units_samples = [
                max(0.0, self.rng.gauss(product_data['mean_units'], product_data['std_units']))
                for _ in range(self.num_simulations)
            ]
            avg_units = statistics.fmean(units_samples)

            # Each unit earns the forecast's per-unit sales and profit, so the
            # expected totals match the forecasts both players are shown.
            mean_units = product_data['mean_units']
            sales_per_unit = product_data['mean_sales'] / mean_units if mean_units else 0.0
            profit_per_unit = product_data['mean_profit'] / mean_units if mean_units else 0.0

            results[product_name] = {
                'discount': discount,
                'avg_units': avg_units,
                'avg_sales': avg_units * sales_per_unit,
                'avg_profit': avg_units * profit_per_unit,
            }

        return results

    def _handle_no_deal(self) -> ta.Outcome:
        """Handle case where no deal was reached."""
        cached = self.game_state.get("terminal_result")
        if cached is not None:
            return self._final_outcome(cached["brand_won"], cached["vendor_won"])

        results_str = render_no_deal(self.brand_target, self.vendor_target)
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
