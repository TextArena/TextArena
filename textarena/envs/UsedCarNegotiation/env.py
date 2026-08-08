import os, re, random
from typing import Any, Dict, Optional, Tuple

import textarena as ta


class UsedCarNegotiationEnv(ta.Env):
    def __init__(self, max_rounds: int = 10, batna: str = None):
        self.max_rounds = max_rounds; self.max_price = 10_000; self.min_price = 7_000
        if batna: self.batna = batna
        else: self.batna = random.choice([("strong", "weak"), ("weak", "strong"), ("strong", "strong")])
        self.player_roles = {}
        self.player_instructions = {}
        self.game_dir = os.path.dirname(__file__)
        with open(os.path.join(self.game_dir, "instructions", "blue_book.txt"), "r") as f: self.blue_book = f.read()

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        current_pid = self.state.current_player_id; opponent_pid = abs(current_pid-1); action = action.strip()
        self.state.add_observation(from_id=current_pid, to_id=current_pid, message=f"Your action: {action}", observation_type=ta.ObservationType.PLAYER_ACTION)

        # Progress the negotiation
        if action.upper().startswith("[OFFER:"):
            match = re.search(r"\$?(\d+)", action)
            if match: 
                price = int(match.group(1))
                message = f"The {self.player_roles[current_pid]} proposed a price of ${price}."
                self.state.game_state["current_offer"][current_pid] = price
                self.state.game_state["negotiation_history"].append({"player_id": current_pid, "action_type": "OFFER", "content": message, "round": self.state.turn})
                self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            else: self.state.set_invalid_move(reason="You were not specifying a valid price.")
        elif action.upper() == "[ACCEPT]":
            if not self.state.game_state["current_offer"][opponent_pid]: self.state.set_invalid_move(reason="There is no offer to accept.")
            message = f"The {self.player_roles[current_pid]} accepted the offer."
        elif action.upper() == "[REJECT]":
            if not self.state.game_state["current_offer"][opponent_pid]: self.state.set_invalid_move(reason="There is no offer to reject.")
            message = f"The {self.player_roles[current_pid]} rejected the offer."
            self.state.game_state["current_offer"][opponent_pid] = None
            self.state.game_state["negotiation_history"].append({"player_id": current_pid, "action_type": "REJECT", "content": message, "round": self.state.turn})
            self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        elif action.upper().startswith("[DISCUSS:"):
            content = action[8:].strip()
            message = f"The {self.player_roles[current_pid]} says: {content}"
            self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.state.game_state["negotiation_history"].append({"player_id": current_pid, "action_type": "DISCUSS", "content": message, "round": self.state.turn})
        else: self.state.set_invalid_move(reason="You were not specifying a valid action.")

        # Check if the negotiation is over
        if action.upper() == "[ACCEPT]" or self.state.turn >= self.max_rounds:
            self.state.rewards = {i: self._reward_func(self.state.game_state["current_offer"][opponent_pid], self.player_roles[i]) for i in range(self.state.num_players)}
            self.state.done = True

        return self.state.step(rotate_player=action.upper().startswith(("[DISCUSS:", "[OFFER:")))

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_rounds, seed=seed)
        roles = ["buyer", "seller"]; self.player_roles[0] = roles.pop(random.randint(0, 1)); self.player_roles[1] = roles.pop()
        self.player_instructions = {i: self._load_instruction(self.player_roles[i], self.batna[i]) for i in range(num_players)}
        self.state.reset(game_state={"negotiation_history": [], "current_offer": {i: None for i in range(num_players)}}, player_prompt_function=self._generate_player_prompt)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id}.\n"
            f"You are in a price negotiation with {self.state.num_players} players and a maximum of {self.state.max_turns} rounds.\n"
            f"{self.player_instructions[player_id]}\n\n"
            f"{self.blue_book}\n\n"
            "Available actions:\n"
            f"- [Offer: <PRICE>] - Some price for which you offer to {'buy' if self.player_roles[player_id] == 'buyer' else 'sell'} the car\n"
            f"- [Accept] - In case of a pending offer by the {'buyer' if self.player_roles[player_id] == 'seller' else 'seller'}, accept the offer and end the negotiation\n"
            f"- [Reject] - In case of a pending offer by the {'buyer' if self.player_roles[player_id] == 'seller' else 'seller'}, reject the offer.\n"
            "- [Discuss: <MESSAGE>] - Make a statement or argument\n\n"
            "Guidelines:\n"
            "- Do not use coercion, lie, or misrepresent any facts presented to you in order to accomplish your goals in the negotiation\n"
            "- The game ends when a player accepts an offer or the maximum number of rounds is reached.\n"
        )

    def _reward_func(self, price: int, role: str) -> float:
        if not price: return 0.0
        if role == "buyer": return max(0.0, (self.max_price-price) / (self.max_price-self.min_price))
        elif role == "seller": return max(0.0, (price-self.min_price) / (self.max_price-self.min_price))
        else: raise ValueError(f"Invalid role: {role}")

    def _load_instruction(self, role: str, batna: str) -> str: 
        with open(os.path.join(self.game_dir, "instructions", role, f"{batna}.txt"), "r") as f: instruction = f.read()
        return instruction
