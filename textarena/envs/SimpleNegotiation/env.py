import re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta
from textarena.envs.SimpleNegotiation.renderer import create_board_str


class SimpleNegotiationEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    def __init__(self, max_turns: Optional[int] = 10):
        if max_turns is not None and (
            not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0
        ):
            raise ValueError("max_turns must be a positive integer or None")
        self.max_turns = max_turns
        self.resource_names = ["Wheat", "Wood", "Sheep", "Brick", "Ore"]
        self.base_values = {"Wheat": 5, "Wood": 10, "Sheep": 15, "Brick": 25, "Ore": 40}
        # Canonical commands must occupy their own line. Bracketed forms remain
        # accepted only for backwards compatibility.
        self.accept_pattern = re.compile(r"^\s*(?:Accept|\[\s*Accept\s*\])\s*$", re.IGNORECASE)
        self.deny_pattern = re.compile(r"^\s*(?:Deny|\[\s*Deny\s*\])\s*$", re.IGNORECASE)
        self.offer_pattern = re.compile(
            r"^\s*(?:"
            r"Offer\s*:\s*(?P<bare>[^\[\]\r\n]+?)"
            r"|\[\s*Offer:?\s*(?:I\s+(?:give|offer)\s+)?(?P<legacy>[^\[\]\r\n]+?)\s*\]"
            r")\s*$",
            re.IGNORECASE,
        )

    def get_board_str(self):
        return create_board_str(
            player_resources=self.game_state["player_resources"], player_values=self.game_state["player_values"],
            inventory_values=self.game_state["inventory_value"], current_offer=self.game_state["current_offer"],
            viewer_id=self.state.current_player_id,
        )

    def setup(self) -> Dict[str, Any]:
        player_resources = {0: {resource: self.rng.randint(5, 25) for resource in self.resource_names}, 1: {resource: self.rng.randint(5, 25) for resource in self.resource_names}}
        game_state = {"current_offer": None, "player_resources": player_resources, "player_values": {}, "trade_history": []}

        # Generate player-specific values for each resource type (±20% of base value, capped at 5 and 40)
        for player_id in [0, 1]:
            game_state["player_values"][player_id] = {}
            for resource in self.resource_names:
                base_value = self.base_values[resource]
                variation = int(0.2 * base_value)
                min_value = max(base_value - variation, 5)
                max_value = min(base_value + variation, 40)
                value = self.rng.randint(min_value, max_value)
                game_state["player_values"][player_id][resource] = value

        # Keep track of the inventory (both initial and current)
        for player_id in [0, 1]:
            initial_value = self._calculate_player_inventory_value(player_id, game_state)
            game_state.setdefault("inventory_value", {})[player_id] = {"initial": initial_value, "current": initial_value, "change": 0}
        return game_state

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        resource_value_list = "\n\t+ ".join(
            [f"{f'[{res}]':{' '}<8}  Qty: {game_state['player_resources'][player_id][res]:{' '}<2}   Value: {game_state['player_values'][player_id][res]}" for res in game_state['player_resources'][player_id].keys()]
        )
        return (
            f"You are Player {player_id} in the Negotiation Game.\nYou have some resources, and your task is to trade such that the total value of your resources increases.\n"
            f"The resources and associated values you currently have are:\n\t+ {resource_value_list}\nAt each turn, you can talk to your opponent and make a trade offer.\n"
            "Put any structured command on its own line:\n"
            "  - Offer: 3 Sheep, 2 Ore -> 5 Brick, 2 Sheep\n"
            "  - Accept — accept an incoming offer.\n"
            "  - Deny — deny an incoming offer (default).\n"
            f"The game lasts for {self.max_turns} turns in total."
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state

        command, command_match, parse_error = self._extract_command(action)
        if parse_error is not None:
            return self.invalid(parse_error)

        # Parse and validate any new offer up front so an invalid move never mutates state.
        parsed_offer = None
        if command == "offer":
            offer_text = command_match.group("bare") or command_match.group("legacy")
            parsed_offer = self._parse_offer(offer_text.strip())
            if not parsed_offer:
                return self.invalid(f"Player {player_id} made a trade offer in an incorrect format.")
            if not self._check_if_sufficient_resources(trade_resources=parsed_offer["offered_resources"], player_resources=gs["player_resources"][player_id]):
                return self.invalid(f"Player {player_id} tried to make a trade offer without having the necessary resources.")

        # Respond to an existing offer
        current_offer = gs["current_offer"]
        if command in {"accept", "deny"} and current_offer is None:
            return self.invalid(f"There is no current offer to {command}.")
        if current_offer and current_offer["to_player"] != player_id:
            return self.invalid("Only the intended recipient may respond to the current offer.")

        if current_offer and command == "accept":
            if not self._check_if_sufficient_resources(trade_resources=current_offer["requested_resources"], player_resources=gs["player_resources"][player_id]):
                return self.invalid("Player tried accepting a trade without having the necessary resources.")
            proposer_id = current_offer["from_player"]
            if not self._check_if_sufficient_resources(
                trade_resources=current_offer["offered_resources"],
                player_resources=gs["player_resources"][proposer_id],
            ):
                return self.invalid("The proposer no longer has the resources required for this trade.")
            self._execute_trade(acceptor_id=player_id)
            return None
        elif current_offer:
            self.broadcast(f"Player {player_id} rejected the trade offer.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self._mark_current_offer("Rejected")
            gs["current_offer"] = None

        # Register the new offer (if any)
        if parsed_offer:
            gs["current_offer"] = {
                "from_player": player_id, "to_player": 1 - player_id,
                "offered_resources": parsed_offer["offered_resources"], "requested_resources": parsed_offer["requested_resources"]
            }
            gs["trade_history"].append({
                "from_player": player_id, "to_player": 1 - player_id, "offered_resources": parsed_offer["offered_resources"],
                "requested_resources": parsed_offer["requested_resources"], "outcome": None  # To be updated upon acceptance
            })
            self.broadcast(f"Player {player_id} made the following offer to Player {1 - player_id}: {self._offer_to_str(parsed_offer)}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            self.broadcast(f"Player {player_id} made no new trade offer.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None

    def _extract_command(
        self, action: str
    ) -> Tuple[Optional[str], Optional[re.Match], Optional[str]]:
        """Return the one structured command present in an otherwise free-text message."""
        commands = []
        for line in action.splitlines():
            if self.accept_pattern.fullmatch(line):
                commands.append(("accept", None))
            elif self.deny_pattern.fullmatch(line):
                commands.append(("deny", None))
            else:
                offer_match = self.offer_pattern.fullmatch(line)
                if offer_match:
                    commands.append(("offer", offer_match))
                elif re.match(r"^\s*\[?\s*(?:Accept|Deny|Offer)\b", line, re.IGNORECASE):
                    return None, None, "Malformed structured command."

        if len(commands) > 1:
            return None, None, "Submit at most one structured command per turn."
        if not commands:
            return None, None, None
        command, match = commands[0]
        return command, match, None

    def _execute_trade(self, acceptor_id: int) -> None:
        """Execute the currently pending trade (already validated)."""
        gs = self.game_state
        current_offer = gs["current_offer"]
        proposer_id = current_offer["from_player"]
        for resource, qty in current_offer["offered_resources"].items():
            gs["player_resources"][proposer_id][resource] -= qty
            gs["player_resources"][acceptor_id][resource] += qty
        for resource, qty in current_offer["requested_resources"].items():
            gs["player_resources"][acceptor_id][resource] -= qty
            gs["player_resources"][proposer_id][resource] += qty
        self.broadcast(f"Player {acceptor_id} accepted the trade offer from Player {proposer_id}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._mark_current_offer("Accepted")
        self._update_inventory_values()
        gs["current_offer"] = None

    def _mark_current_offer(self, outcome: str) -> None:
        current_offer = self.game_state["current_offer"]
        if current_offer is None:
            return
        for entry in reversed(self.game_state["trade_history"]):
            if (
                entry["outcome"] is None
                and entry["from_player"] == current_offer["from_player"]
                and entry["to_player"] == current_offer["to_player"]
            ):
                entry["outcome"] = outcome
                return

    def _check_if_sufficient_resources(self, trade_resources: Dict[str, int], player_resources: Dict[str, int]) -> bool:
        """ Check if a player has sufficient resources for a trade """
        for resource, qty in trade_resources.items():
            if player_resources.get(resource, 0) < qty: return False
        return True

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
        except Exception:
            return None

    def _parse_resource_list(self, resource_str: str) -> Optional[Dict[str, int]]:
        token_re = re.compile(r'(\d+)\s+([A-Za-z]+)', re.IGNORECASE)
        matches = list(token_re.finditer(resource_str))
        if not matches: return None # nothing recognised
        leftovers = token_re.sub("", resource_str)
        leftovers = re.sub(r"(?:\s|,|\band\b)+", "", leftovers, flags=re.IGNORECASE)
        if leftovers:
            return None
        resources: Dict[str, int] = {}
        aliases = {
            "Wheats": "Wheat", "Woods": "Wood", "Sheeps": "Sheep",
            "Bricks": "Brick", "Ores": "Ore",
        }
        for match in matches:
            qty_str, raw_name = match.groups()
            qty = int(qty_str)
            name = aliases.get(raw_name.title(), raw_name.title())
            if name not in self.resource_names or qty <= 0: return None # invalid entry
            resources[name] = resources.get(name, 0) + qty
        return resources

    def _offer_to_str(self, parsed_offer: Dict[str, Dict[str, int]]) -> str:
        offered = ", ".join(f"{qty} {res}" for res, qty in parsed_offer["offered_resources"].items())
        requested = ", ".join(f"{qty} {res}" for res, qty in parsed_offer["requested_resources"].items())
        return f"Offered items: {offered} -> Requested items: {requested}"

    def on_turn_limit(self) -> ta.Outcome:
        inventory_value = self.game_state["inventory_value"]
        if inventory_value[0]["change"] == inventory_value[1]["change"]:
            return self.draw(reason="Same change in inventory value for all players. Draw.")
        winner_id = 0 if (inventory_value[0]["change"] > inventory_value[1]["change"]) else 1
        return self.winner(winner_id, reason=f"Player {winner_id} won by having a larger gain in inventory value.")

    def _update_inventory_values(self):
        for player_id in range(self.state.num_players):
            current_inventory_value = self._calculate_player_inventory_value(player_id=player_id, game_state=self.game_state) # Calculate current inventory value
            self.game_state["inventory_value"][player_id]["current"] = current_inventory_value
            self.game_state["inventory_value"][player_id]["change"] = current_inventory_value - self.game_state["inventory_value"][player_id]["initial"]

    def _calculate_player_inventory_value(self, player_id: int, game_state: Dict[str, Any]) -> float:
        return sum([qty * game_state["player_values"][player_id][res] for res, qty in game_state["player_resources"][player_id].items()])
