import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.BlindAuction.renderer import create_board_str


class BlindAuctionEnv(ta.GameEnv):
    """
    N-player Blind Auction game with conversation phase followed by bidding phase.
    Players can:
    - Broadcast messages to all players
    - Send private messages to specific players
    - Submit bids for multiple items (during bidding phase)
    """

    min_players = 3
    max_players = 15
    broadcast_actions = False  # raw actions are echoed only to their author; messages are re-emitted below

    # Canonical bare commands. Each command occupies one line or semicolon-separated segment.
    bare_broadcast_pattern = re.compile(r"^Broadcast\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
    bare_whisper_pattern = re.compile(
        r"^Whisper\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    bare_bid_pattern = re.compile(
        r"^Bid\s+(?:on\s+)?(?:Item\s+)?(\d+)\s*:\s*(\d+)$",
        re.IGNORECASE,
    )

    bare_patterns = {"Broadcast": bare_broadcast_pattern, "Whisper": bare_whisper_pattern, "Bid": bare_bid_pattern}
    command_name_pattern = re.compile(r"(Broadcast|Whisper|Bid)\b", re.IGNORECASE)
    # Line breaks always separate commands, but a semicolon only does when a command follows it,
    # so message text may contain semicolons.
    command_separator = re.compile(r";\s*(?=(?:Broadcast|Whisper|Bid)\b)", re.IGNORECASE)
    # The lookbehind keeps the trailing alternative from restarting at every character of an inner
    # whitespace run, which is quadratic.
    segment_padding = re.compile(r"^[\s;]+|(?<![\s;])[\s;]+$")

    def __init__(
        self,
        starting_capital: int = 1000,
        num_items: int = 5,
        conversation_rounds: int = 3,
        base_item_values: Optional[List[int]] = None
    ):
        """
        Initialize a BlindAuction game environment.

        Args:
            starting_capital (int): Starting capital for each player.
            num_items (int): Number of items to auction.
            conversation_rounds (int): Number of rounds for conversation phase.
            base_item_values (Optional[List[int]]): Base values for items. If None, will be generated.
        """
        if not isinstance(starting_capital, int) or isinstance(starting_capital, bool) or starting_capital <= 0:
            raise ValueError("starting_capital must be a positive integer")
        if not isinstance(num_items, int) or isinstance(num_items, bool) or num_items <= 0:
            raise ValueError("num_items must be a positive integer")
        if not isinstance(conversation_rounds, int) or isinstance(conversation_rounds, bool) or conversation_rounds < 0:
            raise ValueError("conversation_rounds must be a non-negative integer")
        if base_item_values is not None:
            if not isinstance(base_item_values, (list, tuple)) or any(
                not isinstance(value, int) or isinstance(value, bool) or value <= 0
                for value in base_item_values
            ):
                raise ValueError("base_item_values must be a sequence of positive integers")
        self.starting_capital = starting_capital
        self.num_items = num_items
        self.conversation_rounds = conversation_rounds
        self.base_item_values = list(base_item_values) if base_item_values is not None else None

        # Item names for flavor
        self.item_names = [
            "Ancient Vase", "Diamond Necklace", "Antique Clock", "Signed Painting",
            "Gold Statue", "Rare Manuscript", "Silver Chalice", "Vintage Watch",
            "Jade Figurine", "Bronze Sculpture", "Crystal Decanter", "Royal Tapestry",
            "Emerald Ring", "Ivory Chess Set", "Pearl Earrings", "Platinum Coin Collection",
            "Ruby Brooch", "Sapphire Tiara", "Telescope", "Amber Fossil"
        ]

    def get_board_str(self):
        return create_board_str(
            game_state=self.state.game_state,
            viewer_id=self.state.current_player_id,
            reveal_all=self.state.done,
        )

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players

        if self.base_item_values is None:
            base_item_values = [self.rng.randint(50, 500) for _ in range(self.num_items)]
        else:
            base_item_values = list(self.base_item_values[:self.num_items])
            while len(base_item_values) < self.num_items:
                base_item_values.append(self.rng.randint(50, 500))

        available_names = self.item_names + [
            f"Mystery Item {i}" for i in range(len(self.item_names), self.num_items)
        ]

        # Assign item names for this game (randomized order)
        item_names = self.rng.sample(available_names, self.num_items)

        # Generate player-specific item values (±20% around base values)
        player_item_values = {}
        for pid in range(num_players):
            player_item_values[pid] = {}
            for i, base_value in enumerate(base_item_values):
                variation = base_value // 5
                min_value = max(1, base_value - variation)
                max_value = base_value + variation
                player_item_values[pid][i] = self.rng.randint(min_value, max_value)

        return {
            "phase": "conversation" if self.conversation_rounds > 0 else "bidding",
            "round": 1,  # Current conversation round
            "item_names": item_names[:self.num_items],
            "base_item_values": base_item_values,
            "player_item_values": player_item_values,
            "remaining_capital": {pid: self.starting_capital for pid in range(num_players)},
            "player_bids": {pid: {} for pid in range(num_players)},  # {player_id: {item_id: bid_amount}}
            "auction_results": None,  # Will be populated after bidding phase
            "conversations_completed": 0,  # Track completed conversation turns
            "bidding_done": {pid: False for pid in range(num_players)},
        }

    def on_start(self):
        if self.conversation_rounds == 0:
            self._announce_bidding_phase()

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        item_values = []
        for i in range(self.num_items):
            item_name = game_state["item_names"][i]
            value = game_state["player_item_values"][player_id][i]
            item_values.append(f"- Item {i}: {item_name} - Value to you: {value} coins")
        items_str = "\n".join(item_values)

        return (
            f"Welcome to the Blind Auction, Player {player_id}!\n\n"
            f"You have {self.starting_capital} coins to bid on {self.num_items} valuable items.\n\n"
            f"The auction has two phases:\n"
            f"1. Conversation Phase ({self.conversation_rounds} rounds): Talk with other players to gather information or make deals.\n"
            f"2. Bidding Phase (1 round): Submit blind bids on items. Highest bidder wins each item.\n\n"
            f"Available Items (with their value TO YOU):\n{items_str}\n\n"
            f"Note: Each player may value items differently, up to ±20% difference!\n\n"
            f"Available Commands:\n"
            f"- Conversation Phase:\n"
            f"  'Broadcast: message' - Send a message to all players\n"
            f"  'Whisper X: message' - Send a private message to Player X\n"
            f"  You can send several messages per turn, one per line. Messages may contain semicolons, "
            f"but a semicolon followed by a command name starts a new command.\n\n"
            f"- Bidding Phase:\n"
            f"  'Bid Item X: amount' - Bid the specified amount on Item X\n"
            f"  To submit multiple bids, put each bid on its own line or separate bids with semicolons.\n\n"
            f"The winner is the player with the highest net worth (total subjective item value + remaining coins)."
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if gs["phase"] == "conversation":
            failure_reason = self._handle_conversation_action(player_id, action)
        else:
            failure_reason = self._handle_bidding_action(player_id, action)

        if failure_reason is not None:
            return self.invalid(failure_reason)

        if gs["phase"] == "conversation":
            gs["conversations_completed"] += 1
            gs["round"] = min(
                self.conversation_rounds,
                gs["conversations_completed"] // self.state.num_players + 1,
            )
            if gs["conversations_completed"] >= self.conversation_rounds * self.state.num_players:
                self._transition_to_bidding_phase()
            return None
        gs["bidding_done"][player_id] = True
        if all(gs["bidding_done"].values()):
            return self._determine_auction_results()
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """Forfeit one phase action without eliminating a player from an N-player game."""
        gs = self.game_state
        self.message(
            player_id,
            f"You made too many invalid moves in a row and your {'message' if gs['phase'] == 'conversation' else 'bid'} "
            f"turn is forfeited. Reason: {reason}",
            ta.ObservationType.GAME_ADMIN,
        )
        self.state.game_info[player_id]["turn_count"] += 1
        self.state.turn += 1
        if gs["phase"] == "conversation":
            gs["conversations_completed"] += 1
            if gs["conversations_completed"] >= self.conversation_rounds * self.state.num_players:
                self._transition_to_bidding_phase()
        else:
            gs["bidding_done"][player_id] = True
            if all(gs["bidding_done"].values()):
                return self._determine_auction_results()
        next_player = self.state.next_alive_player(after=player_id)
        if next_player is not None:
            self.set_next_player(next_player)
        return None

    def _handle_conversation_action(self, player_id: int, action: str) -> Optional[str]:
        """Process conversation phase actions (broadcasts and whispers). Nothing is
        emitted unless every command is valid; returns the failure reason otherwise."""
        commands, other_segments = self._parse_commands(action)
        for segment in other_segments:
            malformed = self._malformed_command_reason(segment)
            if malformed is not None:
                return malformed
        if commands["Bid"]:
            return "Bid commands are only allowed during the bidding phase."
        if other_segments:
            return "Conversation actions may contain only complete Broadcast or Whisper commands."
        events = []
        for (msg,) in commands["Broadcast"]:
            msg = self.strip_role_tags(msg).strip()
            if msg:
                events.append((-1, f"(Broadcast) Player {player_id} says: {msg}"))
        for target_pid_str, msg in commands["Whisper"]:
            target_pid = self._parse_number(target_pid_str)
            if target_pid is None or target_pid not in range(self.state.num_players):
                return f"Attempted to whisper to non-existent Player {target_pid_str}."
            if target_pid == player_id:
                return "You cannot whisper to yourself."
            msg = self.strip_role_tags(msg).strip()
            if msg:
                events.append((target_pid, f"(Private) Player {player_id} says: {msg}"))
        if not events:
            return "Submit at least one Broadcast or Whisper command during conversation."

        for to_id, message in events:
            if to_id == -1:
                self.broadcast(message, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            else:
                self.message(to_id, message, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        return None

    def _handle_bidding_action(self, player_id: int, action: str) -> Optional[str]:
        """Process bidding phase actions. Bids are recorded only if every bid command is
        valid and the total is affordable; returns the failure reason otherwise."""
        gs = self.game_state
        commands, other_segments = self._parse_commands(action)
        names = [self._command_name(segment) for segment in other_segments]
        if "Bid" in names:
            return self._malformed_command_reason(other_segments[names.index("Bid")])
        if commands["Broadcast"] or commands["Whisper"] or any(names):
            return "Communication commands are not allowed during the bidding phase."
        if gs["bidding_done"][player_id]:
            return "You have already submitted your sealed bids."
        bids = commands["Bid"]

        if not bids:  # not bidding is allowed
            self.broadcast(f"Player {player_id} submitted no bids this turn.", ta.ObservationType.GAME_MESSAGE)
            return None
        if other_segments:
            return "A bid submission may contain only complete Bid commands."

        total_bid_amount = 0
        valid_bids = []
        seen_items = set()
        for item_id_str, bid_amount_str in bids:
            try:
                item_id, bid_amount = int(item_id_str), int(bid_amount_str)
            except ValueError:
                return "Bid item and amount must be reasonably sized integers."
            if item_id not in range(self.num_items):
                return f"Bid on non-existent Item {item_id}."
            if bid_amount <= 0:
                return f"Bid amount must be positive, got {bid_amount}."
            if item_id in seen_items:
                return f"Submit at most one bid for Item {item_id}."
            seen_items.add(item_id)
            total_bid_amount += bid_amount
            valid_bids.append((item_id, bid_amount))

        if total_bid_amount > gs["remaining_capital"][player_id]:
            return f"Total bid amount {total_bid_amount} exceeds your remaining capital {gs['remaining_capital'][player_id]}."

        for item_id, bid_amount in valid_bids:
            gs["player_bids"][player_id][item_id] = bid_amount

        # Confirm bids were received (don't reveal specific amounts)
        bid_items = [item_id for item_id, _ in valid_bids]
        self.message(player_id, f"Player {player_id} submitted bids for Items: {', '.join(map(str, bid_items))}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None

    def _transition_to_bidding_phase(self) -> None:
        """Transition from conversation phase to bidding phase."""
        self.game_state["phase"] = "bidding"
        self._announce_bidding_phase()

    def _announce_bidding_phase(self) -> None:
        self.broadcast("Conversation phase complete! Now entering the bidding phase. Each player will have one turn to submit bids.", ta.ObservationType.GAME_MESSAGE)
        self.broadcast(
            "Bidding format: 'Bid Item X: amount'. Put multiple bids on separate lines or separate them with semicolons.\n"
            "You have to submit all of your bids in a single turn. Highest bidder wins each item.",
            ta.ObservationType.GAME_MESSAGE,
        )

    def _determine_auction_results(self) -> ta.Outcome:
        """Determine the results of the auction and calculate the winner."""
        game_state = self.game_state
        num_players = self.state.num_players

        auction_results = {
            "item_winners": {},      # {item_id: winner_pid}
            "winning_bids": {},      # {item_id: winning_bid_amount}
            "player_wins": {},       # {player_id: [item_ids]}
            "player_spent": {},      # {player_id: total_spent}
            "player_value": {},      # {player_id: total_value_of_won_items}
            "player_profit": {},     # {player_id: total_value - total_spent}
            "player_net_worth": {},  # {player_id: remaining_capital + item_value}
        }

        # Determine winners for each item (ties mean nobody wins the item)
        for item_id in range(self.num_items):
            highest_bid = 0
            winner_pid = None
            for pid in range(num_players):
                bid = game_state["player_bids"][pid].get(item_id, 0)
                if bid > highest_bid:
                    highest_bid = bid
                    winner_pid = pid
                elif bid == highest_bid:
                    winner_pid = None

            if winner_pid is not None and highest_bid > 0:
                auction_results["item_winners"][item_id] = winner_pid
                auction_results["winning_bids"][item_id] = highest_bid
                auction_results["player_wins"].setdefault(winner_pid, []).append(item_id)
                auction_results["player_spent"][winner_pid] = auction_results["player_spent"].get(winner_pid, 0) + highest_bid
                item_value = game_state["player_item_values"][winner_pid][item_id]
                auction_results["player_value"][winner_pid] = auction_results["player_value"].get(winner_pid, 0) + item_value

        # Calculate profit and net worth for each player
        for pid in range(num_players):
            auction_results["player_wins"].setdefault(pid, [])
            auction_results["player_spent"].setdefault(pid, 0)
            auction_results["player_value"].setdefault(pid, 0)
            value = auction_results["player_value"].get(pid, 0)
            spent = auction_results["player_spent"].get(pid, 0)
            remaining = self.starting_capital - spent
            game_state["remaining_capital"][pid] = remaining
            auction_results["player_profit"][pid] = value - spent
            auction_results["player_net_worth"][pid] = remaining + value

        game_state["auction_results"] = auction_results
        self._announce_auction_results()
        return self._determine_winner()

    def _announce_auction_results(self) -> None:
        """Announce the results of the auction to all players."""
        game_state = self.game_state
        results = game_state["auction_results"]

        message = "==================== AUCTION RESULTS ====================\n\n"
        message += "🏆 ITEM RESULTS:\n"
        for item_id in range(self.num_items):
            item_name = game_state["item_names"][item_id]
            if item_id in results["item_winners"]:
                winner_pid = results["item_winners"][item_id]
                winning_bid = results["winning_bids"][item_id]
                item_value = game_state["player_item_values"][winner_pid][item_id]
                profit = item_value - winning_bid
                message += f"- Item {item_id} ({item_name}): Won by Player {winner_pid} for {winning_bid} coins\n"
                message += f"  Value to Player {winner_pid}: {item_value} coins (Profit: {profit} coins)\n"
            else:
                message += f"- Item {item_id} ({item_name}): No valid bids\n"

        message += "\n💰 PLAYER RESULTS:\n"
        for pid in range(self.state.num_players):
            remaining = game_state["remaining_capital"][pid]
            initial = self.starting_capital
            spent = results["player_spent"].get(pid, 0)
            value = results["player_value"].get(pid, 0)
            profit = results["player_profit"].get(pid, 0)
            net_worth = remaining + value
            results["player_net_worth"][pid] = net_worth

            message += f"- Player {pid}:\n"
            items_won = results["player_wins"].get(pid, [])
            if items_won:
                message += "  Items Won:\n"
                for item_id in items_won:
                    item_name = game_state["item_names"][item_id]
                    bid = results["winning_bids"][item_id]
                    value_to_player = game_state["player_item_values"][pid][item_id]
                    message += f"  - Item {item_id} ({item_name}): Paid {bid} coins, Value {value_to_player} coins\n"
            else:
                message += "  Items Won: None\n"

            message += "  Financial Summary:\n"
            message += f"  - Initial Capital: {initial} coins\n"
            message += f"  - Total Spent: {spent} coins\n"
            message += f"  - Remaining Capital: {remaining} coins\n"
            message += f"  - Total Item Value: {value} coins\n"
            message += f"  - Profit: {profit} coins\n"
            message += f"  - Net Worth: {net_worth} coins\n\n"

        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

    def _determine_winner(self) -> ta.Outcome:
        """Determine the winner of the auction based on net worth."""
        game_state = self.game_state
        results = game_state["auction_results"]

        max_worth = max(results["player_net_worth"].values(), default=0)
        winners = [pid for pid, worth in results["player_net_worth"].items() if worth == max_worth]

        if len(winners) == 1:
            winner = winners[0]
            profit = results["player_profit"].get(winner, 0)
            remaining = game_state["remaining_capital"][winner]
            item_value = results["player_value"].get(winner, 0)
            reason = (
                f"Player {winner} won with a final net worth of {max_worth} coins! "
                f"(Remaining capital: {remaining} coins, Item value: {item_value} coins, "
                f"Profit: {profit} coins)"
            )
            return self.winner(winner, reason=reason)

        if len(winners) == self.state.num_players:
            return self.draw(reason=f"All players tied with a net worth of {max_worth} coins.")

        details = []
        for pid in winners:
            profit = results["player_profit"].get(pid, 0)
            remaining = game_state["remaining_capital"][pid]
            details.append(
                f"Player {pid} (Net worth: {max_worth} coins, "
                f"Remaining capital: {remaining} coins, "
                f"Profit: {profit} coins)"
            )
        reason = f"Multiple players tied for first with a net worth of {max_worth} coins:\n" + "\n".join(details)
        return self.winner(winners, reason=reason)

    def _parse_commands(self, text: str) -> Tuple[Dict[str, List[tuple]], List[str]]:
        """Group the action's commands by type, and collect the segments that are not complete commands."""
        commands: Dict[str, List[tuple]] = {name: [] for name in self.bare_patterns}
        other_segments = []
        for segment in self._command_segments(text):
            parsed = self._parse_segment(segment)
            if parsed is None:
                other_segments.append(segment)
                continue
            name, groups = parsed
            commands[name].append(groups)
        return commands, other_segments

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

    def _command_name(self, segment: str) -> Optional[str]:
        match = self.command_name_pattern.match(segment)
        return match.group(1).capitalize() if match else None

    def _malformed_command_reason(self, segment: str) -> Optional[str]:
        name = self._command_name(segment)
        if name is None:
            return None
        return (
            f"Malformed {name} command: {segment!r}. "
            "(A line break, or a semicolon followed by a command name, starts a new command.)"
        )

    @staticmethod
    def _parse_number(digits: str) -> Optional[int]:
        """Parse a player id; None if it has implausibly many digits."""
        significant = digits.lstrip("0") or "0"
        return int(significant) if len(significant) <= 18 else None
