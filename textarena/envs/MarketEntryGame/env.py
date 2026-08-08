import re
from typing import Dict, Any, Optional, Tuple

import textarena as ta
from textarena.envs.MarketEntryGame.renderer import create_board_str

class MarketEntryGameEnv(ta.Env):
    def __init__(self, 
                 num_rounds: int = 5, 
                 communication_turns: int = 3,
                 market_capacity: int = 2,
                 entry_profit: int = 15,
                 overcrowding_penalty: int = -5,
                 safe_payoff: int = 5,
                 default_num_players: int = 4):
        """
        Initialize the Market Entry Game environment.
        
        Args:
            num_rounds: Number of rounds to play
            communication_turns: Number of communication turns before each decision
            market_capacity: Maximum number of players that can profitably enter
            entry_profit: Profit when market is not overcrowded
            overcrowding_penalty: Loss when market is overcrowded
            safe_payoff: Guaranteed payoff for staying out
            num_players: Number of players in the game (default 4)
        """
        self.num_rounds = num_rounds
        self.communication_turns = communication_turns
        self.market_capacity = market_capacity
        self.entry_profit = entry_profit
        self.overcrowding_penalty = overcrowding_penalty
        self.safe_payoff = safe_payoff
        self.default_num_players = default_num_players
        
        # Action regex - matches [E] for enter or [S] for stay out
        self.decision_pattern = re.compile(r"\[(E|S)\]", re.IGNORECASE)
        
        # Public message regex - matches messages in curly braces like {Hello everyone!}
        self.public_message_pattern = re.compile(r"\{([^}]*)\}", re.DOTALL)

    def get_board_str(self):
        gs = self.state.game_state
        return create_board_str(gs)

    def reset(self, num_players: Optional[int] = None, seed: Optional[int] = None):
        if num_players is None:
            num_players = self.default_num_players
            
        self.state = ta.FFAMultiPlayerState(
            num_players=num_players, 
            seed=seed,
            max_turns=self.num_rounds * num_players * (self.communication_turns + 1),
            error_allowance=2  # Allow 2 errors before elimination
        )
        
        game_state = {
            "round": 1,
            "num_rounds": self.num_rounds,
            "phase": "conversation",
            "conversation_round": 0,
            "total_conversation_rounds": self.communication_turns,
            "decisions": {i: None for i in range(num_players)},  # 'E' for enter, 'S' for stay out
            "total_scores": {i: 0 for i in range(num_players)},
            "round_scores": {i: 0 for i in range(num_players)},
            "market_capacity": self.market_capacity,
            "entry_profit": self.entry_profit,
            "overcrowding_penalty": self.overcrowding_penalty,
            "safe_payoff": self.safe_payoff,
            "history": [],
            "eliminations": [],  # Track eliminated players
            "pending_messages": {},  # Store messages until all players have acted
            "pending_decisions": {}  # Store decisions until all players have acted
        }
        
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.state.add_observation(
            message=f"--- Starting Round {self.state.game_state['round']} ---\n"
                    f"Communication phase: Submit your message using {{message}} format for public communication.",
            observation_type=ta.ObservationType.GAME_MESSAGE
        )

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in a Market Entry Game spanning "
            f"{game_state['num_rounds']} rounds.\n\n"
            f"Game Structure:\n"
            f"- Each round, you must decide whether to ENTER the market or STAY OUT.\n"
            f"- Market capacity: {game_state['market_capacity']} players can profitably enter.\n"
            f"- Before each decision you have {game_state['total_conversation_rounds']} "
            f"turns to communicate with other players.\n"
            f"- Communication is SIMULTANEOUS: Messages from a turn are revealed only after all players submit.\n"
            f"- After communication, all players SIMULTANEOUSLY choose to Enter [E] or Stay Out [S].\n"
            f"- Decisions are revealed only after all players have decided.\n\n"
            f"Payoff Structure:\n"
            f"- If you STAY OUT: guaranteed {game_state['safe_payoff']} points\n"
            f"- If you ENTER:\n"
            f"  • When ≤{game_state['market_capacity']} players enter: {game_state['entry_profit']} points\n"
            f"  • When >{game_state['market_capacity']} players enter: {game_state['overcrowding_penalty']} points (loss!)\n\n"
            f"Example Scenarios (with {self.state.num_players} players):\n"
            f"- If 2 players enter (not overcrowded): entrants get {game_state['entry_profit']}, others get {game_state['safe_payoff']}\n"
            f"- If 3 players enter (overcrowded!): entrants get {game_state['overcrowding_penalty']}, the one who stayed out gets {game_state['safe_payoff']}\n"
            f"- If all enter: everyone gets {game_state['overcrowding_penalty']}\n"
            f"- If none enter: everyone gets {game_state['safe_payoff']}\n\n"
            f"How to Play:\n"
            f"- You can think internally and reason about your strategy (this won't be shared).\n"
            f"- Your goal is to maximize your total score across all rounds.\n"
            f"- During conversation: send public messages using {{message}} format.\n"
            f"  Example: 'I'm considering entering. {{I think only 2 of us should enter this round}}'\n"
            f"  Only the text in curly braces will be visible to other players.\n"
            f"- During decision phase: include '[E]' to enter or '[S]' to stay out.\n"
            f"  Example: 'Based on our discussion, I will [E] enter the market.'\n"
            f"- Invalid moves (wrong format) will result in warnings, then elimination.\n"
            f"- If you don't send any public message during conversation (no {{}} format), others will see that you remained silent.\n\n"
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(
            to_id=self.state.current_player_id,
            from_id=self.state.current_player_id,
            message=action,
            observation_type=ta.ObservationType.PLAYER_ACTION
        )
        
        match self.state.game_state["phase"]:
            case "conversation":
                self._handle_conversation_phase(action)
            case "decision":
                self._handle_decision_phase(action)
                
        return self.state.step()

    def _extract_public_message(self, action: str) -> Optional[str]:
        """Extract and validate public message from action using {message} format."""
        matches = self.public_message_pattern.findall(action)
        if matches:
            valid_messages = [match.strip() for match in matches if match.strip()]
            if valid_messages:
                return " ".join(valid_messages)
        return None

    def _handle_conversation_phase(self, action: str):
        # Extract only the public message portion
        public_message = self._extract_public_message(action)
        
        # Store the public message (or None if no public message was sent)
        self.state.game_state["pending_messages"][self.state.current_player_id] = public_message
        
        # Check if all alive players have submitted their actions
        alive_players = [p for p in range(self.state.num_players) if self.state.is_player_alive(p)]
        
        if all(p in self.state.game_state["pending_messages"] for p in alive_players):
            # All alive players have submitted - now broadcast public messages simultaneously
            messages_to_broadcast = []
            
            for sender_id in alive_players:
                public_msg = self.state.game_state["pending_messages"][sender_id]
                if public_msg:
                    messages_to_broadcast.append(f"Player {sender_id}: {public_msg}")
                else:
                    messages_to_broadcast.append(f"Player {sender_id}: [remained silent]")
            
            # Broadcast all messages to all players at once
            if messages_to_broadcast:
                full_message = "Messages from this turn:\n" + "\n".join(messages_to_broadcast)
                for receiver_id in alive_players:
                    self.state.add_observation(
                        to_id=receiver_id,
                        from_id=ta.GAME_ID,
                        message=full_message,
                        observation_type=ta.ObservationType.GAME_MESSAGE
                    )
            
            # Clear pending messages
            self.state.game_state["pending_messages"] = {}
            
            # Advance conversation round
            self.state.game_state["conversation_round"] += 1
            
            if self.state.game_state["conversation_round"] >= self.state.game_state["total_conversation_rounds"]:
                # Switch to decision phase
                self.state.game_state["phase"] = "decision"
                self.state.add_observation(
                    message=f"Conversation finished for round {self.state.game_state['round']}.\n"
                           f"Decision phase: Submit '[E]' to enter the market or '[S]' to stay out.\n"
                           f"Decisions will be revealed after all players decide.",
                    observation_type=ta.ObservationType.GAME_MESSAGE
                )

    def _handle_decision_phase(self, action: str):
        # Extract decision
        match = self.decision_pattern.search(action)
        if match:
            decision = match.group(1).upper()  # 'E' or 'S'
            self.state.game_state["pending_decisions"][self.state.current_player_id] = decision
        else:
            # No valid decision found - use the state's invalid move handling
            eliminated = self.state.set_invalid_move(
                f"No valid decision found. Please use '[E]' to enter or '[S]' to stay out."
            )
            if not eliminated:
                return  # Player gets another chance
            else:
                # Player eliminated - default to stay out
                self.state.game_state["pending_decisions"][self.state.current_player_id] = 'S'
                self.state.game_state["eliminations"].append(self.state.current_player_id)
                self.state.add_observation(
                    message=f"Player {self.state.current_player_id} eliminated for too many invalid moves.",
                    observation_type=ta.ObservationType.GAME_MESSAGE
                )
        
        # Check if all alive players have made their decisions
        alive_players = [p for p in range(self.state.num_players) if self.state.is_player_alive(p)]
        if all(p in self.state.game_state["pending_decisions"] for p in alive_players):
            # All players have decided - now reveal all decisions
            self.state.game_state["decisions"] = self.state.game_state["pending_decisions"].copy()
            self.state.game_state["pending_decisions"] = {}
            
            # Count entries
            entries = sum(1 for p in alive_players if self.state.game_state["decisions"].get(p) == 'E')
            
            # Announce all decisions at once
            decision_msg = "All players have made their decisions:\n"
            for pid in sorted(alive_players):
                decision = self.state.game_state["decisions"][pid]
                decision_text = "ENTERED" if decision == 'E' else "STAYED OUT"
                decision_msg += f"Player {pid}: {decision_text}\n"
            
            decision_msg += f"\nMarket Status: {entries} player(s) entered"
            if entries > self.state.game_state["market_capacity"]:
                decision_msg += f" (OVERCROWDED! Capacity is {self.state.game_state['market_capacity']})"
            elif entries > 0:
                decision_msg += f" (Not overcrowded, capacity is {self.state.game_state['market_capacity']})"
                
            self.state.add_observation(
                message=decision_msg,
                observation_type=ta.ObservationType.GAME_MESSAGE
            )
            
            # Now resolve the round
            self._resolve_round()
            
            # Advance to next round or finish
            self.state.game_state["round"] += 1
            if self.state.game_state["round"] > self.state.game_state["num_rounds"]:
                self._determine_winner()
            else:
                # Reset for next round
                self.state.game_state["decisions"] = {i: None for i in range(self.state.num_players)}
                self.state.game_state["pending_messages"] = {}
                self.state.game_state["pending_decisions"] = {}
                self.state.game_state["phase"] = "conversation"
                self.state.game_state["conversation_round"] = 0
                self.state.add_observation(
                    message=f"--- Starting Round {self.state.game_state['round']} ---\n"
                           f"Communication phase: Submit your message using {{message}} format for public communication.",
                    observation_type=ta.ObservationType.GAME_MESSAGE
                )

    def _resolve_round(self):
        decisions = self.state.game_state["decisions"]
        alive_players = [p for p in range(self.state.num_players) if self.state.is_player_alive(p)]
        
        # Count how many players entered
        entrants = [p for p in alive_players if decisions.get(p) == 'E']
        num_entrants = len(entrants)
        
        # Determine if market is overcrowded
        is_overcrowded = num_entrants > self.state.game_state["market_capacity"]
        
        # Calculate payoffs
        round_info = {
            "round": self.state.game_state["round"],
            "decisions": {p: decisions.get(p) for p in alive_players},
            "num_entrants": num_entrants,
            "is_overcrowded": is_overcrowded,
            "payoffs": {}
        }
        
        result_message = f"Round {self.state.game_state['round']} results:\n"
        result_message += f"Market capacity: {self.state.game_state['market_capacity']}\n"
        result_message += f"Players who entered: {num_entrants}\n"
        result_message += f"Market status: {'OVERCROWDED' if is_overcrowded else 'Not overcrowded'}\n\n"
        
        for player_id in range(self.state.num_players):
            if self.state.is_player_alive(player_id):
                decision = decisions.get(player_id)
                
                if decision == 'E':  # Player entered
                    if is_overcrowded:
                        payoff = self.state.game_state["overcrowding_penalty"]
                        result_message += f"Player {player_id}: ENTERED (overcrowded) = {payoff} points\n"
                    else:
                        payoff = self.state.game_state["entry_profit"]
                        result_message += f"Player {player_id}: ENTERED (profitable) = {payoff} points\n"
                else:  # Player stayed out
                    payoff = self.state.game_state["safe_payoff"]
                    result_message += f"Player {player_id}: STAYED OUT = {payoff} points\n"
                
                round_info["payoffs"][player_id] = payoff
                self.state.game_state["round_scores"][player_id] = payoff
                self.state.game_state["total_scores"][player_id] += payoff
                
                result_message += f"  Total score: {self.state.game_state['total_scores'][player_id]}\n"
            else:
                result_message += f"Player {player_id}: ELIMINATED\n"
        
        # Save round history
        self.state.game_state["history"].append(round_info)
        
        # Announce results
        self.state.add_observation(
            message=result_message,
            observation_type=ta.ObservationType.GAME_MESSAGE
        )

    def _determine_winner(self):
        # Only consider alive players for winning
        alive_players = [p for p in range(self.state.num_players) if self.state.is_player_alive(p)]
        scores = {p: self.state.game_state["total_scores"][p] for p in alive_players}
        
        if not scores:  # No alive players
            self.state.set_draw(reason="All players eliminated!")
            return
            
        max_score = max(scores.values())
        winners = [p for p, s in scores.items() if s == max_score]
        
        final_message = f"Game Over! Final scores:\n"
        for player_id in range(self.state.num_players):
            score = self.state.game_state["total_scores"][player_id]
            status = " (eliminated)" if not self.state.is_player_alive(player_id) else ""
            final_message += f"Player {player_id}: {score}{status}\n"
        
        if len(winners) == 1:
            self.state.set_winners(
                player_ids=winners,
                reason=f"{final_message}\nPlayer {winners[0]} wins with {max_score} points!"
            )
        else:
            # Multiple winners - use set_game_outcome with normalized rewards
            reward_dict = {}
            for p in range(self.state.num_players):
                if not self.state.is_player_alive(p):
                    reward_dict[p] = -1  # Eliminated players get -1
                elif p in winners:
                    reward_dict[p] = 1   # Winners get 1
                else:
                    reward_dict[p] = 0   # Other players get 0
                    
            self.state.set_game_outcome(
                reward_dict=reward_dict,
                reason=f"{final_message}\nDraw! Players {', '.join(map(str, winners))} tied with {max_score} points."
            )