import re
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta
from textarena.state import TeamMultiPlayerState
from textarena.envs.NegotiateToSurvive.renderer import (
    get_board_str,
    render_resources_and_coins
)


class NegotiateToSurviveEnv(ta.Env):
    """
    5-player survival negotiation game where players trade resources and coins.
    
    Two game variants:
    - Distributive: Team needs 4/5 resources to survive, highest coins wins
    - Integrative: Team needs all 5 resources to survive, all survivors win
    """
    
    def __init__(self, 
                 game_variant: str = "distributive",
                 max_rounds: int = 100,
                 starting_coins: int = 50,
                 error_allowance: int = 3):
        """
        Initialize the Negotiate to Survive environment.
        
        Args:
            game_variant: "distributive" or "integrative"
            max_rounds: Maximum number of rounds
            starting_coins: Starting coins per player
            error_allowance: Number of invalid moves allowed before default action
        """
        self.game_variant = game_variant
        self.max_rounds = max_rounds
        self.starting_coins = starting_coins
        self.error_allowance = error_allowance
        
        # Game constants
        self.resources = ["food", "water", "shelter", "medicine", "clothing"]
        self.num_players = 5
        
        # Game state
        self.player_resources = {}  # {player_id: [list of resources]}
        self.player_coins = {}      # {player_id: coins}
        self.resource_history = {}  # {resource: [player_ids who had it]}
        self.proposals = {}         # {proposal_id: proposal_data}
        self.proposal_counter = 0
        self.whisper_history = []   # List of whisper messages
        
    def reset(self, num_players: int = 5, seed: Optional[int] = None):
        """Reset the environment to initial state."""
        if num_players != 5:
            raise ValueError(f"Negotiate to Survive requires exactly 5 players, got {num_players}")
        
        # Initialize TextArena state
        self.state = TeamMultiPlayerState(
            num_players=num_players,
            max_turns=self.max_rounds,
            seed=seed,
            error_allowance=self.error_allowance
        )
        
        # Initialize game state
        self._initialize_game_state()
        
        game_state = {
            "player_resources": self.player_resources,
            "player_coins": self.player_coins,
            "resource_history": self.resource_history,
            "proposals": self.proposals,
            "whisper_history": self.whisper_history,
            "game_variant": self.game_variant
        }
        
        # Reset state with player prompt function
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt
        )
        
        # Set starting player
        self.state.current_player_id = 0
    
    def _initialize_game_state(self):
        """Initialize players with resources and coins."""
        # Assign one resource to each player
        for i in range(self.num_players):
            resource = self.resources[i]
            self.player_resources[i] = [resource]  # List of resources
            self.player_coins[i] = self.starting_coins
            
            # Initialize resource history
            if resource not in self.resource_history:
                self.resource_history[resource] = []
            self.resource_history[resource].append(i)
        
        # Reset other state
        self.proposals = {}
        self.proposal_counter = 0
        self.whisper_history = []
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Generate initial prompt for a player."""
        # Determine survival target based on variant but don't reveal which variant
        if self.game_variant == "distributive":
            survival_target = "at least 4 of the 5 resources"
            win_condition = "The surviving team member with the highest coins wins."
        else:  # integrative
            survival_target = "all 5 resources"
            win_condition = "All surviving team members win together."
        
        player_resource = self.player_resources[player_id]
        player_coins = self.player_coins[player_id]
        
        prompt = f"""NEGOTIATE TO SURVIVE

OBJECTIVE:
To survive, you must possess {survival_target} at some point in the game. {win_condition}

GAME SETUP:
- 5 players, each starting with one unique resource and {self.starting_coins} coins
- Resources: food, water, shelter, medicine, clothing
- Resource possession is PUBLIC knowledge
- Resource possession HISTORY is tracked and PUBLIC
- Maximum {self.max_rounds} rounds

YOUR STATUS:
- You are Player {player_id}
- Your resource: {player_resource}
- Your coins: {player_coins}

TURN STRUCTURE:
Each turn you can:
1. Write free text (automatically broadcast to all players)
2. Take ONE bracketed action:
   - [Whisper] <player_id> <message> - private message (others see "Player X whispered to Player Y")
   - [Propose] <coins> for <resource> - propose trade (public)
   - [Accept] <proposal_id> - accept existing proposal
   - [Pass] - no action this turn

TRADING RULES:
- Proposals specify coins offered for a specific resource
- Players can only propose coins for resources; no barter trades allowed
- Only the player who currently owns the resource can accept
- Successful trades transfer both resource and coins
- All proposals are public and tracked with IDs

EXAMPLES:
I think we need to work together to get all resources.
[Whisper] 2 Are you willing to trade your medicine?

Based on our discussion, here is my offer.
[Propose] 30 for medicine

That is a fair deal for both off us.
[Accept] 1
"""
        prompt+="\n" + "-" * 50 + "\n"
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
        can_advance = False
        if self._is_valid_action(action):
            self._process_valid_action(current_pid, action)
            can_advance = True
        else:
            # Handle invalid action
            can_advance = self._handle_invalid_action(current_pid, action)
        
        # Check for game end conditions
        if self._check_game_end() or self.state.turn >= self.max_rounds - 1:
            self._end_game()
            return self.state.step()
        
        # Advance to next player if we can advance
        if can_advance:
            self.state.current_player_id = (self.state.current_player_id + 1) % self.state.num_players
        
        return self.state.step()
    
    def _is_valid_action(self, action: str) -> bool:
        """Check if an action is valid."""
        action = action.strip()
        
        # Check for bracketed actions
        if "[Whisper]" in action:
            return self._is_valid_whisper(action)
        elif "[Propose]" in action:
            return self._is_valid_proposal(action)
        elif "[Accept]" in action:
            return self._is_valid_accept(action)
        elif "[Pass]" in action:
            return True
        
        return False
    
    def _is_valid_whisper(self, action: str) -> bool:
        """Check if whisper action is valid."""
        try:
            # Pattern: [Whisper] <player_id> <message>
            match = re.search(r'\[Whisper\]\s*(\d+)\s+(.+)', action, re.DOTALL)
            if not match:
                return False
            
            target_player = int(match.group(1))
            message = match.group(2).strip()
            
            # Check valid target player
            if target_player < 0 or target_player >= self.num_players:
                return False
            
            # Can't whisper to yourself
            if target_player == self.state.current_player_id:
                return False
            
            # Must have a message
            if not message:
                return False
            
            return True
        except Exception:
            return False
    
    def _is_valid_proposal(self, action: str) -> bool:
        """Check if proposal action is valid."""
        try:
            # Pattern: [Propose] <coins> for <resource>
            match = re.search(r'\[Propose\]\s*(\d+)\s+for\s+(\w+)', action, re.IGNORECASE)
            if not match:
                return False
            
            coins = int(match.group(1))
            resource = match.group(2).lower()
            
            # Check valid resource
            if resource not in self.resources:
                return False
            
            # Check player has enough coins
            if coins > self.player_coins[self.state.current_player_id]:
                return False
            
            # Check coins is positive
            if coins <= 0:
                return False
            
            return True
        except Exception:
            return False
    
    def _is_valid_accept(self, action: str) -> bool:
        """Check if accept action is valid."""
        try:
            # Pattern: [Accept] <proposal_id>
            match = re.search(r'\[Accept\]\s*(\d+)', action)
            if not match:
                return False
            
            proposal_id = int(match.group(1))
            
            # Check proposal exists
            if proposal_id not in self.proposals:
                return False
            
            proposal = self.proposals[proposal_id]
            
            # Check current player is not the proposer (can't accept own proposal)
            if proposal["proposer"] == self.state.current_player_id:
                return False
            
            # Check current player owns the requested resource
            if proposal["resource"] not in self.player_resources[self.state.current_player_id]:
                return False
            
            # Check proposer still has enough coins
            if self.player_coins[proposal["proposer"]] < proposal["coins"]:
                return False
            
            return True
        except Exception:
            return False
    
    def _process_valid_action(self, player_id: int, action: str):
        """Process a valid action."""
        # Extract free text (everything before bracketed action)
        free_text = self._extract_free_text(action)
        
        if free_text:
            # Broadcast free text
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id}: {free_text}",
                observation_type=ta.ObservationType.GAME_MESSAGE
            )
        
        # Process bracketed action
        if "[Whisper]" in action:
            self._process_whisper(player_id, action)
        elif "[Propose]" in action:
            self._process_proposal(player_id, action)
        elif "[Accept]" in action:
            self._process_accept(player_id, action)
        elif "[Pass]" in action:
            self._process_pass(player_id, action)
    
    def _extract_free_text(self, action: str) -> str:
        """Extract free text before bracketed actions."""
        # Find first bracketed action
        bracket_match = re.search(r'\[(Whisper|Propose|Accept|Pass)\]', action)
        if bracket_match:
            return action[:bracket_match.start()].strip()
        return action.strip()
    
    def _process_whisper(self, player_id: int, action: str):
        """Process whisper action."""
        match = re.search(r'\[Whisper\]\s*(\d+)\s+(.+)', action, re.DOTALL)
        target_player = int(match.group(1))
        message = match.group(2).strip()
        
        # Send private message to target
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=target_player,
            message=f"Player {player_id} whispers to you: {message}",
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
        
        # Notify others that whisper occurred (but not content)
        for pid in range(self.num_players):
            if pid != player_id and pid != target_player:
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=pid,
                    message=f"Player {player_id} whispered to Player {target_player}",
                    observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
                )
        
        # Record whisper in history
        self.whisper_history.append({
            "from": player_id,
            "to": target_player,
            "message": message,
            "round": self.state.turn
        })
    
    def _process_proposal(self, player_id: int, action: str):
        """Process proposal action."""
        match = re.search(r'\[Propose\]\s*(\d+)\s+for\s+(\w+)', action, re.IGNORECASE)
        coins = int(match.group(1))
        resource = match.group(2).lower()
        
        # Create proposal
        self.proposal_counter += 1
        proposal_id = self.proposal_counter
        
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "proposer": player_id,
            "coins": coins,
            "resource": resource,
            "round": self.state.turn
        }
        
        # Find who owns the resource
        resource_owner = None
        for pid, owned_resources in self.player_resources.items():
            if resource in owned_resources:
                resource_owner = pid
                break
        
        # Announce proposal
        if resource_owner is not None:
            message = f"Player {player_id} proposes: {coins} coins for {resource} (Proposal #{proposal_id}) - Player {resource_owner} can accept"
        else:
            message = f"Player {player_id} proposes: {coins} coins for {resource} (Proposal #{proposal_id}) - No one currently owns this resource"
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _process_accept(self, player_id: int, action: str):
        """Process accept action."""
        match = re.search(r'\[Accept\]\s*(\d+)', action)
        proposal_id = int(match.group(1))
        proposal = self.proposals[proposal_id]
        
        proposer = proposal["proposer"]
        coins = proposal["coins"]
        resource_wanted = proposal["resource"]
        
        # Execute trade - proposer gets resource, accepter gets coins
        self.player_coins[proposer] -= coins
        self.player_coins[player_id] += coins
        
        # Transfer resource: proposer gets the resource, accepter loses it
        self.player_resources[proposer].append(resource_wanted)
        self.player_resources[player_id].remove(resource_wanted)
        
        # Update resource history
        if resource_wanted not in self.resource_history:
            self.resource_history[resource_wanted] = []
        if proposer not in self.resource_history[resource_wanted]:
            self.resource_history[resource_wanted].append(proposer)
        
        # Announce trade
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"TRADE COMPLETED: Player {player_id} sold {resource_wanted} to Player {proposer} for {coins} coins",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        # Remove the accepted proposal
        del self.proposals[proposal_id]
    
    def _process_pass(self, player_id: int, action: str):
        """Process pass action."""
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"Player {player_id} passes this turn",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
    
    def _handle_invalid_action(self, player_id: int, action: str) -> bool:
        """Handle invalid action using TeamMultiPlayerState's escalation."""
        reason = self._get_invalid_action_reason(action)
        
        # Use TeamMultiPlayerState's built-in escalation handling
        should_apply_default = self.state.set_invalid_move(reason)
        
        if should_apply_default:
            # Apply default action (pass) and advance turn
            self._apply_default_action(player_id)
            return True
        else:
            # Player gets another chance
            return False
    
    def _get_invalid_action_reason(self, action: str) -> str:
        """Get specific reason why action is invalid."""
        if "[Whisper]" in action:
            return "Invalid whisper format. Use: [Whisper] <player_id> <message>"
        elif "[Propose]" in action:
            return "Invalid proposal format. Use: [Propose] <coins> for <resource>"
        elif "[Accept]" in action:
            return "Invalid accept format or proposal doesn't exist. Use: [Accept] <proposal_id>"
        elif not any(keyword in action for keyword in ["[Whisper]", "[Propose]", "[Accept]", "[Pass]"]):
            return "No valid action found. Use: [Whisper], [Propose], [Accept], or [Pass]"
        else:
            return "Invalid action format"
    
    def _apply_default_action(self, player_id: int):
        """Apply default action (pass) when player exceeds error allowance."""
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"Player {player_id} exceeded error limit, defaulting to [Pass]",
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Reset error count after applying default
        self.state.error_count = 0
        self.state.made_invalid_move = False
    
    def _check_game_end(self) -> bool:
        """Check if game should end (survival conditions met)."""
        # Check if any individual player has met the survival conditions
        for player_id in range(self.num_players):
            player_resources_owned = set()
            
            # Check what resources this player has owned throughout the game
            for resource, history in self.resource_history.items():
                if player_id in history:
                    player_resources_owned.add(resource)
            
            if self.game_variant == "distributive":
                # Player needs to have owned at least 4 different resources
                if len(player_resources_owned) >= 4:
                    return True
            elif self.game_variant == "integrative":
                # Player needs to have owned all 5 resources
                if len(player_resources_owned) >= 5:
                    return True
        
        return False
    
    def _end_game(self):
        """End the game and determine winners."""
        survival_met = self._check_game_end()
        
        rewards = {}
        if survival_met:
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message="SURVIVAL CONDITIONS MET! The team has survived.",
                observation_type=ta.ObservationType.GAME_ADMIN
            )
            
            if self.game_variant == "distributive":
                # Highest coins wins
                max_coins = max(self.player_coins.values())
                winners = [pid for pid, coins in self.player_coins.items() if coins == max_coins]
                
                if len(winners) == 1:
                    winner_id = winners[0]
                    for pid in range(self.num_players):
                        if pid==winner_id:
                            self.state.game_info[pid]["winner"] = True
                            rewards[pid] = 1
                        else:
                            self.state.game_info[pid]["winner"] = False
                            rewards[pid] = -1
                    self.state.step_info["winner_reason"] = f"Player {winner_id} wins with {max_coins} coins"
                else:
                    # Tie
                    for pid in range(self.num_players):
                        self.state.game_info[pid]["winner"] = False
                        #co-winners get drawn; others get lost
                        if pid in winners:
                            rewards[pid] = 0
                        else:
                            rewards[pid] = -1
                    self.state.step_info["draw_reason"] = f"Tie with {max_coins} coins among players {winners}"
            
            elif self.game_variant == "integrative":
                # All players win
                for pid in range(self.num_players):
                    self.state.game_info[pid]["winner"] = True
                    rewards[pid] = 1
                self.state.step_info["winner_reason"] = "All players survived together"
        
        else:
            # Survival conditions not met
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message="GAME OVER: Survival conditions not met. Everyone loses.",
                observation_type=ta.ObservationType.GAME_ADMIN
            )
            
            for pid in range(self.num_players):
                self.state.game_info[pid]["winner"] = False
                rewards[pid] = -1
            self.state.step_info["draw_reason"] = "Survival conditions not met"
        
        self.state.rewards = rewards
        self.state.done = True
    
    def get_observation(self):
        """Get observation for current player."""
        player_id = self.state.current_player_id
        observation = self.state.get_current_player_observation()
        
        # Add current game state
        game_state_info = get_board_str(
            self.player_resources,
            self.resource_history,
            self.proposals,
            self.game_variant
        )
        
        # Add player's current status
        player_status = render_resources_and_coins(
            player_id,
            self.player_resources,
            self.player_coins
        )
        
        observation.append((ta.GAME_ID, game_state_info, ta.ObservationType.GAME_BOARD))
        observation.append((ta.GAME_ID, player_status, ta.ObservationType.GAME_BOARD))
        
        return player_id, observation
