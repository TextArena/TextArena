import re
import random
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta
from textarena.envs.WinAsMuchAsYouCan.renderer import get_board_str


class WinAsMuchAsYouCanEnv(ta.Env):
    """
    Win as Much as You Can environment.
    
    A 4-player game where players choose X or Y in 10 rounds to maximize points.
    Features communication phases in rounds 5, 8, and 10 with different scoring multipliers.
    
    Key mechanics:
    - 4 players (fixed)
    - 10 scoring rounds with specific communication phases
    - Point scoring based on X/Y distribution
    - Communication phases with public/private messaging
    - Scoring multipliers: 1x (rounds 1-4,6-7,9), 3x (round 5), 5x (round 8), 10x (round 10)
    """
    
    def __init__(self, error_allowance: int = 3):
        """
        Initialize the Win as Much as You Can environment.
        
        Args:
            error_allowance: Number of invalid moves allowed per player
        """
        super().__init__()
        self.error_allowance = error_allowance
        
        # Regex patterns for parsing actions
        self.broadcast_pattern = re.compile(r"\[Broadcast\]\s*(.*)", re.IGNORECASE | re.DOTALL)
        self.whisper_pattern = re.compile(r"\[Whisper\s+to\s+(\d+)\]\s*(.*)", re.IGNORECASE | re.DOTALL)
        self.pass_pattern = re.compile(r"\[Pass\]", re.IGNORECASE)
        self.choose_x_pattern = re.compile(r"\[Choose\s+X\]", re.IGNORECASE)
        self.choose_y_pattern = re.compile(r"\[Choose\s+Y\]", re.IGNORECASE)
    
    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the environment to initial state."""
        if num_players != 4:
            raise ValueError("Win as Much as You Can requires exactly 4 players")
        
        # Initialize state (no max_turns needed - game naturally ends after 10 rounds)
        self.state = ta.FFAMultiPlayerState(
            num_players=num_players,
            max_turns=None,
            error_allowance=self.error_allowance,
            seed=seed
        )
        
        # Initialize game state
        game_state = {
            "current_round": 1,
            "current_phase": "act",  # Start with act phase for rounds 1-4
            "player_choices": {},
            "player_scores": {0: 0, 1: 0, 2: 0, 3: 0},
            "round_history": [],
            "talk_round": 0,
            "max_talk_rounds": 40,
            "players_passed": set(),
            "talk_messages": [],
            "round_multipliers": {
                1: 1, 2: 1, 3: 1, 4: 1,
                5: 3,
                6: 1, 7: 1,
                8: 5,
                9: 1,
                10: 10
            },
            "communication_rounds": {5, 8, 10} 
        }
        
        # Reset state
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt
        )
        
        # Start with player 0
        self.state.current_player_id = 0
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Generate the prompt for a player."""
        
        # Store current state info for synchronization
        game_state["_current_active_player"] = self.state.current_player_id
        game_state["_current_turn"] = self.state.turn
        
        prompt = f"""You are Player {player_id} in Win as Much as You Can.

OBJECTIVE:
Earn the most points possible over 10 rounds by choosing X or Y strategically.

SCORING RUBRIC (per round):
- 1 X and 3 Y's: X wins 3 points, Y's lose 1 point each
- 2 X's and 2 Y's: X's win 2 points each, Y's lose 2 points each  
- 3 X's and 1 Y: X's win 1 point each, Y loses 3 points
- 4 X's: All X's lose 1 point each
- 4 Y's: All Y's win 1 point each

ROUND STRUCTURE:
- Rounds 1-4, 6-7, 9: Act phase only (1x points)
- Round 5: Talk phase -> Act phase (3x points)
- Round 8: Talk phase -> Act phase (5x points)  
- Round 10: Talk phase -> Act phase (10x points)

TALK PHASE RULES:
- Maximum 40 conversation rounds (10 per player)
- Public messages: [Broadcast] your message (everyone sees sender and content)
- Private messages: [Whisper to X] your message (only sender and receiver know content, others see "A private message was sent")
- End participation: [Pass]
- Phase ends when max rounds reached OR all players pass

ACT PHASE RULES:
- Choose your action: [Choose X] or [Choose Y]
- All players choose simultaneously
- Round scored when all choices collected
"""
        
        return prompt
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process a player's action."""
        current_player_id = self.state.current_player_id
        
        
        # Log the action (but handle whispers specially for privacy)
        if self.whisper_pattern.search(action):
            # For whispers, only log to sender - receiver gets the processed message
            self.state.add_observation(
                from_id=current_player_id,
                to_id=current_player_id,
                message=action,
                observation_type=ta.ObservationType.PLAYER_ACTION
            )
        else:
            # For all other actions, log to everyone
            self.state.add_observation(
                from_id=current_player_id,
                to_id=-1,
                message=action,
                observation_type=ta.ObservationType.PLAYER_ACTION
            )
        
        # Process the action based on current phase
        success = self._process_action(current_player_id, action)
        
        # Check for phase transitions and game end
        if success:
            phase_ended = self._check_if_phase_should_end(current_player_id, action)
            if phase_ended:
                self._check_phase_transition()
            self._check_game_end()
        
        # Let TextArena handle the step but don't auto-rotate players
        done, info = self.state.step(rotate_player=False)
        
        # Only advance turn after successful actions
        if success and not self.state.done:
            current_phase = self.state.game_state["current_phase"]
            if current_phase == "talk":
                # Don't advance turn if we just started a new talk phase
                if self.state.game_state.get("talk_round", 0) > 0:
                    # Advance to next player who can talk
                    next_talker = self._get_next_talk_player()
                    if next_talker is not None:
                        self.state.current_player_id = next_talker
            elif current_phase == "act":
                # Advance to next player who needs to choose
                next_chooser = self._get_next_player_needing_choice()
                if next_chooser is not None:
                    self.state.current_player_id = next_chooser
        
        return done, info
    
    def _process_action(self, player_id: int, action: str) -> bool:
        """Process a player's action based on current phase."""
        current_phase = self.state.game_state["current_phase"]
        
        if current_phase == "talk":
            return self._process_talk_phase(player_id, action)
        elif current_phase == "act":
            return self._process_act_phase(player_id, action)
        else:
            self.state.set_invalid_move("Unknown game phase")
            return False
    
    def _process_talk_phase(self, player_id: int, action: str) -> bool:
        """Process actions during talk phase."""
        # Note: player_id is the original player who made the action
        # Turn validation is handled by the turn management system
        
        # Check if player already passed
        if player_id in self.state.game_state["players_passed"]:
            self.state.set_invalid_move("You have already passed")
            return False
        
        broadcast_match = self.broadcast_pattern.search(action)
        whisper_match = self.whisper_pattern.search(action)
        pass_match = self.pass_pattern.search(action)
        
        if broadcast_match:
            message = broadcast_match.group(1).strip()
            if not message:
                self.state.set_invalid_move("Broadcast message cannot be empty")
                return False
            
            # Send public message to all players
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id} (Broadcast): {message}",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
            
            # Record in talk history
            self.state.game_state["talk_messages"].append({
                "round": self.state.game_state["current_round"],
                "talk_round": self.state.game_state["talk_round"],
                "from": player_id,
                "to": "all",
                "message": message,
                "type": "broadcast"
            })
            
            return True
        
        elif whisper_match:
            target_str = whisper_match.group(1)
            message = whisper_match.group(2).strip()
            
            try:
                target_id = int(target_str)
            except ValueError:
                self.state.set_invalid_move(f"Invalid target player: {target_str}")
                return False
            
            if target_id < 0 or target_id >= 4:
                self.state.set_invalid_move("Target player must be 0, 1, 2, or 3")
                return False
            
            if target_id == player_id:
                self.state.set_invalid_move("Cannot whisper to yourself")
                return False
            
            if not message:
                self.state.set_invalid_move("Whisper message cannot be empty")
                return False
            
            # Send private message to receiver (they know who sent it)
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=target_id,
                message=f"Player {player_id} (Private): {message}",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
            
            # Send confirmation to sender (they know who they sent to)
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=player_id,
                message=f"You sent private message to Player {target_id}: {message}",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
            
            # Notify others that a private message was sent (without details)
            for pid in range(4):
                if pid != player_id and pid != target_id:
                    self.state.add_observation(
                        from_id=ta.GAME_ID,
                        to_id=pid,
                        message="A private message was sent between two players",
                        observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
                    )
            
            # Record in talk history (all private messages are anonymous)
            self.state.game_state["talk_messages"].append({
                "round": self.state.game_state["current_round"],
                "talk_round": self.state.game_state["talk_round"],
                "from": player_id,
                "to": target_id,
                "message": message,
                "type": "whisper",
                "hidden": True  # All private messages are anonymous
            })
            
            return True
        
        elif pass_match:
            # Player passes - no more talking this phase
            self.state.game_state["players_passed"].add(player_id)
            
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id} passed",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
            
            return True
        
        else:
            self.state.set_invalid_move("Use [Broadcast] message, [Whisper to X] message, or [Pass]")
            return False
    
    def _process_act_phase(self, player_id: int, action: str) -> bool:
        """Process actions during act phase."""
        # In act phase, any player can make their choice (not turn-based)
        # No need to check if it's their turn - simultaneous choices allowed
        
        # Check if player already made a choice
        if player_id in self.state.game_state["player_choices"]:
            self.state.set_invalid_move("You have already made your choice this round")
            return False
        
        choose_x_match = self.choose_x_pattern.search(action)
        choose_y_match = self.choose_y_pattern.search(action)
        
        if choose_x_match:
            self.state.game_state["player_choices"][player_id] = "X"
            
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id} made their choice",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
            
            return True
        
        elif choose_y_match:
            self.state.game_state["player_choices"][player_id] = "Y"
            
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id} made their choice",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
            
            return True
        
        else:
            self.state.set_invalid_move("Use [Choose X] or [Choose Y]")
            return False
    
    def _get_next_talk_player(self) -> Optional[int]:
        """Get the next player who can still talk."""
        current_player = self.state.current_player_id
        passed_players = self.state.game_state["players_passed"]
        
        # Check if we've reached max talk rounds
        if self.state.game_state["talk_round"] >= self.state.game_state["max_talk_rounds"]:
            return None
        
        # Find next player who hasn't passed
        for i in range(1, 5):  # Check next 4 players
            next_player = (current_player + i) % 4
            if next_player not in passed_players:
                return next_player
        
        # All players have passed
        return None
    
    def _get_next_player_needing_choice(self) -> Optional[int]:
        """Get the next player who needs to make a choice."""
        choices_made = set(self.state.game_state["player_choices"].keys())
        
        # Find first player who hasn't made a choice
        for player_id in range(4):
            if player_id not in choices_made:
                return player_id
        
        # All players have made choices
        return None
    
    def _check_if_phase_should_end(self, player_id: int, action: str) -> bool:
        """Check if the current phase should end based on the action taken."""
        current_phase = self.state.game_state["current_phase"]
        
        if current_phase == "talk":
            # Increment talk round after each valid action
            self.state.game_state["talk_round"] += 1
            
            # Phase ends when:
            # 1. Max talk rounds reached, OR
            # 2. All players have passed
            max_rounds = self.state.game_state["max_talk_rounds"]
            talk_round = self.state.game_state["talk_round"]
            passed_players = self.state.game_state["players_passed"]
            
            if talk_round >= max_rounds:
                return True
            
            if len(passed_players) >= 4:
                return True
            
            return False
        
        elif current_phase == "act":
            # Phase ends when all 4 players have made their choices
            choices_made = len(self.state.game_state["player_choices"])
            return choices_made >= 4
        
        return False
    
    def _check_phase_transition(self):
        """Check if we should transition to the next phase."""
        current_phase = self.state.game_state["current_phase"]
        current_round = self.state.game_state["current_round"]
        
        if current_phase == "talk":
            # Move from talk to act phase
            self.state.game_state["current_phase"] = "act"
            
            # Reset for act phase
            self.state.game_state["player_choices"] = {}
            
            # Set current player to first player needing choice
            self.state.current_player_id = 0
            
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Talk phase ended. Now choosing X or Y for Round {current_round}",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
        
        elif current_phase == "act":
            # Score the round and move to next round
            self._score_round()
            
            # Check if game is complete
            if current_round >= 10:
                self._end_game()
                return
            
            # Move to next round
            next_round = current_round + 1
            self.state.game_state["current_round"] = next_round
            
            # Determine if next round has talk phase
            if next_round in self.state.game_state["communication_rounds"]:
                self.state.game_state["current_phase"] = "talk"
                self.state.game_state["talk_round"] = 0
                self.state.game_state["players_passed"] = set()
                self.state.current_player_id = 0  # Start talk with player 0
                
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=f"Round {next_round} - Talk phase begins",
                    observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
                )
            else:
                self.state.game_state["current_phase"] = "act"
                self.state.game_state["player_choices"] = {}
                self.state.current_player_id = 0  # Start act with player 0
                
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=f"Round {next_round} - Choose X or Y",
                    observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
                )
    
    def _score_round(self):
        """Score the current round based on player choices."""
        choices = self.state.game_state["player_choices"]
        current_round = self.state.game_state["current_round"]
        multiplier = self.state.game_state["round_multipliers"][current_round]
        
        # Count X's and Y's
        x_count = sum(1 for choice in choices.values() if choice == "X")
        y_count = 4 - x_count
        
        # Calculate base points based on scoring rubric
        if x_count == 1 and y_count == 3:
            # X wins 3, Y's lose 1
            base_points = {"X": 3, "Y": -1}
        elif x_count == 2 and y_count == 2:
            # X's win 2, Y's lose 2
            base_points = {"X": 2, "Y": -2}
        elif x_count == 3 and y_count == 1:
            # X's win 1, Y loses 3
            base_points = {"X": 1, "Y": -3}
        elif x_count == 4:
            # All X's lose 1
            base_points = {"X": -1, "Y": 0}
        elif y_count == 4:
            # All Y's win 1
            base_points = {"X": 0, "Y": 1}
        else:
            # Should not happen with 4 players
            base_points = {"X": 0, "Y": 0}
        
        # Apply multiplier and update scores
        round_results = {}
        for player_id, choice in choices.items():
            points_earned = base_points[choice] * multiplier
            self.state.game_state["player_scores"][player_id] += points_earned
            round_results[player_id] = {
                "choice": choice,
                "points": points_earned
            }
        
        # Record round history
        self.state.game_state["round_history"].append({
            "round": current_round,
            "choices": choices.copy(),
            "x_count": x_count,
            "y_count": y_count,
            "base_points": base_points.copy(),
            "multiplier": multiplier,
            "results": round_results.copy()
        })
        
        # Announce results
        choices_str = ", ".join([f"Player {pid}: {choice}" for pid, choice in sorted(choices.items())])
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"Round {current_round} Results: {choices_str} ({x_count} X's, {y_count} Y's)",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        # Announce scoring
        for player_id, result in round_results.items():
            points = result["points"]
            total = self.state.game_state["player_scores"][player_id]
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id}: {points:+d} points (Total: {total})",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
    
    def _check_game_end(self):
        """Check if the game should end."""
        # Game ends after round 10 is scored
        if self.state.game_state["current_round"] >= 10 and self.state.game_state["current_phase"] == "act":
            # Check if round 10 has been scored
            if len(self.state.game_state["round_history"]) >= 10:
                self._end_game()
    
    def _end_game(self):
        """End the game and determine winner."""
        final_scores = self.state.game_state["player_scores"]
        max_score = max(final_scores.values())
        winners = [pid for pid, score in final_scores.items() if score == max_score]
        
        # Announce final scores
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message="GAME OVER - Final Scores:",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        for player_id in range(4):
            score = final_scores[player_id]
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=f"Player {player_id}: {score} points",
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
            )
        
        if len(winners) == 1:
            winner_id = winners[0]
            self.state.set_winners(
                player_ids=[winner_id],
                reason=f"Player {winner_id} wins with {max_score} points!"
            )
        else:
            # Tie - all tied players are winners
            self.state.set_winners(
                player_ids=winners,
                reason=f"Tie between players {winners} with {max_score} points each!"
            )
        
        # Set rewards based on final scores; 1 win, -1 lose, 0 draw to follow TextArena convention
        if max_score > 0:
            rewards = {}
            for pid, score in final_scores.items():
                if pid in winners:
                    rewards[pid] = 1
                else:
                    rewards[pid] = -1
        else:
            # All scores are 0 or negative
            rewards = {pid: 0 for pid in range(4)}  # Equal rewards for tie at 0
        
        self.state.rewards = rewards
        self.state.done = True
    
    def get_observation(self):
        """Get observation for current player."""
        player_id = self.state.current_player_id
        observation = self.state.get_current_player_observation()
        
        # Add current game board state
        board_str = get_board_str(self.state.game_state, player_id)
        observation.append((ta.GAME_ID, board_str, ta.ObservationType.GAME_BOARD))
        
        return player_id, observation
    
    def get_board_str(self) -> str:
        """Get the current board string for a player."""
        return get_board_str(self.state.game_state, self.state.current_player_id)
