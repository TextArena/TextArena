import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

import textarena as ta
from textarena.envs.SimpleBlindAuction.renderer import create_board_str


class SimpleBlindAuctionEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    def __init__(self, starting_capital: int = 1000, num_items: int = 5, conversation_rounds: int = 3, base_item_values: Optional[List[int]] = None):
        """
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
        self.max_turns = conversation_rounds * 2 + 2
        self.item_names = [ # Item names for flavor
            "Ancient Vase", "Diamond Necklace", "Antique Clock", "Signed Painting", "Gold Statue", "Rare Manuscript", "Silver Chalice", "Vintage Watch",
            "Jade Figurine", "Bronze Sculpture", "Crystal Decanter", "Royal Tapestry", "Emerald Ring", "Ivory Chess Set", "Pearl Earrings"
        ]
        self.bid_pattern = re.compile(r"Bid\s+(?:on\s+)?(?:Item\s+)?(\d+)\s*:\s*(\d+)", re.IGNORECASE)
        self.legacy_bid_pattern = re.compile(r"\[\s*Bid\s+(?:on\s+)?(?:Item\s+)?(\d+)\s*:\s*(\d+)\s*\]", re.IGNORECASE)
        self.bid_start_pattern = re.compile(r"\[?\s*Bid\b", re.IGNORECASE)
        # Bids are separated by line breaks or by semicolons followed by the next bid, as in BlindAuction.
        self.bid_separator = re.compile(r";\s*(?=\[?\s*Bid\b)", re.IGNORECASE)
        self.segment_padding = re.compile(r"^[\s;]+|[\s;]+$")

    def get_board_str(self):
        return create_board_str(
            game_state=self.game_state,
            viewer_id=self.state.current_player_id,
            reveal_all=self.state.done,
        )

    def setup(self) -> Dict[str, Any]:
        available_names = self.item_names + [
            f"Mystery Item {i}" for i in range(len(self.item_names), self.num_items)
        ]
        item_names = self.rng.sample(available_names, self.num_items)

        # Generate base item values if not provided
        if self.base_item_values is None: base_item_values = [self.rng.randint(50, 500) for _ in range(self.num_items)]
        else:
            base_item_values = list(self.base_item_values[:self.num_items])
            while len(base_item_values) < self.num_items: base_item_values.append(self.rng.randint(50, 500)) # Add random values if needed

        # Generate player-specific item values (±20% around base values)
        player_item_values = {}
        for pid in range(2):
            player_item_values[pid] = {}
            for i in range(self.num_items):
                base_value = base_item_values[i]
                variation = base_value // 5  # ±20%, without overflowing through float
                min_value = max(1, base_value - variation)
                max_value = base_value + variation
                player_item_values[pid][i] = self.rng.randint(min_value, max_value)

        return {
            "phase": "conversation" if self.conversation_rounds > 0 else "bidding",
            "round": 1,  # Current conversation round
            "item_names": item_names[:self.num_items],
            "base_item_values": base_item_values,
            "player_item_values": player_item_values,
            "remaining_capital": {0: self.starting_capital, 1: self.starting_capital},
            "player_bids": {0: {}, 1: {}},  # Format: {player_id: {item_id: bid_amount}}
            "auction_results": None,  # Will be populated after bidding phase
            "conversations_completed": 0,  # Track completed conversation turns
            "bidding_done": {0: False, 1: False}
        }

    def on_start(self):
        if self.conversation_rounds == 0:
            self._announce_bidding_phase()

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        # Create a formatted list of items with values
        item_values = []
        for i in range(self.num_items):
            item_name = game_state["item_names"][i]
            value = game_state["player_item_values"][player_id][i]
            item_values.append(f"- Item {i}: {item_name} - Value to you: {value} coins")
        items_str = "\n".join(item_values)
        return (
            f"You are Player {player_id} in a 2-player Simple Blind Auction game.\n\n"
            f"You have {self.starting_capital} coins to bid on {self.num_items} valuable items.\n\n"
            f"The auction has two phases:\n"
            f"1. Conversation Phase ({self.conversation_rounds} rounds): Talk with the other player. All messages are public.\n"
            f"2. Bidding Phase (1 round): Submit blind bids on items. Highest bidder wins each item.\n\n"
            f"Available Items (with their value TO YOU):\n{items_str}\n\n"
            f"Note: Each player may value items differently, up to ±20% difference!\n\n"
            f"How to play:\n"
            f"- Conversation Phase: Just type your messages normally\n"
            f"- Bidding Phase: Submit all of your bids in one reply as 'Bid on Item X: amount', "
            f"one per line or separated by semicolons\n"
            f"  Example:\nBid on Item 0: 250\nBid on Item 3: 175\n"
            f"  or: Bid on Item 0: 250; Bid on Item 3: 175\n\n"
            f"Your goal is to win items that are worth more to you than what you paid.\n"
            f"The player with the highest net worth at the end wins.\n"
            f"Net worth = remaining capital + value of won items.\n"
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # Conversation messages are public; bid submissions are sealed (echoed only to their author).
        return -1 if self.game_state["phase"] == "conversation" else player_id

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if gs["phase"] == "conversation":
            gs["conversations_completed"] += 1
            if gs["conversations_completed"] >= self.conversation_rounds * 2: self._transition_to_bidding_phase()
            return None
        return self._handle_bidding_action(player_id, action)

    def _transition_to_bidding_phase(self) -> None:
        """Transition from conversation phase to bidding phase."""
        self.game_state["phase"] = "bidding"
        self._announce_bidding_phase()

    def _announce_bidding_phase(self) -> None:
        message = (
            "Conversation phase complete! Now entering the bidding phase.\n"
            "Submit all of your bids in one reply using the format: Bid on Item X: amount\n"
            "Put each bid on its own line or separate bids with semicolons. For example:\n"
            "Bid on Item 0: 150\nBid on Item 2: 200\nBid on Item 4: 350"
        )
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

    def _handle_bidding_action(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        bids = self._parse_bids(action)
        if bids is None:
            return self.invalid(
                "Malformed or mixed bid command. Submit only complete bids such as 'Bid on Item 0: 250', "
                "one per line or separated by semicolons."
            )
        if gs["bidding_done"][player_id]:
            return self.invalid("You have already submitted your sealed bids.")
        if not bids:
            # Even with zero bids the player is "done" for this environment's rules
            self.message(player_id, "You submitted no valid bids.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            # Validate every bid before mutating any state
            total_bid_amount = 0
            valid_bids = []
            seen_items = set()
            for item_id_str, bid_amount_str in bids:
                try:
                    item_id = int(item_id_str); bid_amount = int(bid_amount_str)
                except ValueError:
                    return self.invalid("Bid item and amount must be reasonably sized integers.")
                if item_id not in range(self.num_items): return self.invalid(f"Item {item_id} does not exist. Valid items are 0-{self.num_items-1}.")
                if bid_amount <= 0: return self.invalid("Bid amount must be positive.")
                if item_id in seen_items: return self.invalid(f"Submit at most one bid for Item {item_id}.")
                seen_items.add(item_id)
                total_bid_amount += bid_amount
                valid_bids.append((item_id, bid_amount))
            if total_bid_amount > gs["remaining_capital"][player_id]:
                return self.invalid(f"Total bid amount {total_bid_amount} exceeds your remaining capital {gs['remaining_capital'][player_id]}.")

            for item_id, bid_amount in valid_bids: gs["player_bids"][player_id][item_id] = bid_amount # Record valid bids

            # Confirm bids were received (privately)
            bid_items = [item_id for item_id, _ in valid_bids]
            self.message(player_id, f"You submitted bids for Items: {', '.join(map(str, bid_items))}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.message(1 - player_id, f"Player {player_id} has submitted bids.", ta.ObservationType.GAME_ACTION_DESCRIPTION) # Public notification (without specific details)

        gs["bidding_done"][player_id] = True
        if all(gs["bidding_done"].values()): return self._determine_auction_results()
        return None

    def _parse_bids(self, action: str) -> Optional[List[tuple[str, str]]]:
        """Parse bids that are either all bare or all legacy bracketed tokens.

        Returns [] for a reply without any bid and None for malformed or mixed bids."""
        segments = []
        for line in action.splitlines():
            for segment in self.bid_separator.split(line):
                segment = self.segment_padding.sub("", segment)
                if segment:
                    segments.append(segment)
        if not segments:
            return []

        bare_matches = [self.bid_pattern.fullmatch(segment) for segment in segments]
        if all(bare_matches):
            return [match.groups() for match in bare_matches]

        legacy_bids = [self.legacy_bid_pattern.findall(segment) for segment in segments]
        if all(bids and not self.legacy_bid_pattern.sub("", segment).strip() for bids, segment in zip(legacy_bids, segments)):
            return [bid for bids in legacy_bids for bid in bids]
        if any(self.bid_start_pattern.match(segment) for segment in segments):
            return None
        return []

    def _determine_auction_results(self) -> ta.Outcome:
        """Determine the results of the auction and calculate the winner."""
        game_state = self.game_state

        # Initialize results
        auction_results = {
            "item_winners": {},           # {item_id: winner_pid}
            "winning_bids": {},           # {item_id: winning_bid_amount}
            "player_wins": defaultdict(list),  # {player_id: [item_ids]}
            "player_spent": defaultdict(int),  # {player_id: total_spent}
            "player_value": defaultdict(int),  # {player_id: total_value_of_won_items}
            "player_profit": defaultdict(int),  # {player_id: total_value - total_spent}
            "player_net_worth": defaultdict(int)  # {player_id: remaining_capital + item_value}
        }

        # Determine winners for each item
        for item_id in range(self.num_items):
            player0_bid = game_state["player_bids"][0].get(item_id, 0)
            player1_bid = game_state["player_bids"][1].get(item_id, 0)

            # If there's a tie or no bids, no one wins
            if player0_bid > player1_bid:   winner_pid = 0; highest_bid = player0_bid
            elif player1_bid > player0_bid: winner_pid = 1; highest_bid = player1_bid
            else: continue # Tie or no bids - no winner

            # Record the result for this item
            auction_results["item_winners"][item_id] = winner_pid
            auction_results["winning_bids"][item_id] = highest_bid
            auction_results["player_wins"][winner_pid].append(item_id)
            auction_results["player_spent"][winner_pid] += highest_bid

            # Calculate value to the winner
            item_value = game_state["player_item_values"][winner_pid][item_id]
            auction_results["player_value"][winner_pid] += item_value

        # Calculate profit and net worth for each player
        for pid in range(2):
            value = auction_results["player_value"][pid]
            spent = auction_results["player_spent"][pid]
            remaining = self.starting_capital - spent
            game_state["remaining_capital"][pid] = remaining
            auction_results["player_profit"][pid] = value - spent # Profit = value of items - amount spent
            auction_results["player_net_worth"][pid] = remaining + value # Net worth = remaining capital + value of items
        game_state["auction_results"] = auction_results # Save results to game state
        self._announce_auction_results() # Announce results
        return self._determine_winner() # Determine the winner

    def _announce_auction_results(self) -> None:
        game_state = self.game_state
        results = game_state["auction_results"]
        # Announce overall auction results
        message = "==================== AUCTION RESULTS ====================\n\n"
        # Results for each item
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
                message += f"- Item {item_id} ({item_name}): No winner (tie or no bids)\n"
        message += "\n💰 PLAYER RESULTS:\n"
        for pid in range(2):
            # Calculate remaining capital
            remaining = game_state["remaining_capital"][pid]
            initial = self.starting_capital
            spent = results["player_spent"][pid]
            value = results["player_value"][pid]
            profit = results["player_profit"][pid]
            net_worth = remaining + value  # Net worth = remaining capital + value of items
            message += f"- Player {pid}:\n"
            # Show items won with details
            items_won = results["player_wins"][pid]
            if items_won:
                message += f"  Items Won:\n"
                for item_id in items_won:
                    item_name = game_state["item_names"][item_id]
                    bid = results["winning_bids"][item_id]
                    value_to_player = game_state["player_item_values"][pid][item_id]
                    message += f"  - Item {item_id} ({item_name}): Paid {bid} coins, Value {value_to_player} coins\n"
            else:
                message += f"  Items Won: None\n"

            # Show financial summary
            message += f"  Financial Summary:\n"
            message += f"  - Initial Capital: {initial} coins\n"
            message += f"  - Total Spent: {spent} coins\n"
            message += f"  - Remaining Capital: {remaining} coins\n"
            message += f"  - Total Item Value: {value} coins\n"
            message += f"  - Profit: {profit} coins\n"
            message += f"  - Net Worth: {net_worth} coins\n\n"

        # Send the results
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

    def _determine_winner(self) -> ta.Outcome:
        game_state = self.game_state
        results = game_state["auction_results"]

        # Find the player(s) with the highest net worth
        max_worth = max(results["player_net_worth"].values(), default=0)
        winners = [pid for pid, worth in results["player_net_worth"].items() if worth == max_worth]

        # Set the winner(s)
        if len(winners) == 1:
            winner = winners[0]
            profit = results["player_profit"][winner]
            spent = results["player_spent"][winner]
            remaining = game_state["remaining_capital"][winner]
            item_value = results["player_value"][winner]
            reason = f"Player {winner} won with a final net worth of {max_worth} coins! (Remaining capital: {remaining} coins, Item value: {item_value} coins, Profit: {profit} coins)"
            return self.winner(winner, reason=reason)
        else:
            # For ties, provide detailed info for all winners
            details = []
            for pid in winners:
                profit = results["player_profit"][pid]
                remaining = game_state["remaining_capital"][pid]
                details.append(f"Player {pid} (Net worth: {max_worth} coins, Remaining capital: {remaining} coins, Profit: {profit} coins)")
            return self.draw(reason=f"Both players tied with a net worth of {max_worth} coins.\n" + "\n".join(details))
