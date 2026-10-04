import re
import copy
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class NegotiationEnv(ta.GameEnv):
    """
    N-player Negotiation Game with the ability to:
      - broadcast messages,
      - send private messages,
      - make multiple offers to specific opponents,
      - accept/deny multiple pending offers.
    """

    min_players = 2
    max_players = 15
    broadcast_actions = False  # raw actions are echoed only to their author; tokens are re-emitted below

    # Canonical bare commands. Each command occupies one line or semicolon-delimited segment.
    bare_broadcast_pattern = re.compile(r"^Broadcast\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
    bare_whisper_pattern = re.compile(
        r"^Whisper\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    bare_offer_pattern = re.compile(
        r"^Offer\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:?\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    bare_accept_pattern = re.compile(r"^Accept\s*#?\s*(\d+)$", re.IGNORECASE)
    bare_deny_pattern = re.compile(r"^Deny\s*#?\s*(\d+)$", re.IGNORECASE)

    # Legacy bracketed commands retained for backwards compatibility.
    # Broadcast supports three historical alternatives:
    #   A: [Broadcast: message] inside the brackets
    #   B: [Broadcast message] inside the brackets (no colon)
    #   C: [Broadcast] message (outside the brackets)
    broadcast_pattern = re.compile(
        r"(?:"
        r"\s*\[Broadcast\s*:\s*(.+?)\]"           # Alternative A: colon present.
        r"|"
        r"\s*\[Broadcast((?:\s+).+?)\]"           # Alternative B: no colon, whitespace inside.
        r"|"
        r"\s*\[Broadcast\](\s+.+?)(?=\s*\[|$)"    # Alternative C: message appears after the bracket.
        r")",
        re.IGNORECASE | re.DOTALL
    )

    # Whisper: require a player id and a colon
    whisper_pattern = re.compile(r"\s*\[Whisper\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:\s*(.+?)\]", re.IGNORECASE | re.DOTALL)

    offer_pattern = re.compile(r"\[Offer\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:?\s*(.+?)\]", re.IGNORECASE | re.DOTALL)
    accept_pattern = re.compile(r"\[Accept\s*#?\s*(\d+)\]", re.IGNORECASE)
    deny_pattern = re.compile(r"\[Deny\s*#?\s*(\d+)\]", re.IGNORECASE)

    def __init__(self, turn_multiple: int = 3):
        """
        Initialize the N-player Negotiation Game environment.

        Args:
            turn_multiple (int): Number of turns per player
        """
        if not isinstance(turn_multiple, int) or isinstance(turn_multiple, bool) or turn_multiple <= 0:
            raise ValueError("turn_multiple must be a positive integer")
        self.resource_names = ["Wheat", "Wood", "Sheep", "Brick", "Ore"]
        self.base_values = {"Wheat": 5, "Wood": 10, "Sheep": 15, "Brick": 25, "Ore": 40}
        self.turn_multiple = turn_multiple

    @property
    def terminal_render_keys(self):
        return ["player_resources", "player_values", "pending_offers"]

    def reset(self, num_players: int, seed: Optional[int] = None):
        if not 2 <= num_players <= 15:
            raise ValueError(f"The number of players has to be between 2 and 15, received {num_players}")
        self.max_turns = int(num_players * self.turn_multiple)
        super().reset(num_players=num_players, seed=seed)

    def setup(self) -> Dict[str, Any]:
        # Initialize each player's resources to random amounts and each player's private resource values
        player_resources, player_values = {}, {}
        for pid in range(self.state.num_players):
            player_resources[pid] = {r: self.rng.randint(5, 25) for r in self.resource_names}
            # random personal valuations (±20% around base, but clamp 5..40)
            player_values[pid] = {}
            for r in self.resource_names:
                base = self.base_values[r]
                variation = int(0.2 * base)
                low, high = max(5, base - variation), min(40, base + variation)
                player_values[pid][r] = self.rng.randint(low, high)
        return {
            "player_resources": player_resources,
            "player_values": player_values,
            "pending_offers": {},
            "offer_id_counter": 0,
        }

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        resources = game_state["player_resources"][player_id]
        valuations = game_state["player_values"][player_id]
        resource_lines = [f"- {resources[r]} x {r} (value: {valuations[r]} each)" for r in self.resource_names]
        resource_str = "\n".join(resource_lines)

        prompt = (
            f"You are Player {player_id} in a multi-player game of Negotiation with {self.state.num_players} players.\n"
            f"You have:\n{resource_str}\n\n"
            "You can broadcast messages, privately message someone, or make trade offers.\n"
            "You can also accept or deny any offers you received previously.\n"
            f"Your personal valuations are shown above; your goal is to maximize your total resource value.\n"
            "Available actions:\n"
            "  'Broadcast: Some message' - Send a message to all players\n"
            "  'Whisper X: Some message' - Send a private message to a specific player\n"
            "  'Offer to X: 2 Wheat -> 3 Wood' - Make a single trade offer to a specific player\n"
            "  'Accept #X' or 'Deny #X' - Accept or deny a single trade offer\n"
            "To combine commands in one turn, put each command on its own line or separate them with semicolons.\n"
        )
        if self.state.max_turns is not None:
            prompt += f"Game ends after {self.state.max_turns} turns.\n"
        return prompt

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        failure_reason = self._process_action(player_id, action)
        if failure_reason is None:
            return None
        if self.state.error_count >= self.state.error_allowance:
            # The player already used up their warning: forfeit the turn (counts as a
            # normal turn, play rotates on) instead of eliminating them.
            self.state.game_info[player_id]["invalid_move"] = True
            return None
        return self.invalid(failure_reason)

    def _process_action(self, player_id: int, action: str) -> Optional[str]:
        """Process every command in the action. All effects are simulated first and only
        committed (with their observations) if no command is invalid; returns the first
        failure reason otherwise."""
        gs = self.game_state
        resources = copy.deepcopy(gs["player_resources"])
        pending = copy.deepcopy(gs["pending_offers"])
        offer_counter = gs["offer_id_counter"]
        events: List[Tuple[int, int, str, ta.ObservationType]] = []  # (to_id, from_id, message, type)

        malformed = self._find_malformed_bare_command(action)
        if malformed is not None:
            return malformed

        # 1. broadcasts (never invalid; empty ones are skipped)
        for msg_content in self._parse_broadcast(action):
            if msg_content.strip():
                events.append((-1, player_id, f"(Broadcast) Player {player_id} says:{msg_content}", ta.ObservationType.PLAYER_ACTION))

        # 2. private messages
        for target_str, msg_content in self._parse_whisper(action):
            msg_content = msg_content.strip()
            target_pid = int(target_str)
            if target_pid not in range(self.state.num_players):
                return f"Attempted to message a non-existent player {target_pid}."
            if target_pid == player_id:
                return "You cannot send a private message to yourself."
            if not msg_content:
                return "Empty private message?"
            events.append((target_pid, player_id, f"(Private) Player {player_id} says:{msg_content}", ta.ObservationType.PLAYER_ACTION))

        # 3. offers
        for target_str, offer_str in self._parse_offers(action):
            offer_str = offer_str.strip()
            target_pid = int(target_str)
            if target_pid not in range(self.state.num_players):
                return f"Offer made to invalid player ID {target_pid}"
            if target_pid == player_id:
                return "You cannot make a trade offer to yourself."

            parts = re.split(r"->", offer_str)  # e.g. "2 Wood -> 1 Ore"
            if len(parts) != 2:
                return f"Cannot parse Offer: '{offer_str}'. Must be like '2 Wheat -> 3 Wood'."
            offered_dict = self._parse_resource_list(parts[0].strip())
            requested_dict = self._parse_resource_list(parts[1].strip())
            if offered_dict is None or requested_dict is None:
                return f"Invalid resource format in offer: '{offer_str}'"
            if not self._check_sufficient_resources(player_id, offered_dict, resources):
                return f"You do not hold enough resources to offer {offered_dict} to Player {target_pid}."

            offer_counter += 1
            pending[offer_counter] = {
                "from": player_id,
                "to": target_pid,
                "offered_resources": offered_dict,
                "requested_resources": requested_dict,
            }
            events.append((-1, ta.GAME_ID, f"Offer #{offer_counter} created: Player {player_id} -> Player {target_pid}.", ta.ObservationType.GAME_ACTION_DESCRIPTION))
            events.append((
                target_pid, ta.GAME_ID,
                f"You have a new Offer ID #{offer_counter} from Player {player_id}: "
                f"{self._offer_to_str(offered_dict, requested_dict)}\n"
                f"You can reply with 'accept #{offer_counter}' or 'deny #{offer_counter}'.",
                ta.ObservationType.GAME_MESSAGE,
            ))

        # 4. accepts
        for offer_id_str in self._parse_offer_responses(action, self.accept_pattern, self.bare_accept_pattern):
            offer_id = int(offer_id_str)
            if offer_id not in pending:
                return f"Offer #{offer_id} does not exist."
            off = pending[offer_id]
            if off["to"] != player_id:
                return f"Offer #{offer_id} is not addressed to you."
            if not self._check_sufficient_resources(off["from"], off["offered_resources"], resources):
                # The offering player no longer has enough resources: the offer is canceled (not an invalid move)
                events.append((-1, ta.GAME_ID, f"Offer #{offer_id} canceled because Player {off['from']} no longer has enough resources to fulfill it.", ta.ObservationType.GAME_MESSAGE))
                del pending[offer_id]
                continue
            if not self._check_sufficient_resources(off["to"], off["requested_resources"], resources):
                return f"You do not have enough resources to fulfill Offer #{offer_id}."

            self._exchange_resources(off["from"], off["to"], off["offered_resources"], off["requested_resources"], resources)
            events.append((
                -1, ta.GAME_ID,
                f"Player {off['to']} ACCEPTED Offer #{offer_id} from Player {off['from']}: "
                f"{self._offer_to_str(off['offered_resources'], off['requested_resources'])}",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            ))
            del pending[offer_id]

        # 5. denies
        for offer_id_str in self._parse_offer_responses(action, self.deny_pattern, self.bare_deny_pattern):
            offer_id = int(offer_id_str)
            if offer_id not in pending:
                return f"Offer #{offer_id} does not exist."
            off = pending[offer_id]
            if off["to"] != player_id:
                return f"Offer #{offer_id} is not addressed to you."
            events.append((-1, ta.GAME_ID, f"Player {player_id} DENIED Offer #{offer_id} from Player {off['from']}.", ta.ObservationType.GAME_ACTION_DESCRIPTION))
            del pending[offer_id]

        # commit: everything was valid
        gs["player_resources"] = resources
        gs["pending_offers"] = pending
        gs["offer_id_counter"] = offer_counter
        for to_id, from_id, message, obs_type in events:
            if to_id == -1:
                self.broadcast(message, obs_type, from_id=from_id)
            else:
                self.message(to_id, message, obs_type, from_id=from_id)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self._determine_winner()

    # --- Helper Methods for Broadcasts and Whispers ---
    def _parse_broadcast(self, text: str) -> List[str]:
        """Extract canonical bare and legacy bracketed broadcast commands."""
        results = []
        for segment in self._bare_command_segments(text):
            match = self.bare_broadcast_pattern.fullmatch(segment)
            if match:
                results.append(" " + match.group(1).strip())
        for g1, g2, g3 in self.broadcast_pattern.findall(text):
            msg = g1 or g2 or g3
            if msg and msg.strip():
                if not msg.startswith(" "):
                    msg = " " + msg
                results.append(msg)
        return results

    def _parse_whisper(self, text: str) -> List[Tuple[str, str]]:
        """Extract canonical bare and legacy bracketed whisper commands."""
        results = []
        for segment in self._bare_command_segments(text):
            match = self.bare_whisper_pattern.fullmatch(segment)
            if match:
                results.append((match.group(1), " " + match.group(2).strip()))
        for pid_str, msg in self.whisper_pattern.findall(text):
            if msg and not msg.startswith(" "):
                msg = " " + msg
            results.append((pid_str, msg))
        return results

    def _parse_offers(self, text: str) -> List[Tuple[str, str]]:
        """Extract canonical bare and legacy bracketed offer commands."""
        results = []
        for segment in self._bare_command_segments(text):
            match = self.bare_offer_pattern.fullmatch(segment)
            if match:
                results.append(match.groups())
        results.extend(self.offer_pattern.findall(text))
        return results

    def _parse_offer_responses(self, text: str, bracketed_pattern, bare_pattern) -> List[str]:
        """Extract canonical bare and legacy bracketed offer responses."""
        results = []
        for segment in self._bare_command_segments(text):
            match = bare_pattern.fullmatch(segment)
            if match:
                results.append(match.group(1))
        results.extend(bracketed_pattern.findall(text))
        return results

    def _bare_command_segments(self, text: str) -> List[str]:
        return [segment.strip() for segment in re.split(r"[;\n]+", text) if segment.strip()]

    def _find_malformed_bare_command(self, text: str) -> Optional[str]:
        bare_patterns = {
            "Broadcast": self.bare_broadcast_pattern,
            "Whisper": self.bare_whisper_pattern,
            "Offer": self.bare_offer_pattern,
            "Accept": self.bare_accept_pattern,
            "Deny": self.bare_deny_pattern,
        }
        legacy_patterns = (
            self.broadcast_pattern,
            self.whisper_pattern,
            self.offer_pattern,
            self.accept_pattern,
            self.deny_pattern,
        )
        segments = self._bare_command_segments(text)
        if not segments:
            return "No command was provided."

        for segment in segments:
            if any(pattern.fullmatch(segment) for pattern in bare_patterns.values()):
                continue

            legacy_remainder = segment
            for pattern in legacy_patterns:
                legacy_remainder = pattern.sub("", legacy_remainder)
            if not legacy_remainder.strip():
                continue

            for command, pattern in bare_patterns.items():
                if re.match(rf"^{command}\b", segment, re.IGNORECASE) and not pattern.fullmatch(segment):
                    return f"Malformed {command} command."
            return f"Unrecognized command: {segment!r}."
        return None

    def _check_sufficient_resources(self, pid: int, needed: Dict[str, int], all_resources: Dict[int, Dict[str, int]]) -> bool:
        """Return True if player `pid` has at least `needed[resource]` of each resource."""
        for resource, qty in needed.items():
            if all_resources[pid].get(resource, 0) < qty:
                return False
        return True

    def _exchange_resources(self, from_pid: int, to_pid: int, offered: Dict[str, int], requested: Dict[str, int], res: Dict[int, Dict[str, int]]):
        """Move `offered` from `from_pid` to `to_pid` and `requested` the other way."""
        for r, q in offered.items():
            res[from_pid][r] -= q
            res[to_pid][r] += q
        for r, q in requested.items():
            res[to_pid][r] -= q
            res[from_pid][r] += q

    def _parse_resource_list(self, resource_str: str) -> Optional[Dict[str, int]]:
        """Parse e.g. "2 Wheat, 1 Ore" into {"Wheat": 2, "Ore": 1}. Returns None on parse error."""
        items = re.split(r",\s*|\s+and\s+", resource_str, flags=re.IGNORECASE)
        parsed = {}
        for item in items:
            item = item.strip()
            if not item:
                continue
            match = re.match(r"(\d+)\s+(.+)", item)  # "<qty> <ResourceName>"
            if not match:
                return None
            qty_str, rname = match.groups()
            qty = int(qty_str)
            rname = rname.strip().title()
            if rname not in self.resource_names:
                return None
            if qty <= 0:
                return None
            parsed[rname] = parsed.get(rname, 0) + qty
        return parsed if parsed else None

    def _offer_to_str(self, offered: Dict[str, int], requested: Dict[str, int]) -> str:
        off_str = ", ".join(f"{q} {r}" for r, q in offered.items())
        req_str = ", ".join(f"{q} {r}" for r, q in requested.items())
        return f"{off_str} -> {req_str}"

    def _determine_winner(self) -> ta.Outcome:
        """Score each player's inventory at their own valuations; highest value wins."""
        final_values = {pid: self._calculate_inventory_value(pid, self.game_state) for pid in range(self.state.num_players)}
        best_pid = max(final_values, key=final_values.get)
        best_val = final_values[best_pid]
        winners = [p for p, v in final_values.items() if v == best_val]
        if len(winners) == 1:
            return self.winner(best_pid, reason=f"Player {best_pid} wins with a total value of {best_val}!")
        return self.draw(reason=f"Tie among players {winners} with value {best_val}.")

    def _calculate_inventory_value(self, pid: int, game_state: Dict[str, Any]) -> int:
        """Sum of (count_of_resource * that_player's_value_for_resource)."""
        resources = game_state["player_resources"][pid]
        values = game_state["player_values"][pid]
        return sum(resources[r] * values[r] for r in self.resource_names)
