import re, random
from typing import Any, Dict, Optional, Tuple

import textarena as ta
from textarena.envs.SimpleNegotiation.renderer import create_board_str


class SimpleNegotiationEnv(ta.Env):
    def __init__(self, max_turns: Optional[int] = 10):
        self.max_turns = max_turns
        self.resource_names = ["Wheat", "Wood", "Sheep", "Brick", "Ore"]
        self.base_values = {"Wheat": 5, "Wood": 10, "Sheep": 15, "Brick": 25, "Ore": 40}
        self.accept_pattern = re.compile(r"\[Accept\]", re.IGNORECASE)
        self.deny_pattern = re.compile(r"\[Deny\]", re.IGNORECASE)
        self.offer_pattern = re.compile(r"\[Offer:?\s*(?:I\s+(?:give|offer)\s+)?([^\[\]]+?)\s*\.*\]", re.IGNORECASE | re.DOTALL)

    def get_board_str(self):
        return create_board_str(
            player_resources=self.state.game_state["player_resources"], player_values=self.state.game_state["player_values"], 
            inventory_values=self.state.game_state["inventory_value"], current_offer=self.state.game_state["current_offer"]
        )

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        player_resources = {0: {resource: random.randint(5, 25) for resource in self.resource_names}, 1: {resource: random.randint(5, 25) for resource in self.resource_names}}
        game_state = {"current_offer": None, "player_resources": player_resources, "player_values": {}, "trade_history": []}

        # Generate player-specific values for each resource type (±20% of base value, capped at 5 and 40)
        for player_id in [0, 1]:
            game_state["player_values"][player_id] = {}
            for resource in self.resource_names:
                base_value = self.base_values[resource]
                variation = int(0.2 * base_value)
                min_value = max(base_value - variation, 5)
                max_value = min(base_value + variation, 40)
                value = random.randint(min_value, max_value)
                game_state["player_values"][player_id][resource] = value

        # Keep track of the inventory (both initial and current)
        for player_id in [0, 1]:
            initial_value = self._calculate_player_inventory_value(player_id, game_state)
            game_state.setdefault("inventory_value", {})[player_id] = {"initial": initial_value, "current": initial_value, "change": 0}

        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)

    def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        resource_value_list = "\n\t+ ".join(
            [f"{f'[{res}]':{' '}<8}  Qty: {game_state['player_resources'][player_id][res]:{' '}<2}   Value: {game_state['player_values'][player_id][res]}" for res in game_state['player_resources'][player_id].keys()]
        )
        return "\n".join([
            self.t("player_prompt", "intro", player_id=player_id),
            self.t("player_prompt", "objective"),
            self.t("player_prompt", "resources", resource_value_list=resource_value_list),
            self.t("player_prompt", "turn_action"),
            self.t("player_prompt", "special_tokens"),
            self.t("player_prompt", "offer_format"),
            self.t("player_prompt", "accept"),
            self.t("player_prompt", "deny"),
            self.t("player_prompt", "duration", max_turns=self.max_turns)
        ])

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self._check_and_execute_existing_offer(player_id=self.state.current_player_id, action=action) # Check if the player is responding to an existing offer
        self._check_for_new_offer(player_id=self.state.current_player_id, action=action) # Check if the player's action contains a new trade offer
        if self.state.check_turn_limit(): self._determine_winner() # If turn limit, determine winner
        return self.state.step()

    def _check_and_execute_existing_offer(self, player_id: int, action: str) -> None:
        # check if an offer exists, and whether it was accepted
        if self.state.game_state["current_offer"] and self.accept_pattern.search(action): 
            self._attempt_to_execute_trade(player_id=player_id, action=action)
        elif self.state.game_state["current_offer"]:
            self.state.add_observation(message=self.t("offers", "reject", player_id=self.state.current_player_id), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else: 
            self.state.game_state["current_offer"] = None  # make sure the offer is reset

    def _attempt_to_execute_trade(self, player_id: int, action: str) -> None:
        """ Attempt to execute the trade if both players have sufficient resources """
        current_offer = self.state.game_state["current_offer"]
        proposer_id = current_offer["from_player"]
        acceptor_id = player_id

        # # Check if the trade can be executed
        # if proposer_valid and acceptor_valid:
        if self._check_if_sufficient_resources(trade_resources=current_offer["requested_resources"], player_resources=self.state.game_state["player_resources"][acceptor_id]):
            # Execute the trade
            for resource, qty in current_offer["offered_resources"].items():
                self.state.game_state["player_resources"][proposer_id][resource] -= qty
                self.state.game_state["player_resources"][acceptor_id][resource] += qty
            for resource, qty in current_offer["requested_resources"].items():
                self.state.game_state["player_resources"][acceptor_id][resource] -= qty
                self.state.game_state["player_resources"][proposer_id][resource] += qty
            self.state.add_observation(message=self.t("offers", "accept", proposer_id=proposer_id, acceptor_id=acceptor_id), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

            # Update trade history with outcome
            self.state.game_state["trade_history"].append({
                "from_player": proposer_id, "to_player": acceptor_id, "offered_resources": current_offer["offered_resources"],
                "requested_resources": current_offer["requested_resources"], "outcome": "Accepted"
            })

            self._update_inventory_values() # Update player inventory value
            self.state.game_state["current_offer"] = None # Reset trade offer
        else: self.state.set_invalid_move(reason=self.t("invalid_move", "receiving_with_no_resource")) # If not, throw invalid move

    def _check_if_sufficient_resources(self, trade_resources: Dict[str, int], player_resources: Dict[str, int]) -> bool:
        """ Check if a player has sufficient resources for a trade """
        for resource, qty in trade_resources.items():
            if player_resources.get(resource, 0) < qty: return False
        return True

    def _check_for_new_offer(self, player_id: int, action: str):
        """ Check if the player's action contains a new trade offer """
        # Check if the game has already done
        if not self.state.done:
            offer_match = self.offer_pattern.search(action)
            if offer_match:
                matched_offer = offer_match.group(1).strip()
                parsed_offer = self._parse_offer(matched_offer)
                if parsed_offer:
                    # check if necessary resourcs
                    if self._check_if_sufficient_resources(trade_resources=parsed_offer["offered_resources"], player_resources=self.state.game_state["player_resources"][player_id]):
                        # Add the offer to the game state with consistent keys
                        self.state.game_state["current_offer"] = {
                            "from_player": player_id, "to_player": 1 - player_id,
                            "offered_resources": parsed_offer["offered_resources"], "requested_resources": parsed_offer["requested_resources"]
                        }
                        # Update trade history with the new offer
                        self.state.game_state["trade_history"].append({
                            "from_player": player_id, "to_player": 1 - player_id, "offered_resources": parsed_offer["offered_resources"],
                            "requested_resources": parsed_offer["requested_resources"], "outcome": None  # To be updated upon acceptance
                        })
                        self.state.add_observation(message=self.t("offers", "proposal", player_id=player_id, opponent_id=1 - player_id, offer_details=self._offer_to_str(parsed_offer)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    else: self.state.set_invalid_move(reason=self.t("invalid_move", "proposing_with_no_resource")) # If not, throw invalid move
                else: self.state.set_invalid_move(reason=self.t("invalid_move", "incorrect_offer_format")) # If offer format is incorrect, throw invalid move
            else: self.state.add_observation(message=self.t("invalid_move", "no_new_offer", player_id=player_id), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _parse_offer(self, offer_str: str) -> Optional[Dict[str, Dict[str, int]]]:
        """Parse a trade offer string into a structured dictionary"""
        try:
            offer_str = ' '.join(offer_str.split()) # Remove any line breaks and extra spaces for robust parsing
            offer_str = re.sub(r'[.,!?]+$', '', offer_str) # Remove trailing punctuation (e.g., period)
            offer_str = re.sub(r'^(I\s+(?:give|offer)\s+)', '', offer_str, flags=re.IGNORECASE) # Remove leading phrases like "I give" or "I offer"
            offer_parts = re.split(r'\s*->\s*', offer_str) # Split by '->' to separate offered and requested resources
            if len(offer_parts) != 2: return None  # Erroneous offer
            offered_items_str = offer_parts[0].strip()
            requested_items_str = offer_parts[1].strip()
            offered_items = self._parse_resource_list(offered_items_str)
            requested_items = self._parse_resource_list(requested_items_str)
            if not offered_items or not requested_items: return None  # Erroneous offer
            return {'offered_resources': offered_items, 'requested_resources': requested_items}
        except Exception as e: return None

    def _parse_resource_list(self, resource_str: str) -> Optional[Dict[str, int]]:
        pairs = re.findall(r'(\d+)\s+([A-Za-z]+)', resource_str, re.IGNORECASE)
        if not pairs: return None # nothing recognised
        resources: Dict[str, int] = {}
        for qty_str, raw_name in pairs:
            qty = int(qty_str)
            name = {"Sheeps": "Sheep", "Woods": "Wood"}.get(raw_name.title(), raw_name.title())
            if name not in self.resource_names or qty <= 0: return None # invalid entry
            resources[name] = resources.get(name, 0) + qty
        return resources

    def _offer_to_str(self, parsed_offer: Dict[str, Dict[str, int]]) -> str:
        offered = ", ".join(f"{qty} {res}" for res, qty in parsed_offer["offered_resources"].items())
        requested = ", ".join(f"{qty} {res}" for res, qty in parsed_offer["requested_resources"].items())
        return f"Offered items: {offered} -> Requested items: {requested}"

    def _determine_winner(self):
        if not self.state.done:
            if self.state.game_state["inventory_value"][0]["change"] == self.state.game_state["inventory_value"][1]["change"]:
                self.state.set_draw(reason=self.t("outcome", "draw"))
            else:
                winner_id = 0 if (self.state.game_state["inventory_value"][0]["change"] > self.state.game_state["inventory_value"][1]["change"]) else 1
                self.state.set_winner(player_id=winner_id, reason=self.t("outcome", "win", winner_id=winner_id))

    def _update_inventory_values(self):
        for player_id in range(self.state.num_players):
            current_inventory_value = self._calculate_player_inventory_value(player_id=player_id, game_state=self.state.game_state) # Calculate current inventory value
            self.state.game_state["inventory_value"][player_id]["current"] = current_inventory_value
            self.state.game_state["inventory_value"][player_id]["change"] = current_inventory_value - self.state.game_state["inventory_value"][player_id]["initial"]

    def _calculate_player_inventory_value(self, player_id: int, game_state: Dict[str, Any]) -> float:
        return sum([qty * game_state["player_values"][player_id][res] for res, qty in game_state["player_resources"][player_id].items()])
