import os, re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta


class UsedCarNegotiationEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    def __init__(self, max_rounds: int = 10, batna: Optional[Tuple[str, str]] = None):
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds <= 0:
            raise ValueError("max_rounds must be a positive integer")
        if batna is not None and (
            not isinstance(batna, (tuple, list))
            or len(batna) != 2
            or any(
                not isinstance(position, str) or position not in {"strong", "weak"}
                for position in batna
            )
        ):
            raise ValueError("batna must contain exactly two values chosen from 'strong' and 'weak'")
        self.max_rounds = max_rounds; self.max_turns = max_rounds
        self.max_price = 10_000; self.min_price = 7_000
        self._configured_batna = tuple(batna) if batna is not None else None
        self.game_dir = os.path.dirname(__file__)
        with open(os.path.join(self.game_dir, "instructions", "blue_book.txt"), "r") as f: self.blue_book = f.read()
        self.offer_pattern = re.compile(r"\s*Offer\s*:\s*\$?(?P<price>\d+)\s*", re.IGNORECASE)
        self.accept_pattern = re.compile(r"\s*Accept\s*", re.IGNORECASE)
        self.reject_pattern = re.compile(r"\s*Reject\s*", re.IGNORECASE)
        # The content ends at its last non-space character, so a long whitespace run inside it is scanned only once.
        self.discuss_pattern = re.compile(r"\s*Discuss\s*:\s*(?P<content>.*\S)\s*", re.IGNORECASE | re.DOTALL)

    @property
    def player_roles(self) -> Dict[int, str]:
        return self.game_state["player_roles"]

    @property
    def player_instructions(self) -> Dict[int, str]:
        return self.game_state["player_instructions"]

    def setup(self) -> Dict[str, Any]:
        batna = self._configured_batna or self.rng.choice([("strong", "weak"), ("weak", "strong"), ("strong", "strong")])
        batna_by_role = {"buyer": batna[0], "seller": batna[1]}
        roles = ["buyer", "seller"]
        player_roles = {0: roles.pop(self.rng.randint(0, 1)), 1: roles.pop()}
        player_batna = {i: batna_by_role[player_roles[i]] for i in range(2)}
        player_instructions = {i: self._load_instruction(player_roles[i], player_batna[i]) for i in range(2)}
        return {
            "negotiation_history": [], "current_offer": {i: None for i in range(2)},
            "player_roles": player_roles, "player_instructions": player_instructions,
            "batna": batna, "player_batna": player_batna,
        }

    def prompt(self, player_id: int) -> str:
        player_roles = self.player_roles
        return (
            f"You are Player {player_id}.\n"
            f"You are in a price negotiation with {self.state.num_players} players and a maximum of {self.max_rounds} turns.\n"
            f"{self.player_instructions[player_id]}\n\n"
            f"{self.blue_book}\n\n"
            "Available actions:\n"
            f"- Offer: <PRICE> - Some price for which you offer to {'buy' if player_roles[player_id] == 'buyer' else 'sell'} the car\n"
            f"- Accept - In case of a pending offer by the {'buyer' if player_roles[player_id] == 'seller' else 'seller'}, accept the offer and end the negotiation\n"
            f"- Reject - In case of a pending offer by the {'buyer' if player_roles[player_id] == 'seller' else 'seller'}, reject the offer.\n"
            "- Discuss: <MESSAGE> - Make a statement or argument\n\n"
            "Guidelines:\n"
            "- Do not use coercion, lie, or misrepresent any facts presented to you in order to accomplish your goals in the negotiation\n"
            "- The game ends when a player accepts an offer or the maximum number of turns is reached.\n"
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # the env sends its own private "Your action: ..." echo in apply()

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        opponent_pid = 1 - player_id; action = self.strip_role_tags(action).strip()

        offer_match = self.offer_pattern.fullmatch(action)
        accept_match = self.accept_pattern.fullmatch(action)
        reject_match = self.reject_pattern.fullmatch(action)
        discuss_match = self.discuss_pattern.fullmatch(action)
        rotate = False
        if offer_match:
            try:
                price = int(offer_match.group("price"))
            except ValueError:
                return self.invalid("The offer price is not a valid integer.")
            if price < self.min_price or price > self.max_price:
                return self.invalid(f"Offer price must be between ${self.min_price} and ${self.max_price}.")
            self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            message = f"The {self.player_roles[player_id]} proposed a price of ${price}."
            gs["current_offer"] = {i: None for i in range(self.state.num_players)}
            gs["current_offer"][player_id] = price
            gs["negotiation_history"].append({"player_id": player_id, "action_type": "OFFER", "content": message, "round": self.state.turn})
            self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
            rotate = True
        elif accept_match:
            price = gs["current_offer"][opponent_pid]
            if price is None: return self.invalid("There is no offer to accept.")
            self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            message = f"The {self.player_roles[player_id]} accepted the offer of ${price}."
            gs["negotiation_history"].append({"player_id": player_id, "action_type": "ACCEPT", "content": message, "round": self.state.turn})
            self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
            rewards = {i: self._reward_func(price, self.player_roles[i]) for i in range(self.state.num_players)}
            return self.outcome(rewards, reason=message)
        elif reject_match:
            if gs["current_offer"][opponent_pid] is None: return self.invalid("There is no offer to reject.")
            self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            message = f"The {self.player_roles[player_id]} rejected the offer."
            gs["current_offer"][opponent_pid] = None
            gs["negotiation_history"].append({"player_id": player_id, "action_type": "REJECT", "content": message, "round": self.state.turn})
            self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        elif discuss_match:
            content = discuss_match.group("content").strip()
            self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            message = f"The {self.player_roles[player_id]} says: {content}"
            self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
            gs["negotiation_history"].append({"player_id": player_id, "action_type": "DISCUSS", "content": message, "round": self.state.turn})
            rotate = True
        else:
            return self.invalid("You were not specifying a valid action.")

        if not rotate: self.set_next_player(player_id)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.draw(reason="The maximum number of negotiation turns was reached without an accepted offer.")

    def _reward_func(self, price: int, role: str) -> float:
        if not price: return 0.0
        if role == "buyer": return min(1.0, max(0.0, (self.max_price-price) / (self.max_price-self.min_price)))
        elif role == "seller": return min(1.0, max(0.0, (price-self.min_price) / (self.max_price-self.min_price)))
        else: raise ValueError(f"Invalid role: {role}")

    def _load_instruction(self, role: str, batna: str) -> str:
        with open(os.path.join(self.game_dir, "instructions", role, f"{batna}.txt"), "r") as f: instruction = f.read()
        return instruction
