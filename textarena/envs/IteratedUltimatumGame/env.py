import re
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta
from textarena.envs.IteratedUltimatumGame.renderer import create_board_str


class IteratedUltimatumGameEnv(ta.Env):
    """Environment for the Iterated Ultimatum Game.
    
    A two-player game where:
    - Players alternate as Proposer and Responder across rounds
    - Each round: Proposer has a pool of money and makes an offer to Responder
    - Responder can accept or reject the offer
    - If accepted: Proposer gets (pool - offer), Responder gets offer
    - If rejected: Both players get nothing for that round
    - Players accumulate money across multiple rounds
    """

    def __init__(self, pool: int = 10, max_turns: Optional[int] = 4, alternate_roles: bool = False):
        """
        Initialize the Iterated Ultimatum Game environment.
        
        Args:
            pool (int): Amount of money available each round
            max_turns (int): Maximum number of turns (should be even for balanced gameplay)
        """
        self.pool = pool
        self.max_turns = max_turns
        self.alternate_roles = alternate_roles
        
        # Regex patterns for parsing player actions
        self.offer_pattern = re.compile(
            r"\[Offer:\s*\$?(\d+)\]", re.IGNORECASE
        )
        self.accept_pattern = re.compile(r"\[Accept\]", re.IGNORECASE)
        self.reject_pattern = re.compile(r"\[Reject\]", re.IGNORECASE)

    def get_board_str(self):
        """Get the current board state as a string."""
        # Determine current proposer based on who is acting in offering phase
        if self.state.game_state["phase"] == "offering":
            current_proposer = self.state.current_player_id
        else:
            # In responding phase, proposer is the other player
            current_proposer = 1 - self.state.current_player_id
            
        return create_board_str(
            pool=self.state.game_state["pool"],
            current_offer=self.state.game_state.get("current_offer"),
            game_phase=self.state.game_state["phase"],
            round_number=self.state.game_state["round_number"],
            total_rounds=self.max_turns // 2,
            player_totals=self.state.game_state["player_totals"],
            round_history=self.state.game_state["round_history"],
            current_proposer=current_proposer,
        )

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        """Generate the prompt for a player including history."""
   
        prompt = (
            f"You are Player {player_id}, playing {self.max_turns // 2} rounds of Iterated Ultimatum Game.\n"
            f"You have ${game_state['pool']} to split this round between yourself and Player {1-player_id}.\n\n"
            "Proposer:\n"
            "  - Make an offer: [Offer: $X] (0 <= X <= pool)\n"
            "  - If accepted → You get $(pool - X), other player gets $X\n"
            "  - If rejected → Both get $0\n"
            "  - Example: [Offer: $3]  or  'I think this is fair. [Offer: $5]'\n\n"
            "Responder:\n"
            "  - Decide on the offer with either [Accept] or [Reject]\n"
            "  - Example: 'That seems reasonable. [Accept]'\n"
            "            'Too unfair. [Reject]'\n"
        )
        
        return prompt

    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the Iterated Ultimatum Game to its initial state."""
        # Initialize game state
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)

        game_state = {
            "pool": self.pool,
            "phase": "offering",  # "offering" or "responding" 
            "round_number": 1,
            "current_offer": None,
            "player_totals": {0: 0, 1: 0},  # Accumulated money across rounds
            "round_history": [],  # History of all previous rounds
            "current_proposer_id": self.state.current_player_id,
            "current_responder_id": 1 - self.state.current_player_id
        }

        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt,
        )

        self.state.add_observation(
            message=(
                f"--- Round {self.state.game_state['round_number']} begins! ---\n"
                f"Player {self.state.game_state['current_proposer_id']} is the proposer, Player {self.state.game_state['current_responder_id']} is the responder."
            ),
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
        
        # TwoPlayerState starts with player 0 by default

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process the player's action."""
        # Update the observations and log the action
        self.state.add_observation(
            from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION
        )

        rotate_player = True # default auto switch
        game_phase = self.state.game_state["phase"]

        if game_phase == "offering":
            # Current player is making an offer
            self._handle_proposer_action(action)
        elif game_phase == "responding":
            # Current player is responding to the offer
            self._handle_responder_action(action)
            rotate_player = False if self.alternate_roles else True

        return self.state.step(rotate_player=rotate_player)

    def _handle_proposer_action(self, action: str) -> None:
        """Handle the proposer's offer action."""
        offer_match = self.offer_pattern.search(action)
        
        if not offer_match:
            reason = "Proposer must make an offer using the format [Offer: $X]."
            self.state.set_invalid_move(reason=reason)
            return

        try:
            offer = int(offer_match.group(1))
        except ValueError:
            reason = "Offer amount must be a valid integer."
            self.state.set_invalid_move(reason=reason)
            return

        # Validate offer amount
        if offer < 0 or offer > self.state.game_state["pool"]:
            reason = f"Offer must be between $0 and ${self.state.game_state['pool']}."
            self.state.set_invalid_move(reason=reason)
            return

        # Valid offer - update game state
        self.state.game_state["current_offer"] = offer
        self.state.game_state["phase"] = "responding"
        
        # Broadcast the offer
        proposer_id = self.state.current_player_id
        responder_id = 1 - proposer_id
        self.state.add_observation(
            message=f"Round {self.state.game_state['round_number']}: Player {proposer_id} offers ${offer} to Player {responder_id} (keeping ${self.state.game_state['pool'] - offer}).",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        # TwoPlayerState will automatically switch to responder on next step

    def _handle_responder_action(self, action: str) -> None:
        """Handle the responder's accept/reject action."""
        current_offer = self.state.game_state["current_offer"]
        
        if current_offer is None:
            reason = "No current offer to respond to."
            self.state.set_invalid_move(reason=reason)
            return

        if self.accept_pattern.search(action):
            # Offer accepted
            self._execute_accepted_offer()
        elif self.reject_pattern.search(action):
            # Offer rejected
            self._execute_rejected_offer()
        else:
            reason = "Responder must either [Accept] or [Reject] the offer."
            self.state.set_invalid_move(reason=reason)

    def _execute_accepted_offer(self) -> None:
        """Execute the round when offer is accepted."""
        offer = self.state.game_state["current_offer"]
        pool = self.state.game_state["pool"]
        # The responder is the current player, proposer is the other player
        responder_id = self.state.current_player_id
        proposer_id = 1 - responder_id
        
        # Calculate gains for this round
        proposer_gain = pool - offer
        responder_gain = offer
        
        # Update total money
        self.state.game_state["player_totals"][proposer_id] += proposer_gain
        self.state.game_state["player_totals"][responder_id] += responder_gain
        
        # Add to history
        self.state.game_state["round_history"].append({
            "round": self.state.game_state["round_number"],
            "proposer": proposer_id,
            "responder": responder_id,
            "offer": offer,
            "decision": "Accept",
            "proposer_gain": proposer_gain,
            "responder_gain": responder_gain,
        })
        
        # Broadcast result
        self.state.add_observation(
            message=f"Player {responder_id} accepted! Round {self.state.game_state['round_number']} gains: Player {proposer_id} +${proposer_gain}, Player {responder_id} +${responder_gain}. New totals: Player 0: ${self.state.game_state['player_totals'][0]}, Player 1: ${self.state.game_state['player_totals'][1]}.",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        self._advance_to_next_round()

    def _execute_rejected_offer(self) -> None:
        """Execute the round when offer is rejected."""
        # The responder is the current player, proposer is the other player
        responder_id = self.state.current_player_id
        proposer_id = 1 - responder_id
        offer = self.state.game_state["current_offer"]
        
        # Add to history (no gains)
        self.state.game_state["round_history"].append({
            "round": self.state.game_state["round_number"],
            "proposer": proposer_id,
            "responder": responder_id,
            "offer": offer,
            "decision": "Reject",
            "proposer_gain": 0,
            "responder_gain": 0,
        })
        
        # Broadcast result
        self.state.add_observation(
            message=f"Player {responder_id} rejected the offer! Round {self.state.game_state['round_number']} gains: Both players +$0. Totals remain: Player 0: ${self.state.game_state['player_totals'][0]}, Player 1: ${self.state.game_state['player_totals'][1]}.",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        self._advance_to_next_round()

    def _advance_to_next_round(self) -> None:
        """Advance to the next round or end the game."""
        if self.state.game_state["round_number"] >= (self.max_turns // 2):
            self._determine_final_winner()
        else:
            self.state.game_state["round_number"] += 1
            self.state.game_state["phase"] = "offering"
            self.state.game_state["current_offer"] = None

            if self.alternate_roles:
                # Swap proposer each round
                proposer_id = 1 - self.state.game_state["current_proposer_id"]
            else:
                # Keep proposer fixed (default to Player 0)
                proposer_id = self.state.game_state.get("current_proposer_id", 0)

            responder_id = 1 - proposer_id

            self.state.game_state["current_proposer_id"] = proposer_id
            self.state.game_state["current_responder_id"] = responder_id

            self.state.add_observation(
                message=(
                    f"--- Round {self.state.game_state['round_number']} begins! ---\n"
                    f"Player {proposer_id} is the proposer, Player {responder_id} is the responder."
                ),
                observation_type=ta.ObservationType.GAME_MESSAGE
            )

    def _determine_final_winner(self) -> None:
        """Determine the winner based on total accumulated money."""
        total_0 = self.state.game_state["player_totals"][0]
        total_1 = self.state.game_state["player_totals"][1]
        
        if total_0 > total_1:
            self.state.set_winner(
                player_id=0, 
                reason=f"Player 0 won with ${total_0} total vs Player 1's ${total_1}."
            )
        elif total_1 > total_0:
            self.state.set_winner(
                player_id=1, 
                reason=f"Player 1 won with ${total_1} total vs Player 0's ${total_0}."
            )
        else:
            self.state.set_draw(
                reason=f"Draw! Both players finished with ${total_0} total."
            ) 