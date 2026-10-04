import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.IteratedUltimatumGame.renderer import create_board_str


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class IteratedUltimatumGameEnv(ta.GameEnv):
    """Environment for the Iterated Ultimatum Game.

    A two-player game where:
    - Players alternate as Proposer and Responder across rounds
    - Each round: Proposer has a pool of money and makes an offer to Responder
    - Responder can accept or reject the offer
    - If accepted: Proposer gets (pool - offer), Responder gets offer
    - If rejected: Both players get nothing for that round
    - Players accumulate money across multiple rounds
    """

    min_players = 2
    max_players = 2

    def __init__(self, pool: int = 10, max_turns: Optional[int] = 4, alternate_roles: bool = False):
        """
        Initialize the Iterated Ultimatum Game environment.

        Args:
            pool (int): Amount of money available each round
            max_turns (int): Maximum number of turns (should be even for balanced gameplay)
        """
        if (
            not isinstance(pool, int)
            or isinstance(pool, bool)
            or pool < 0
            or not _is_renderable(pool)
        ):
            raise ValueError("pool must be a non-negative integer")
        if (
            not isinstance(max_turns, int)
            or isinstance(max_turns, bool)
            or max_turns <= 0
            or max_turns % 2
            or not _is_renderable(max_turns)
        ):
            raise ValueError("max_turns must be a positive even integer")
        if not isinstance(alternate_roles, bool):
            raise ValueError("alternate_roles must be a boolean")

        self.pool = pool
        self.max_turns = max_turns
        self.alternate_roles = alternate_roles

        # Regex patterns for parsing player actions (bare forms, tolerating optional stray brackets)
        self.offer_pattern = re.compile(
            r"^\s*\[?\s*Offer:\s*\$?(\d+)\s*\]?\s*$", re.IGNORECASE
        )
        self.accept_pattern = re.compile(r"^\s*\[?\s*Accept\s*\]?\s*$", re.IGNORECASE)
        self.reject_pattern = re.compile(r"^\s*\[?\s*Reject\s*\]?\s*$", re.IGNORECASE)

    def get_board_str(self):
        """Get the current board state as a string."""
        return create_board_str(
            pool=self.game_state["pool"],
            current_offer=self.game_state.get("current_offer"),
            game_phase=self.game_state["phase"],
            round_number=self.game_state["round_number"],
            total_rounds=self.max_turns // 2,
            player_totals=self.game_state["player_totals"],
            round_history=self.game_state["round_history"],
            current_proposer=self.game_state["current_proposer_id"],
            alternate_roles=self.alternate_roles,
        )

    def prompt(self, player_id: int) -> str:
        """Generate the prompt for a player including history."""
        initial_role = "Proposer" if player_id == self.game_state["current_proposer_id"] else "Responder"
        role_cadence = (
            "The Proposer and Responder roles alternate after each round."
            if self.alternate_roles
            else f"Player {self.game_state['current_proposer_id']} remains the Proposer every round."
        )
        return (
            f"You are Player {player_id}, playing {self.max_turns // 2} rounds of Iterated Ultimatum Game.\n"
            f"You begin as the {initial_role}. {role_cadence}\n"
            f"Each round, the Proposer splits a ${self.game_state['pool']} pool with the Responder.\n"
            "Money adds up over all rounds: the player with more money after the last round wins, and equal totals are a draw.\n\n"
            "Proposer:\n"
            "  - Make an offer by replying 'Offer: $X' (0 <= X <= pool)\n"
            "  - If accepted → You get $(pool - X), other player gets $X\n"
            "  - If rejected → Both get $0\n"
            "  - Example: 'Offer: $3'\n\n"
            "Responder:\n"
            "  - Decide on the offer by replying either 'accept' or 'reject'\n"
        )

    def setup(self) -> Dict[str, Any]:
        return {
            "pool": self.pool,
            "phase": "offering",  # "offering" or "responding"
            "round_number": 1,
            "current_offer": None,
            "player_totals": {0: 0, 1: 0},  # Accumulated money across rounds
            "round_history": [],  # History of all previous rounds
            "current_proposer_id": 0,
            "current_responder_id": 1,
        }

    def on_start(self):
        self.broadcast(
            f"--- Round {self.game_state['round_number']} begins! ---\n"
            f"Player {self.game_state['current_proposer_id']} is the proposer, Player {self.game_state['current_responder_id']} is the responder.",
            ta.ObservationType.GAME_MESSAGE,
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Process the player's action."""
        if (
            not isinstance(player_id, int)
            or isinstance(player_id, bool)
            or not 0 <= player_id < self.state.num_players
            or not self.state.is_player_alive(player_id)
            or player_id != self.current_player_id
        ):
            return self.invalid("Action submitted by an unauthorized player.")
        game_phase = self.game_state["phase"]
        if game_phase == "offering":
            # Current player is making an offer
            return self._handle_proposer_action(player_id, action)
        else:
            # Current player is responding to the offer
            result = self._handle_responder_action(player_id, action)
            if result is None:
                self.set_next_player(self.game_state["current_proposer_id"])
            return result

    def _handle_proposer_action(self, player_id: int, action: str) -> Optional[ta.Invalid]:
        """Handle the proposer's offer action."""
        if player_id != self.game_state["current_proposer_id"]:
            return self.invalid(f"It is Player {self.game_state['current_proposer_id']}'s turn to propose.")

        offer_match = self.offer_pattern.search(action)

        if not offer_match:
            return self.invalid("Proposer must make an offer using the format 'Offer: $X'.")

        try:
            offer = int(offer_match.group(1))
        except ValueError:
            return self.invalid("Offer amount must be a valid integer.")

        # Validate offer amount
        if offer < 0 or offer > self.game_state["pool"]:
            return self.invalid(f"Offer must be between $0 and ${self.game_state['pool']}.")

        # Valid offer - update game state
        self.game_state["current_offer"] = offer
        self.game_state["phase"] = "responding"

        # Broadcast the offer
        responder_id = 1 - player_id
        self.broadcast(
            f"Round {self.game_state['round_number']}: Player {player_id} offers ${offer} to Player {responder_id} (keeping ${self.game_state['pool'] - offer}).",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        return None  # round-robin rotation passes the turn to the responder

    def _handle_responder_action(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Handle the responder's accept/reject action."""
        if player_id != self.game_state["current_responder_id"]:
            return self.invalid(f"It is Player {self.game_state['current_responder_id']}'s turn to respond.")

        current_offer = self.game_state["current_offer"]

        if current_offer is None:
            return self.invalid("No current offer to respond to.")

        if self.accept_pattern.search(action):
            return self._execute_accepted_offer(player_id)
        elif self.reject_pattern.search(action):
            return self._execute_rejected_offer(player_id)
        else:
            return self.invalid("Responder must reply with either 'accept' or 'reject'.")

    def _execute_accepted_offer(self, responder_id: int) -> Optional[ta.Outcome]:
        """Execute the round when offer is accepted."""
        offer = self.game_state["current_offer"]
        pool = self.game_state["pool"]
        proposer_id = 1 - responder_id

        # Calculate gains for this round
        proposer_gain = pool - offer
        responder_gain = offer

        # Update total money
        self.game_state["player_totals"][proposer_id] += proposer_gain
        self.game_state["player_totals"][responder_id] += responder_gain

        # Add to history
        self.game_state["round_history"].append({
            "round": self.game_state["round_number"],
            "proposer": proposer_id,
            "responder": responder_id,
            "offer": offer,
            "decision": "Accept",
            "proposer_gain": proposer_gain,
            "responder_gain": responder_gain,
        })

        # Broadcast result
        self.broadcast(
            f"Player {responder_id} accepted! Round {self.game_state['round_number']} gains: Player {proposer_id} +${proposer_gain}, Player {responder_id} +${responder_gain}. New totals: Player 0: ${self.game_state['player_totals'][0]}, Player 1: ${self.game_state['player_totals'][1]}.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )

        return self._advance_to_next_round()

    def _execute_rejected_offer(self, responder_id: int) -> Optional[ta.Outcome]:
        """Execute the round when offer is rejected."""
        proposer_id = 1 - responder_id
        offer = self.game_state["current_offer"]

        # Add to history (no gains)
        self.game_state["round_history"].append({
            "round": self.game_state["round_number"],
            "proposer": proposer_id,
            "responder": responder_id,
            "offer": offer,
            "decision": "Reject",
            "proposer_gain": 0,
            "responder_gain": 0,
        })

        # Broadcast result
        self.broadcast(
            f"Player {responder_id} rejected the offer! Round {self.game_state['round_number']} gains: Both players +$0. Totals remain: Player 0: ${self.game_state['player_totals'][0]}, Player 1: ${self.game_state['player_totals'][1]}.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )

        return self._advance_to_next_round()

    def _advance_to_next_round(self) -> Optional[ta.Outcome]:
        """Advance to the next round or end the game."""
        if self.game_state["round_number"] >= (self.max_turns // 2):
            self.game_state["phase"] = "complete"
            return self._determine_final_winner()

        self.game_state["round_number"] += 1
        self.game_state["phase"] = "offering"
        self.game_state["current_offer"] = None

        if self.alternate_roles:
            # Swap proposer each round
            proposer_id = 1 - self.game_state["current_proposer_id"]
        else:
            # Keep proposer fixed (default to Player 0)
            proposer_id = self.game_state.get("current_proposer_id", 0)

        responder_id = 1 - proposer_id

        self.game_state["current_proposer_id"] = proposer_id
        self.game_state["current_responder_id"] = responder_id

        self.broadcast(
            f"--- Round {self.game_state['round_number']} begins! ---\n"
            f"Player {proposer_id} is the proposer, Player {responder_id} is the responder.",
            ta.ObservationType.GAME_MESSAGE,
        )
        return None

    def _determine_final_winner(self) -> ta.Outcome:
        """Determine the winner based on total accumulated money."""
        total_0 = self.game_state["player_totals"][0]
        total_1 = self.game_state["player_totals"][1]

        if total_0 > total_1:
            return self.winner(0, reason=f"Player 0 won with ${total_0} total vs Player 1's ${total_1}.")
        elif total_1 > total_0:
            return self.winner(1, reason=f"Player 1 won with ${total_1} total vs Player 0's ${total_0}.")
        else:
            return self.draw(reason=f"Draw! Both players finished with ${total_0} total.")
