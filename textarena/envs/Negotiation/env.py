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

    # Canonical bare commands. Each command occupies one line or semicolon-separated segment.
    bare_broadcast_pattern = re.compile(r"^Broadcast\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
    bare_whisper_pattern = re.compile(
        r"^Whisper\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    bare_offer_pattern = re.compile(
        r"^Offer\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:?\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    bare_accept_pattern = re.compile(r"^Accept\s*(?:#\s*)?(\d+)$", re.IGNORECASE)
    bare_deny_pattern = re.compile(r"^Deny\s*(?:#\s*)?(\d+)$", re.IGNORECASE)

    bare_patterns = {
        "Broadcast": bare_broadcast_pattern,
        "Whisper": bare_whisper_pattern,
        "Offer": bare_offer_pattern,
        "Accept": bare_accept_pattern,
        "Deny": bare_deny_pattern,
    }
    # Line breaks always separate commands, but a semicolon only does when a command follows it,
    # so message text may contain semicolons.
    command_separator = re.compile(r";\s*(?=(?:Broadcast|Whisper|Offer|Accept|Deny)\b)", re.IGNORECASE)
    # The lookbehind keeps the trailing alternative from restarting at every character of an inner
    # whitespace run, which is quadratic.
    segment_padding = re.compile(r"^[\s;]+|(?<![\s;])[\s;]+$")

    turn_multiple = ta.Param(
        3, "The turns per player, so the game lasts `num_players × turn_multiple` turns.", min=1,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resource_names = ["Wheat", "Wood", "Sheep", "Brick", "Ore"]
        self.base_values = {"Wheat": 5, "Wood": 10, "Sheep": 15, "Brick": 25, "Ore": 40}

    def setup(self) -> Dict[str, Any]:
        self.state.max_turns = self.state.num_players * self.turn_multiple
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
            "Messages may contain semicolons, but a semicolon followed by a command name (e.g. '; Offer') starts a new command.\n"
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
            self.message(
                player_id,
                f"Your action was invalid again and your turn is forfeited. Reason: {failure_reason}",
                ta.ObservationType.GAME_ADMIN,
            )
            return None
        return self.invalid(failure_reason)

    def _process_action(self, player_id: int, action: str) -> Optional[str]:
        """Process every command in the action. All effects are simulated first and only
        committed (with their observations) if no command is invalid; returns the first
        failure reason otherwise."""
        gs = self.game_state
        commands, failure_reason = self._parse_commands(action)
        if failure_reason is not None:
            return failure_reason
        resources = copy.deepcopy(gs["player_resources"])
        pending = copy.deepcopy(gs["pending_offers"])
        offer_counter = gs["offer_id_counter"]
        events: List[Tuple[int, int, str, ta.ObservationType]] = []  # (to_id, from_id, message, type)

        # 1. broadcasts (never invalid; empty ones are skipped)
        for (msg_content,) in commands["Broadcast"]:
            msg_content = self.strip_role_tags(msg_content).strip()
            if msg_content:
                events.append((-1, player_id, f"(Broadcast) Player {player_id} says: {msg_content}", ta.ObservationType.PLAYER_ACTION))

        # 2. private messages
        for target_str, msg_content in commands["Whisper"]:
            msg_content = self.strip_role_tags(msg_content).strip()
            target_pid = self._parse_number(target_str)
            if target_pid is None or target_pid not in range(self.state.num_players):
                return f"Attempted to message a non-existent player {target_str}."
            if target_pid == player_id:
                return "You cannot send a private message to yourself."
            if not msg_content:
                return "Empty private message?"
            events.append((target_pid, player_id, f"(Private) Player {player_id} says: {msg_content}", ta.ObservationType.PLAYER_ACTION))

        # 3. offers
        for target_str, offer_str in commands["Offer"]:
            offer_str = offer_str.strip()
            target_pid = self._parse_number(target_str)
            if target_pid is None or target_pid not in range(self.state.num_players):
                return f"Offer made to invalid player ID {target_str}"
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
        for (offer_id_str,) in commands["Accept"]:
            offer_id = self._parse_number(offer_id_str)
            if offer_id not in pending:
                return f"Offer #{offer_id_str} does not exist."
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
        for (offer_id_str,) in commands["Deny"]:
            offer_id = self._parse_number(offer_id_str)
            if offer_id not in pending:
                return f"Offer #{offer_id_str} does not exist."
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

    # --- Command parsing ---
    def _parse_commands(self, text: str) -> Tuple[Dict[str, List[tuple]], Optional[str]]:
        """Group the action's commands by type; returns a failure reason instead if any part is not a complete command."""
        commands: Dict[str, List[tuple]] = {name: [] for name in self.bare_patterns}
        segments = self._command_segments(text)
        if not segments:
            return commands, "No command was provided."
        for segment in segments:
            parsed = self._parse_segment(segment)
            if parsed is None:
                return commands, self._describe_invalid_segment(segment)
            name, groups = parsed
            commands[name].append(groups)
        return commands, None

    def _command_segments(self, text: str) -> List[str]:
        segments = []
        for line in text.splitlines():
            for segment in self.command_separator.split(line):
                segment = self.segment_padding.sub("", segment)
                if segment:
                    segments.append(segment)
        return segments

    def _parse_segment(self, segment: str) -> Optional[Tuple[str, tuple]]:
        """Parse one command; None if the segment is anything else.

        Each segment is parsed exactly once, so message text is never scanned for commands."""
        for name, pattern in self.bare_patterns.items():
            match = pattern.fullmatch(segment)
            if match:
                return name, match.groups()
        return None

    def _describe_invalid_segment(self, segment: str) -> str:
        command = re.match(r"(Broadcast|Whisper|Offer|Accept|Deny)\b", segment, re.IGNORECASE)
        if command:
            return (
                f"Malformed {command.group(1).capitalize()} command: {segment!r}. "
                "(A line break, or a semicolon followed by a command name, starts a new command.)"
            )
        return f"Unrecognized command: {segment!r}."

    @staticmethod
    def _parse_number(digits: str) -> Optional[int]:
        """Parse a player id, offer id, or quantity; None if it has implausibly many digits."""
        significant = digits.lstrip("0") or "0"
        return int(significant) if len(significant) <= 18 else None

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
        items = re.split(r",\s*|(?<!\s)\s+and\s+", resource_str, flags=re.IGNORECASE)
        parsed = {}
        for item in items:
            item = item.strip()
            if not item:
                continue
            match = re.match(r"(\d+)\s+(.+)", item)  # "<qty> <ResourceName>"
            if not match:
                return None
            qty_str, rname = match.groups()
            qty = self._parse_number(qty_str)
            rname = rname.strip().title()
            if rname not in self.resource_names:
                return None
            if qty is None or qty <= 0:
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
