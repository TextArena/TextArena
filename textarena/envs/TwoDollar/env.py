"""
Two Dollar Negotiation Game Environment

A classic negotiation exercise where two players must agree on how to split $2.00.
Each player has secret role instructions that may include minimum thresholds,
behavioral constraints, or strategic guidelines.

Based on the original Two Dollar game used in negotiation research and education.
"""

import os
import json
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta
from textarena.state import TwoPlayerState
from textarena.envs.TwoDollar.renderer import render_game_state, render_negotiation_summary, render_final_results

class TwoDollarEnv(ta.Env):
    """
    Two-player negotiation environment where players split a fixed amount of money.
    Players have secret role instructions that create different constraints and objectives.
    """
    
    def __init__(self, 
                 player_roles: Optional[List[str]] = None,
                 total_amount: float = 2.00,
                 max_rounds: int = 20,
                 error_allowance: int = 3):
        """
        Initialize the Two Dollar environment.
        
        Args:
            player_roles: List of 2 role names, or None for random assignment
            total_amount: Total money to be split (default: $2.00)
            max_rounds: Maximum number of negotiation rounds
            error_allowance: Number of invalid moves allowed before applying default action
        """
        self.player_roles_config = player_roles
        self.total_amount = total_amount
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance
        
        # Load all available roles
        self.available_roles = self._load_available_roles()
        
        # Game state
        self.player_roles = {}  # Assigned roles for current game
        self.player_proposal_history = {0: [], 1: []}  # All proposals per player
        self.negotiation_history = []  # Complete action history
        self.current_proposal = {"amount": None, "proposer": None}
        self.final_amounts = {0: 0.0, 1: 0.0}
        self.player_deadline = {}  # For x_rounds role
        
    def _load_available_roles(self) -> Dict[str, Dict]:
        """Load all role definitions from enforceable and non_enforceable folders"""
        roles_dir = os.path.join(os.path.dirname(__file__), "roles")
        available_roles = {}
        
        # Load from both folders
        for folder in ["enforceable", "non_enforceable"]:
            folder_path = os.path.join(roles_dir, folder)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith('.json'):
                        role_name = filename[:-5]  # Remove .json
                        with open(os.path.join(folder_path, filename), 'r') as f:
                            available_roles[role_name] = json.load(f)
        
        return available_roles
    
    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the environment to initial state."""
        if num_players != 2:
            raise ValueError("TwoDollar game requires exactly 2 players")
        
        # Set random seed if provided
        if seed is not None:
            random.seed(seed)
        
        # Assign roles
        if self.player_roles_config is None:
            # Random assignment
            self.player_roles = self._assign_random_roles()
        else:
            # Specific assignment
            if len(self.player_roles_config) != 2:
                raise ValueError("player_roles must contain exactly 2 role names")
            self.player_roles = self._assign_specific_roles(self.player_roles_config)
        
        # Initialize TextArena state
        self.state = TwoPlayerState(
            num_players=num_players,
            max_turns=self.max_rounds,
            seed=seed,
            error_allowance=self.error_allowance
        )
        
        # Initialize game state
        game_state = {
            "current_proposal": {"amount": None, "proposer": None},
            "negotiation_history": [],
            "player_proposal_history": {0: [], 1: []},
            "final_amounts": {0: 0.0, 1: 0.0}
        }
        
        # Reset game state
        self.player_proposal_history = {0: [], 1: []}
        self.negotiation_history = []
        self.current_proposal = {"amount": None, "proposer": None}
        self.final_amounts = {0: 0.0, 1: 0.0}
        
        # Set deadlines for x_rounds role
        self.player_deadline = {}
        for player_id, role in self.player_roles.items():
            if role.get("name") == "x_rounds":
                self.player_deadline[player_id] = self.max_rounds // 2
        
        # Call the state's reset method
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt
        )
    
    def _assign_random_roles(self) -> Dict[int, Dict]:
        """Randomly assign 2 different roles"""
        # Pick 2 different roles randomly
        selected_roles = random.sample(list(self.available_roles.keys()), 2)
        
        return {
            0: self.available_roles[selected_roles[0]],
            1: self.available_roles[selected_roles[1]]
        }
    
    def _assign_specific_roles(self, role_names: List[str]) -> Dict[int, Dict]:
        """Assign specific roles by name"""
        player_roles = {}
        
        for i, role_name in enumerate(role_names):
            if role_name not in self.available_roles:
                raise ValueError(f"Unknown role: {role_name}. Available roles: {list(self.available_roles.keys())}")
            player_roles[i] = self.available_roles[role_name]
        
        return player_roles
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Generate initial prompt for a player."""
        role = self.player_roles[player_id]
        
        # Basic game setup
        prompt = f"""TWO DOLLAR NEGOTIATION GAME

You are Player {player_id} negotiating with another player over how to split ${self.total_amount:.2f} total.
There are {self.max_rounds} maximum rounds.

GAME RULES:
- You must reach an agreement on how to split the ${self.total_amount:.2f}
- If no agreement is reached, both players get $0.00
- You have secret instructions that only you can see (below)

REQUIRED ACTION FORMAT:
Always provide your reasoning/persuasion BEFORE the bracketed action.
Any text after the bracketed action will be ignored.

Available actions:
- Make a proposal: "I think this is fair because... [Propose] $X.XX"
- Accept current proposal: "This works for me because... [Accept]"  
- Reject current proposal: "I can't accept this because... [Reject]"

"""
        
        # Add role-specific instructions
        prompt += f"\n=== YOUR SECRET INSTRUCTIONS ===\n"
        prompt += f"{role['instructions']}\n"
        
        # Add victory/failure conditions
        prompt += f"\nVICTORY CONDITION: {role['victory_condition']}\n"
        prompt += f"FAILURE CONDITION: {role['failure_condition']}\n"
        
        # Add deadline info for x_rounds role
        if role.get("name") == "x_rounds":
            deadline = self.player_deadline.get(player_id, self.max_rounds // 2)
            prompt = prompt.replace("{deadline}", str(deadline))
            prompt = prompt.replace("{total_rounds}", str(self.max_rounds))
        
        return prompt
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process a player's action."""
        current_pid = self.state.current_player_id
        
        # Log the action
        self.state.add_observation(
            from_id=current_pid,
            to_id=current_pid,
            message=f"Your action: {action}",
            observation_type=ta.ObservationType.PLAYER_ACTION
        )
        
        # Process the action
        if self._is_valid_action(action):
            self._process_valid_action(current_pid, action)
        
        # Check for game end conditions
        deal_accepted = self._check_deal_accepted()
        max_turns_reached = self.state.turn >= self.max_rounds - 1
        
        if deal_accepted or max_turns_reached:
            self._end_game()
        
        # Let TextArena handle turn advancement and return
        return self.state.step()
    
    def _is_valid_action(self, action: str) -> bool:
        """Check if an action is valid."""
        action = action.strip()
        
        # Check for standard bracketed actions - handle both formats
        has_propose = "[Propose $" in action or ("[Propose]" in action and "$" in action)
        has_accept = "[Accept]" in action
        has_reject = "[Reject]" in action
        
        # Count how many action types are present
        action_count = sum([has_propose, has_accept, has_reject])
        
        if action_count == 0:
            self.state.set_invalid_move("Invalid action. Use: [Propose] $X.XX, [Accept], or [Reject]")
            return False
        elif action_count > 1:
            self.state.set_invalid_move("Multiple actions detected. Use only one action per turn: [Propose] $X.XX, [Accept], or [Reject]")
            return False
        
        # Validate proposal format
        if has_propose:
            if not self._is_valid_proposal(action):
                # Get specific error message for proposal validation
                amount = self._extract_proposal_amount(action)
                if amount is None:
                    self.state.set_invalid_move("Invalid proposal format. Use: [Propose] $X.XX where X.XX is a valid dollar amount")
                elif amount < 0 or amount > self.total_amount:
                    self.state.set_invalid_move(f"Invalid amount ${amount:.2f}. Must be between $0.00 and ${self.total_amount:.2f}")
                else:
                    self.state.set_invalid_move("Invalid proposal format")
                return False
        
        # Validate accept/reject actions require a current proposal
        if has_accept or has_reject:
            if self.current_proposal["amount"] is None:
                action_type = "accept" if has_accept else "reject"
                self.state.set_invalid_move(f"No current proposal to {action_type}")
                return False
            
            # Players cannot accept/reject their own proposals
            if self.current_proposal["proposer"] == self.state.current_player_id:
                action_type = "accept" if has_accept else "reject"
                self.state.set_invalid_move(f"You cannot {action_type} your own proposal")
                return False
        
        # Role-specific validation
        valid, error_msg = self._validate_role_specific_action(self.state.current_player_id, action)
        if not valid:
            self.state.set_invalid_move(error_msg)
            return False
        
        return True
    
    def _is_valid_proposal(self, action: str) -> bool:
        """Check if a proposal has valid format and amount."""
        try:
            # Extract amount from [Propose $X.XX]
            amount = self._extract_proposal_amount(action)
            if amount is None:
                return False
            
            # Check if amount is valid (0 to total_amount)
            if amount < 0 or amount > self.total_amount:
                return False
            
            return True
        except Exception:
            return False
    
    def _extract_proposal_amount(self, action: str) -> Optional[float]:
        """Extract dollar amount from proposal action."""
        try:
            # Look for [Propose] $X.XX pattern
            match = re.search(r'\[Propose\]\s*\$(\d+(?:\.\d+)?)', action)
            if match:
                return float(match.group(1))
            return None
        except Exception:
            return None
    
    def _validate_role_specific_action(self, player_id: int, action: str) -> Tuple[bool, Optional[str]]:
        """Validate action against player's role requirements"""
        role = self.player_roles[player_id]
        
        if role.get("enforcement") == "action_validation":
            if role["name"] == "say_little":
                # Count words before bracketed action
                message_part = action.split('[')[0].strip()
                word_count = len(message_part.split())
                if word_count > role["behavioral_rules"]["max_words_per_message"]:
                    return False, role["behavioral_rules"]["violation_message"].format(word_count=word_count)
            
            elif role["name"] == "high_tension" and ("[Propose $" in action or ("[Propose]" in action and "$" in action)):
                # Check concession size against own previous proposals
                amount = self._extract_proposal_amount(action)
                proposals = self.player_proposal_history[player_id]
                
                if proposals and amount is not None and amount < proposals[-1]:  # Making concession
                    concession = proposals[-1] - amount
                    max_concession = role["behavioral_rules"]["max_concession"]
                    if concession > max_concession:
                        return False, role["behavioral_rules"]["violation_message"].format(concession=concession)
        
        return True, None
    
    def _process_valid_action(self, player_id: int, action: str):
        """Process a valid action."""
        action = action.strip()
        
        if "[Propose]" in action and "$" in action:
            self._process_proposal(player_id, action)
        elif "[Accept]" in action:
            self._process_accept(player_id, action)
        elif "[Reject]" in action:
            self._process_reject(player_id, action)
    
    def _process_proposal(self, player_id: int, action: str):
        """Process a deal proposal."""
        # Extract rationale and amount
        rationale = action.split("[Propose]")[0].strip()
        amount = self._extract_proposal_amount(action)
        
        if amount is None:
            return  # Should not happen due to validation
        
        # Update current proposal
        self.current_proposal = {"amount": amount, "proposer": player_id}
        self.state.game_state["current_proposal"] = self.current_proposal
        
        # Record in history
        self._record_action(player_id, "propose", amount, rationale)
        
        # Announce the proposal
        other_amount = self.total_amount - amount
        message = f"Player {player_id} proposes: ${amount:.2f} for themselves, ${other_amount:.2f} for their opponent"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _process_accept(self, player_id: int, action: str):
        """Process an accept action."""
        rationale = action.split("[Accept]")[0].strip()
        
        # Record in history
        self._record_action(player_id, "accept", self.current_proposal["amount"], rationale)
        
        # Announce acceptance
        message = f"Player {player_id} accepts the proposal"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _process_reject(self, player_id: int, action: str):
        """Process a reject action."""
        rationale = action.split("[Reject]")[0].strip()
        
        # Record in history
        self._record_action(player_id, "reject", None, rationale)
        
        # Announce rejection
        message = f"Player {player_id} rejects the proposal"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"

        # Reset the proposal amount to none
        self.current_proposal["amount"] = None
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _record_action(self, player_id: int, action_type: str, amount: Optional[float] = None, message: str = ""):
        """Record all actions for analysis"""
        self.negotiation_history.append({
            "player_id": player_id,
            "action_type": action_type,
            "amount": amount,
            "message": message,
            "round": self.state.turn
        })
        
        # Track proposals separately for easy access
        if action_type == "propose" and amount is not None:
            self.player_proposal_history[player_id].append(amount)
        
        # Update game state
        self.state.game_state["negotiation_history"] = self.negotiation_history
        self.state.game_state["player_proposal_history"] = self.player_proposal_history
    
    
    def _check_deal_accepted(self) -> bool:
        """Check if the current deal has been accepted."""
        if self.current_proposal["amount"] is None:
            return False
        
        # Look for recent accept action from the NON-proposer
        if self.negotiation_history:
            last_action = self.negotiation_history[-1]
            # Only count as accepted if someone other than the proposer accepted
            if (last_action["action_type"] == "accept" and 
                last_action["player_id"] != self.current_proposal["proposer"]):
                return True
        
        return False
    
    
    def _end_game(self):
        """End the game and determine final amounts."""
        if self._check_deal_accepted():
            # Deal was accepted
            self._finalize_accepted_deal()
        else:
            # No deal reached
            self._handle_no_deal()
        
        self.state.done = True
    
    def _finalize_accepted_deal(self):
        """Finalize an accepted deal and check role compliance."""
        proposer_id = self.current_proposal["proposer"]
        accepter_id = 1 - proposer_id
        proposer_amount = self.current_proposal["amount"]
        accepter_amount = self.total_amount - proposer_amount
        
        # Set initial amounts
        self.final_amounts[proposer_id] = proposer_amount
        self.final_amounts[accepter_id] = accepter_amount
        
        # Check role compliance for each player
        for player_id in [0, 1]:
            role = self.player_roles[player_id]
            player_amount = self.final_amounts[player_id]
            
            # Check enforceable roles
            if role.get("enforcement") == "end_game_check":
                if role.get("threshold") is not None:
                    threshold = role.get("threshold", 0)
                    if player_amount < threshold:
                        self.final_amounts[player_id] = 0.0  # Failed threshold
                        
                elif role.get("name") == "x_rounds":
                    # Check if they met their deadline
                    deadline = self.player_deadline.get(player_id, self.max_rounds // 2)
                    met_deadline = False
                    for action in self.negotiation_history:
                        if (action["player_id"] == player_id and 
                            action["action_type"] == "accept" and 
                            action["round"] < deadline):
                            met_deadline = True
                            break
                    
                    if not met_deadline:
                        self.final_amounts[player_id] = 0.0  # Failed deadline
            
            elif role.get("enforcement") == "action_validation":
                # These were already enforced during the game via 3-strike system
                # If player got here, they didn't exceed error allowance
                pass
        
        # Announce final results
        deal_str = f"${self.final_amounts[0]:.2f} for Player 0, ${self.final_amounts[1]:.2f} for Player 1"
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"DEAL FINALIZED: {deal_str}",
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Set rewards and winners
        self._set_final_rewards()
    
    def _handle_no_deal(self):
        """Handle case where no deal was reached."""
        self.final_amounts = {0: 0.0, 1: 0.0}
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message="NO DEAL REACHED - Both players receive $0.00",
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Set rewards and winners
        self._set_final_rewards()

    def _set_final_rewards(self):
        """Set final rewards and winner information."""        
        # Determine winners (players who got more than $0)
        winners = [pid for pid in [0, 1] if self.final_amounts[pid] > 0]
        
        if len(winners) == 2:
            # Both players won (got some money)
            if self.final_amounts[0] > self.final_amounts[1]:
                # Player 0 got more
                self.state.set_winner(player_id=0, reason=f"Player 0 received more money (${self.final_amounts[0]:.2f} vs ${self.final_amounts[1]:.2f})")
            elif self.final_amounts[1] > self.final_amounts[0]:
                # Player 1 got more
                self.state.set_winner(player_id=1, reason=f"Player 1 received more money (${self.final_amounts[1]:.2f} vs ${self.final_amounts[0]:.2f})")
            else:
                # Equal amounts - draw
                self.state.set_draw(reason=f"Both players received equal amounts (${self.final_amounts[0]:.2f} each)")
        elif len(winners) == 1:
            # Only one player won
            self.state.set_winner(player_id=winners[0], reason=f"Player {winners[0]} met their role requirements, Player {1 - winners[0]} failed")
        else:
            # No winners - both failed
            self.state.set_draw(reason="Both players failed to meet their role requirements")
    
    def get_observation(self):
        """Get observation for current player."""
        player_id = self.state.current_player_id
        observation = self.state.get_current_player_observation()
        
        # Add current round information
        round_info = f"=== ROUND {self.state.turn + 1} of {self.max_rounds} ===\n"
        observation.append((ta.GAME_ID, round_info, ta.ObservationType.GAME_BOARD))
        
        # Add current game state information
        if self.current_proposal["amount"] is not None:
            proposer_id = self.current_proposal["proposer"]
            amount = self.current_proposal["amount"]
            other_amount = self.total_amount - amount
            
            proposal_info = f"\nCURRENT PROPOSAL:\n"
            proposal_info += f"Player {proposer_id} wants ${amount:.2f}, Player {1 - proposer_id} gets ${other_amount:.2f}\n"
            
            observation.append((ta.GAME_ID, proposal_info, ta.ObservationType.GAME_BOARD))
        
        return player_id, observation

    def get_board_str(self) -> str:
        """
        Return the main board string:
        - Ongoing: current state (proposals + history)
        - Done: negotiation summary (and results)
        """
        if getattr(self.state, "done", False):
            # Show summary + results at the end
            summary = render_negotiation_summary(
                negotiation_history=self.negotiation_history,
                player_proposal_history=self.player_proposal_history,
                total_amount=self.total_amount,
            )
            results = render_final_results(
                final_amounts=self.final_amounts,
                player_roles=self.player_roles,
                total_amount=self.total_amount,
            )
            return f"{summary}\n\n{results}"
        
        # Default ongoing board
        return render_game_state(
            current_proposal=self.current_proposal,
            total_amount=self.total_amount,
            negotiation_history=self.negotiation_history,
            max_history_items=5,
        )